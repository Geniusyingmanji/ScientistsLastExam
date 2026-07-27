#!/usr/bin/env python3
"""Rebuild and calibrate the ElectrolyteConductivityDesign real-data replay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Electrochemistry/ElectrolyteConductivityDesign"
VERIFICATION = TASK / "verification"
BUILDER_PATH = ROOT / "scripts/build_electrolyte_conductivity_data.py"
sys.path.insert(0, str(ROOT))

from frontier_science.evaluate import evaluate_candidate  # noqa: E402
from frontier_science.metric_visibility import search_visible_metrics  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _public_quality(problem):
    rows = tuple(problem["candidate_formulations"])
    weights = np.asarray(problem["application_weights"], dtype=float)
    curves = np.asarray([row["proxy_conductivity_s_cm"] for row in rows])
    logs = np.log(curves)
    quality = ((logs - np.min(logs, axis=0)) / (
        np.ptp(logs, axis=0) + 1.0e-12
    )) @ weights
    x = np.asarray([(
        float(row["ratios"]["pc_in_cyclic_carbonates"]),
        float(row["ratios"]["salt_to_cyclic_carbonates"]),
    ) for row in rows])
    x = (x - np.min(x, axis=0)) / (np.ptp(x, axis=0) + 1.0e-12)
    return rows, weights, curves, quality, x


def _diversity(x, indices):
    return float(np.mean([
        np.mean(np.abs(x[left] - x[right]))
        for left, right in itertools.combinations(indices, 2)
    ]))


def _choose_batch(rows, quality, x, allowed=None):
    allowed = range(len(rows)) if allowed is None else tuple(allowed)
    best = None
    for indices in itertools.combinations(allowed, 3):
        value = 0.90 * float(np.mean(quality[list(indices)]))
        value += 0.10 * _diversity(x, indices)
        ids = tuple(rows[index]["id"] for index in indices)
        if (
            best is None or value > best[0] + 1.0e-15
            or (abs(value - best[0]) <= 1.0e-15 and ids < best[1])
        ):
            best = (value, ids)
    return list(best[1])


def truth_blind_assay_policy(problem, assay):
    """Top-proxy assay allocation followed by observed discovery-batch selection."""
    rows, weights, proxy_curves, proxy_quality, x = _public_quality(problem)
    # The policy is intentionally simple and preregisterable: spend all eight
    # assays on the proxy's leading candidates, then optimize the same declared
    # batch objective over the actually measured subset.
    queried = list(np.argsort(-proxy_quality)[:int(problem["assay_budget"])])
    measured_quality = []
    for index in queried:
        result = assay(rows[index]["id"])
        curve = np.asarray(result["mean_conductivity_s_cm"], dtype=float)
        logs = np.log(curve)
        proxy_logs = np.log(proxy_curves)
        normalized = (logs - np.min(proxy_logs, axis=0)) / (
            np.ptp(proxy_logs, axis=0) + 1.0e-12
        )
        measured_quality.append(float(normalized @ weights))
    # Optimize inside the measured subset using its local feature coordinates.
    local_rows = [rows[index] for index in queried]
    ids = _choose_batch(
        local_rows, np.asarray(measured_quality), x[queried], range(len(queried))
    )
    return {"formulation_ids": ids}


def _frozen_anchor_policy(oracle, anchor_key):
    """Build a policy for one explicitly named, evaluator-sealed witness."""

    def policy(problem, assay):
        oracle._consume_unique_assays(problem, assay)
        weights = np.asarray(problem["application_weights"], dtype=float)
        world = next(
            row for row in oracle.WORLDS
            if np.allclose(row["weights"], weights, atol=0, rtol=0)
        )
        return {
            "formulation_ids": list(
                oracle._anchors()[world["name"]][anchor_key]
            )
        }

    return policy


def _rebuild_data(builder, csv_path, expected):
    rebuilt = builder.build(Path(csv_path))
    rendered = json.dumps(
        rebuilt, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True
    ) + "\n"
    return {
        "rebuilt_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        "expected_sha256": _sha256(expected),
        "exact_match": rendered.encode("utf-8") == expected.read_bytes(),
        "source_formulation_count": len(rebuilt["source_formulations"]),
        "candidate_formulation_count": len(rebuilt["candidates"]),
        "source": rebuilt["source"],
        "contract": rebuilt["contract"],
    }


def _independent_arrhenius_checks(document):
    records = []
    max_r2_error = 0.0
    max_mse_error = 0.0
    max_activation_error = 0.0
    gas_constant = 8.314
    temperatures = np.asarray(document["contract"]["temperatures_c"]) + 273.15
    inverse = 1000.0 / temperatures
    for candidate in document["candidates"]:
        for field in (
            "discovery_replicates", "confirmation_replicates", "audit_replicates"
        ):
            for repeat in candidate[field]:
                conductivity = np.asarray(repeat["conductivity_s_cm"], dtype=float)
                logs = np.log(conductivity)
                slope, intercept = np.polyfit(inverse, logs, 1)
                predicted = intercept + slope * inverse
                mse = float(np.mean((logs - predicted) ** 2))
                r2 = float(1.0 - np.sum((logs - predicted) ** 2) / np.sum(
                    (logs - np.mean(logs)) ** 2
                ))
                activation = float(-slope * gas_constant)
                max_r2_error = max(max_r2_error, abs(r2 - repeat["arrhenius_r2"]))
                max_mse_error = max(max_mse_error, abs(mse - repeat["arrhenius_mse"]))
                max_activation_error = max(
                    max_activation_error,
                    abs(activation - repeat["arrhenius_activation_energy"]),
                )
                records.append(repeat["experiment_id"])
    return {
        "experiment_count": len(records),
        "unique_experiment_count": len(set(records)),
        "maximum_absolute_r2_error": max_r2_error,
        "maximum_absolute_mse_error": max_mse_error,
        "maximum_absolute_activation_energy_error": max_activation_error,
    }


def calibrate(csv_path):
    oracle = _load(VERIFICATION / "evaluator.py", "electrolyte_oracle")
    builder = _load(BUILDER_PATH, "electrolyte_builder")
    spec = find_task(
        "Electrochemistry/ElectrolyteConductivityDesign", include_uncertified=True
    )
    secure_baseline = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
    direct_baseline = oracle.evaluate(oracle._baseline_policy)
    direct_reference = oracle.evaluate(oracle._reference_policy)
    direct_robust_reference = oracle.evaluate(oracle._robust_reference_policy)
    direct_confirmation_reference = oracle.evaluate(_frozen_anchor_policy(
        oracle, "confirmation_reference_ids"
    ))
    direct_confirmation_robust_reference = oracle.evaluate(_frozen_anchor_policy(
        oracle, "confirmation_robust_reference_ids"
    ))
    truth_blind = oracle.evaluate(truth_blind_assay_policy)
    rebuild = _rebuild_data(builder, csv_path, oracle.DATA_PATH)
    arrhenius = _independent_arrhenius_checks(oracle.DATA_DOCUMENT)

    headroom = []
    reference_rebuild = []
    for world in oracle.WORLDS:
        anchor = oracle._anchors()[world["name"]]
        nominal = anchor["reference_utility"] - anchor["baseline_utility"]
        robust = (
            anchor["robust_reference_utility"]
            - anchor["baseline_lower_utility"]
        )
        headroom.append(min(nominal, robust))
        reference_rebuild.append({
            "world": world["name"],
            "split": world["split"],
            "baseline_ids": list(anchor["baseline_ids"]),
            "reference_ids": list(anchor["reference_ids"]),
            "robust_reference_ids": list(anchor["robust_reference_ids"]),
            "confirmation_reference_ids": list(
                anchor["confirmation_reference_ids"]
            ),
            "confirmation_robust_reference_ids": list(
                anchor["confirmation_robust_reference_ids"]
            ),
            "nominal_headroom": nominal,
            "repeat_robust_headroom": robust,
        })

    visible = search_visible_metrics(secure_baseline)
    secure_baseline_ids = [
        list(row["selected_ids"]) for row in secure_baseline["per_world"]
    ]
    direct_baseline_ids = [
        list(row["selected_ids"]) for row in direct_baseline["per_world"]
    ]
    execution_passed = bool(
        rebuild["exact_match"]
        and rebuild["source_formulation_count"] == 85
        and rebuild["candidate_formulation_count"] == 23
        and arrhenius["experiment_count"] == 141
        and arrhenius["unique_experiment_count"] == 141
        and arrhenius["maximum_absolute_r2_error"] < 1e-12
        and arrhenius["maximum_absolute_mse_error"] < 1e-12
        and arrhenius["maximum_absolute_activation_energy_error"] < 1e-10
        and min(headroom) > 0.04
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["candidate_world_call_count"] == 8
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and secure_baseline_ids == direct_baseline_ids
        and direct_baseline["combined_score"] == 0.0
        and direct_baseline["robustness_score"] == 0.0
        and direct_baseline["heldout_policy_score"] == 0.0
        and direct_reference["combined_score"] == 1.0
        and direct_reference["heldout_policy_score"] == 1.0
        and direct_robust_reference["robustness_score"] == 1.0
        and direct_robust_reference["heldout_robustness_score"] == 1.0
        and direct_confirmation_reference["confirmation_score"] == 1.0
        and direct_confirmation_reference["heldout_confirmation_score"] == 1.0
        and direct_confirmation_robust_reference["confirmation_robustness_score"] == 1.0
        and direct_confirmation_robust_reference["heldout_confirmation_robustness_score"] == 1.0
        and direct_confirmation_reference[
            "development_confirmation_mean_weighted_conductivity_s_cm"
        ] >= direct_baseline[
            "development_confirmation_mean_weighted_conductivity_s_cm"
        ] * 1.05
        and direct_confirmation_reference[
            "heldout_confirmation_mean_weighted_conductivity_s_cm"
        ] >= direct_baseline[
            "heldout_confirmation_mean_weighted_conductivity_s_cm"
        ] * 1.05
        and truth_blind["valid"] == 1.0
        and truth_blind["development_mean_assay_calls"] == 8.0
        and truth_blind["heldout_mean_assay_calls"] == 8.0
        and truth_blind["development_assay_unique_rate"] == 1.0
        and truth_blind["heldout_assay_unique_rate"] == 1.0
        and truth_blind["combined_score"] > 0.25
        and truth_blind["heldout_policy_score"] > 0.25
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "PUBLIC_EIS_OFFLINE_OPTIMIZATION_REPLAY_WITH_SEPARATE_UNTOUCHED_"
            "REPEAT_CONFIRMATION_NOT_COMPLETE_CELL_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "Electrochemistry/ElectrolyteConductivityDesign",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                TASK / "Task.md", TASK / "TASK_CARD.yaml", TASK / "solution.py",
                VERIFICATION / "evaluator.py", oracle.DATA_PATH, BUILDER_PATH,
            )
        },
        "source_rebuild": rebuild,
        "independent_arrhenius_recalculation": arrhenius,
        "reference_rebuild": reference_rebuild,
        "minimum_nominal_or_robust_headroom": min(headroom),
        "secure_baseline": secure_baseline,
        "direct_baseline": direct_baseline,
        "direct_reference": direct_reference,
        "direct_robust_reference": direct_robust_reference,
        "direct_confirmation_reference": direct_confirmation_reference,
        "direct_confirmation_robust_reference": (
            direct_confirmation_robust_reference
        ),
        "truth_blind_assay_policy": {
            "method": (
                "assay the eight leading historical-proxy candidates and select "
                "the best measured diversity-aware batch"
            ),
            "metrics": truth_blind,
        },
        "descriptive_findings": {
            "visible_assay_optimization_has_positive_development_gain": (
                truth_blind["combined_score"] > 0.0
            ),
            "visible_assay_optimization_transfers_to_heldout_profiles": (
                truth_blind["heldout_policy_score"] > 0.0
            ),
            "untouched_confirmation_supports_the_selected_policy": (
                truth_blind["confirmation_score"] > 0.0
                and truth_blind["heldout_confirmation_score"] > 0.0
            ),
            "untouched_confirmation_landscape_has_material_headroom": (
                direct_confirmation_reference[
                    "development_confirmation_mean_weighted_conductivity_s_cm"
                ] >= direct_baseline[
                    "development_confirmation_mean_weighted_conductivity_s_cm"
                ] * 1.05
                and direct_confirmation_reference[
                    "heldout_confirmation_mean_weighted_conductivity_s_cm"
                ] >= direct_baseline[
                    "heldout_confirmation_mean_weighted_conductivity_s_cm"
                ] * 1.05
            ),
            "nominal_and_repeat_robust_reference_batches_differ": any(
                row["reference_ids"] != row["robust_reference_ids"]
                for row in reference_rebuild
            ),
        },
        "limitations": [
            "The task replays a finite public dataset and cannot rule out pretraining contamination or an external lookup table.",
            "The visible optimization metric reuses the two discovery repeats returned by the charged assay; untouched repeats are reported separately as confirmation and may reverse the apparent gain.",
            "The held-out axis changes temperature-duty weights over the same EC/PC/EMC/LiPF6 candidate formulations, not chemistry, laboratory or instrument family.",
            "Conductivity alone does not establish electrochemical stability, safety, electrode compatibility, cycle life, manufacturability or complete-cell performance.",
            "A prospective server-held formulation campaign, new batches, independent EIS analysis and complete-cell validation remain required for scientific-discovery claims.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calibrate(args.csv)
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    metrics = report["truth_blind_assay_policy"]["metrics"]
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        "data_sha256": report["source_rebuild"]["rebuilt_sha256"],
        "truth_blind_combined_score": metrics["combined_score"],
        "truth_blind_heldout_score": metrics["heldout_policy_score"],
        "truth_blind_confirmation_score": metrics["confirmation_score"],
        "truth_blind_heldout_confirmation_score": metrics[
            "heldout_confirmation_score"
        ],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
