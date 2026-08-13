"""Content-addressed boundary sentinels for long-horizon runs.

The scientific trajectory records evaluated candidates.  This module records a
second, append-only boundary ledger for artifacts that existed at preregistered
times or decisions, including artifacts whose evaluation completed only later.
Artifact and raw-evaluation payloads are immutable and hash-addressed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SENTINEL_SCHEMA_VERSION = 1
SENTINEL_TYPES = {
    "t0",
    "first_valid",
    "submission",
    "commit",
    "abstain",
    "fixed_grid",
    "terminal",
}
EVALUATION_STATUSES = {
    "completed",
    "completed_after_schedule",
    "reused_deterministic",
    "not_evaluated",
    "not_applicable",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(path.parent), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _durable_append(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(path.parent), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _finite_nonnegative(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise ValueError("%s must be finite and non-negative" % label)
    return float(value)


class SentinelLedger:
    """Append immutable artifact-bound boundary records for one run."""

    def __init__(self, workdir: Path, *, resume: bool = False) -> None:
        self.workdir = Path(workdir).resolve()
        self.root = self.workdir / "sentinels"
        self.path = self.root / "sentinel_events.jsonl"
        self.artifact_root = self.root / "artifacts"
        self.evaluation_root = self.root / "evaluations"
        self.response_root = self.root / "responses"
        if resume:
            if not self.path.is_file():
                raise FileNotFoundError(
                    "boundary-sentinel resume requires sentinel_events.jsonl"
                )
            self.events = load_sentinel_events(self.path, workdir=self.workdir)
        else:
            if self.path.exists() or self.root.exists() and any(self.root.iterdir()):
                raise FileExistsError(
                    "sentinel ledger already exists; use resume or a new workdir"
                )
            self.root.mkdir(parents=True, exist_ok=True)
            self.events: list[dict[str, Any]] = []

    def _store_artifact(self, source: Optional[str]) -> dict[str, Any]:
        if source is None:
            return {
                "artifact_sha256": None,
                "artifact_utf8_bytes": None,
                "artifact_path": None,
            }
        payload = source.encode("utf-8")
        digest = _sha256(payload)
        relative = Path("sentinels") / "artifacts" / digest / "candidate.py"
        target = self.workdir / relative
        if target.is_file():
            if target.read_bytes() != payload:
                raise ValueError("content-addressed artifact payload differs")
        else:
            _atomic_write_bytes(target, payload)
        return {
            "artifact_sha256": digest,
            "artifact_utf8_bytes": len(payload),
            "artifact_path": relative.as_posix(),
        }

    def _store_evaluation(
        self, evaluation: Optional[dict[str, Any]], status: str,
    ) -> dict[str, Any]:
        if status not in EVALUATION_STATUSES:
            raise ValueError("unknown sentinel evaluation status %r" % status)
        if evaluation is None:
            if status not in {"not_evaluated", "not_applicable"}:
                raise ValueError("completed/reused sentinel lacks evaluation payload")
            return {
                "status": status,
                "sha256": None,
                "path": None,
            }
        if status in {"not_evaluated", "not_applicable"}:
            raise ValueError("unevaluated sentinel unexpectedly has evaluation payload")
        payload = _canonical_json(evaluation)
        digest = _sha256(payload)
        relative = Path("sentinels") / "evaluations" / (digest + ".json")
        target = self.workdir / relative
        if target.is_file():
            if target.read_bytes() != payload:
                raise ValueError("content-addressed evaluation payload differs")
        else:
            _atomic_write_bytes(target, payload)
        return {
            "status": status,
            "sha256": digest,
            "path": relative.as_posix(),
        }

    def _store_response(self, response: Optional[str]) -> dict[str, Any]:
        if response is None:
            return {"sha256": None, "utf8_bytes": None, "path": None}
        payload = response.encode("utf-8")
        digest = _sha256(payload)
        relative = Path("sentinels") / "responses" / (digest + ".txt")
        target = self.workdir / relative
        if target.is_file():
            if target.read_bytes() != payload:
                raise ValueError("content-addressed provider response differs")
        else:
            _atomic_write_bytes(target, payload)
        return {
            "sha256": digest,
            "utf8_bytes": len(payload),
            "path": relative.as_posix(),
        }

    def capture(
        self,
        sentinel_type: str,
        *,
        source: Optional[str],
        source_step: Optional[int],
        artifact_published_elapsed_seconds: float,
        recorded_elapsed_seconds: float,
        selection_policy: str,
        evaluation: Optional[dict[str, Any]] = None,
        evaluation_status: str = "not_evaluated",
        evaluation_completed_elapsed_seconds: Optional[float] = None,
        scheduled_elapsed_seconds: Optional[float] = None,
        feedback_visible: bool = False,
        capture_method: str = "atomic_state_transition",
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        provider_response: Optional[str] = None,
    ) -> dict[str, Any]:
        if sentinel_type not in SENTINEL_TYPES:
            raise ValueError("unknown sentinel type %r" % sentinel_type)
        if source_step is not None and (
            isinstance(source_step, bool) or not isinstance(source_step, int)
            or source_step < 0
        ):
            raise ValueError("sentinel source_step must be a non-negative integer or null")
        published = _finite_nonnegative(
            artifact_published_elapsed_seconds,
            "artifact_published_elapsed_seconds",
        )
        recorded = _finite_nonnegative(
            recorded_elapsed_seconds, "recorded_elapsed_seconds"
        )
        if published > recorded:
            raise ValueError("sentinel artifact cannot be published after it is recorded")
        if self.events and recorded < float(
            self.events[-1]["recorded_elapsed_seconds"]
        ):
            raise ValueError("sentinel recorded time must be monotone")
        scheduled = None
        if scheduled_elapsed_seconds is not None:
            scheduled = _finite_nonnegative(
                scheduled_elapsed_seconds, "scheduled_elapsed_seconds"
            )
        if sentinel_type == "terminal" and scheduled is not None and published > scheduled:
            raise ValueError("terminal artifact was published after its scheduled cutoff")
        completed = None
        if evaluation_completed_elapsed_seconds is not None:
            completed = _finite_nonnegative(
                evaluation_completed_elapsed_seconds,
                "evaluation_completed_elapsed_seconds",
            )
            if completed < published:
                raise ValueError("evaluation cannot complete before artifact publication")
        artifact = self._store_artifact(source)
        evaluation_ref = self._store_evaluation(evaluation, evaluation_status)
        response_ref = self._store_response(provider_response)
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise ValueError("sentinel idempotency_key must be a nonempty string")
            existing = next(
                (
                    row for row in self.events
                    if row.get("idempotency_key") == idempotency_key
                ),
                None,
            )
            if existing is not None:
                expected = {
                    "sentinel_type": sentinel_type,
                    "source_step": source_step,
                    "scheduled_elapsed_seconds": scheduled,
                    "artifact_published_elapsed_seconds": published,
                    "artifact_sha256": artifact["artifact_sha256"],
                    "selection_policy": str(selection_policy),
                    "evaluation": evaluation_ref,
                    "provider_response": response_ref,
                    "metadata": dict(metadata or {}),
                }
                if any(existing.get(key) != value for key, value in expected.items()):
                    raise ValueError(
                        "sentinel idempotency key was reused with different content"
                    )
                return existing
        event = {
            "schema_version": SENTINEL_SCHEMA_VERSION,
            "sequence": len(self.events),
            "sentinel_type": sentinel_type,
            "source_step": source_step,
            "scheduled_elapsed_seconds": scheduled,
            "artifact_published_elapsed_seconds": published,
            "recorded_elapsed_seconds": recorded,
            "capture_lag_seconds": (
                None if scheduled is None else max(0.0, recorded - scheduled)
            ),
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            **artifact,
            "selection_policy": str(selection_policy),
            "capture_method": str(capture_method),
            "evaluation": evaluation_ref,
            "provider_response": response_ref,
            "evaluation_completed_elapsed_seconds": completed,
            "feedback_visible": bool(feedback_visible),
            "reason": reason,
            "idempotency_key": idempotency_key,
            "metadata": dict(metadata or {}),
        }
        if sentinel_type == "t0" and self.events:
            raise ValueError("t0 sentinel must be the first ledger event")
        if sentinel_type == "terminal" and any(
            row["sentinel_type"] == "terminal" for row in self.events
        ):
            raise ValueError("sentinel ledger already has a terminal event")
        _durable_append(self.path, event)
        self.events.append(event)
        return event

    def has_type(self, sentinel_type: str) -> bool:
        return any(row["sentinel_type"] == sentinel_type for row in self.events)

    def latest_artifact_event(self) -> Optional[dict[str, Any]]:
        return next(
            (
                row for row in reversed(self.events)
                if row.get("artifact_sha256") is not None
            ),
            None,
        )

    def snapshot(self) -> dict[str, Any]:
        validated = load_sentinel_events(self.path, workdir=self.workdir)
        type_counts = {
            name: sum(row["sentinel_type"] == name for row in validated)
            for name in sorted(SENTINEL_TYPES)
        }
        return {
            "schema_version": SENTINEL_SCHEMA_VERSION,
            "ledger_path": str(self.path.relative_to(self.workdir)),
            "ledger_sha256": _sha256(self.path.read_bytes()),
            "event_count": len(validated),
            "type_counts": type_counts,
            "has_terminal": type_counts["terminal"] == 1,
            "events": validated,
        }


def load_sentinel_events(
    path: Path, *, workdir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    path = Path(path).resolve()
    root = Path(workdir).resolve() if workdir is not None else path.parent.parent
    events = []
    prior_recorded = 0.0
    terminal_seen = False
    idempotency_keys: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("schema_version") != SENTINEL_SCHEMA_VERSION:
            raise ValueError("unsupported sentinel schema at line %d" % line_number)
        if event.get("sequence") != len(events):
            raise ValueError("sentinel sequence is not contiguous")
        if event.get("sentinel_type") not in SENTINEL_TYPES:
            raise ValueError("unknown sentinel type")
        if not isinstance(event.get("metadata", {}), dict):
            raise ValueError("sentinel metadata must be an object")
        key = event.get("idempotency_key")
        if key is not None:
            if not isinstance(key, str) or not key or key in idempotency_keys:
                raise ValueError("sentinel idempotency key is invalid or duplicated")
            idempotency_keys.add(key)
        recorded = _finite_nonnegative(
            event.get("recorded_elapsed_seconds"),
            "recorded_elapsed_seconds",
        )
        if events and recorded < prior_recorded:
            raise ValueError("sentinel recorded time is not monotone")
        prior_recorded = recorded
        artifact_hash = event.get("artifact_sha256")
        artifact_path = event.get("artifact_path")
        if artifact_hash is None:
            if artifact_path is not None or event.get("artifact_utf8_bytes") is not None:
                raise ValueError("null sentinel artifact has non-null metadata")
        else:
            target = root / str(artifact_path)
            payload = target.read_bytes()
            if _sha256(payload) != artifact_hash:
                raise ValueError("sentinel artifact hash differs")
            if len(payload) != event.get("artifact_utf8_bytes"):
                raise ValueError("sentinel artifact byte count differs")
        evaluation = event.get("evaluation")
        if not isinstance(evaluation, dict) or evaluation.get("status") not in EVALUATION_STATUSES:
            raise ValueError("sentinel evaluation reference is invalid")
        evaluation_hash = evaluation.get("sha256")
        evaluation_path = evaluation.get("path")
        if evaluation_hash is None:
            if evaluation_path is not None:
                raise ValueError("null evaluation hash has a path")
        else:
            payload = (root / str(evaluation_path)).read_bytes()
            if _sha256(payload) != evaluation_hash:
                raise ValueError("sentinel evaluation hash differs")
            json.loads(payload)
        response = event.get("provider_response")
        if response is not None:
            if not isinstance(response, dict):
                raise ValueError("sentinel provider response reference is invalid")
            response_hash = response.get("sha256")
            response_path = response.get("path")
            if response_hash is None:
                if response_path is not None or response.get("utf8_bytes") is not None:
                    raise ValueError("null provider response has non-null metadata")
            else:
                payload = (root / str(response_path)).read_bytes()
                if _sha256(payload) != response_hash:
                    raise ValueError("sentinel provider response hash differs")
                if len(payload) != response.get("utf8_bytes"):
                    raise ValueError("sentinel provider response byte count differs")
        if event["sentinel_type"] == "t0" and events:
            raise ValueError("t0 sentinel is not first")
        if event["sentinel_type"] == "terminal":
            scheduled = event.get("scheduled_elapsed_seconds")
            if scheduled is not None and float(
                event["artifact_published_elapsed_seconds"]
            ) > float(scheduled):
                raise ValueError("terminal artifact was published after cutoff")
            if terminal_seen:
                raise ValueError("multiple terminal sentinels")
            terminal_seen = True
        elif terminal_seen:
            raise ValueError("sentinel event appears after terminal")
        events.append(event)
    return events
