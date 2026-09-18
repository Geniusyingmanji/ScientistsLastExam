"""Paired construction controls for one scientific episode task.

Only explicitly registered operator baselines execute here. This is not a model
calibration runner and cannot confer frontier eligibility. Raw cells stay private.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import os
from pathlib import Path
import statistics

from .scientific_episode import (
    EpisodeSession, _load_module, _task_directory, create_environment, digest,
    prepare_output, run_policy, save_report, source_binding, validate_episode_report,
)


def _finite(value):
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


def _axes(metrics):
    """Preserve denominators, never average per-world FDRs or missing values."""
    scalars, ratios, used = {}, {}, set()
    for key, value in metrics.items():
        if isinstance(value, dict) and {"numerator", "denominator"} <= set(value):
            numerator, denominator = value["numerator"], value["denominator"]
            if not (_finite(numerator) and _finite(denominator) and 0 <= numerator <= denominator):
                raise ValueError("invalid metric ratio: " + key)
            if key in ratios and ratios[key] != (numerator, denominator):
                raise ValueError("conflicting metric ratio: " + key)
            ratios[key] = (numerator, denominator)
            used.add(key)
        elif key.endswith("_numerator"):
            axis = key[:-10]
            denominator_key = axis + "_denominator"
            if denominator_key in metrics:
                numerator, denominator = value, metrics[denominator_key]
                if not (_finite(numerator) and _finite(denominator) and 0 <= numerator <= denominator):
                    raise ValueError("invalid metric ratio: " + axis)
                if axis in ratios and ratios[axis] != (numerator, denominator):
                    raise ValueError("conflicting metric ratio: " + axis)
                ratios[axis] = (numerator, denominator)
                used.update((key, denominator_key, axis, axis + "_rate"))
    for key, value in metrics.items():
        if key not in used and _finite(value):
            scalars[key] = float(value)
    return scalars, ratios


def _distribution(values):
    return {"n": len(values), "mean": statistics.fmean(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def _scientific(row):
    return (row["status"] == "completed" and isinstance(row.get("metrics"), dict)
            and row["metrics"].get("valid") is not False)


def _write_private(path, document):
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, allow_nan=False)
        handle.write("\n")


def summarize_cells(cells, policies, primary_metric=None):
    summaries = {}
    for policy in policies:
        rows = [row for row in cells if row["policy"] == policy]
        completed = [row for row in rows if row["status"] == "completed"]
        scientific = [row for row in completed if _scientific(row)]
        scalar_values, ratio_values = {}, {}
        for row in scientific:
            scalars, ratios = _axes(row["metrics"])
            for key, value in scalars.items():
                scalar_values.setdefault(key, []).append(value)
            for key, value in ratios.items():
                ratio_values.setdefault(key, []).append(value)
        pooled = {}
        for key, values in sorted(ratio_values.items()):
            numerator = sum(value[0] for value in values)
            denominator = sum(value[1] for value in values)
            pooled[key] = {"numerator": numerator, "denominator": denominator,
                           "value": numerator / denominator if denominator else None,
                           "worlds_reporting": len(values),
                           "status": "measured" if denominator else "zero_denominator"}
        summaries[policy] = {
            "attempted_worlds": len(rows), "completed_worlds": len(completed),
            "scientifically_valid_worlds": len(scientific),
            "status_counts": dict(Counter(row["status"] for row in rows)),
            "experiment_units": _distribution([row["resources"]["experiment_units"] for row in rows]),
            "completed_experiment_units": _distribution([row["resources"]["experiment_units"] for row in completed]),
            "scalar_metrics": {key: _distribution(values) for key, values in sorted(scalar_values.items())},
            "pooled_ratios": pooled,
        }
    paired = []
    if primary_metric:
        by_policy = {policy: {row["world_index"]: row for row in cells
                              if row["policy"] == policy} for policy in policies}
        for other in policies[1:]:
            deltas, equal_spend = [], 0
            for world, left in by_policy[policies[0]].items():
                right = by_policy[other].get(world)
                if not right or not _scientific(left) or not _scientific(right):
                    continue
                lvalue = _axes(left["metrics"])[0].get(primary_metric)
                rvalue = _axes(right["metrics"])[0].get(primary_metric)
                if lvalue is None or rvalue is None:
                    continue
                deltas.append(lvalue - rvalue)
                equal_spend += left["resources"]["experiment_units"] == right["resources"]["experiment_units"]
            paired.append({"left": policies[0], "right": other, "metric": primary_metric,
                           "difference_left_minus_right": _distribution(deltas),
                           "equal_actual_spend_pairs": equal_spend,
                           "interpretation": "descriptive paired difference; no independence or significance claim"})
    return {"policies": summaries, "paired_comparisons": paired,
            "aggregation_scope": "one task version; completed valid cells only; failures are not scientific zeros",
            "cost_semantics": "equal budget caps do not imply equal actual expenditure",
            "world_semantics": "paired seeds may share a generator family; these are not independent model draws"}


def run_panel(task, policy_names, output_dir, *, world_count=24, seed_start=0,
              budget_units=None, max_steps=64, wall_seconds=300.0, primary_metric=None):
    if isinstance(world_count, bool) or not isinstance(world_count, int) or not 1 <= world_count <= 512:
        raise ValueError("world_count must be an integer from 1 through 512")
    if isinstance(seed_start, bool) or not isinstance(seed_start, int) or seed_start < 0:
        raise ValueError("seed_start must be a nonnegative integer")
    if budget_units is not None and (isinstance(budget_units, bool) or not isinstance(budget_units, int) or budget_units < 1):
        raise ValueError("budget_units must be a positive integer")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("max_steps must be a positive integer")
    if not _finite(wall_seconds) or wall_seconds <= 0:
        raise ValueError("wall_seconds must be positive and finite")
    if not policy_names or len(set(policy_names)) != len(policy_names):
        raise ValueError("choose distinct operator policies")
    task_id, task_dir = _task_directory(task)
    reference_path = task_dir / "verification" / "reference.py"
    available = getattr(_load_module(reference_path), "POLICIES", {})
    if any(name not in available for name in policy_names):
        raise ValueError("unknown policy; available: " + ", ".join(sorted(available)))
    binding = source_binding(task)
    directory = prepare_output(output_dir)
    if any(directory.iterdir()):
        raise ValueError("episode panel output must be empty")
    cells = []
    for world in range(world_count):
        seed = seed_start + world
        for policy_index, policy in enumerate(policy_names):
            cell_binding = {**binding, "private_world_seed": seed, "mode": "operator_baseline",
                            "baseline": policy, "episode_protocol": "sle-scientific-episode-v1"}
            relative = "world_%04d_policy_%02d" % (world, policy_index)
            try:
                environment = create_environment(task, seed)
                if budget_units is not None:
                    environment.budget_units = budget_units
                session = EpisodeSession(environment, max_steps=max_steps, wall_seconds=wall_seconds,
                                         binding=cell_binding)
                # Reload operator policy globals at each independent world boundary.
                reference = _load_module(reference_path)
            except Exception as exc:
                # Initialization ran no policy experiments. Retain an explicit cell
                # failure, separate from a valid episode, and continue other worlds.
                failure = {"kind": "episode_initialization_failure", "binding": cell_binding,
                           "status": "infrastructure_error", "error_type": type(exc).__name__,
                           "detail": str(exc)[:2000]}
                failure["sha256"] = digest(failure)
                failure_path = directory / (relative + "_failure.json")
                _write_private(failure_path, failure)
                cells.append({"world_index": world, "policy": policy, "status": "infrastructure_error",
                              "resources": {"experiment_units": 0}, "metrics": None,
                              "failure_sha256": failure["sha256"], "failure_path": failure_path.name})
                continue
            report = run_policy(session, reference.POLICIES[policy])
            validate_episode_report(report)
            report_path = save_report(directory / relative, report)
            cells.append({"world_index": world, "policy": policy, "status": report["status"],
                          "resources": report["resources"], "metrics": report["metrics"],
                          "episode_sha256": report["sha256"],
                          "episode_path": report_path.relative_to(directory).as_posix()})
    if source_binding(task) != binding:
        raise ValueError("episode source/runtime changed during panel; cells cannot form a frozen comparison")
    document = {"schema_version": 1, "kind": "episode_construction_panel", "task_id": task_id,
                "binding": binding, "world_count": world_count, "private_seed_start": seed_start,
                "budget_units_override": budget_units, "policies": list(policy_names),
                "frontier_eligible": False, "frontier_model_draws": 0,
                "summary": summarize_cells(cells, policy_names, primary_metric), "cells": cells}
    document["sha256"] = digest(document)
    path = directory / "panel.json"
    _write_private(path, document)
    return document, path


def command(args):
    document, path = run_panel(args.task, args.policies, args.output_dir,
                               world_count=args.worlds, seed_start=args.seed_start,
                               budget_units=args.budget_units, max_steps=args.max_steps,
                               wall_seconds=args.wall_seconds, primary_metric=args.metric)
    print(json.dumps({"task": document["task_id"], "worlds": document["world_count"],
                      "frontier_eligible": False, "private_panel": str(path),
                      "summary": document["summary"]}, indent=2, allow_nan=False))
    return 0 if all(_scientific(row) for row in document["cells"]) else 2


def add_parser(sub):
    parser = sub.add_parser("episode-panel", help="paired scientific construction controls; no model API calls")
    parser.set_defaults(fn=command)
    parser.add_argument("--task", required=True)
    parser.add_argument("--policies", nargs="+", required=True)
    parser.add_argument("--worlds", type=int, default=24)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--budget-units", type=int)
    parser.add_argument("--max-steps", type=int, default=64)
    parser.add_argument("--wall-seconds", type=float, default=300.0)
    parser.add_argument("--metric", help="optional scalar axis for paired differences; no cross-task averaging")
    parser.add_argument("--output-dir", required=True)
