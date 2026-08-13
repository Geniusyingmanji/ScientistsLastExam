#!/usr/bin/env python3
"""Audit the wave-6 tandem-photovoltaic candidate admission gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sle.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


TASK_ID = "Photovoltaics/PhotovoltaicTandemDesign"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    calibration = _load(
        ROOT / "scripts/calibrate_photovoltaic_tandem.py",
        "wave6_photovoltaic_calibration",
    ).audit()
    nominal = calibration["nominal_reference_policy"]
    robust = calibration["robust_reference_policy"]
    record = {
        "task": TASK_ID,
        "admission": "candidate",
        "resolved_capability_gap": (
            "adds a cost-conditioned scientific-instrument design curve rather than a "
            "fixed scalar optimum: the policy jointly chooses junction count, band gaps "
            "and finite optical depths across budgets, while held-out spectra, current "
            "matching and thermal/process/optical robustness remain separately auditable"
        ),
        "development_world_count": 5,
        "heldout_world_count": 3,
        "fabrication_budget_options_per_world": 3,
        "sealed_shift_count": 6,
        "baseline_score": calibration["weak_baseline"]["combined_score"],
        "nominal_reference_development_score": nominal["combined_score"],
        "nominal_reference_heldout_score": nominal["heldout_policy_score"],
        "nominal_reference_development_robustness": nominal["robustness_score"],
        "nominal_reference_heldout_robustness": nominal[
            "heldout_robustness_score"
        ],
        "robust_reference_development_score": robust["combined_score"],
        "robust_reference_heldout_score": robust["heldout_policy_score"],
        "robust_reference_development_robustness": robust["robustness_score"],
        "robust_reference_heldout_robustness": robust[
            "heldout_robustness_score"
        ],
        "nominal_junction_counts_by_budget_option": calibration[
            "nominal_reference_junction_counts_by_budget_option"
        ],
        "robust_junction_counts_by_budget_option": calibration[
            "robust_reference_junction_counts_by_budget_option"
        ],
        "minimum_nominal_headroom": calibration["minimum_nominal_headroom"],
        "minimum_robust_headroom": calibration["minimum_robust_headroom"],
        "maximum_independent_runtime_efficiency_gap": calibration[
            "maximum_independent_runtime_efficiency_gap"
        ],
        "canonical_ideal_efficiencies": [
            row["independent_efficiency"]
            for row in calibration["independent_ideal_limits"]
        ],
        "spectrum_generated_sha256": calibration[
            "spectrum_generated_sha256"
        ],
        "spectrum_upstream_sha256": calibration[
            "spectrum_provenance"
        ]["upstream_sha256"],
        "search_visible_metric_keys": calibration[
            "metric_sealing"
        ]["visible_metric_keys"],
        "limitations": calibration["limitations"],
        "passed": calibration["execution_passed"],
    }
    execution_passed = bool(
        record["passed"]
        and record["baseline_score"] == 0.0
        and record["nominal_reference_development_score"] == 1.0
        and record["nominal_reference_heldout_score"] == 1.0
        and record["robust_reference_development_robustness"] == 1.0
        and record["robust_reference_heldout_robustness"] == 1.0
        and record["robust_reference_development_score"] > 0.85
        and record["minimum_nominal_headroom"] > 0.02
        and record["minimum_robust_headroom"] > 0.02
        and record["nominal_junction_counts_by_budget_option"]
        == [[1], [2, 3], [3, 4]]
        and record["robust_junction_counts_by_budget_option"]
        == [[1], [2], [3]]
    )
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_CANDIDATE_ADMISSION_AUDIT",
        "evidence_scope": (
            "INTERNAL_REDUCED_ORDER_PHOTOVOLTAIC_TASK_ADMISSION_NOT_DEVICE_"
            "VALIDATION_RECORD_EFFICIENCY_OR_AUTONOMOUS_DISCOVERY_EVIDENCE"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "records": [record],
        "summary": {
            "task_count": 1,
            "recommended_candidate_count": int(execution_passed),
            "recommended_quarantine_count": int(not execution_passed),
            "resolved_capability_gap_count": int(execution_passed),
        },
    }
    finalize_report_trust(report, execution_passed)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "execution_passed": report["execution_passed"],
        "trust_decision": report["trust_decision"],
        **report["summary"],
    }, indent=2))
    print("Report: %s" % args.output.resolve())
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
