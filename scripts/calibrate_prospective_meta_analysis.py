#!/usr/bin/env python3
"""Calibrate ProspectiveMetaAnalysis-v1 anchors and evidence-integrity gates."""

from __future__ import annotations

import argparse
import copy
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
TASK = ROOT / "benchmarks/Biology/ProspectiveMetaAnalysis"
sys.path.insert(0, str(ROOT))

from sle.evaluate import evaluate_candidate  # noqa: E402
from sle.metric_visibility import search_visible_metrics  # noqa: E402
from sle.provenance import finalize_report_trust, source_provenance  # noqa: E402
from sle.registry import find_task  # noqa: E402


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("prospective_meta_calibration", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load prospective evidence oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _independent_fixed_tau_fit(records, tau):
    rows = [
        row for row in records
        if row["record_type"] == "registry_result"
        and row["randomized"]
        and row["population"] == "target_condition"
        and row["comparator"] == "standard_care"
        and row["preregistered_primary"] == "response_12w"
    ]
    x = np.asarray([row["moderator_value"] for row in rows], dtype=float)
    y = np.asarray([row["outcomes"][0]["effect"] for row in rows], dtype=float)
    se = np.asarray([row["outcomes"][0]["standard_error"] for row in rows], dtype=float)
    design = np.column_stack((np.ones_like(x), x))
    weights = 1.0 / (se * se + float(tau) ** 2)
    beta = np.linalg.solve(
        design.T @ (weights[:, None] * design), design.T @ (weights * y)
    )
    return beta


def _naive_highlighted_article_fit(records):
    rows = [row for row in records if row["record_type"] == "publication"]
    x, y, se = [], [], []
    for row in rows:
        highlighted = next(
            outcome for outcome in row["outcomes"]
            if outcome["name"] == row["highlighted_outcome"]
        )
        x.append(row["moderator_value"])
        y.append(highlighted["effect"])
        se.append(highlighted["standard_error"])
    x, y, se = map(lambda values: np.asarray(values, dtype=float), (x, y, se))
    design = np.column_stack((np.ones_like(x), x))
    weights = 1.0 / (se * se)
    return np.linalg.solve(
        design.T @ (weights[:, None] * design), design.T @ (weights * y)
    )


def _world_checks(oracle):
    checks = []
    maximum_independent_beta_gap = 0.0
    minimum_nonlinear_z = float("inf")
    maximum_supported_z = 0.0
    minimum_naive_article_intercept_bias = float("inf")
    for split, specs in (
        ("development", oracle.DEVELOPMENT_SPECS),
        ("heldout", oracle.HELDOUT_SPECS),
    ):
        for spec in specs:
            world = oracle._make_world(spec)
            problem = oracle._public_problem(world)
            screening = oracle._reference_screening(problem)
            expected = oracle._expected_screening(world)
            linear = oracle._fit_meta_regression(problem["records"], quadratic=False)
            quadratic = oracle._fit_meta_regression(problem["records"], quadratic=True)
            independent = _independent_fixed_tau_fit(
                problem["records"], linear["tau"]
            )
            beta_gap = float(np.max(np.abs(independent - linear["beta"][:2])))
            maximum_independent_beta_gap = max(maximum_independent_beta_gap, beta_gap)
            quadratic_se = math.sqrt(float(quadratic["covariance"][2, 2]))
            quadratic_z = abs(float(quadratic["beta"][2])) / quadratic_se
            if world["kind"] == "nonlinear":
                minimum_nonlinear_z = min(minimum_nonlinear_z, quadratic_z)
            else:
                maximum_supported_z = max(maximum_supported_z, quadratic_z)

            publications = [
                copy.deepcopy(record) for record in problem["records"]
                if record["record_type"] == "publication"
            ]
            for record in publications:
                record["record_id"] += "-calibration-duplicate"
                record["highlighted_outcome"] = "biomarker_response"
            duplicate_fit = oracle._fit_meta_regression(
                list(problem["records"]) + publications, quadratic=False
            )
            duplicate_beta_gap = float(np.max(np.abs(
                duplicate_fit["beta"] - linear["beta"]
            )))
            naive_beta = _naive_highlighted_article_fit(problem["records"])
            naive_intercept_bias = abs(
                float(naive_beta[0]) - world["truth"]["intercept"]
            )
            minimum_naive_article_intercept_bias = min(
                minimum_naive_article_intercept_bias, naive_intercept_bias
            )
            model = oracle._reference_pre_model(problem)
            checks.append({
                "split": split,
                "seed": int(spec[0]),
                "kind": str(spec[1]),
                "record_count": len(problem["records"]),
                "eligible_lineage_count": len(expected["included_registration_ids"]),
                "primary_record_count": len(expected["primary_record_ids"]),
                "duplicate_group_count": len(expected["duplicate_groups"]),
                "selective_report_count": len(expected["selective_report_ids"]),
                "screening_exact": bool(
                    set(screening["included_registration_ids"])
                    == expected["included_registration_ids"]
                    and set(screening["primary_record_ids"])
                    == expected["primary_record_ids"]
                    and oracle._pairs(screening["duplicate_groups"])
                    == oracle._pairs(expected["duplicate_groups"])
                    and set(screening["selective_report_ids"])
                    == expected["selective_report_ids"]
                ),
                "linear_tau": float(linear["tau"]),
                "linear_beta": [float(value) for value in linear["beta"][:2]],
                "independent_fixed_tau_beta": [float(value) for value in independent],
                "independent_beta_max_abs_gap": beta_gap,
                "publication_duplication_beta_max_abs_gap": duplicate_beta_gap,
                "naive_highlighted_article_beta": [
                    float(value) for value in naive_beta
                ],
                "naive_highlighted_article_intercept_bias": naive_intercept_bias,
                "quadratic_lack_of_fit_coefficient": float(quadratic["beta"][2]),
                "quadratic_lack_of_fit_z": quadratic_z,
                "truth_blind_abstain": bool(model["abstain"]),
                "expected_abstain": world["kind"] == "nonlinear",
                "passed": bool(
                    beta_gap < 1.0e-12
                    and duplicate_beta_gap == 0.0
                    and model["abstain"] == (world["kind"] == "nonlinear")
                ),
            })
    return {
        "records": checks,
        "maximum_independent_beta_gap": maximum_independent_beta_gap,
        "minimum_nonlinear_lack_of_fit_z": minimum_nonlinear_z,
        "maximum_supported_lack_of_fit_z": maximum_supported_z,
        "minimum_naive_highlighted_article_intercept_bias": (
            minimum_naive_article_intercept_bias
        ),
        "passed": all(record["passed"] for record in checks),
    }


def _invalid_checks(oracle):
    world = oracle._make_world(oracle.DEVELOPMENT_SPECS[0])
    problem = oracle._public_problem(world)
    screening = oracle._reference_screening(problem)
    pre = oracle._reference_pre_model(problem)
    base = {
        "screening": screening,
        "preconfirmation": pre,
        "site_id": "site_c",
        "sample_size": 200,
        "forecast": {
            "predicted_effect": pre["intercept"],
            "prediction_interval": [pre["intercept"] - 0.5, pre["intercept"] + 0.5],
        },
    }
    variants = {}
    nonfinite = copy.deepcopy(base)
    nonfinite["preconfirmation"]["tau"] = float("nan")
    variants["nonfinite"] = nonfinite
    unknown = copy.deepcopy(base)
    unknown["screening"]["primary_record_ids"].append("REC-unknown")
    variants["unknown_record"] = unknown
    inconsistent = copy.deepcopy(base)
    inconsistent["forecast"]["predicted_effect"] += 0.2
    variants["inconsistent_forecast"] = inconsistent
    overbudget = copy.deepcopy(base)
    overbudget["site_id"] = "site_a"
    overbudget["sample_size"] = 300
    variants["overbudget"] = overbudget
    records = {}
    for name, value in variants.items():
        try:
            oracle._validate_commit(value, problem)
            rejected = False
            reason = "accepted"
        except Exception as exc:
            rejected = True
            reason = "%s: %s" % (type(exc).__name__, exc)
        records[name] = {"rejected": rejected, "reason": reason}
    return {"records": records, "passed": all(row["rejected"] for row in records.values())}


def calibrate():
    oracle = _load_oracle()
    spec = find_task(
        "EvidenceSynthesis/ProspectiveMetaAnalysis", include_uncertified=True
    )
    direct_baseline = oracle.evaluate(oracle.weak_baseline)
    secure_baseline = evaluate_candidate(
        spec, spec.initial_program_path, timeout_s=120
    )
    truth_blind = oracle.evaluate(oracle.reference_policy)
    oracle_reference = oracle.evaluate(oracle.oracle_reference_policy)
    world_checks = _world_checks(oracle)
    invalid = _invalid_checks(oracle)
    visible = search_visible_metrics(secure_baseline)
    direct_json = json.loads(json.dumps(direct_baseline, allow_nan=False))
    execution_passed = bool(
        len(oracle.DEVELOPMENT_SPECS) == 6
        and len(oracle.HELDOUT_SPECS) == 4
        and world_checks["passed"]
        and world_checks["minimum_nonlinear_lack_of_fit_z"] > 2.0
        and world_checks["maximum_supported_lack_of_fit_z"] < 2.0
        and world_checks["minimum_naive_highlighted_article_intercept_bias"] > 0.01
        and invalid["passed"]
        and secure_baseline == direct_json
        and secure_baseline["valid"] == 1.0
        and secure_baseline["combined_score"] == 0.0
        and secure_baseline["robustness_score"] == 0.0
        and set(visible) == {
            "combined_score", "valid", "feasibility_rate", "raw_score"
        }
        and 0.75 < truth_blind["combined_score"] < 0.99
        and 0.70 < truth_blind["heldout_policy_score"] < 0.99
        and truth_blind["development_evidence_integrity_score"] == 1.0
        and truth_blind["heldout_evidence_integrity_score"] == 1.0
        and truth_blind["development_false_discovery_rate"] == 0.0
        and truth_blind["heldout_false_discovery_rate"] == 0.0
        and truth_blind["development_unsupported_refusal_rate"] == 1.0
        and truth_blind["heldout_unsupported_refusal_rate"] == 1.0
        and truth_blind["development_mean_confirmation_calls"] == 1.0
        and truth_blind["heldout_mean_confirmation_calls"] == 1.0
        and oracle_reference["combined_score"] == 1.0
        and oracle_reference["robustness_score"] == 1.0
        and oracle_reference["heldout_policy_score"] == 1.0
        and oracle_reference["heldout_robustness_score"] == 1.0
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_TASK_CALIBRATION",
        "evidence_scope": (
            "SYNTHETIC_REGISTERED_STUDY_EVIDENCE_SYNTHESIS_AND_PROSPECTIVE_"
            "CONFIRMATION_NOT_CLINICAL_OR_REAL_META_ANALYSIS_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "task": "EvidenceSynthesis/ProspectiveMetaAnalysis",
        "task_source_sha256": {
            str(path.relative_to(ROOT)): _sha256(path)
            for path in (
                TASK / "Task.md", TASK / "TASK_CARD.yaml", TASK / "solution.py",
                TASK / "verification/evaluator.py",
                TASK / "frontier_eval/metadata.yaml",
            )
        },
        "task_dimensions": {
            "development_world_count": len(oracle.DEVELOPMENT_SPECS),
            "heldout_world_count": len(oracle.HELDOUT_SPECS),
            "eligible_lineages_per_world": 14,
            "site_count": len(oracle.SITES),
            "study_budget": oracle.STUDY_BUDGET,
            "supported_world_count": sum(
                kind != "nonlinear"
                for _, kind in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
            ),
            "unsupported_world_count": sum(
                kind == "nonlinear"
                for _, kind in oracle.DEVELOPMENT_SPECS + oracle.HELDOUT_SPECS
            ),
        },
        "direct_weak_baseline": direct_baseline,
        "secure_weak_baseline": secure_baseline,
        "secure_baseline_exactly_matches_direct": secure_baseline == direct_json,
        "search_visible_baseline_metrics": visible,
        "truth_blind_reference": truth_blind,
        "oracle_reference": oracle_reference,
        "world_checks": world_checks,
        "invalid_artifact_checks": invalid,
        "difficulty_gate": {
            "baseline_is_zero": direct_baseline["combined_score"] == 0.0,
            "truth_blind_reference_has_headroom": 0.75 < truth_blind["combined_score"] < 0.99,
            "heldout_reference_has_headroom": 0.70 < truth_blind["heldout_policy_score"] < 0.99,
            "truth_blind_reference_refuses_all_nonlinear_worlds": bool(
                truth_blind["development_unsupported_refusal_rate"] == 1.0
                and truth_blind["heldout_unsupported_refusal_rate"] == 1.0
            ),
            "naive_highlighted_article_analysis_is_materially_biased": bool(
                world_checks["minimum_naive_highlighted_article_intercept_bias"] > 0.01
            ),
            "passed": bool(
                direct_baseline["combined_score"] == 0.0
                and 0.75 < truth_blind["combined_score"] < 0.99
                and 0.70 < truth_blind["heldout_policy_score"] < 0.99
            ),
        },
        "limitations": [
            "The study corpora, registries, publications and prospective results are synthetic standardized-effect summaries, not human-participant research.",
            "Known registration identifiers make lineage de-duplication executable; real reviews require source-document investigation, author contact and risk-of-bias assessment.",
            "The public linear moderator family and quadratic lack-of-fit control omit multi-level dependence, endpoint covariance, cluster trials, missing data and individual participant data.",
            "Fixed repository-visible seeds require server-held corpora and contamination/shortcut auditing.",
            "A sealed simulated confirmation is not independent laboratory, clinical or policy confirmation.",
            "Task calibration does not measure GPT-5.5, feedback causality, population performance or autonomous scientific discovery.",
        ],
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = calibrate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        key: report[key]
        for key in ("passed", "execution_passed", "trust_decision", "trusted_evidence")
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
