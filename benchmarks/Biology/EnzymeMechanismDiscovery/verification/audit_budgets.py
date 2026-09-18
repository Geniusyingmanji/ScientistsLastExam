"""Bounded matched-cost budget study; never a frontier-model difficulty claim."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.Biology.EnzymeMechanismDiscovery.verification.episode import create_environment
from benchmarks.Biology.EnzymeMechanismDiscovery.verification.reference import discover


def audit(count=24):
    rows = []
    for budget in (60, 80, 104):
        for adaptive in (False, True):
            records = []
            for seed in range(count):
                environment = create_environment(seed)
                environment.budget_units = budget
                claim = discover(environment.public_problem(), environment.experiment,
                                 adaptive=adaptive, comparison_budget=budget)
                records.append(environment.evaluate(claim, environment.confirm(claim)))
            rows.append({"comparison_cap": budget, "policy": "adaptive" if adaptive else "fixed",
                         "worlds": count, "charged_cost": sum(r["experiment_budget_used"] for r in records) / count,
                         "mechanism_successes": sum(r["mechanism_recovery"]["numerator"] for r in records),
                         "confirmation_passes": sum(r["confirmation_pass_rate"]["numerator"] for r in records),
                         "confirmation_denominator": sum(r["confirmation_pass_rate"]["denominator"] for r in records),
                         "mean_score": sum(r["combined_score"] for r in records) / count,
                         "mean_rmse_mM": sum(r["confirmation_rmse_mM"] for r in records) / count})
    directory = Path(__file__).resolve().parents[1]
    return {"status": "construction_budget_study_not_frontier_calibration", "world_seed_range": [0, count - 1],
            "source_sha256": {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (directory / "model.py", directory / "verification/episode.py",
                                        directory / "verification/reference.py", Path(__file__).resolve())},
            "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.worlds < 1:
        parser.error("--worlds must be positive")
    args.output.write_text(json.dumps(audit(args.worlds), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
