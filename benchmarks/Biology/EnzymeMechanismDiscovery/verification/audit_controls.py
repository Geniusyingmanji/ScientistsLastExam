"""Reproducible construction controls, not frontier-model calibration.

Run from repository root with ``python -m
benchmarks.Biology.EnzymeMechanismDiscovery.verification.audit_controls``.
Only aggregate metrics are written; individual world answers are not exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.Biology.EnzymeMechanismDiscovery.verification.episode import create_environment
from benchmarks.Biology.EnzymeMechanismDiscovery.verification.reference import (
    abstain_control, fixed_design_control, initial_rate_control, no_query_control, solve,
)


def audit(count=24):
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("world count must be positive")
    rows = []
    for name, method in (("adaptive_witness", solve), ("fixed_dynamic_design", fixed_design_control),
                         ("static_rate_control", initial_rate_control), ("no_query", no_query_control),
                         ("always_abstain", abstain_control)):
        metrics = []
        for seed in range(count):
            environment = create_environment(seed)
            claim = method(environment.public_problem(), environment.experiment)
            metrics.append(environment.evaluate(claim, environment.confirm(claim)))
        row = {"method": name, "worlds": count,
               "mean_combined_score": sum(m["combined_score"] for m in metrics) / count,
               "mean_budget_used": sum(m["experiment_budget_used"] for m in metrics) / count}
        for key in ("mechanism_recovery", "false_discovery_rate", "correct_refusal_rate",
                    "discovery_coverage", "confirmation_pass_rate"):
            numerator = sum(m[key]["numerator"] for m in metrics)
            denominator = sum(m[key]["denominator"] for m in metrics)
            row[key] = {"numerator": numerator, "denominator": denominator,
                        "value": numerator / denominator if denominator else None}
        errors = [m["confirmation_rmse_mM"] for m in metrics if m["confirmation_rmse_mM"] is not None]
        row["mean_confirmation_rmse_mM"] = sum(errors) / len(errors) if errors else None
        rows.append(row)
    directory = Path(__file__).resolve().parents[1]
    files = [directory / "model.py", directory / "verification/episode.py",
             directory / "verification/reference.py", Path(__file__).resolve()]
    return {"schema_version": 1, "status": "construction_controls_not_difficulty_calibration",
            "task_id": create_environment(0).task_id, "world_seed_range": [0, count - 1],
            "frontier_model_draws": 0,
            "source_sha256": {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in files}, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=24)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = json.dumps(audit(args.worlds), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(document, encoding="utf-8")
    else:
        print(document, end="")


if __name__ == "__main__":
    main()
