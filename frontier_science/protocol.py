"""Canonical trajectory records and budget-aware benchmark metrics."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 2


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class TrajectoryEvent:
    step: int
    oracle_calls: int
    score: float
    best_score: float
    valid: bool
    accepted: bool
    wall_seconds: float
    cumulative_wall_seconds: float
    candidate_sha256: str
    parent_sha256: str | None
    budget_units: int | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    algorithm_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, **asdict(self)}


def append_event(path: Path, event: TrajectoryEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.to_dict(), allow_nan=False, separators=(",", ":")) + "\n")


def load_trajectory(path: Path) -> list[dict[str, Any]]:
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported trajectory schema at line %d" % line_number)
        events.append(event)
    validate_trajectory(events)
    return events


def validate_trajectory(events: list[dict[str, Any]]) -> None:
    previous_calls = 0
    previous_best = float("-inf")
    for index, event in enumerate(events):
        if event.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported trajectory schema")
        if int(event.get("step", -1)) != index:
            raise ValueError("trajectory steps must be contiguous from zero")
        budget_units = int(event.get("budget_units") or event.get("oracle_calls", 0))
        if budget_units != index + 1:
            raise ValueError("trajectory budget_units must equal step + 1")
        oracle_calls = int(event.get("oracle_calls", 0))
        if oracle_calls < 1 or oracle_calls < previous_calls or oracle_calls > budget_units:
            raise ValueError("trajectory oracle_calls violate monotone budget accounting")
        for key in ("score", "best_score", "wall_seconds", "cumulative_wall_seconds"):
            value = event.get(key)
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(float(value))):
                raise ValueError("trajectory %s must be finite numeric" % key)
        best = float(event["best_score"])
        if best < previous_best:
            raise ValueError("trajectory best_score must be monotone")
        if float(event["wall_seconds"]) < 0 or float(event["cumulative_wall_seconds"]) < 0:
            raise ValueError("trajectory time cannot be negative")
        if index and float(event["cumulative_wall_seconds"]) < float(
            events[index - 1]["cumulative_wall_seconds"]
        ):
            raise ValueError("trajectory cumulative time must be monotone")
        for key in ("valid", "accepted"):
            if not isinstance(event.get(key), bool):
                raise ValueError("trajectory %s must be boolean" % key)
        for key in ("candidate_sha256", "parent_sha256"):
            value = event.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError("trajectory %s must be a string or null" % key)
        for key in ("metrics", "llm", "algorithm_metadata"):
            if key in event and not isinstance(event.get(key), dict):
                raise ValueError("trajectory %s must be an object" % key)
        error = event.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError("trajectory error must be a string or null")
        previous_calls = oracle_calls
        previous_best = best


def best_so_far_auc(events: Iterable[dict[str, Any]], budget: int | None = None) -> float:
    """Best-feasible score AUC over charged benchmark-budget slots.

    The result is divided by the requested horizon and therefore remains in score units.
    """
    def position(event: dict[str, Any]) -> int:
        return int(event.get("budget_units") or event["oracle_calls"])

    points = list(events)
    if not points:
        return float("nan")
    validate_trajectory(points)
    horizon = int(budget if budget is not None else position(points[-1]))
    if horizon <= 0:
        raise ValueError("AUC budget must be positive")
    current_x = 0
    current_best = 0.0
    area = 0.0
    for event in points:
        call = max(1, position(event))
        # A result at budget unit k owns slot [k-1,k]. ``oracle_calls`` is kept
        # separately because unparsable proposals consume budget but no oracle call.
        x_before = min(horizon, max(current_x, call - 1))
        area += current_best * (x_before - current_x)
        current_x = x_before
        if bool(event.get("valid")):
            current_best = max(current_best, float(event["best_score"]))
        x_after = min(horizon, max(current_x, call))
        area += current_best * (x_after - current_x)
        current_x = x_after
        if current_x >= horizon:
            break
    area += current_best * (horizon - current_x)
    return area / horizon


def summarize_trajectory(events: list[dict[str, Any]], budget: int | None = None) -> dict[str, Any]:
    if not events:
        raise ValueError("empty trajectory")
    validate_trajectory(events)
    final = events[-1]
    scores = [float(e["best_score"]) for e in events if bool(e.get("valid"))]
    proposal_events = [event for event in events if int(event.get("step", 0)) > 0]

    def usage_sum(key: str, zero: int | float) -> int | float | None:
        if not proposal_events:
            return zero
        values = [(event.get("llm") or {}).get(key) for event in proposal_events]
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in values):
            return None
        if any(not math.isfinite(float(value)) for value in values):
            return None
        return sum(values)

    llm_totals = {
        "calls": len(proposal_events),
        "provider_usage_records": sum(
            isinstance((event.get("llm") or {}).get("total_tokens"), (int, float))
            for event in proposal_events
        ),
        "input_tokens": usage_sum("input_tokens", 0),
        "output_tokens": usage_sum("output_tokens", 0),
        "total_tokens": usage_sum("total_tokens", 0),
        "estimated_cost_usd": usage_sum("estimated_cost_usd", 0.0),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "oracle_calls": int(final["oracle_calls"]),
        "budget_units": int(final.get("budget_units") or final["oracle_calls"]),
        "best_score": max(scores) if scores else -1e18,
        "best_so_far_auc": best_so_far_auc(events, budget=budget),
        "valid_rate": sum(bool(e.get("valid")) for e in events) / len(events),
        "accepted": sum(bool(e.get("accepted")) for e in events[1:]),
        "wall_seconds": float(final["cumulative_wall_seconds"]),
        "llm": llm_totals,
    }


def mean_confidence_interval(values: Iterable[float | None]) -> dict[str, float | int | None]:
    clean = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            clean.append(number)
    if not clean:
        return {"n": 0, "mean": None, "ci95_low": None, "ci95_high": None}
    mean = sum(clean) / len(clean)
    if len(clean) == 1:
        return {"n": 1, "mean": mean, "ci95_low": mean, "ci95_high": mean}
    variance = sum((x - mean) ** 2 for x in clean) / (len(clean) - 1)
    # Student-t critical values give valid small-sample intervals; normal 1.96 is
    # only the asymptotic limit and is too optimistic for the default five seeds.
    t95 = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    }.get(len(clean) - 1, 1.96)
    half = t95 * math.sqrt(variance / len(clean))
    return {"n": len(clean), "mean": mean, "ci95_low": mean - half, "ci95_high": mean + half}
