"""Crash-consistent logical evaluation requests and durable result receipts.

Each planned evaluator call gets one content-derived request id.  A complete
receipt is persisted and fsynced before the search trajectory can consume the
result.  Resume therefore reuses a completed result instead of evaluating the
same proposal again.  An interrupted attempt without a receipt may be retried;
for the deterministic local Frontier-Science tasks this is duplicate compute,
not a second scientific observation, and the logical oracle budget is still
charged exactly once.

This module does not claim physical exactly-once execution for a live or
irreversible laboratory.  Such an oracle must implement the same idempotency
key at the instrument/service boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Frontier-Science runners target POSIX
    fcntl = None


SCHEMA_VERSION = 1


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _durable_atomic_write(path: Path, payload: bytes) -> None:
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


def _finite_nonnegative(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
    ):
        raise ValueError("%s must be finite and non-negative" % label)
    return float(value)


class EvaluationLedger:
    """Persist one logical result for every content-bound evaluator request."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = Path(workdir).resolve()
        self.root = self.workdir / "evaluation_ledger"
        self.request_root = self.root / "requests"
        self.receipt_root = self.root / "receipts"
        self.attempt_root = self.root / "attempts"
        self.lock_root = self.root / "locks"
        self.root.mkdir(parents=True, exist_ok=True)

    def _request_document(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict) or not request:
            raise ValueError("evaluation request must be a nonempty object")
        payload = _canonical_json(request)
        request_id = _sha256(payload)
        return {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "request_sha256": request_id,
            "request": request,
        }

    def _request_path(self, request_id: str) -> Path:
        return self.request_root / (request_id + ".json")

    def _receipt_path(self, request_id: str) -> Path:
        return self.receipt_root / (request_id + ".json")

    def _attempt_path(self, request_id: str, attempt_index: int) -> Path:
        return self.attempt_root / request_id / ("%06d.json" % attempt_index)

    def prepare(self, request: dict[str, Any]) -> dict[str, Any]:
        document = self._request_document(request)
        path = self._request_path(document["request_id"])
        payload = _canonical_json(document)
        if path.is_file():
            if path.read_bytes() != payload:
                raise ValueError("evaluation request id has different content")
        else:
            _durable_atomic_write(path, payload)
        return document

    def _load_request(self, request_id: str) -> dict[str, Any]:
        path = self._request_path(request_id)
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("evaluation request schema is invalid")
        request = document.get("request")
        expected = self._request_document(request)
        if document != expected or expected["request_id"] != request_id:
            raise ValueError("evaluation request content binding differs")
        return document

    def _load_receipt(self, request_id: str) -> Optional[dict[str, Any]]:
        path = self._receipt_path(request_id)
        if not path.is_file():
            return None
        receipt = json.loads(path.read_text(encoding="utf-8"))
        request = self._load_request(request_id)
        metrics = receipt.get("metrics") if isinstance(receipt, dict) else None
        if not (
            isinstance(receipt, dict)
            and receipt.get("schema_version") == SCHEMA_VERSION
            and receipt.get("request_id") == request_id
            and receipt.get("request_sha256") == request["request_sha256"]
            and isinstance(receipt.get("completed_at_utc"), str)
            and bool(receipt.get("completed_at_utc"))
            and isinstance(metrics, dict)
            and receipt.get("metrics_sha256") == _sha256(_canonical_json(metrics))
        ):
            raise ValueError("evaluation receipt content binding differs")
        _finite_nonnegative(
            receipt.get("evaluation_wall_seconds"), "evaluation_wall_seconds"
        )
        # Reject non-finite/non-JSON nested values even if a hand-edited hash matches.
        _canonical_json(metrics)
        return receipt

    def require_receipt_id(self, request_id: str) -> dict[str, Any]:
        if not isinstance(request_id, str) or len(request_id) != 64:
            raise ValueError("evaluation receipt request id is invalid")
        receipt = self._load_receipt(request_id)
        if receipt is None:
            raise ValueError("committed trajectory lacks a durable evaluation receipt")
        return receipt

    def require_request_id(self, request_id: str) -> dict[str, Any]:
        if not isinstance(request_id, str) or len(request_id) != 64:
            raise ValueError("evaluation request id is invalid")
        return self._load_request(request_id)

    def require_bound_record(self, request_id: str) -> dict[str, Any]:
        request = self.require_request_id(request_id)
        receipt = self.require_receipt_id(request_id)
        return {"request": request["request"], "receipt": receipt}

    def require_receipt(self, request: dict[str, Any]) -> dict[str, Any]:
        expected = self._request_document(request)
        actual = self._load_request(expected["request_id"])
        if actual != expected:
            raise ValueError("evaluation request content binding differs")
        return self.require_receipt_id(expected["request_id"])

    def _next_attempt_index(self, request_id: str) -> int:
        root = self.attempt_root / request_id
        if not root.is_dir():
            return 1
        indices = []
        for path in root.glob("*.json"):
            try:
                indices.append(int(path.stem))
            except ValueError as exc:
                raise ValueError("evaluation attempt filename is invalid") from exc
        return max(indices, default=0) + 1

    def _start_attempt(self, request_id: str) -> tuple[int, dict[str, Any]]:
        attempt_index = self._next_attempt_index(request_id)
        attempt = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "attempt_index": attempt_index,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "started",
            "completed_at_utc": None,
            "evaluation_wall_seconds": None,
            "outcome": None,
        }
        _durable_atomic_write(
            self._attempt_path(request_id, attempt_index), _canonical_json(attempt)
        )
        return attempt_index, attempt

    def _finish_attempt(
        self,
        attempt: dict[str, Any],
        *,
        wall_seconds: float,
        outcome: str,
    ) -> None:
        if outcome not in {"receipt_committed", "infrastructure_failure", "exception"}:
            raise ValueError("unknown evaluation attempt outcome")
        completed = dict(attempt)
        completed.update({
            "status": "completed",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_wall_seconds": _finite_nonnegative(
                wall_seconds, "evaluation_wall_seconds"
            ),
            "outcome": outcome,
        })
        _durable_atomic_write(
            self._attempt_path(
                str(completed["request_id"]), int(completed["attempt_index"])
            ),
            _canonical_json(completed),
        )

    def evaluate_once(
        self,
        request: dict[str, Any],
        evaluator: Callable[[], dict[str, Any]],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> dict[str, Any]:
        """Return a durable receipt, reusing it without another evaluator call."""

        request_document = self._request_document(request)
        request_id = request_document["request_id"]
        if fcntl is None:
            raise RuntimeError("evaluation ledger requires POSIX advisory locks")
        self.lock_root.mkdir(parents=True, exist_ok=True)
        lock_path = self.lock_root / (request_id + ".lock")
        with lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                request_document = self.prepare(request)
                prior = self._load_receipt(request_id)
                if prior is not None:
                    return {**prior, "receipt_reused": True, "attempt_index": None}

                attempt_index, attempt = self._start_attempt(request_id)
                started = clock()
                try:
                    metrics = evaluator()
                except BaseException:  # retain an attempt record for injected crashes
                    wall = max(0.0, float(clock()) - float(started))
                    self._finish_attempt(attempt, wall_seconds=wall, outcome="exception")
                    raise
                wall = max(0.0, float(clock()) - float(started))
                if not isinstance(metrics, dict):
                    self._finish_attempt(attempt, wall_seconds=wall, outcome="exception")
                    raise ValueError("evaluator result must be an object")
                _canonical_json(metrics)
                if metrics.get("infrastructure_failure"):
                    self._finish_attempt(
                        attempt, wall_seconds=wall, outcome="infrastructure_failure"
                    )
                    return {
                        "schema_version": SCHEMA_VERSION,
                        "request_id": request_id,
                        "request_sha256": request_document["request_sha256"],
                        "metrics": metrics,
                        "metrics_sha256": _sha256(_canonical_json(metrics)),
                        "evaluation_wall_seconds": wall,
                        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                        "receipt_reused": False,
                        "attempt_index": attempt_index,
                        "receipt_committed": False,
                    }

                receipt = {
                    "schema_version": SCHEMA_VERSION,
                    "request_id": request_id,
                    "request_sha256": request_document["request_sha256"],
                    "metrics_sha256": _sha256(_canonical_json(metrics)),
                    "metrics": metrics,
                    "evaluation_wall_seconds": wall,
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                path = self._receipt_path(request_id)
                payload = _canonical_json(receipt)
                if path.is_file():
                    if path.read_bytes() != payload:
                        raise ValueError("evaluation receipt id has different content")
                else:
                    _durable_atomic_write(path, payload)
                # The receipt is the commit point. Attempt completion is secondary.
                validated = self._load_receipt(request_id)
                self._finish_attempt(
                    attempt, wall_seconds=wall, outcome="receipt_committed"
                )
                return {
                    **validated,
                    "receipt_reused": False,
                    "attempt_index": attempt_index,
                    "receipt_committed": True,
                }
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def snapshot(self) -> dict[str, Any]:
        requests = []
        for path in sorted(self.request_root.glob("*.json")):
            requests.append(self._load_request(path.stem))
        receipts = []
        for request in requests:
            receipt = self._load_receipt(request["request_id"])
            if receipt is not None:
                receipts.append(receipt)
        request_ids = [row["request_id"] for row in requests]
        receipt_ids = [row["request_id"] for row in receipts]
        attempts = []
        if self.attempt_root.is_dir():
            for path in sorted(self.attempt_root.glob("*/*.json")):
                attempt = json.loads(path.read_text(encoding="utf-8"))
                if not (
                    isinstance(attempt, dict)
                    and attempt.get("schema_version") == SCHEMA_VERSION
                    and attempt.get("request_id") == path.parent.name
                    and attempt.get("attempt_index") == int(path.stem)
                    and attempt.get("status") in {"started", "completed"}
                ):
                    raise ValueError("evaluation attempt ledger is invalid")
                if attempt["request_id"] not in request_ids:
                    raise ValueError("evaluation attempt lacks a bound request")
                if attempt["status"] == "started":
                    if not (
                        attempt.get("completed_at_utc") is None
                        and attempt.get("evaluation_wall_seconds") is None
                        and attempt.get("outcome") is None
                    ):
                        raise ValueError("started evaluation attempt has outcome fields")
                else:
                    if not (
                        isinstance(attempt.get("completed_at_utc"), str)
                        and bool(attempt.get("completed_at_utc"))
                        and attempt.get("outcome") in {
                            "receipt_committed", "infrastructure_failure", "exception"
                        }
                    ):
                        raise ValueError("completed evaluation attempt is malformed")
                    _finite_nonnegative(
                        attempt.get("evaluation_wall_seconds"),
                        "evaluation_wall_seconds",
                    )
                attempts.append(attempt)
        by_request: dict[str, list[int]] = {}
        for attempt in attempts:
            by_request.setdefault(attempt["request_id"], []).append(
                int(attempt["attempt_index"])
            )
        if any(sorted(indices) != list(range(1, len(indices) + 1))
               for indices in by_request.values()):
            raise ValueError("evaluation attempt indices are not contiguous")
        if any(
            row.get("outcome") == "receipt_committed"
            and row["request_id"] not in receipt_ids
            for row in attempts
        ):
            raise ValueError("committed evaluation attempt lacks its receipt")
        return {
            "schema_version": SCHEMA_VERSION,
            "semantics": (
                "exactly_once_logical_scientific_outcome_and_oracle_budget_for_"
                "deterministic_local_evaluators_not_physical_exactly_once_execution"
            ),
            "request_count": len(requests),
            "receipt_count": len(receipts),
            "attempt_count": len(attempts),
            "incomplete_attempt_count": sum(
                row.get("status") == "started" for row in attempts
            ),
            "infrastructure_failure_attempt_count": sum(
                row.get("outcome") == "infrastructure_failure" for row in attempts
            ),
            "open_request_ids": sorted(set(request_ids) - set(receipt_ids)),
            "request_ids": request_ids,
            "receipt_ids": receipt_ids,
        }


class RunLease:
    """Hold one non-blocking process lease for a mutable run directory."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = Path(workdir).resolve()
        self.path = self.workdir.parent / (".%s.run.lock" % self.workdir.name)
        self.handle = None

    def __enter__(self) -> "RunLease":
        if fcntl is None:
            raise RuntimeError("run lease requires POSIX advisory locks")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            fcntl.flock(
                self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
            )
        except BlockingIOError as exc:
            self.handle.close()
            self.handle = None
            raise RuntimeError(
                "run workdir is already leased by another process"
            ) from exc
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None
