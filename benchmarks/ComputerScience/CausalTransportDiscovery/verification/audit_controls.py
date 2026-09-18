"""Frozen local construction comparison; never represents frontier model draws."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics


def load(name):
    spec = importlib.util.spec_from_file_location("transport_audit_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit(start=0, count=24):
    episode, reference = load("episode"), load("reference")
    conditions = {}
    for name, policy in reference.POLICIES.items():
        rows, costs, calls = [], [], []
        for seed in range(start, start + count):
            environment = episode.create_environment(seed)
            used, experiments = [0], [0]

            def execute(tool, arguments):
                charge = environment.action_cost(tool, arguments)
                if used[0] + charge > environment.budget_units:
                    raise RuntimeError("construction control exceeded budget")
                used[0] += charge
                experiments[0] += 1
                return environment.experiment(tool, arguments)

            claim = policy(environment.public_problem(), execute)
            rows.append(environment.evaluate(claim, environment.confirm(claim)))
            costs.append(used[0])
            calls.append(experiments[0])
        result = {"world_count": count, "budget_min": min(costs), "budget_max": max(costs),
                  "max_experiment_calls": max(calls)}
        for key in ("curve_rmse", "population_prediction_rmse", "confirmation_observed_rmse",
                    "mean_population_bound_width", "mean_coefficient_interval_score"):
            values = [r[key] for r in rows if r[key] is not None]
            result[key] = {"mean": statistics.mean(values) if values else None, "measured_worlds": len(values)}
        for key in ("mechanism_recovery", "exact_generator_mask_recovery_diagnostic", "false_discovery_rate",
                    "modifier_omission_rate", "claimed_curve_coverage", "correct_refusal_rate",
                    "unsupported_point_claim_rate", "joint_success", "population_bound_coverage"):
            numerator = sum(row[key]["numerator"] for row in rows)
            denominator = sum(row[key]["denominator"] for row in rows)
            result[key] = episode.ratio(numerator, denominator)
        conditions[name] = result
    task = Path(__file__).resolve().parents[1]
    names = ("model.py", "Task.md", "TASK_CARD.yaml", "references/known_best.md", "verification/episode.py", "verification/reference.py", "verification/audit_controls.py")
    return {"status": "construction_only_not_difficulty_certification", "task_id": episode.TASK_ID,
            "frontier_model_draws": 0, "seed_start": start, "world_count": count,
            "paired_worlds": "seeds share nuisance variables within each adjacent pair; not independent model draws",
            "source_sha256": {name: hashlib.sha256((task / name).read_bytes()).hexdigest() for name in names},
            "conditions": conditions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--worlds", type=int, default=24)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worlds < 1 or args.seed_start < 0:
        parser.error("world count must be positive and seed start nonnegative")
    text = json.dumps(audit(args.seed_start, args.worlds), indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
