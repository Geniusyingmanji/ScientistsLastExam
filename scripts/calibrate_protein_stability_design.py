#!/usr/bin/env python3
"""Rebuild and calibrate the ProteinStabilityDesign real-data replay task."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Biology/ProteinStabilityDesign"
VERIFICATION = TASK / "verification"
BUILDER_PATH = ROOT / "scripts/build_protein_stability_data.py"
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


# Coarse public residue descriptors.  They are used only by the truth-blind calibration
# policy and are not fitted to this benchmark's hidden labels.
HYDROPATHY = {
    "A": 1.8, "C": 2.5, "D": -3.5, "E": -3.5, "F": 2.8,
    "G": -0.4, "H": -3.2, "I": 4.5, "K": -3.9, "L": 3.8,
    "M": 1.9, "N": -3.5, "P": -1.6, "Q": -3.5, "R": -4.5,
    "S": -0.8, "T": -0.7, "V": 4.2, "W": -0.9, "Y": -1.3,
}
VOLUME = {
    "A": 88.6, "C": 108.5, "D": 111.1, "E": 138.4, "F": 189.9,
    "G": 60.1, "H": 153.2, "I": 166.7, "K": 168.6, "L": 166.7,
    "M": 162.9, "N": 114.1, "P": 112.7, "Q": 143.8, "R": 173.4,
    "S": 89.0, "T": 116.1, "V": 140.0, "W": 227.8, "Y": 193.6,
}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sequence(problem, pair):
    result = list(problem["wild_type_sequence"])
    left, right = [int(value) for value in problem["mutable_positions"]]
    result[left], result[right] = pair
    return "".join(result)


def _residue_charge(residue):
    if residue in "KR":
        return 1.0
    if residue == "H":
        return 0.3
    if residue in "DE":
        return -1.0
    return 0.0


def _public_features(problem):
    positions = tuple(int(value) for value in problem["mutable_positions"])
    proxy = {
        int(row["position"]): row["scores"]
        for row in problem["single_mutation_proxy"]
    }
    pairs = tuple(str(pair) for pair in problem["candidate_residue_pairs"])
    additive = np.asarray([
        float(proxy[positions[0]][pair[0]]) + float(proxy[positions[1]][pair[1]])
        for pair in pairs
    ])
    rows = []
    for pair, proxy_value in zip(pairs, additive):
        left, right = pair
        rows.append((
            1.0,
            proxy_value,
            HYDROPATHY[left], HYDROPATHY[right],
            VOLUME[left] / 100.0, VOLUME[right] / 100.0,
            _residue_charge(left), _residue_charge(right),
            float(left in "FWHY"), float(right in "FWHY"),
            float(left in "GP"), float(right in "GP"),
            HYDROPATHY[left] * HYDROPATHY[right] / 10.0,
            _residue_charge(left) * _residue_charge(right),
            abs(VOLUME[left] - VOLUME[right]) / 100.0,
        ))
    features = np.asarray(rows, dtype=float)
    features[:, 1:] = (
        features[:, 1:] - np.mean(features[:, 1:], axis=0)
    ) / (np.std(features[:, 1:], axis=0) + 1.0e-8)
    return pairs, additive, features


def _pair_distance(left, right):
    return sum(a != b for a, b in zip(left, right)) / 2.0


def _choose_batch(pairs, predicted, batch_size=8, diversity_weight=0.25):
    predicted = np.asarray(predicted, dtype=float)
    normalized = (
        (predicted - np.min(predicted))
        / (np.max(predicted) - np.min(predicted) + 1.0e-12)
    )
    chosen = []
    for _ in range(batch_size):
        best = None
        best_gain = -math.inf
        for index, pair in enumerate(pairs):
            if index in chosen:
                continue
            diversity_gain = sum(
                _pair_distance(pair, pairs[prior]) for prior in chosen
            )
            gain = (
                (1.0 - diversity_weight) * normalized[index] / batch_size
                + diversity_weight * diversity_gain / math.comb(batch_size, 2)
            )
            if (gain > best_gain + 1.0e-15
                    or (abs(gain - best_gain) <= 1.0e-15
                        and (best is None or pair < pairs[best]))):
                best, best_gain = index, gain
        chosen.append(best)
    return chosen


def truth_blind_assay_policy(problem, assay):
    """D-optimal public-feature regression using exactly twelve measured pairs."""
    pairs, additive, features = _public_features(problem)
    normalized_proxy = (
        (additive - np.min(additive))
        / (np.max(additive) - np.min(additive) + 1.0e-12)
    )
    inverse = np.eye(features.shape[1], dtype=float) * 2.0
    queried = []
    for _ in range(int(problem["assay_budget"])):
        scores = []
        for index, feature in enumerate(features):
            if index in queried:
                scores.append(-math.inf)
                continue
            information = float(feature @ inverse @ feature)
            scores.append(information * (0.2 + 0.8 * normalized_proxy[index]))
        selected = int(np.argmax(scores))
        queried.append(selected)
        feature = features[selected]
        product = inverse @ feature
        inverse -= np.outer(product, product) / (1.0 + float(feature @ product))

    observed = np.asarray([
        float(assay(_sequence(problem, pairs[index]))["stability_ddg"])
        for index in queried
    ])
    matrix = features[queried]
    regularizer = np.diag(
        [0.01, 0.05] + [2.0] * (features.shape[1] - 2)
    )
    coefficients = np.linalg.solve(
        matrix.T @ matrix + regularizer, matrix.T @ observed
    )
    predicted = features @ coefficients
    selected = _choose_batch(pairs, predicted)
    return {
        "sequences": [_sequence(problem, pairs[index]) for index in selected]
    }


def _rebuild_data(builder, reference_csv, processed_zip, raw_zip, expected):
    rebuilt = builder.build(reference_csv, processed_zip, raw_zip)
    rendered = json.dumps(
        rebuilt, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
    ) + "\n"
    return {
        "rebuilt_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "expected_sha256": _sha256(expected),
        "exact_match": rendered.encode("utf-8") == expected.read_bytes(),
        "world_count": len(rebuilt["worlds"]),
        "candidate_counts": {
            row["id"]: row["candidate_count"] for row in rebuilt["worlds"]
        },
        "source": rebuilt["source"],
    }


def calibrate(reference_csv, processed_zip, raw_zip):
    oracle = _load(VERIFICATION / "evaluator.py", "protein_stability_oracle")
    builder = _load(BUILDER_PATH, "protein_stability_builder")
    spec = find_task("ProteinEngineering/ProteinStabilityDesign", include_uncertified=True)
    secure_baseline = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
    direct_baseline = oracle.evaluate(oracle._baseline_policy)
    direct_reference = oracle.evaluate(oracle._reference_policy)
    truth_blind = oracle.evaluate(truth_blind_assay_policy)
    rebuild = _rebuild_data(
        builder, Path(reference_csv), Path(processed_zip), Path(raw_zip), oracle.DATA_PATH
    )

    reference_rebuild = []
    minimum_headroom = math.inf
    minimum_protease_headroom = math.inf
    for world in oracle.WORLDS:
        anchors = oracle._anchors()[world["id"]]
        rebuilt_rows = oracle._search_reference_rows(world)
        frozen_rows = oracle._reference_rows(world)
        exact = tuple(row["mutation"] for row in rebuilt_rows) == tuple(
            row["mutation"] for row in frozen_rows
        )
        utility_headroom = (
            anchors["reference"]["utility"] - anchors["baseline"]["utility"]
        )
        protease_headroom = min(
            anchors["reference"][field] - anchors["baseline"][field]
            for field in ("trypsin_quality", "chymotrypsin_quality")
        )
        minimum_headroom = min(minimum_headroom, utility_headroom)
        minimum_protease_headroom = min(
            minimum_protease_headroom, protease_headroom
        )
        reference_rebuild.append({
            "world_id": world["id"],
            "split": world["split"],
            "candidate_count": len(world["candidates"]),
            "baseline_mutations": [
                row["mutation"] for row in anchors["baseline_rows"]
            ],
            "frozen_reference_mutations": [
                row["mutation"] for row in frozen_rows
            ],
            "rebuilt_reference_mutations": [
                row["mutation"] for row in rebuilt_rows
            ],
            "exact_match": exact,
            "baseline": anchors["baseline"],
            "reference": anchors["reference"],
            "utility_headroom": utility_headroom,
            "minimum_protease_quality_headroom": protease_headroom,
        })

    source = oracle.DATA_DOCUMENT["source"]
    provenance_passed = bool(
        rebuild["exact_match"]
        and rebuild["world_count"] == 8
        and min(rebuild["candidate_counts"].values()) >= 300
        and source["article"]["doi"] == "10.1038/s41586-023-06328-6"
        and source["article"]["license"] == "CC-BY-4.0"
        and source["proteingym"]["dataset_doi"] == "10.5281/zenodo.15293562"
        and source["proteingym"]["version"] == "1.3"
        and source["proteingym"]["repository_commit"]
        == builder.PROTEINGYM_COMMIT
    )
    visible = search_visible_metrics(secure_baseline)
    execution_passed = bool(
        oracle.PROTEIN_STABILITY_DESIGN_V1
        and provenance_passed
        and all(row["exact_match"] for row in reference_rebuild)
        and minimum_headroom > 0.10
        and minimum_protease_headroom > 1.0e-3
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["candidate_world_call_count"] == 8
        and set(visible) == {"combined_score", "valid", "feasibility_rate", "raw_score"}
        and direct_baseline["valid"] == 1.0
        and direct_baseline["combined_score"] == 0.0
        and direct_baseline["heldout_policy_score"] == 0.0
        and direct_baseline["robustness_score"] == 0.0
        and direct_reference["valid"] == 1.0
        and direct_reference["combined_score"] == 1.0
        and direct_reference["heldout_policy_score"] == 1.0
        and direct_reference["robustness_score"] == 1.0
        and direct_reference["heldout_robustness_score"] == 1.0
        and truth_blind["valid"] == 1.0
        and truth_blind["development_mean_assay_calls"] == 12.0
        and truth_blind["heldout_mean_assay_calls"] == 12.0
        and truth_blind["combined_score"] > 0.35
        and truth_blind["heldout_policy_score"] > 0.25
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "PUBLIC_DMS_OFFLINE_EXPERIMENT_DESIGN_REPLAY_NOT_NEW_PROTEIN_"
            "WET_LAB_FUNCTION_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "ProteinEngineering/ProteinStabilityDesign",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                TASK / "Task.md", TASK / "TASK_CARD.yaml", TASK / "solution.py",
                VERIFICATION / "evaluator.py", oracle.DATA_PATH, BUILDER_PATH,
            )
        },
        "source_rebuild": rebuild,
        "data_provenance_checks_passed": provenance_passed,
        "reference_rebuild": reference_rebuild,
        "minimum_utility_headroom": minimum_headroom,
        "minimum_protease_quality_headroom": minimum_protease_headroom,
        "secure_baseline": secure_baseline,
        "direct_baseline": direct_baseline,
        "direct_reference": direct_reference,
        "truth_blind_assay_policy": {
            "method": (
                "D-optimal selection over public additive and coarse residue features, "
                "twelve charged measurements, ridge fit and diversity-aware batch selection"
            ),
            "metrics": truth_blind,
        },
        "limitations": [
            "The task replays finite public DMS measurements and cannot rule out pretraining contamination or an external lookup table.",
            "The held-out split covers protein domains within one cDNA-display dataset, not prospective laboratory generalization.",
            "The assay reports proteolysis-derived stability and does not establish expression, activity, binding, toxicity or in-vivo fitness.",
            "The diversity-aware reference uses full hidden landscapes only as a normalization witness and is not available to runtime policies.",
            "A prospective server-held protein panel, synthesis, independent biophysical measurements and functional assays remain required for scientific-discovery claims.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-csv", type=Path, required=True)
    parser.add_argument("--processed-zip", type=Path, required=True)
    parser.add_argument("--raw-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate(args.reference_csv, args.processed_zip, args.raw_zip)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "passed": report["passed"],
        "data_sha256": report["source_rebuild"]["rebuilt_sha256"],
        "truth_blind_combined_score": report["truth_blind_assay_policy"]["metrics"]["combined_score"],
        "truth_blind_heldout_score": report["truth_blind_assay_policy"]["metrics"]["heldout_policy_score"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
