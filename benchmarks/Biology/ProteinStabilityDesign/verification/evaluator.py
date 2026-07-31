"""Trusted evaluator for budgeted protein-stability batch design.

The labels are published cDNA-display proteolysis measurements, not a synthetic
protein oracle.  Runtime candidates see only single-mutant additive proxies and
may reveal a small number of double-mutant measurements through a charged replay
callback.  Independent raw trypsin/chymotrypsin readouts remain sealed.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import numpy as np


PROTEIN_STABILITY_DESIGN_V1 = True
DATA_PATH = Path(__file__).with_name("protein_stability_landscapes_v1.json")
DATA_SHA256 = "7983438c683ea5b3a43bdd212b524413ecdbf1ece63cad79ab37b1149da1ba4a"
BATCH_SIZE = 8
ASSAY_BUDGET = 12
DIVERSITY_WEIGHT = 0.25

# Frozen outputs of ``_search_reference_rows``.  The calibration script rebuilds these
# from the complete landscapes and requires an exact mutation-by-mutation match.  Keeping
# the witnesses literal makes ordinary candidate evaluation cheap without hiding how the
# normalization reference was constructed.
REFERENCE_MUTATIONS = {
    "SPTN1_CHICK_Tsuboyama_2023_1TUD": (
        "K12I:S49K", "K12I:S49R", "K12L:S49K", "K12L:S49R",
        "K12R:S49A", "K12R:S49D", "K12R:S49W", "K12V:S49R",
    ),
    "UBE4B_HUMAN_Tsuboyama_2023_3L1X": (
        "S39C:T41C", "S39F:T41F", "S39F:T41W", "S39H:T41W",
        "S39H:T41Y", "S39N:T41F", "S39Y:T41W", "S39Y:T41Y",
    ),
    "CUE1_YEAST_Tsuboyama_2023_2MYX": (
        "R41A:D46E", "R41K:D46E", "R41L:D46C", "R41L:D46F",
        "R41L:D46V", "R41M:D46F", "R41M:D46Y", "R41Q:D46C",
    ),
    "RCRO_LAMBD_Tsuboyama_2023_1ORC": (
        "R36C:E52W", "R36C:E52Y", "R36L:E52I", "R36L:E52Q",
        "R36W:E52I", "R36W:E52S", "R36W:E52V", "R36Y:E52M",
    ),
    "NUSA_ECOLI_Tsuboyama_2023_1WCL": (
        "L42C:A60W", "L42F:A60I", "L42F:A60V", "L42M:A60I",
        "L42M:A60V", "L42W:A60I", "L42W:A60L", "L42W:A60V",
    ),
    "VILI_CHICK_Tsuboyama_2023_1YU5": (
        "E28C:K59Y", "E28H:K59L", "E28I:K59I", "E28I:K59M",
        "E28T:K59V", "E28V:K59L", "E28W:K59A", "E28Y:K59D",
    ),
    "RBP1_HUMAN_Tsuboyama_2023_2KWH": (
        "E9C:R12F", "E9C:R12I", "E9C:R12W", "E9H:R12H",
        "E9L:R12C", "E9Q:R12M", "E9W:R12L", "E9Y:R12C",
    ),
    "CSN4_MOUSE_Tsuboyama_2023_1UFM": (
        "E14F:R55W", "E14I:R55I", "E14I:R55L", "E14I:R55V",
        "E14L:R55Y", "E14M:R55L", "E14M:R55M", "E14V:R55I",
    ),
}


def _load_data():
    payload = DATA_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise RuntimeError("protein landscape data hash mismatch")
    document = json.loads(payload.decode("utf-8"))
    if document.get("schema_version") != 1:
        raise RuntimeError("unsupported protein landscape schema")
    if document.get("builder_version") != "protein-stability-design-v1":
        raise RuntimeError("unsupported protein landscape builder")
    contract = document.get("contract", {})
    if contract.get("batch_size") != BATCH_SIZE:
        raise RuntimeError("batch-size contract mismatch")
    if contract.get("assay_budget") != ASSAY_BUDGET:
        raise RuntimeError("assay-budget contract mismatch")
    worlds = tuple(document.get("worlds", ()))
    if len(worlds) != 8:
        raise RuntimeError("expected eight protein-domain worlds")
    if sum(row.get("split") == "development" for row in worlds) != 5:
        raise RuntimeError("expected five development protein domains")
    if sum(row.get("split") == "heldout" for row in worlds) != 3:
        raise RuntimeError("expected three held-out protein domains")
    for world in worlds:
        if world.get("candidate_count") != len(world.get("candidates", ())):
            raise RuntimeError("candidate-count mismatch")
        if len(world.get("candidates", ())) < 300:
            raise RuntimeError("protein landscape is too small")
    return document, worlds


DATA_DOCUMENT, WORLDS = _load_data()
DEVELOPMENT_WORLDS = tuple(row for row in WORLDS if row["split"] == "development")
HELDOUT_WORLDS = tuple(row for row in WORLDS if row["split"] == "heldout")


def _candidate_map(world):
    return {row["sequence"]: row for row in world["candidates"]}


def _problem(world):
    proxy = []
    for row in world["single_mutation_proxy"]:
        proxy.append({
            "position": int(row["position_zero_based"]),
            "wild_type_residue": str(row["wild_type_residue"]),
            "scores": dict(row["scores"]),
        })
    pairs = tuple("".join(row["residues"]) for row in world["candidates"])
    if len(set(pairs)) != len(pairs):
        raise RuntimeError("candidate residue pairs are not unique")
    return {
        "wild_type_sequence": str(world["wild_type_sequence"]),
        "mutable_positions": tuple(int(value) for value in world["positions_zero_based"]),
        "candidate_residue_pairs": pairs,
        "single_mutation_proxy": tuple(proxy),
        "batch_size": BATCH_SIZE,
        "assay_budget": ASSAY_BUDGET,
        "objective": (
            "select a high-stability, diverse batch under limited double-mutant assays"
        ),
    }


class _Laboratory:
    def __init__(self, world):
        self.rows = _candidate_map(world)
        self.calls = 0
        self.sequences = []
        self.failure = None

    def _fail(self, code, message):
        if self.failure is None:
            self.failure = str(code)
        raise ValueError(str(message))

    def assay(self, sequence):
        if self.calls >= ASSAY_BUDGET:
            self._fail("budget_exceeded", "protein assay budget exceeded")
        if not isinstance(sequence, str):
            self._fail("invalid_assay", "assay sequence must be text")
        row = self.rows.get(sequence)
        if row is None:
            self._fail("invalid_assay", "sequence is not a feasible measured double mutant")
        self.calls += 1
        self.sequences.append(sequence)
        return {
            "stability_ddg": float(row["stability_ddg"]),
            "combined_delta_g_95ci": float(row["combined_delta_g_95ci"]),
            "budget_cost": 1,
            "remaining_budget": ASSAY_BUDGET - self.calls,
        }


def _validate_submission(submission, world):
    if not isinstance(submission, Mapping):
        raise ValueError("submission must be a mapping")
    sequences = submission.get("sequences")
    if not isinstance(sequences, (list, tuple)):
        raise ValueError("sequences must be a list or tuple")
    if len(sequences) != BATCH_SIZE:
        raise ValueError("submission must contain exactly eight sequences")
    if any(not isinstance(sequence, str) for sequence in sequences):
        raise ValueError("every submitted sequence must be text")
    if len(set(sequences)) != BATCH_SIZE:
        raise ValueError("submitted sequences must be distinct")
    rows = _candidate_map(world)
    try:
        selected = [rows[sequence] for sequence in sequences]
    except KeyError as exc:
        raise ValueError("submitted sequence is not a feasible measured double mutant") from exc
    return tuple(sequences), tuple(selected)


def _pair_distance(left, right):
    return sum(a != b for a, b in zip(left["residues"], right["residues"])) / 2.0


def _diversity(rows):
    distances = [
        _pair_distance(left, right)
        for index, left in enumerate(rows)
        for right in rows[index + 1:]
    ]
    return float(np.mean(distances))


def _field_quality(world, rows, field):
    values = np.asarray([float(row[field]) for row in world["candidates"]])
    lower = float(np.min(values))
    upper = float(np.max(values))
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise RuntimeError("degenerate protein landscape field: " + field)
    return float(np.mean([
        (float(row[field]) - lower) / (upper - lower) for row in rows
    ]))


def _batch_metrics(world, rows):
    stability_quality = _field_quality(world, rows, "stability_ddg")
    diversity = _diversity(rows)
    utility = (1.0 - DIVERSITY_WEIGHT) * stability_quality + DIVERSITY_WEIGHT * diversity
    ranked_true = sorted(
        world["candidates"], key=lambda row: (-float(row["stability_ddg"]), row["mutation"])
    )
    top_count = max(1, int(math.ceil(0.10 * len(ranked_true))))
    true_top = {row["sequence"] for row in ranked_true[:top_count]}
    ranked_proxy = sorted(
        world["candidates"], key=lambda row: (-float(row["additive_proxy"]), row["mutation"])
    )
    proxy_top = {row["sequence"] for row in ranked_proxy[:top_count]}
    selected_proxy_promotions = [row for row in rows if row["sequence"] in proxy_top]
    false_promotions = [
        row for row in selected_proxy_promotions if row["sequence"] not in true_top
    ]
    return {
        "utility": float(utility),
        "stability_quality": stability_quality,
        "mean_stability_ddg": float(np.mean([
            float(row["stability_ddg"]) for row in rows
        ])),
        "diversity": diversity,
        "top_decile_hit_rate": sum(
            row["sequence"] in true_top for row in rows
        ) / BATCH_SIZE,
        "selected_proxy_top_decile_count": len(selected_proxy_promotions),
        "proxy_false_promotion_rate": (
            len(false_promotions) / len(selected_proxy_promotions)
            if selected_proxy_promotions else 0.0
        ),
        "trypsin_quality": _field_quality(world, rows, "trypsin_delta_g"),
        "chymotrypsin_quality": _field_quality(world, rows, "chymotrypsin_delta_g"),
        "mean_trypsin_delta_g": float(np.mean([
            float(row["trypsin_delta_g"]) for row in rows
        ])),
        "mean_chymotrypsin_delta_g": float(np.mean([
            float(row["chymotrypsin_delta_g"]) for row in rows
        ])),
        "mean_combined_delta_g_95ci": float(np.mean([
            float(row["combined_delta_g_95ci"]) for row in rows
        ])),
    }


def _baseline_rows(world):
    return tuple(sorted(
        world["candidates"],
        key=lambda row: (-float(row["additive_proxy"]), row["mutation"]),
    )[:BATCH_SIZE])


def _reference_objective(world, rows):
    return _batch_metrics(world, rows)["utility"]


def _search_reference_rows(world):
    candidates = tuple(world["candidates"])
    chosen = []
    for _ in range(BATCH_SIZE):
        best = None
        best_gain = -math.inf
        for row in candidates:
            if row in chosen:
                continue
            trial = tuple(chosen + [row])
            # Use the final-batch objective terms at their final denominators.  Constants
            # omitted here do not affect ranking during constructive greedy search.
            stability = _field_quality(world, (row,), "stability_ddg")
            diversity_gain = sum(_pair_distance(row, prior) for prior in chosen)
            gain = (
                (1.0 - DIVERSITY_WEIGHT) * stability / BATCH_SIZE
                + DIVERSITY_WEIGHT * diversity_gain / math.comb(BATCH_SIZE, 2)
            )
            if (gain > best_gain + 1.0e-15
                    or (abs(gain - best_gain) <= 1.0e-15
                        and (best is None or row["mutation"] < best["mutation"]))):
                best, best_gain = row, gain
        chosen.append(best)

    for _ in range(100):
        current = _reference_objective(world, tuple(chosen))
        best_swap = None
        for index in range(BATCH_SIZE):
            for row in candidates:
                if row in chosen:
                    continue
                trial = list(chosen)
                trial[index] = row
                value = _reference_objective(world, tuple(trial))
                key = (index, row["mutation"])
                if value <= current + 1.0e-15:
                    continue
                if (best_swap is None or value > best_swap[0] + 1.0e-15
                        or (abs(value - best_swap[0]) <= 1.0e-15
                            and key < best_swap[1])):
                    best_swap = (value, key, index, row)
        if best_swap is None:
            break
        chosen[best_swap[2]] = best_swap[3]
    return tuple(sorted(chosen, key=lambda row: row["mutation"]))


def _reference_rows(world):
    by_mutation = {row["mutation"]: row for row in world["candidates"]}
    mutations = REFERENCE_MUTATIONS.get(world["id"])
    if mutations is None or len(mutations) != BATCH_SIZE or len(set(mutations)) != BATCH_SIZE:
        raise RuntimeError("invalid frozen reference mutation list")
    try:
        rows = tuple(by_mutation[mutation] for mutation in mutations)
    except KeyError as exc:
        raise RuntimeError("frozen reference mutation is absent from landscape") from exc
    return tuple(sorted(rows, key=lambda row: row["mutation"]))


@lru_cache(maxsize=1)
def _anchors():
    result = {}
    for world in WORLDS:
        baseline_rows = _baseline_rows(world)
        reference_rows = _reference_rows(world)
        baseline = _batch_metrics(world, baseline_rows)
        reference = _batch_metrics(world, reference_rows)
        if reference["utility"] <= baseline["utility"] + 0.05:
            raise RuntimeError("insufficient baseline/reference utility headroom")
        for field in ("trypsin_quality", "chymotrypsin_quality"):
            if reference[field] <= baseline[field] + 1.0e-6:
                raise RuntimeError("reference does not improve sealed protease readout")
        result[world["id"]] = {
            "baseline_rows": baseline_rows,
            "reference_rows": reference_rows,
            "baseline": baseline,
            "reference": reference,
        }
    return result


def _normalized(value, baseline, reference):
    if reference <= baseline:
        raise RuntimeError("invalid normalization anchors")
    return float(np.clip((value - baseline) / (reference - baseline), 0.0, 1.0))


def _evaluate_world(design_stable_batch, world, index):
    laboratory = _Laboratory(world)
    try:
        submission = design_stable_batch(_problem(world), laboratory.assay)
        sequences, rows = _validate_submission(submission, world)
        if laboratory.failure is not None:
            raise ValueError("callback contract was violated")
    except Exception:
        return {
            "world_index": int(index),
            "split": str(world["split"]),
            "valid": False,
            "failure_kind": laboratory.failure or "invalid_submission",
            "batch_score": 0.0,
            "batch_utility": 0.0,
            "mean_stability_ddg": 0.0,
            "stability_quality": 0.0,
            "top_decile_hit_rate": 0.0,
            "batch_diversity": 0.0,
            "proxy_false_promotion_rate": 0.0,
            "selected_proxy_top_decile_count": 0,
            "trypsin_score": 0.0,
            "chymotrypsin_score": 0.0,
            "protease_joint_score": 0.0,
            "mean_trypsin_delta_g": 0.0,
            "mean_chymotrypsin_delta_g": 0.0,
            "mean_combined_delta_g_95ci": 0.0,
            "assay_calls": laboratory.calls,
            "unique_assay_calls": len(set(laboratory.sequences)),
            "assay_unique_rate": 0.0,
            "selected_assayed_fraction": 0.0,
            "selected_unmeasured_fraction": 0.0,
            "normalized_utility_gain_per_assay": 0.0,
        }

    # Trusted calculations deliberately sit outside the candidate-artifact exception
    # boundary. A broken data anchor or scoring implementation is infrastructure failure,
    # not a candidate failure, and must propagate to the outer trusted driver.
    metrics = _batch_metrics(world, rows)
    anchors = _anchors()[world["id"]]
    batch_score = _normalized(
        metrics["utility"], anchors["baseline"]["utility"],
        anchors["reference"]["utility"],
    )
    trypsin_score = _normalized(
        metrics["trypsin_quality"], anchors["baseline"]["trypsin_quality"],
        anchors["reference"]["trypsin_quality"],
    )
    chymotrypsin_score = _normalized(
        metrics["chymotrypsin_quality"],
        anchors["baseline"]["chymotrypsin_quality"],
        anchors["reference"]["chymotrypsin_quality"],
    )
    unique_assays = len(set(laboratory.sequences))
    selected_assayed = len(set(sequences) & set(laboratory.sequences))
    return {
        "world_index": int(index),
        "split": str(world["split"]),
        "valid": True,
        "failure_kind": None,
        "batch_score": batch_score,
        "batch_utility": metrics["utility"],
        "mean_stability_ddg": metrics["mean_stability_ddg"],
        "stability_quality": metrics["stability_quality"],
        "top_decile_hit_rate": metrics["top_decile_hit_rate"],
        "batch_diversity": metrics["diversity"],
        "proxy_false_promotion_rate": metrics["proxy_false_promotion_rate"],
        "selected_proxy_top_decile_count": metrics["selected_proxy_top_decile_count"],
        "trypsin_score": trypsin_score,
        "chymotrypsin_score": chymotrypsin_score,
        "protease_joint_score": math.sqrt(trypsin_score * chymotrypsin_score),
        "mean_trypsin_delta_g": metrics["mean_trypsin_delta_g"],
        "mean_chymotrypsin_delta_g": metrics["mean_chymotrypsin_delta_g"],
        "mean_combined_delta_g_95ci": metrics["mean_combined_delta_g_95ci"],
        "assay_calls": laboratory.calls,
        "unique_assay_calls": unique_assays,
        "assay_unique_rate": unique_assays / max(laboratory.calls, 1),
        "selected_assayed_fraction": selected_assayed / BATCH_SIZE,
        "selected_unmeasured_fraction": 1.0 - selected_assayed / BATCH_SIZE,
        "normalized_utility_gain_per_assay": batch_score / max(laboratory.calls, 1),
    }


def _split_metrics(records):
    return {
        "batch_score": float(np.mean([row["batch_score"] for row in records])),
        "batch_utility": float(np.mean([row["batch_utility"] for row in records])),
        "mean_stability_ddg": float(np.mean([
            row["mean_stability_ddg"] for row in records
        ])),
        "top_decile_hit_rate": float(np.mean([
            row["top_decile_hit_rate"] for row in records
        ])),
        "diversity": float(np.mean([row["batch_diversity"] for row in records])),
        "proxy_false_promotion_rate": float(np.mean([
            row["proxy_false_promotion_rate"] for row in records
        ])),
        "trypsin_score": float(np.mean([row["trypsin_score"] for row in records])),
        "chymotrypsin_score": float(np.mean([
            row["chymotrypsin_score"] for row in records
        ])),
        "protease_joint_score": float(np.mean([
            row["protease_joint_score"] for row in records
        ])),
        "valid_rate": float(np.mean([bool(row["valid"]) for row in records])),
        "mean_assay_calls": float(np.mean([row["assay_calls"] for row in records])),
        "mean_assay_unique_rate": float(np.mean([
            row["assay_unique_rate"] for row in records
        ])),
        "mean_selected_assayed_fraction": float(np.mean([
            row["selected_assayed_fraction"] for row in records
        ])),
        "mean_selected_unmeasured_fraction": float(np.mean([
            row["selected_unmeasured_fraction"] for row in records
        ])),
        "mean_normalized_utility_gain_per_assay": float(np.mean([
            row["normalized_utility_gain_per_assay"] for row in records
        ])),
    }


def evaluate(design_stable_batch):
    records = []
    for index, world in enumerate(WORLDS):
        if index and hasattr(design_stable_batch, "reset_session"):
            design_stable_batch.reset_session()
        records.append(_evaluate_world(design_stable_batch, world, index))
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
        "development_mean_stability_ddg": dev["mean_stability_ddg"],
        "development_top_decile_hit_rate": dev["top_decile_hit_rate"],
        "development_batch_diversity": dev["diversity"],
        "development_proxy_false_promotion_rate": dev["proxy_false_promotion_rate"],
        "development_trypsin_score": dev["trypsin_score"],
        "development_chymotrypsin_score": dev["chymotrypsin_score"],
        "robustness_score": dev["protease_joint_score"] if development_valid else 0.0,
        "heldout_policy_score": held["batch_score"] if heldout_valid else 0.0,
        "heldout_batch_utility": held["batch_utility"],
        "heldout_mean_stability_ddg": held["mean_stability_ddg"],
        "heldout_top_decile_hit_rate": held["top_decile_hit_rate"],
        "heldout_batch_diversity": held["diversity"],
        "heldout_proxy_false_promotion_rate": held["proxy_false_promotion_rate"],
        "heldout_trypsin_score": held["trypsin_score"],
        "heldout_chymotrypsin_score": held["chymotrypsin_score"],
        "heldout_robustness_score": (
            held["protease_joint_score"] if heldout_valid else 0.0
        ),
        "heldout_feasibility_rate": held["valid_rate"],
        "development_mean_assay_calls": dev["mean_assay_calls"],
        "heldout_mean_assay_calls": held["mean_assay_calls"],
        "development_assay_unique_rate": dev["mean_assay_unique_rate"],
        "heldout_assay_unique_rate": held["mean_assay_unique_rate"],
        "development_selected_assayed_fraction": dev["mean_selected_assayed_fraction"],
        "heldout_selected_assayed_fraction": held["mean_selected_assayed_fraction"],
        "development_selected_unmeasured_fraction": dev["mean_selected_unmeasured_fraction"],
        "heldout_selected_unmeasured_fraction": held["mean_selected_unmeasured_fraction"],
        "development_normalized_utility_gain_per_assay": dev[
            "mean_normalized_utility_gain_per_assay"
        ],
        "heldout_normalized_utility_gain_per_assay": held[
            "mean_normalized_utility_gain_per_assay"
        ],
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
    wild_type = problem["wild_type_sequence"]
    left, right = problem["mutable_positions"]
    proxy = {row["position"]: row["scores"] for row in problem["single_mutation_proxy"]}
    pairs = sorted(
        problem["candidate_residue_pairs"],
        key=lambda pair: (-(proxy[left][pair[0]] + proxy[right][pair[1]]), pair),
    )[:BATCH_SIZE]
    sequences = []
    for pair in pairs:
        sequence = list(wild_type)
        sequence[left], sequence[right] = pair
        sequences.append("".join(sequence))
    return {"sequences": sequences}


def _reference_policy(problem, assay):
    del assay
    wild_type = problem["wild_type_sequence"]
    world = next(row for row in WORLDS if row["wild_type_sequence"] == wild_type)
    return {
        "sequences": [row["sequence"] for row in _anchors()[world["id"]]["reference_rows"]]
    }
