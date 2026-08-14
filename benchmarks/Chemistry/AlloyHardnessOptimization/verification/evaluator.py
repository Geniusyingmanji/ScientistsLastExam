"""Trusted evaluator for study-held alloy-hardness batch design.

The oracle is a replay of DOI-grouped measurements in the Borg et al. MPEA
literature compilation.  Candidate code sees a historical composition/process
proxy and may reveal two measurements from each later study through a charged
callback.  Study identity, all unqueried labels and sparse exact-recipe
measurements from other DOI sources remain sealed.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import numpy as np


ALLOY_HARDNESS_OPTIMIZATION_V1 = True
DATA_PATH = Path(__file__).with_name("alloy_hardness_v1.json")
DATA_SHA256 = "a55effd2a4077b63a19a45a91729698e07b1bd9e89a72da79b87f2528a09d003"
BATCH_SIZE = 3
ASSAY_BUDGET = 2
DIVERSITY_WEIGHT = 0.10
CONFIDENCE_LEVEL = 0.90


def _load_data():
    payload = DATA_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise RuntimeError("alloy hardness data hash mismatch")
    document = json.loads(payload.decode("utf-8"))
    if document.get("schema_version") != 1:
        raise RuntimeError("unsupported alloy hardness schema")
    if document.get("builder_version") != "alloy-hardness-optimization-v1":
        raise RuntimeError("unsupported alloy hardness builder")
    contract = document.get("contract", {})
    if contract.get("batch_size") != BATCH_SIZE:
        raise RuntimeError("alloy batch-size contract mismatch")
    if contract.get("assay_budget") != ASSAY_BUDGET:
        raise RuntimeError("alloy assay-budget contract mismatch")
    worlds = tuple(document.get("worlds", ()))
    if len(worlds) != 13:
        raise RuntimeError("expected thirteen alloy study worlds")
    if sum(row.get("split") == "development" for row in worlds) != 8:
        raise RuntimeError("expected eight development alloy studies")
    if sum(row.get("split") == "heldout" for row in worlds) != 5:
        raise RuntimeError("expected five held-out alloy studies")
    dois = set()
    ids = set()
    for world in worlds:
        if world.get("candidate_count") != len(world.get("candidates", ())):
            raise RuntimeError("alloy candidate-count mismatch")
        if len(world.get("candidates", ())) < 4:
            raise RuntimeError("alloy study world is too small")
        if world.get("source_doi") in dois:
            raise RuntimeError("alloy DOI appears in multiple worlds")
        dois.add(world.get("source_doi"))
        for row in world["candidates"]:
            if row["id"] in ids:
                raise RuntimeError("alloy candidate identifier is not unique")
            ids.add(row["id"])
    return document, worlds


DATA_DOCUMENT, WORLDS = _load_data()
DEVELOPMENT_WORLDS = tuple(row for row in WORLDS if row["split"] == "development")
HELDOUT_WORLDS = tuple(row for row in WORLDS if row["split"] == "heldout")


def _candidate_map(world):
    return {row["id"]: row for row in world["candidates"]}


def _problem(world):
    candidates = []
    for row in world["candidates"]:
        candidates.append({
            "id": str(row["id"]),
            "composition": dict(row["composition"]),
            "processing_method": str(row["processing_method"]),
            "proxy_hardness_hv": float(row["proxy_hardness_hv"]),
        })
    return {
        "candidates": tuple(candidates),
        "batch_size": BATCH_SIZE,
        "assay_budget": ASSAY_BUDGET,
        "required_prediction_confidence": CONFIDENCE_LEVEL,
        "objective": (
            "select a diverse, high-hardness batch under two study-replay assays"
        ),
        "scope_warning": (
            "composition and coarse processing do not determine hardness; detailed "
            "processing, microstructure and measurement protocol are unobserved"
        ),
    }


class _Laboratory:
    def __init__(self, world):
        self.rows = _candidate_map(world)
        self.calls = 0
        self.ids = []
        self.failure = None

    def _fail(self, code, message):
        if self.failure is None:
            self.failure = str(code)
        raise ValueError(str(message))

    def assay(self, candidate_id):
        if self.calls >= ASSAY_BUDGET:
            self._fail("budget_exceeded", "alloy assay budget exceeded")
        if not isinstance(candidate_id, str):
            self._fail("invalid_assay", "alloy candidate identifier must be text")
        row = self.rows.get(candidate_id)
        if row is None:
            self._fail("invalid_assay", "unknown alloy candidate identifier")
        self.calls += 1
        self.ids.append(candidate_id)
        return {
            "hardness_hv": float(row["study_hardness_hv"]),
            "budget_cost": 1,
            "remaining_budget": ASSAY_BUDGET - self.calls,
        }


def _finite(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise ValueError(name + " must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    if low is not None and value < low:
        raise ValueError(name + " is below its public bound")
    if high is not None and value > high:
        raise ValueError(name + " is above its public bound")
    return value


def _validate_submission(submission, world):
    if not isinstance(submission, Mapping):
        raise ValueError("submission must be a mapping")
    if set(submission) != {"alloy_ids", "predictions"}:
        raise ValueError("submission has the wrong fields")
    alloy_ids = submission["alloy_ids"]
    if not isinstance(alloy_ids, (list, tuple)) or len(alloy_ids) != BATCH_SIZE:
        raise ValueError("alloy_ids must contain exactly three identifiers")
    if any(not isinstance(value, str) for value in alloy_ids):
        raise ValueError("every alloy identifier must be text")
    if len(set(alloy_ids)) != BATCH_SIZE:
        raise ValueError("submitted alloy identifiers must be distinct")
    rows = _candidate_map(world)
    if not set(alloy_ids).issubset(rows):
        raise ValueError("submission contains an unknown alloy identifier")

    predictions = submission["predictions"]
    if not isinstance(predictions, Mapping) or set(predictions) != set(alloy_ids):
        raise ValueError("predictions must be keyed by exactly the selected alloys")
    normalized = {}
    for candidate_id in alloy_ids:
        value = predictions[candidate_id]
        if not isinstance(value, Mapping) or set(value) != {
            "predicted_hardness_hv", "interval_hv"
        }:
            raise ValueError("each prediction has the wrong fields")
        point = _finite(
            value["predicted_hardness_hv"], "predicted hardness", 0.0, 2000.0
        )
        interval = value["interval_hv"]
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise ValueError("interval_hv must have two endpoints")
        low = _finite(interval[0], "hardness interval lower", 0.0, 2000.0)
        high = _finite(interval[1], "hardness interval upper", 0.0, 2000.0)
        if low > high or not low <= point <= high:
            raise ValueError("hardness interval must be ordered and contain its point")
        normalized[candidate_id] = {
            "predicted_hardness_hv": point,
            "interval_hv": (low, high),
        }
    return tuple(alloy_ids), tuple(rows[value] for value in alloy_ids), normalized


def _composition_distance(left, right):
    # The trusted host and isolated candidate run with independent hash seeds.
    # Sort before summation so the public baseline and trusted reference follow
    # the same floating-point reduction order in every process.
    elements = sorted(set(left["composition"]) | set(right["composition"]))
    return float(0.5 * sum(abs(
        float(left["composition"].get(element, 0.0))
        - float(right["composition"].get(element, 0.0))
    ) for element in elements))


def _diversity(rows):
    return float(np.mean([
        _composition_distance(left, right)
        for left, right in itertools.combinations(rows, 2)
    ]))


def _quality_values(world, field):
    values = np.asarray([float(row[field]) for row in world["candidates"]])
    spread = float(np.ptp(values))
    if spread <= 0.0:
        raise RuntimeError("alloy world has no hardness range")
    return (values - np.min(values)) / spread


def _batch_utility(world, rows, field="study_hardness_hv"):
    positions = {row["id"]: index for index, row in enumerate(world["candidates"])}
    quality = _quality_values(world, field)
    indices = [positions[row["id"]] for row in rows]
    return float(
        (1.0 - DIVERSITY_WEIGHT) * np.mean(quality[indices])
        + DIVERSITY_WEIGHT * _diversity(rows)
    )


def _best_rows(world, field):
    best = None
    for rows in itertools.combinations(world["candidates"], BATCH_SIZE):
        value = _batch_utility(world, rows, field)
        key = tuple(row["id"] for row in rows)
        if (
            best is None or value > best[0] + 1.0e-15
            or (abs(value - best[0]) <= 1.0e-15 and key < best[1])
        ):
            best = (value, key, rows)
    return tuple(best[2])


@lru_cache(maxsize=1)
def _anchors():
    result = {}
    for world in WORLDS:
        baseline_rows = _best_rows(world, "proxy_hardness_hv")
        reference_rows = _best_rows(world, "study_hardness_hv")
        result[world["id"]] = {
            "baseline_rows": baseline_rows,
            "reference_rows": reference_rows,
            "baseline_utility": _batch_utility(world, baseline_rows),
            "reference_utility": _batch_utility(world, reference_rows),
        }
    for split, worlds in (
        ("development", DEVELOPMENT_WORLDS), ("heldout", HELDOUT_WORLDS)
    ):
        baseline = float(np.mean([
            result[world["id"]]["baseline_utility"] for world in worlds
        ]))
        reference = float(np.mean([
            result[world["id"]]["reference_utility"] for world in worlds
        ]))
        if reference <= baseline + 0.05:
            raise RuntimeError("insufficient %s alloy utility headroom" % split)
        result["split_" + split] = {
            "baseline_utility": baseline,
            "reference_utility": reference,
        }
    return result


def _normalized(value, baseline, reference):
    """Zero at the shipped baseline, one at the reference witness, unbounded above it.

    The upper clip is gone. It made the witness the best achievable score, so a result better than
    the witness read as exactly as good as the witness and the task could report nothing about a
    searcher that had beaten it. Every run recorded before this change scored at or below one, so
    their scores are unchanged; removing the cap only stops the next result being invisible.

    The lower clip stays: below the baseline is a worse result, not a negative achievement.
    """
    if reference <= baseline:
        raise RuntimeError("invalid alloy normalization anchors")
    return float(max((value - baseline) / (reference - baseline), 0.0))


def _prediction_metrics(world, rows, predictions, assayed_ids):
    errors = []
    covered = []
    widths = []
    unmeasured_errors = []
    unmeasured_covered = []
    for row in rows:
        prediction = predictions[row["id"]]
        truth = float(row["study_hardness_hv"])
        error = abs(prediction["predicted_hardness_hv"] - truth)
        low, high = prediction["interval_hv"]
        coverage = float(low <= truth <= high)
        errors.append(error)
        covered.append(coverage)
        widths.append(high - low)
        if row["id"] not in assayed_ids:
            unmeasured_errors.append(error)
            unmeasured_covered.append(coverage)
    scale = float(np.ptp([
        candidate["study_hardness_hv"] for candidate in world["candidates"]
    ]))
    mae = float(np.mean(errors))
    point_score = float(math.exp(-mae / max(scale, 1.0)))
    width_quality = float(math.exp(-np.mean(widths) / max(2.0 * scale, 1.0)))
    coverage_rate = float(np.mean(covered))
    distribution_score = float(
        point_score * (0.75 * coverage_rate + 0.25 * width_quality)
    )
    return {
        "prediction_mae_hv": mae,
        "prediction_interval_coverage": coverage_rate,
        "mean_prediction_interval_width_hv": float(np.mean(widths)),
        "prediction_distribution_score": distribution_score,
        "unmeasured_prediction_count": len(unmeasured_errors),
        "unmeasured_prediction_mae_hv": (
            float(np.mean(unmeasured_errors)) if unmeasured_errors else 0.0
        ),
        "unmeasured_interval_coverage": (
            float(np.mean(unmeasured_covered)) if unmeasured_covered else 0.0
        ),
    }


def _confirmation_metrics(rows):
    target_values = []
    confirmation_values = []
    selected_with_confirmation = 0
    for row in rows:
        values = [
            float(record["hardness_hv"])
            for record in row["independent_exact_recipe_confirmations"]
        ]
        if values:
            selected_with_confirmation += 1
            for value in values:
                target_values.append(float(row["study_hardness_hv"]))
                confirmation_values.append(value)
    if not confirmation_values:
        return {
            "selected_with_confirmation_count": 0,
            "selected_confirmation_coverage": 0.0,
            "independent_confirmation_measurement_count": 0,
            "independent_confirmation_mean_hv": 0.0,
            "independent_confirmation_mae_hv": 0.0,
            "independent_confirmation_mean_bias_hv": 0.0,
        }
    target = np.asarray(target_values)
    confirmation = np.asarray(confirmation_values)
    return {
        "selected_with_confirmation_count": selected_with_confirmation,
        "selected_confirmation_coverage": selected_with_confirmation / BATCH_SIZE,
        "independent_confirmation_measurement_count": len(confirmation_values),
        "independent_confirmation_mean_hv": float(np.mean(confirmation)),
        "independent_confirmation_mae_hv": float(np.mean(abs(target - confirmation))),
        "independent_confirmation_mean_bias_hv": float(np.mean(
            target - confirmation
        )),
    }


def _evaluate_world(design_alloy_batch, world, index):
    laboratory = _Laboratory(world)
    try:
        submission = design_alloy_batch(_problem(world), laboratory.assay)
        alloy_ids, rows, predictions = _validate_submission(submission, world)
        if laboratory.failure is not None:
            raise ValueError("callback contract was violated")
    except Exception:
        return {
            "world_index": int(index),
            "split": str(world["split"]),
            "valid": False,
            "failure_kind": laboratory.failure or "invalid_submission",
            "batch_utility": 0.0,
            "mean_hardness_hv": 0.0,
            "top_candidate_hit_rate": 0.0,
            "batch_diversity": 0.0,
            "proxy_false_promotion_rate": 0.0,
            "prediction_distribution_score": 0.0,
            "prediction_mae_hv": 0.0,
            "prediction_interval_coverage": 0.0,
            "mean_prediction_interval_width_hv": 0.0,
            "unmeasured_prediction_count": 0,
            "unmeasured_prediction_mae_hv": 0.0,
            "unmeasured_interval_coverage": 0.0,
            "assay_calls": laboratory.calls,
            "unique_assay_calls": len(set(laboratory.ids)),
            "assay_unique_rate": 0.0,
            "selected_assayed_fraction": 0.0,
            "selected_unmeasured_fraction": 0.0,
            "selected_with_confirmation_count": 0,
            "selected_confirmation_coverage": 0.0,
            "independent_confirmation_measurement_count": 0,
            "independent_confirmation_mean_hv": 0.0,
            "independent_confirmation_mae_hv": 0.0,
            "independent_confirmation_mean_bias_hv": 0.0,
        }

    utility = _batch_utility(world, rows)
    quality = _quality_values(world, "study_hardness_hv")
    positions = {row["id"]: offset for offset, row in enumerate(world["candidates"])}
    true_top = set(np.argsort(-quality)[:BATCH_SIZE])
    proxy_quality = _quality_values(world, "proxy_hardness_hv")
    proxy_top = set(np.argsort(-proxy_quality)[:BATCH_SIZE])
    selected = {positions[row["id"]] for row in rows}
    selected_proxy = selected & proxy_top
    false_promotions = selected_proxy - true_top
    assayed_ids = set(laboratory.ids)
    prediction = _prediction_metrics(
        world, rows, predictions, assayed_ids
    )
    confirmation = _confirmation_metrics(rows)
    unique_assays = len(assayed_ids)
    selected_assayed = len(set(alloy_ids) & assayed_ids)
    return {
        "world_index": int(index),
        "split": str(world["split"]),
        "valid": True,
        "failure_kind": None,
        "batch_utility": utility,
        "mean_hardness_hv": float(np.mean([
            row["study_hardness_hv"] for row in rows
        ])),
        "top_candidate_hit_rate": len(selected & true_top) / BATCH_SIZE,
        "batch_diversity": _diversity(rows),
        "proxy_false_promotion_rate": (
            len(false_promotions) / len(selected_proxy) if selected_proxy else 0.0
        ),
        **prediction,
        "assay_calls": laboratory.calls,
        "unique_assay_calls": unique_assays,
        "assay_unique_rate": unique_assays / max(laboratory.calls, 1),
        "selected_assayed_fraction": selected_assayed / BATCH_SIZE,
        "selected_unmeasured_fraction": 1.0 - selected_assayed / BATCH_SIZE,
        **confirmation,
    }


def _split_metrics(records):
    mean_fields = (
        "batch_utility", "mean_hardness_hv", "top_candidate_hit_rate",
        "batch_diversity", "proxy_false_promotion_rate",
        "prediction_distribution_score", "prediction_mae_hv",
        "prediction_interval_coverage", "mean_prediction_interval_width_hv",
        "unmeasured_prediction_mae_hv", "unmeasured_interval_coverage",
        "assay_calls", "assay_unique_rate", "selected_assayed_fraction",
        "selected_unmeasured_fraction", "selected_confirmation_coverage",
    )
    result = {
        field: float(np.mean([row[field] for row in records]))
        for field in mean_fields
    }
    result["selected_with_confirmation_count"] = int(sum(
        row["selected_with_confirmation_count"] for row in records
    ))
    confirmation_count = int(sum(
        row["independent_confirmation_measurement_count"] for row in records
    ))
    result["independent_confirmation_measurement_count"] = confirmation_count
    for field in (
        "independent_confirmation_mean_hv",
        "independent_confirmation_mae_hv",
        "independent_confirmation_mean_bias_hv",
    ):
        result[field] = (
            float(sum(
                row[field] * row["independent_confirmation_measurement_count"]
                for row in records
            ) / confirmation_count)
            if confirmation_count else 0.0
        )
    result["valid_rate"] = float(np.mean([bool(row["valid"]) for row in records]))
    return result


def evaluate(design_alloy_batch):
    records = []
    for index, world in enumerate(WORLDS):
        if index and hasattr(design_alloy_batch, "reset_session"):
            design_alloy_batch.reset_session()
        records.append(_evaluate_world(design_alloy_batch, world, index))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    anchors = _anchors()
    dev_anchor = anchors["split_development"]
    held_anchor = anchors["split_heldout"]
    dev_score = _normalized(
        dev["batch_utility"], dev_anchor["baseline_utility"],
        dev_anchor["reference_utility"],
    )
    held_score = _normalized(
        held["batch_utility"], held_anchor["baseline_utility"],
        held_anchor["reference_utility"],
    )
    result = {
        "combined_score": dev_score if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["valid_rate"],
        "raw_score": dev_score if development_valid else 0.0,
        "development_batch_utility": dev["batch_utility"],
        "development_mean_hardness_hv": dev["mean_hardness_hv"],
        "development_top_candidate_hit_rate": dev["top_candidate_hit_rate"],
        "development_batch_diversity": dev["batch_diversity"],
        "development_proxy_false_promotion_rate": dev["proxy_false_promotion_rate"],
        "development_prediction_score": dev["prediction_distribution_score"],
        "development_prediction_mae_hv": dev["prediction_mae_hv"],
        "development_prediction_interval_coverage": dev["prediction_interval_coverage"],
        "development_mean_prediction_interval_width_hv": dev[
            "mean_prediction_interval_width_hv"
        ],
        "development_unmeasured_prediction_mae_hv": dev[
            "unmeasured_prediction_mae_hv"
        ],
        "development_unmeasured_interval_coverage": dev[
            "unmeasured_interval_coverage"
        ],
        "development_mean_assay_calls": dev["assay_calls"],
        "development_assay_unique_rate": dev["assay_unique_rate"],
        "development_selected_assayed_fraction": dev["selected_assayed_fraction"],
        "development_selected_unmeasured_fraction": dev[
            "selected_unmeasured_fraction"
        ],
        "development_selected_with_confirmation_count": dev[
            "selected_with_confirmation_count"
        ],
        "development_selected_confirmation_coverage": dev[
            "selected_confirmation_coverage"
        ],
        "development_independent_confirmation_measurement_count": dev[
            "independent_confirmation_measurement_count"
        ],
        "development_independent_confirmation_mae_hv": dev[
            "independent_confirmation_mae_hv"
        ],
        "development_independent_confirmation_mean_bias_hv": dev[
            "independent_confirmation_mean_bias_hv"
        ],
        "heldout_policy_score": held_score if heldout_valid else 0.0,
        "heldout_batch_utility": held["batch_utility"],
        "heldout_mean_hardness_hv": held["mean_hardness_hv"],
        "heldout_top_candidate_hit_rate": held["top_candidate_hit_rate"],
        "heldout_batch_diversity": held["batch_diversity"],
        "heldout_proxy_false_promotion_rate": held["proxy_false_promotion_rate"],
        "heldout_prediction_score": held["prediction_distribution_score"],
        "heldout_prediction_mae_hv": held["prediction_mae_hv"],
        "heldout_prediction_interval_coverage": held["prediction_interval_coverage"],
        "heldout_mean_prediction_interval_width_hv": held[
            "mean_prediction_interval_width_hv"
        ],
        "heldout_unmeasured_prediction_mae_hv": held[
            "unmeasured_prediction_mae_hv"
        ],
        "heldout_unmeasured_interval_coverage": held[
            "unmeasured_interval_coverage"
        ],
        "heldout_mean_assay_calls": held["assay_calls"],
        "heldout_assay_unique_rate": held["assay_unique_rate"],
        "heldout_selected_assayed_fraction": held["selected_assayed_fraction"],
        "heldout_selected_unmeasured_fraction": held[
            "selected_unmeasured_fraction"
        ],
        "heldout_selected_with_confirmation_count": held[
            "selected_with_confirmation_count"
        ],
        "heldout_selected_confirmation_coverage": held[
            "selected_confirmation_coverage"
        ],
        "heldout_independent_confirmation_measurement_count": held[
            "independent_confirmation_measurement_count"
        ],
        "heldout_independent_confirmation_mae_hv": held[
            "independent_confirmation_mae_hv"
        ],
        "heldout_independent_confirmation_mean_bias_hv": held[
            "independent_confirmation_mean_bias_hv"
        ],
        "heldout_feasibility_rate": held["valid_rate"],
        "candidate_world_call_count": len(records),
        "candidate_world_valid_rate": float(np.mean([
            bool(row["valid"]) for row in records
        ])),
        "per_world": records,
    }
    if not development_valid:
        failures = sorted({
            row["failure_kind"] for row in development if not row["valid"]
        })
        result["error_message"] = "candidate invalid: " + ", ".join(failures)
    return result


def _proxy_prediction(row):
    point = float(row["proxy_hardness_hv"])
    return {
        "predicted_hardness_hv": point,
        "interval_hv": [max(0.0, point - 300.0), min(2000.0, point + 300.0)],
    }


def _baseline_policy(problem, assay):
    del assay
    public_ids = {row["id"] for row in problem["candidates"]}
    world = next(
        item for item in WORLDS
        if {row["id"] for row in item["candidates"]} == public_ids
    )
    rows = _anchors()[world["id"]]["baseline_rows"]
    return {
        "alloy_ids": [row["id"] for row in rows],
        "predictions": {row["id"]: _proxy_prediction(row) for row in rows},
    }


def _reference_policy(problem, assay):
    del assay
    public_ids = {row["id"] for row in problem["candidates"]}
    world = next(
        item for item in WORLDS
        if {row["id"] for row in item["candidates"]} == public_ids
    )
    rows = _anchors()[world["id"]]["reference_rows"]
    return {
        "alloy_ids": [row["id"] for row in rows],
        "predictions": {
            row["id"]: {
                "predicted_hardness_hv": float(row["study_hardness_hv"]),
                "interval_hv": [
                    float(row["study_hardness_hv"]),
                    float(row["study_hardness_hv"]),
                ],
            }
            for row in rows
        },
    }
