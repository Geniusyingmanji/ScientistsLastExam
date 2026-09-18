"""Recompute construction controls, not frontier model difficulty certification."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics


def _load(name):
    path = Path(__file__).resolve().with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("audit_diagnostic_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnose(seed_start=1200, world_count=90):
    episode, reference = _load("episode"), _load("reference")
    output = {
        "purpose": "construction_and_identifiability_diagnostic_not_difficulty_calibration",
        "task_id": episode.TASK_ID,
        "seed_start": seed_start,
        "world_count": world_count,
        "world_relation": "private seed triplets share nuisance parameters; not independent model draws",
        "conditions": {},
        "source_sha256": {
            name: hashlib.sha256(Path(__file__).resolve().with_name(name).read_bytes()).hexdigest()
            for name in ("episode.py", "reference.py", "diagnose.py")
        },
    }
    for name, policy in reference.POLICIES.items():
        rows, costs = [], []
        for seed in range(seed_start, seed_start + world_count):
            environment = episode.create_environment(seed)
            used = 0

            def experiment(tool, arguments):
                nonlocal used
                charge = environment.action_cost(tool, arguments)
                if used + charge > environment.budget_units:
                    raise RuntimeError("diagnostic policy exceeds public budget")
                used += charge
                return environment.experiment(tool, arguments)

            claim = policy(environment.public_problem(), experiment)
            rows.append(environment.evaluate(claim, environment.confirm(claim)))
            costs.append(used)
        result = {"world_count": world_count, "budget_min": min(costs), "budget_max": max(costs)}
        for key in ("mechanism_recovery", "effect_estimation_score", "population_absolute_error",
                    "stratum_effect_rmse", "population_interval_width", "population_interval_coverage",
                    "discovery_coverage", "confirmation_success"):
            observations = [row[key] for row in rows if row[key] is not None]
            result[key] = {"mean": statistics.mean(observations) if observations else None,
                           "measured_world_count": len(observations)}
        for prefix in ("false_discovery", "null_false_positive", "correct_refusal"):
            numerator = sum(row[prefix + "_numerator"] for row in rows)
            denominator = sum(row[prefix + "_denominator"] for row in rows)
            result[prefix] = {"numerator": numerator, "denominator": denominator,
                              "rate": numerator / denominator if denominator else None}
        output["conditions"][name] = result
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1200)
    parser.add_argument("--world-count", type=int, default=90)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seed_start < 0 or args.world_count < 1:
        parser.error("seed start must be nonnegative and world count positive")
    text = json.dumps(diagnose(args.seed_start, args.world_count), indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
