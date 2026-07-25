"""Trusted evaluator for budgeted electrolyte-formulation selection.

The oracle is a deterministic replay of independent high-throughput EIS
experiments.  A public polynomial proxy is fitted only to earlier formulations.
Each charged assay exposes two later experimental repeats; scoring uses two
different repeats that never enter candidate feedback.
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


ELECTROLYTE_CONDUCTIVITY_DESIGN_V1 = True
DATA_PATH = Path(__file__).with_name("electrolyte_conductivity_v1.json")
DATA_SHA256 = "0c6899d6eb1a17b9565fb55963d1f46b52ba270cf10a5ec05177a01771593f29"
TEMPERATURES_C = np.arange(-30.0, 61.0, 10.0)
BATCH_SIZE = 3
ASSAY_BUDGET = 8
DIVERSITY_WEIGHT = 0.10
PROXY_RIDGE_ALPHA = 0.01


def _world(name, split, weights):
    values = np.asarray(weights, dtype=float)
    if values.shape != (10,) or np.any(values < 0.0):
        raise ValueError("invalid application profile")
    values /= np.sum(values)
    return {"name": str(name), "split": str(split), "weights": values}


DEVELOPMENT_WORLDS = (
    _world("cold_operation", "development", (.40, .35, .25, 0, 0, 0, 0, 0, 0, 0)),
    _world("cool_start", "development", (0, .10, .30, .40, .20, 0, 0, 0, 0, 0)),
    _world("temperate_duty", "development", (0, 0, 0, .10, .20, .40, .30, 0, 0, 0)),
    _world("broad_range", "development", (.10,) * 10),
    _world("low_mid_cycle", "development", (.125, 0, .25, 0, .375, 0, .25, 0, 0, 0)),
)
HELDOUT_WORLDS = (
    _world("temperature_extremes", "heldout", (.25, .25, 0, 0, 0, 0, 0, 0, .25, .25)),
    _world("seasonal_cycle", "heldout", (.30, 0, .20, 0, 0, 0, 0, .20, 0, .30)),
    _world("mixed_duty", "heldout", (0, .20, 0, .30, 0, .30, 0, 0, .20, 0)),
)
WORLDS = DEVELOPMENT_WORLDS + HELDOUT_WORLDS


def _load_data():
    payload = DATA_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise RuntimeError("electrolyte replay data hash mismatch")
    document = json.loads(payload.decode("utf-8"))
    if document.get("schema_version") != 1:
        raise RuntimeError("unsupported electrolyte data schema")
    if document.get("builder_version") != "electrolyte-conductivity-design-v1":
        raise RuntimeError("unsupported electrolyte builder")
    contract = document.get("contract", {})
    expected = {
        "source_complete_experiment_count": 358,
        "source_formulation_count": 85,
        "candidate_complete_experiment_count": 141,
        "candidate_formulation_count": 23,
        "discovery_replicates_per_assay": 2,
        "confirmation_replicates_per_candidate": 2,
        "batch_size": BATCH_SIZE,
        "assay_budget": ASSAY_BUDGET,
    }
    for key, value in expected.items():
        if contract.get(key) != value:
            raise RuntimeError("electrolyte contract mismatch: " + key)
    if tuple(float(value) for value in contract.get("temperatures_c", ())) != tuple(
        TEMPERATURES_C
    ):
        raise RuntimeError("temperature-grid mismatch")
    source = tuple(document.get("source_formulations", ()))
    candidates = tuple(document.get("candidates", ()))
    if len(source) != 85 or len(candidates) != 23:
        raise RuntimeError("formulation-count mismatch")
    if len({row.get("id") for row in candidates}) != 23:
        raise RuntimeError("candidate identifiers are not unique")
    for row in candidates:
        if len(row.get("discovery_replicates", ())) != 2:
            raise RuntimeError("discovery replicate mismatch")
        if len(row.get("confirmation_replicates", ())) != 2:
            raise RuntimeError("confirmation replicate mismatch")
        for field in ("discovery_replicates", "confirmation_replicates"):
            for repeat in row[field]:
                if len(repeat.get("conductivity_s_cm", ())) != 10:
                    raise RuntimeError("conductivity curve length mismatch")
    return document, source, candidates


DATA_DOCUMENT, SOURCE_FORMULATIONS, CANDIDATES = _load_data()
CANDIDATE_BY_ID = {row["id"]: row for row in CANDIDATES}


def _features(ratios):
    values = np.asarray(ratios, dtype=float)
    if values.ndim == 1:
        values = values.reshape(1, -1)
    u, v = values[:, 0], values[:, 1]
    return np.column_stack((
        np.ones(len(values)),
        u, v,
        u * u, u * v, v * v,
        u * u * u, u * u * v, u * v * v, v * v * v,
    ))


def _ratios(row):
    values = row["ratios"]
    return (
        float(values["pc_in_cyclic_carbonates"]),
        float(values["salt_to_cyclic_carbonates"]),
    )


@lru_cache(maxsize=1)
def _proxy_curves():
    source_x = np.asarray([_ratios(row) for row in SOURCE_FORMULATIONS])
    candidate_x = np.asarray([_ratios(row) for row in CANDIDATES])
    design = _features(source_x)
    candidate_design = _features(candidate_x)
    regularizer = np.eye(design.shape[1], dtype=float)
    regularizer[0, 0] = 0.0
    result = np.zeros((len(CANDIDATES), len(TEMPERATURES_C)), dtype=float)
    for offset in range(len(TEMPERATURES_C)):
        observed = np.log(np.asarray([
            float(row["mean_conductivity_s_cm"][offset])
            for row in SOURCE_FORMULATIONS
        ]))
        coefficients = np.linalg.solve(
            design.T @ design + PROXY_RIDGE_ALPHA * regularizer,
            design.T @ observed,
        )
        result[:, offset] = np.exp(candidate_design @ coefficients)
    if np.any(~np.isfinite(result)) or np.any(result <= 0.0):
        raise RuntimeError("invalid public conductivity proxy")
    return result


def _repeat_matrix(row, field, value):
    result = np.asarray([
        repeat[value] for repeat in row[field]
    ], dtype=float)
    if result.shape != (2, 10) or np.any(~np.isfinite(result)):
        raise RuntimeError("invalid repeated electrolyte measurement")
    return result


@lru_cache(maxsize=1)
def _confirmation_curves():
    return np.asarray([
        np.mean(_repeat_matrix(row, "confirmation_replicates", "conductivity_s_cm"), axis=0)
        for row in CANDIDATES
    ])


@lru_cache(maxsize=1)
def _discovery_curves():
    return np.asarray([
        np.mean(_repeat_matrix(row, "discovery_replicates", "conductivity_s_cm"), axis=0)
        for row in CANDIDATES
    ])


@lru_cache(maxsize=1)
def _discovery_lower_curves():
    return np.asarray([
        np.min(_repeat_matrix(row, "discovery_replicates", "conductivity_s_cm"), axis=0)
        for row in CANDIDATES
    ])


@lru_cache(maxsize=1)
def _confirmation_lower_curves():
    return np.asarray([
        np.min(_repeat_matrix(row, "confirmation_replicates", "conductivity_s_cm"), axis=0)
        for row in CANDIDATES
    ])


def _normalization_bounds(curves):
    logs = np.log(np.asarray(curves, dtype=float))
    lower = np.min(logs, axis=0)
    upper = np.max(logs, axis=0)
    if np.any(upper <= lower):
        raise RuntimeError("degenerate electrolyte temperature surface")
    return lower, upper


def _quality_values(curves, world, bounds):
    logs = np.log(np.asarray(curves, dtype=float))
    lower, upper = bounds
    normalized = (logs - lower) / (upper - lower)
    return normalized @ np.asarray(world["weights"], dtype=float)


def _pair_distance(left, right):
    all_x = np.asarray([_ratios(row) for row in CANDIDATES])
    spans = np.ptp(all_x, axis=0)
    if np.any(spans <= 0.0):
        raise RuntimeError("degenerate electrolyte formulation space")
    return float(np.mean(np.abs((all_x[left] - all_x[right]) / spans)))


def _diversity(indices):
    return float(np.mean([
        _pair_distance(left, right)
        for left, right in itertools.combinations(indices, 2)
    ]))


def _batch_utility(quality, indices):
    return float(
        (1.0 - DIVERSITY_WEIGHT) * np.mean(np.asarray(quality)[list(indices)])
        + DIVERSITY_WEIGHT * _diversity(indices)
    )


def _best_batch(quality):
    best = None
    for indices in itertools.combinations(range(len(CANDIDATES)), BATCH_SIZE):
        value = _batch_utility(quality, indices)
        ids = tuple(CANDIDATES[index]["id"] for index in indices)
        if (
            best is None
            or value > best[0] + 1e-15
            or (abs(value - best[0]) <= 1e-15 and ids < best[1])
        ):
            best = (value, ids, indices)
    return best


@lru_cache(maxsize=1)
def _anchors():
    proxy = _proxy_curves()
    discovery = _discovery_curves()
    lower_discovery = _discovery_lower_curves()
    confirmation = _confirmation_curves()
    lower_confirmation = _confirmation_lower_curves()
    proxy_bounds = _normalization_bounds(proxy)
    discovery_bounds = _normalization_bounds(discovery)
    confirmation_bounds = _normalization_bounds(confirmation)
    result = {}
    for world in WORLDS:
        proxy_quality = _quality_values(proxy, world, proxy_bounds)
        discovery_quality = _quality_values(discovery, world, discovery_bounds)
        discovery_lower_quality = _quality_values(
            lower_discovery, world, discovery_bounds
        )
        confirmation_quality = _quality_values(
            confirmation, world, confirmation_bounds
        )
        confirmation_lower_quality = _quality_values(
            lower_confirmation, world, confirmation_bounds
        )
        baseline = _best_batch(proxy_quality)
        reference = _best_batch(discovery_quality)
        robust_reference = _best_batch(discovery_lower_quality)
        confirmation_reference = _best_batch(confirmation_quality)
        confirmation_robust_reference = _best_batch(confirmation_lower_quality)
        baseline_discovery = _batch_utility(discovery_quality, baseline[2])
        baseline_discovery_lower = _batch_utility(
            discovery_lower_quality, baseline[2]
        )
        baseline_confirmation = _batch_utility(
            confirmation_quality, baseline[2]
        )
        baseline_confirmation_lower = _batch_utility(
            confirmation_lower_quality, baseline[2]
        )
        if reference[0] <= baseline_discovery + 0.04:
            raise RuntimeError("insufficient electrolyte nominal headroom")
        if robust_reference[0] <= baseline_discovery_lower + 0.03:
            raise RuntimeError("insufficient electrolyte repeat-robust headroom")
        result[world["name"]] = {
            "proxy_quality": proxy_quality,
            "discovery_quality": discovery_quality,
            "discovery_lower_quality": discovery_lower_quality,
            "confirmation_quality": confirmation_quality,
            "confirmation_lower_quality": confirmation_lower_quality,
            "baseline_ids": baseline[1],
            "baseline_indices": baseline[2],
            "baseline_utility": baseline_discovery,
            "baseline_lower_utility": baseline_discovery_lower,
            "baseline_confirmation_utility": baseline_confirmation,
            "baseline_confirmation_lower_utility": baseline_confirmation_lower,
            "reference_ids": reference[1],
            "reference_indices": reference[2],
            "reference_utility": reference[0],
            "robust_reference_ids": robust_reference[1],
            "robust_reference_indices": robust_reference[2],
            "robust_reference_utility": robust_reference[0],
            "confirmation_reference_ids": confirmation_reference[1],
            "confirmation_reference_utility": confirmation_reference[0],
            "confirmation_robust_reference_ids": confirmation_robust_reference[1],
            "confirmation_robust_reference_utility": confirmation_robust_reference[0],
        }
    return result


def _problem(world):
    proxy = _proxy_curves()
    candidates = []
    for index, row in enumerate(CANDIDATES):
        candidates.append({
            "id": str(row["id"]),
            "composition_g": {
                key: float(value) for key, value in row["composition_g"].items()
            },
            "ratios": {key: float(value) for key, value in row["ratios"].items()},
            "proxy_conductivity_s_cm": [float(value) for value in proxy[index]],
        })
    return {
        "temperatures_c": [float(value) for value in TEMPERATURES_C],
        "application_weights": [float(value) for value in world["weights"]],
        "candidate_formulations": candidates,
        "batch_size": BATCH_SIZE,
        "assay_budget": ASSAY_BUDGET,
        "objective": (
            "select a diverse three-formulation batch with high weighted ionic "
            "conductivity under eight charged repeated-temperature assays"
        ),
    }


class _Laboratory:
    def __init__(self):
        self.calls = 0
        self.ids = []
        self.failure = None

    def _fail(self, code, message):
        if self.failure is None:
            self.failure = str(code)
        raise ValueError(str(message))

    def assay(self, formulation_id):
        if self.calls >= ASSAY_BUDGET:
            self._fail("budget_exceeded", "electrolyte assay budget exceeded")
        if not isinstance(formulation_id, str):
            self._fail("invalid_assay", "formulation identifier must be text")
        row = CANDIDATE_BY_ID.get(formulation_id)
        if row is None:
            self._fail("invalid_assay", "unknown candidate formulation")
        self.calls += 1
        self.ids.append(formulation_id)
        conductivity = _repeat_matrix(
            row, "discovery_replicates", "conductivity_s_cm"
        )
        fit_quality = _repeat_matrix(
            row, "discovery_replicates", "eis_fit_evaluation"
        )
        cell_sd = _repeat_matrix(
            row, "discovery_replicates", "cell_constant_sd_cm_inv"
        )
        cell = _repeat_matrix(
            row, "discovery_replicates", "cell_constant_cm_inv"
        )
        return {
            "temperatures_c": [float(value) for value in TEMPERATURES_C],
            "replicate_conductivity_s_cm": conductivity.tolist(),
            "mean_conductivity_s_cm": np.mean(conductivity, axis=0).tolist(),
            "minimum_conductivity_s_cm": np.min(conductivity, axis=0).tolist(),
            "maximum_conductivity_s_cm": np.max(conductivity, axis=0).tolist(),
            "mean_eis_fit_evaluation": np.mean(fit_quality, axis=0).tolist(),
            "mean_relative_cell_constant_sd": np.mean(cell_sd / cell, axis=0).tolist(),
            "budget_cost": 1,
            "remaining_budget": ASSAY_BUDGET - self.calls,
        }


def _validate_submission(submission):
    if not isinstance(submission, Mapping):
        raise ValueError("submission must be a mapping")
    ids = submission.get("formulation_ids")
    if not isinstance(ids, (list, tuple)):
        raise ValueError("formulation_ids must be a list or tuple")
    if len(ids) != BATCH_SIZE:
        raise ValueError("submission must contain exactly three formulations")
    if any(not isinstance(value, str) for value in ids):
        raise ValueError("every formulation identifier must be text")
    if len(set(ids)) != BATCH_SIZE:
        raise ValueError("submitted formulation identifiers must be distinct")
    if any(value not in CANDIDATE_BY_ID for value in ids):
        raise ValueError("submission contains an unknown formulation")
    indices = tuple(next(
        index for index, row in enumerate(CANDIDATES) if row["id"] == value
    ) for value in ids)
    return tuple(ids), indices


def _normalized(value, baseline, reference):
    if reference <= baseline:
        raise RuntimeError("invalid electrolyte normalization anchors")
    return float(np.clip((value - baseline) / (reference - baseline), 0.0, 1.0))


def _empty_world(index, world, laboratory, failure):
    return {
        "world_index": int(index),
        "split": str(world["split"]),
        "valid": False,
        "failure_kind": str(failure),
        "batch_score": 0.0,
        "batch_utility": 0.0,
        "repeat_robustness_score": 0.0,
        "repeat_lower_utility": 0.0,
        "confirmation_score": 0.0,
        "confirmation_robustness_score": 0.0,
        "confirmation_utility": 0.0,
        "confirmation_lower_utility": 0.0,
        "mean_weighted_conductivity_s_cm": 0.0,
        "minimum_weighted_conductivity_s_cm": 0.0,
        "confirmation_mean_weighted_conductivity_s_cm": 0.0,
        "confirmation_minimum_weighted_conductivity_s_cm": 0.0,
        "top_quartile_hit_rate": 0.0,
        "confirmation_top_quartile_hit_rate": 0.0,
        "proxy_false_promotion_rate": 0.0,
        "batch_diversity": 0.0,
        "mean_confirmation_eis_fit_quality": 0.0,
        "mean_confirmation_arrhenius_r2": 0.0,
        "campaign_count": 0,
        "assay_calls": laboratory.calls,
        "unique_assay_calls": len(set(laboratory.ids)),
        "assay_unique_rate": 0.0,
        "selected_assayed_fraction": 0.0,
        "normalized_gain_per_assay": 0.0,
    }


def _evaluate_world(design_electrolyte_batch, world, index):
    laboratory = _Laboratory()
    try:
        submission = design_electrolyte_batch(_problem(world), laboratory.assay)
        ids, indices = _validate_submission(submission)
        if laboratory.failure is not None:
            raise ValueError("callback contract was violated")
    except Exception:
        return _empty_world(
            index, world, laboratory,
            laboratory.failure or "invalid_submission",
        )

    anchor = _anchors()[world["name"]]
    utility = _batch_utility(anchor["discovery_quality"], indices)
    lower_utility = _batch_utility(anchor["discovery_lower_quality"], indices)
    batch_score = _normalized(
        utility, anchor["baseline_utility"], anchor["reference_utility"]
    )
    robustness = _normalized(
        lower_utility,
        anchor["baseline_lower_utility"],
        anchor["robust_reference_utility"],
    )

    confirmation_quality_utility = _batch_utility(
        anchor["confirmation_quality"], indices
    )
    confirmation_lower_utility = _batch_utility(
        anchor["confirmation_lower_quality"], indices
    )
    confirmation_score = _normalized(
        confirmation_quality_utility,
        anchor["baseline_confirmation_utility"],
        anchor["confirmation_reference_utility"],
    )
    confirmation_robustness = _normalized(
        confirmation_lower_utility,
        anchor["baseline_confirmation_lower_utility"],
        anchor["confirmation_robust_reference_utility"],
    )
    discovery = _discovery_curves()[list(indices)]
    discovery_repeats = [
        _repeat_matrix(CANDIDATES[position], "discovery_replicates", "conductivity_s_cm")
        for position in indices
    ]
    confirmation = _confirmation_curves()[list(indices)]
    confirmation_repeats = [
        _repeat_matrix(CANDIDATES[position], "confirmation_replicates", "conductivity_s_cm")
        for position in indices
    ]
    weights = np.asarray(world["weights"], dtype=float)
    weighted = np.exp(np.log(discovery) @ weights)
    minimum_weighted = np.asarray([
        np.exp(np.log(values).dot(weights))
        for matrix in discovery_repeats for values in matrix
    ])
    confirmation_weighted = np.exp(np.log(confirmation) @ weights)
    confirmation_minimum_weighted = np.asarray([
        np.exp(np.log(values).dot(weights))
        for matrix in confirmation_repeats for values in matrix
    ])
    true_quality = anchor["discovery_quality"]
    proxy_quality = anchor["proxy_quality"]
    top_count = max(1, int(math.ceil(0.25 * len(CANDIDATES))))
    true_top = set(np.argsort(-true_quality)[:top_count])
    confirmation_top = set(np.argsort(-anchor["confirmation_quality"])[:top_count])
    proxy_top = set(np.argsort(-proxy_quality)[:top_count])
    selected_proxy = [position for position in indices if position in proxy_top]
    false_promotions = [
        position for position in selected_proxy if position not in true_top
    ]
    fit_quality = []
    arrhenius_r2 = []
    campaigns = set()
    for position in indices:
        row = CANDIDATES[position]
        for repeat in row["confirmation_replicates"]:
            fit_quality.extend(float(value) for value in repeat["eis_fit_evaluation"])
            arrhenius_r2.append(float(repeat["arrhenius_r2"]))
            campaigns.add(str(repeat["campaign"]))
    unique_assays = len(set(laboratory.ids))
    selected_assayed = len(set(ids) & set(laboratory.ids))
    return {
        "world_index": int(index),
        "split": str(world["split"]),
        "valid": True,
        "failure_kind": None,
        "batch_score": batch_score,
        "batch_utility": utility,
        "repeat_robustness_score": robustness,
        "repeat_lower_utility": lower_utility,
        "confirmation_score": confirmation_score,
        "confirmation_robustness_score": confirmation_robustness,
        "confirmation_utility": confirmation_quality_utility,
        "confirmation_lower_utility": confirmation_lower_utility,
        "mean_weighted_conductivity_s_cm": float(np.mean(weighted)),
        "minimum_weighted_conductivity_s_cm": float(np.min(minimum_weighted)),
        "confirmation_mean_weighted_conductivity_s_cm": float(
            np.mean(confirmation_weighted)
        ),
        "confirmation_minimum_weighted_conductivity_s_cm": float(
            np.min(confirmation_minimum_weighted)
        ),
        "top_quartile_hit_rate": sum(
            position in true_top for position in indices
        ) / BATCH_SIZE,
        "confirmation_top_quartile_hit_rate": sum(
            position in confirmation_top for position in indices
        ) / BATCH_SIZE,
        "proxy_false_promotion_rate": (
            len(false_promotions) / len(selected_proxy) if selected_proxy else 0.0
        ),
        "batch_diversity": _diversity(indices),
        "mean_confirmation_eis_fit_quality": float(np.mean(fit_quality)),
        "mean_confirmation_arrhenius_r2": float(np.mean(arrhenius_r2)),
        "campaign_count": len(campaigns),
        "assay_calls": laboratory.calls,
        "unique_assay_calls": unique_assays,
        "assay_unique_rate": unique_assays / max(laboratory.calls, 1),
        "selected_assayed_fraction": selected_assayed / BATCH_SIZE,
        "normalized_gain_per_assay": batch_score / max(laboratory.calls, 1),
        "selected_ids": ids,
    }


def _split_metrics(records):
    fields = (
        "batch_score", "batch_utility", "repeat_robustness_score",
        "repeat_lower_utility", "mean_weighted_conductivity_s_cm",
        "confirmation_score", "confirmation_robustness_score",
        "confirmation_utility", "confirmation_lower_utility",
        "minimum_weighted_conductivity_s_cm", "top_quartile_hit_rate",
        "confirmation_mean_weighted_conductivity_s_cm",
        "confirmation_minimum_weighted_conductivity_s_cm",
        "confirmation_top_quartile_hit_rate",
        "proxy_false_promotion_rate", "batch_diversity",
        "mean_confirmation_eis_fit_quality", "mean_confirmation_arrhenius_r2",
        "campaign_count", "assay_calls", "assay_unique_rate",
        "selected_assayed_fraction", "normalized_gain_per_assay",
    )
    result = {
        field: float(np.mean([row[field] for row in records])) for field in fields
    }
    result["valid_rate"] = float(np.mean([bool(row["valid"]) for row in records]))
    return result


def evaluate(design_electrolyte_batch):
    records = []
    for index, world in enumerate(WORLDS):
        if index and hasattr(design_electrolyte_batch, "reset_session"):
            design_electrolyte_batch.reset_session()
        records.append(_evaluate_world(design_electrolyte_batch, world, index))
    development = records[:len(DEVELOPMENT_WORLDS)]
    heldout = records[len(DEVELOPMENT_WORLDS):]
    dev = _split_metrics(development)
    held = _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    result = {
        "combined_score": dev["batch_score"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["valid_rate"],
        "raw_score": dev["batch_score"] if development_valid else 0.0,
        "development_batch_utility": dev["batch_utility"],
        "development_mean_weighted_conductivity_s_cm": dev[
            "mean_weighted_conductivity_s_cm"
        ],
        "development_minimum_weighted_conductivity_s_cm": dev[
            "minimum_weighted_conductivity_s_cm"
        ],
        "development_top_quartile_hit_rate": dev["top_quartile_hit_rate"],
        "development_confirmation_mean_weighted_conductivity_s_cm": dev[
            "confirmation_mean_weighted_conductivity_s_cm"
        ],
        "development_confirmation_minimum_weighted_conductivity_s_cm": dev[
            "confirmation_minimum_weighted_conductivity_s_cm"
        ],
        "development_confirmation_top_quartile_hit_rate": dev[
            "confirmation_top_quartile_hit_rate"
        ],
        "development_proxy_false_promotion_rate": dev[
            "proxy_false_promotion_rate"
        ],
        "development_batch_diversity": dev["batch_diversity"],
        "development_mean_eis_fit_quality": dev[
            "mean_confirmation_eis_fit_quality"
        ],
        "development_mean_arrhenius_r2": dev["mean_confirmation_arrhenius_r2"],
        "development_mean_campaign_count": dev["campaign_count"],
        "robustness_score": (
            dev["repeat_robustness_score"] if development_valid else 0.0
        ),
        "confirmation_score": (
            dev["confirmation_score"] if development_valid else 0.0
        ),
        "confirmation_robustness_score": (
            dev["confirmation_robustness_score"] if development_valid else 0.0
        ),
        "heldout_policy_score": held["batch_score"] if heldout_valid else 0.0,
        "heldout_robustness_score": (
            held["repeat_robustness_score"] if heldout_valid else 0.0
        ),
        "heldout_confirmation_score": (
            held["confirmation_score"] if heldout_valid else 0.0
        ),
        "heldout_confirmation_robustness_score": (
            held["confirmation_robustness_score"] if heldout_valid else 0.0
        ),
        "heldout_mean_weighted_conductivity_s_cm": held[
            "mean_weighted_conductivity_s_cm"
        ],
        "heldout_minimum_weighted_conductivity_s_cm": held[
            "minimum_weighted_conductivity_s_cm"
        ],
        "heldout_top_quartile_hit_rate": held["top_quartile_hit_rate"],
        "heldout_confirmation_mean_weighted_conductivity_s_cm": held[
            "confirmation_mean_weighted_conductivity_s_cm"
        ],
        "heldout_confirmation_minimum_weighted_conductivity_s_cm": held[
            "confirmation_minimum_weighted_conductivity_s_cm"
        ],
        "heldout_confirmation_top_quartile_hit_rate": held[
            "confirmation_top_quartile_hit_rate"
        ],
        "heldout_proxy_false_promotion_rate": held["proxy_false_promotion_rate"],
        "heldout_batch_diversity": held["batch_diversity"],
        "heldout_mean_eis_fit_quality": held["mean_confirmation_eis_fit_quality"],
        "heldout_mean_arrhenius_r2": held["mean_confirmation_arrhenius_r2"],
        "heldout_mean_campaign_count": held["campaign_count"],
        "heldout_feasibility_rate": held["valid_rate"],
        "development_mean_assay_calls": dev["assay_calls"],
        "heldout_mean_assay_calls": held["assay_calls"],
        "development_assay_unique_rate": dev["assay_unique_rate"],
        "heldout_assay_unique_rate": held["assay_unique_rate"],
        "development_selected_assayed_fraction": dev["selected_assayed_fraction"],
        "heldout_selected_assayed_fraction": held["selected_assayed_fraction"],
        "development_normalized_gain_per_assay": dev[
            "normalized_gain_per_assay"
        ],
        "heldout_normalized_gain_per_assay": held["normalized_gain_per_assay"],
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


def _baseline_policy(problem, assay):
    del assay
    weights = np.asarray(problem["application_weights"], dtype=float)
    curves = np.asarray([
        row["proxy_conductivity_s_cm"] for row in problem["candidate_formulations"]
    ])
    bounds = _normalization_bounds(curves)
    normalized = (np.log(curves) - bounds[0]) / (bounds[1] - bounds[0])
    quality = normalized @ weights
    ids = tuple(row["id"] for row in problem["candidate_formulations"])
    indices = _best_batch(quality)[2]
    return {"formulation_ids": [ids[index] for index in indices]}


def _consume_unique_assays(problem, assay):
    for row in problem["candidate_formulations"][:ASSAY_BUDGET]:
        assay(row["id"])


def _reference_policy(problem, assay):
    _consume_unique_assays(problem, assay)
    weights = np.asarray(problem["application_weights"], dtype=float)
    world = next(
        row for row in WORLDS if np.allclose(row["weights"], weights, atol=0, rtol=0)
    )
    return {"formulation_ids": list(_anchors()[world["name"]]["reference_ids"])}


def _robust_reference_policy(problem, assay):
    _consume_unique_assays(problem, assay)
    weights = np.asarray(problem["application_weights"], dtype=float)
    world = next(
        row for row in WORLDS if np.allclose(row["weights"], weights, atol=0, rtol=0)
    )
    return {
        "formulation_ids": list(
            _anchors()[world["name"]]["robust_reference_ids"]
        )
    }
