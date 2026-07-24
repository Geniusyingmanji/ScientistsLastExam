#!/usr/bin/env python3
"""Replay immutable trajectories under alternative observation kernels.

This is an OBS1 measurement audit, not a model-performance evaluator.  The
input event time is the time at which an immutable artifact/state record became
available to the trajectory ledger.  A periodic observer only learns about the
latest event at its next capture; material-event times are therefore retained
as intervals rather than silently replaced by capture or judge-completion time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.protocol import load_trajectory, validate_trajectory  # noqa: E402
from frontier_science.provenance import (  # noqa: E402
    finalize_report_trust,
    source_provenance,
)


DEFAULT_INTERVALS = (300.0, 900.0, 1800.0, 3600.0)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bound_trajectory(
    path: Path, report_paths: list[Path], require_trusted_inputs: bool,
) -> dict[str, Any]:
    """Bind a raw trajectory to the portable snapshot in a batch report."""
    matches = []
    trajectory_hash = _sha256(path)
    for report_path in report_paths:
        resolved_report = report_path.resolve()
        document = json.loads(resolved_report.read_text(encoding="utf-8"))
        provenance = document.get("source_provenance") or {}
        if require_trusted_inputs and not (
            document.get("execution_passed") is True
            and document.get("trusted_evidence") is True
            and document.get("passed") is True
            and provenance.get("source_tree_dirty") is False
            and provenance.get("source_changes") == []
        ):
            raise ValueError("input report is not trusted clean evidence: %s" % report_path)
        for run_index, run in enumerate(document.get("runs") or []):
            workdir = Path(str(run.get("workdir", ""))).resolve()
            snapshot = run.get("trajectory_snapshot") or {}
            if workdir / "trajectory.jsonl" != path:
                continue
            if snapshot.get("trajectory_sha256") != trajectory_hash:
                raise ValueError("raw trajectory differs from report snapshot hash")
            event_count = len(snapshot.get("events") or [])
            raw_count = len(load_trajectory(path))
            if event_count != raw_count:
                raise ValueError("raw trajectory event count differs from report snapshot")
            matches.append({
                "report": str(resolved_report.relative_to(ROOT)),
                "report_sha256": _sha256(resolved_report),
                "report_source_revision": provenance.get("git_revision"),
                "run_index": run_index,
                "task": run.get("task"),
                "algorithm": run.get("algorithm"),
                "feedback_mode": run.get("feedback_mode"),
                "seed": run.get("seed"),
                "snapshot_trajectory_sha256": snapshot.get("trajectory_sha256"),
            })
    if not matches:
        raise ValueError("trajectory is not bound by an input report: %s" % path)
    if len(matches) != 1:
        raise ValueError("trajectory is ambiguously bound by multiple input reports")
    return matches[0]


def _finite(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("%s must be finite numeric" % name)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("%s must be finite numeric" % name)
    return result


def _material_envelope(
    events: list[dict[str, Any]], epsilon: float,
) -> list[dict[str, Any]]:
    """Return valid best-so-far events that improve by more than epsilon."""
    if epsilon < 0:
        raise ValueError("material epsilon cannot be negative")
    material: list[dict[str, Any]] = []
    best = float("-inf")
    for event in events:
        if event.get("valid") is not True:
            continue
        score = _finite(event.get("best_score"), "best_score")
        if not material or score > best + epsilon:
            material.append(event)
            best = score
    return material


def _step_value(
    material: list[dict[str, Any]], time_seconds: float,
) -> tuple[float, int | None, bool]:
    selected: dict[str, Any] | None = None
    for event in material:
        if float(event["cumulative_wall_seconds"]) <= time_seconds + 1e-12:
            selected = event
        else:
            break
    if selected is None:
        return 0.0, None, False
    return float(selected["best_score"]), int(selected["step"]), True


def _current_state(
    events: list[dict[str, Any]], time_seconds: float,
) -> dict[str, Any] | None:
    selected = None
    for event in events:
        if float(event["cumulative_wall_seconds"]) <= time_seconds + 1e-12:
            selected = event
        else:
            break
    return selected


def _auc(points: list[dict[str, Any]], horizon: float) -> float:
    if horizon <= 0:
        raise ValueError("observation horizon must be positive")
    ordered = sorted(points, key=lambda row: float(row["observed_at_seconds"]))
    value = float(ordered[0]["best_score"])
    previous = 0.0
    area = 0.0
    for row in ordered:
        current = min(horizon, max(previous, float(row["observed_at_seconds"])))
        area += value * (current - previous)
        value = float(row["best_score"])
        previous = current
        if previous >= horizon:
            break
    area += value * (horizon - previous)
    return area / horizon


def _boolean_auc(
    points: list[dict[str, Any]], horizon: float, field: str,
) -> float:
    projected = [
        {
            "observed_at_seconds": row["observed_at_seconds"],
            "best_score": 1.0 if row[field] else 0.0,
        }
        for row in points
    ]
    return _auc(projected, horizon)


def _event_grid(events: list[dict[str, Any]], horizon: float) -> list[float]:
    times = {0.0, horizon}
    times.update(
        min(horizon, max(0.0, float(event["cumulative_wall_seconds"])))
        for event in events
    )
    return sorted(times)


def _fixed_grid(horizon: float, interval: float, phase: float) -> list[float]:
    if interval <= 0:
        raise ValueError("observation interval must be positive")
    if not 0 <= phase < interval:
        raise ValueError("phase must lie in [0, interval)")
    times = {0.0, horizon}
    current = phase if phase > 0 else interval
    while current < horizon - 1e-12:
        times.add(current)
        current += interval
    return sorted(times)


def replay_kernel(
    events: list[dict[str, Any]],
    *,
    interval_seconds: float | None,
    phase_seconds: float = 0.0,
    epsilon: float = 0.0,
    horizon_seconds: float | None = None,
) -> dict[str, Any]:
    """Replay one trajectory under an event or periodic observation kernel."""
    if not events:
        raise ValueError("empty trajectory")
    validate_trajectory(events)
    event_times = [
        _finite(event.get("cumulative_wall_seconds"), "cumulative_wall_seconds")
        for event in events
    ]
    if any(right < left for left, right in zip(event_times, event_times[1:])):
        raise ValueError("event times must be monotone")
    if abs(event_times[0]) > 1e-12:
        raise ValueError("trajectory must contain a valid analysis-origin sentinel at t=0")
    observed_horizon = event_times[-1]
    horizon = observed_horizon if horizon_seconds is None else _finite(
        horizon_seconds, "horizon_seconds"
    )
    if horizon < observed_horizon - 1e-12:
        raise ValueError("horizon cannot precede the final input event")

    material = _material_envelope(events, epsilon)
    if interval_seconds is None:
        kernel = "dense_event"
        phase = 0.0
        observation_times = _event_grid(events, horizon)
    else:
        interval = _finite(interval_seconds, "interval_seconds")
        phase = _finite(phase_seconds, "phase_seconds")
        kernel = "fixed" if phase == 0.0 else "random_phase"
        observation_times = _fixed_grid(horizon, interval, phase)

    observations = []
    observed_steps: set[int] = set()
    observed_current_steps: set[int] = set()
    for observed_at in observation_times:
        value, step, valid_envelope = _step_value(material, observed_at)
        current = _current_state(events, observed_at)
        if step is not None:
            observed_steps.add(step)
        if current is not None:
            observed_current_steps.add(int(current["step"]))
        observations.append({
            "observed_at_seconds": observed_at,
            "envelope_source_event_step": step,
            "valid_envelope": valid_envelope,
            "best_score": value,
            "current_event_step": (
                None if current is None else int(current["step"])
            ),
            "current_valid": (
                False if current is None else bool(current["valid"])
            ),
            "current_score": (
                None if current is None or not bool(current["valid"])
                else float(current["score"])
            ),
        })

    intervals = []
    for index, event in enumerate(material):
        event_time = float(event["cumulative_wall_seconds"])
        captures = [time for time in observation_times if time + 1e-12 >= event_time]
        first_capture = captures[0] if captures else None
        previous = max(
            (time for time in observation_times if time < event_time - 1e-12),
            default=0.0,
        )
        intervals.append({
            "event_step": int(event["step"]),
            "event_kind": (
                "baseline_valid"
                if index == 0 and event_time <= 1e-12
                else "first_valid"
                if index == 0
                else "material_improvement"
            ),
            "event_time_seconds": event_time,
            "left_open_seconds": previous,
            "right_closed_seconds": first_capture,
            "interval_width_seconds": (
                None if first_capture is None else first_capture - previous
            ),
            "detection_delay_seconds": (
                None if first_capture is None else first_capture - event_time
            ),
            "material_best_score": float(event["best_score"]),
            "observed_as_distinct_state": int(event["step"]) in observed_steps,
        })

    transition_intervals = [
        row for row in intervals if row["event_kind"] != "baseline_valid"
    ]
    delayed = [
        float(row["detection_delay_seconds"])
        for row in transition_intervals
        if row["detection_delay_seconds"] is not None
    ]
    missed = [
        row for row in transition_intervals
        if not row["observed_as_distinct_state"]
    ]
    transition_count = len(transition_intervals)
    first_valid = intervals[0] if intervals else None
    source_steps = {int(event["step"]) for event in events}
    missed_current_steps = source_steps - observed_current_steps
    return {
        "kernel": kernel,
        "interval_seconds": interval_seconds,
        "phase_seconds": phase,
        "horizon_seconds": horizon,
        "material_epsilon": epsilon,
        "observation_count": len(observations),
        "material_state_count_including_baseline": len(material),
        "first_valid_event": first_valid,
        "post_first_valid_improvement_count": max(0, len(material) - 1),
        "material_transition_count_excluding_valid_t0_baseline": transition_count,
        "observed_material_state_count": len(observed_steps),
        "source_event_state_count": len(source_steps),
        "observed_current_event_state_count": len(observed_current_steps),
        "missed_current_event_state_count": len(missed_current_steps),
        "missed_current_event_state_rate": (
            len(missed_current_steps) / len(source_steps) if source_steps else 0.0
        ),
        "missed_current_event_steps": sorted(missed_current_steps),
        "missed_material_transition_count": len(missed),
        "missed_material_transition_rate": (
            len(missed) / transition_count if transition_count else 0.0
        ),
        "mean_detection_delay_seconds": (
            sum(delayed) / len(delayed) if delayed else None
        ),
        "maximum_detection_delay_seconds": max(delayed, default=None),
        "wall_time_auc": _auc(observations, horizon),
        "wall_time_ever_valid_auc": _boolean_auc(
            observations, horizon, "valid_envelope"
        ),
        "wall_time_current_validity_auc": _boolean_auc(
            observations, horizon, "current_valid"
        ),
        "observations": observations,
        "material_event_intervals": intervals,
    }


def _seeded_phase(interval: float, phase_seed: int) -> float:
    digest = hashlib.sha256(
        ("%d:%0.17g" % (phase_seed, interval)).encode("ascii")
    ).digest()
    fraction = int.from_bytes(digest[:8], "big") / float(1 << 64)
    # Keep the phase strictly inside the interval so it remains a distinct arm.
    fraction = min(1.0 - 2.0**-53, max(2.0**-53, fraction))
    return interval * fraction


def _kernel_specs(
    intervals: Iterable[float], phase_seed: int,
) -> list[tuple[float | None, float]]:
    specs: list[tuple[float | None, float]] = [(None, 0.0)]
    for interval in intervals:
        value = _finite(interval, "interval")
        if value <= 0:
            raise ValueError("intervals must be positive")
        specs.extend(((value, 0.0), (value, _seeded_phase(value, phase_seed))))
    return specs


def _kernel_key(kernel: dict[str, Any]) -> str:
    if kernel["kernel"] == "dense_event":
        return "dense_event"
    return "%s:%g:%g" % (
        kernel["kernel"],
        float(kernel["interval_seconds"]),
        float(kernel["phase_seconds"]),
    )


def _rank_rows(values: list[tuple[str, float]]) -> list[dict[str, Any]]:
    ordered = sorted(values, key=lambda item: (-item[1], item[0]))
    rows = []
    previous_value: float | None = None
    previous_rank = 0
    for position, (label, value) in enumerate(ordered, 1):
        rank = (
            previous_rank
            if previous_value is not None and math.isclose(
                value, previous_value, rel_tol=1e-12, abs_tol=1e-12
            )
            else position
        )
        rows.append({"trajectory": label, "wall_time_auc": value, "rank": rank})
        previous_value = value
        previous_rank = rank
    return rows


def _sign(value: float) -> int:
    if math.isclose(value, 0.0, rel_tol=1e-12, abs_tol=1e-12):
        return 0
    return 1 if value > 0 else -1


def _ranking_analysis(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    by_kernel: dict[str, list[tuple[str, float]]] = {}
    for trajectory in trajectories:
        for kernel in trajectory["kernels"]:
            by_kernel.setdefault(_kernel_key(kernel), []).append((
                trajectory["trajectory"], float(kernel["wall_time_auc"])
            ))
    expected = len(trajectories)
    if any(len(rows) != expected for rows in by_kernel.values()):
        raise ValueError("rank comparison lacks a complete common kernel grid")
    dense_values = dict(by_kernel["dense_event"])
    labels = sorted(dense_values)
    comparisons = []
    for key in sorted(by_kernel):
        values = dict(by_kernel[key])
        reversals = 0
        tie_changes = 0
        pair_count = 0
        for left_index, left in enumerate(labels):
            for right in labels[left_index + 1:]:
                pair_count += 1
                dense_sign = _sign(dense_values[left] - dense_values[right])
                observed_sign = _sign(values[left] - values[right])
                if dense_sign and observed_sign and dense_sign != observed_sign:
                    reversals += 1
                elif (dense_sign == 0) != (observed_sign == 0):
                    tie_changes += 1
        comparisons.append({
            "kernel_key": key,
            "ranks": _rank_rows(list(values.items())),
            "strict_pair_count": pair_count,
            "pairwise_rank_reversal_count_vs_dense": reversals,
            "pairwise_tie_change_count_vs_dense": tie_changes,
        })
    return {
        "enabled": True,
        "caller_attestation": (
            "input trajectories share one scientifically comparable score construct"
        ),
        "comparison_count": len(trajectories),
        "kernels": comparisons,
    }


def analyze(
    paths: list[Path],
    *,
    intervals: Iterable[float] = DEFAULT_INTERVALS,
    epsilon: float = 0.0,
    horizon_seconds: float | None = None,
    compare_ranks: bool = False,
    report_paths: list[Path] | None = None,
    require_trusted_inputs: bool = False,
    phase_seed: int = 20260724,
) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one trajectory is required")
    if compare_ranks and len(paths) < 2:
        raise ValueError("rank comparison requires at least two trajectories")
    if compare_ranks and horizon_seconds is None:
        raise ValueError("rank comparison requires one explicit common horizon")
    if require_trusted_inputs and not report_paths:
        raise ValueError("trusted-input mode requires at least one binding report")
    resolved_reports = [path.resolve() for path in (report_paths or [])]
    for report_path in resolved_reports:
        try:
            report_path.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError("input report must be inside repository") from exc
    interval_values = tuple(float(value) for value in intervals)
    specs = _kernel_specs(interval_values, phase_seed)
    trajectories = []
    for path in paths:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError("trajectory must be inside repository") from exc
        binding = (
            _load_bound_trajectory(resolved, resolved_reports, require_trusted_inputs)
            if resolved_reports else None
        )
        raw_events = load_trajectory(resolved)
        source_origin = float(raw_events[0]["cumulative_wall_seconds"])
        events = []
        for raw in raw_events:
            event = dict(raw)
            event["cumulative_wall_seconds"] = (
                float(raw["cumulative_wall_seconds"]) - source_origin
            )
            events.append(event)
        kernels = [
            replay_kernel(
                events,
                interval_seconds=interval,
                phase_seconds=phase,
                epsilon=epsilon,
                horizon_seconds=horizon_seconds,
            )
            for interval, phase in specs
        ]
        dense = kernels[0]
        for kernel in kernels:
            kernel["auc_delta_from_dense"] = (
                float(kernel["wall_time_auc"]) - float(dense["wall_time_auc"])
            )
        trajectories.append({
            "trajectory": str(relative),
            "trajectory_sha256": _sha256(resolved),
            "input_report_binding": binding,
            "event_count": len(events),
            "analysis_origin_source_seconds": source_origin,
            "source_horizon_seconds": float(raw_events[-1]["cumulative_wall_seconds"]),
            "analysis_last_event_seconds": float(events[-1]["cumulative_wall_seconds"]),
            "analysis_horizon_seconds": float(kernels[0]["horizon_seconds"]),
            "portable_source_events": [
                {
                    "step": int(event["step"]),
                    "source_time_seconds": float(
                        raw_events[index]["cumulative_wall_seconds"]
                    ),
                    "analysis_time_seconds": float(
                        event["cumulative_wall_seconds"]
                    ),
                    "valid": bool(event["valid"]),
                    "accepted": bool(event["accepted"]),
                    "score": float(event["score"]),
                    "best_score": float(event["best_score"]),
                    "candidate_sha256": event["candidate_sha256"],
                }
                for index, event in enumerate(events)
            ],
            "kernels": kernels,
        })

    if compare_ranks:
        rank_analysis: dict[str, Any] | None = _ranking_analysis(trajectories)
    else:
        rank_analysis = None

    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "OBSERVATION_KERNEL_DERIVED_ANALYSIS",
        "evidence_scope": (
            "OFFLINE_MEASUREMENT_SENSITIVITY_NOT_MODEL_PERFORMANCE_OR_"
            "EDGE_BENCH_REANALYSIS"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "design": {
            "plan_id": "OBS1",
            "material_epsilon": epsilon,
            "fixed_intervals_seconds": list(interval_values),
            "phases_per_interval": ["zero", "seeded_uniform_random"],
            "phase_seed": phase_seed,
            "realized_phase_schedule": [
                {
                    "interval_seconds": interval,
                    "phase_seconds": phase,
                }
                for interval, phase in specs if interval is not None
            ],
            "event_time_semantics": "seconds_since_first_recorded_baseline_event",
            "periodic_event_time_semantics": "interval_censored",
            "pre_first_valid_score_fill_for_auc": 0.0,
            "live_state_in_scope": False,
            "rank_comparison_enabled": compare_ranks,
            "rank_comparison_requires_common_score_construct": True,
            "trusted_input_binding_required": require_trusted_inputs,
            "report_bindings": [
                str(path.relative_to(ROOT)) for path in resolved_reports
            ],
        },
        "trajectories": trajectories,
        "rank_analysis": rank_analysis,
        "limitations": [
            "Input event timestamps mark completed ledger events, not latent edit start times.",
            "The first recorded valid baseline event is normalized to analysis time zero; pre-baseline setup time is excluded and retained as analysis_origin_source_seconds.",
            "The audit replays observation only and does not model observer effects or feedback release.",
            "Current trajectory schema is artifact-oriented; path-dependent live-state tasks require timestamped state transitions.",
            "No EdgeBench raw trajectory is public, so this analysis cannot estimate an EdgeBench observation-kernel effect.",
        ],
    }
    complete = bool(
        trajectories
        and all(row["event_count"] > 0 for row in trajectories)
        and all(len(row["kernels"]) == len(specs) for row in trajectories)
        and all(
            len({float(kernel["horizon_seconds"]) for kernel in row["kernels"]}) == 1
            for row in trajectories
        )
        and (
            not require_trusted_inputs
            or all(row["input_report_binding"] is not None for row in trajectories)
        )
    )
    finalize_report_trust(report, complete)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trajectories", nargs="+", type=Path)
    parser.add_argument("--intervals", nargs="+", type=float, default=list(DEFAULT_INTERVALS))
    parser.add_argument("--epsilon", type=float, default=0.0)
    parser.add_argument("--horizon-seconds", type=float)
    parser.add_argument("--phase-seed", type=int, default=20260724)
    parser.add_argument(
        "--compare-ranks", action="store_true",
        help="Attest that inputs share a comparable score and compare AUC ranks",
    )
    parser.add_argument(
        "--reports", nargs="*", type=Path, default=[],
        help="Batch reports whose portable snapshots bind the raw trajectories",
    )
    parser.add_argument(
        "--require-trusted-inputs", action="store_true",
        help="Fail unless every trajectory is bound by one trusted clean report",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(
        args.trajectories,
        intervals=args.intervals,
        epsilon=args.epsilon,
        horizon_seconds=args.horizon_seconds,
        compare_ranks=args.compare_ranks,
        report_paths=args.reports,
        require_trusted_inputs=args.require_trusted_inputs,
        phase_seed=args.phase_seed,
    )
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
