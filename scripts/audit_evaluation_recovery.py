#!/usr/bin/env python3
"""Run process-level crash/restart audits for deterministic evaluator receipts."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.evolve import greedy_rewrite  # noqa: E402
from frontier_science.evaluation_ledger import EvaluationLedger, RunLease  # noqa: E402
from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402
from frontier_science.protocol import load_trajectory  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402
from scripts.run_recovery_fault_worker import (  # noqa: E402
    FAULT_EXIT_CODE,
    TASK,
    direct_request,
    fixture_llm_for_budget,
)


WORKER = ROOT / "scripts/run_recovery_fault_worker.py"
GREEDY_MODES = (
    "baseline_before_trajectory",
    "baseline_after_trajectory",
    "proposal_before_trajectory",
    "proposal_after_trajectory",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_fault(mode: str, workdir: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(WORKER),
        "--mode", mode,
        "--workdir", str(workdir),
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "expected_fault_exit": completed.returncode == FAULT_EXIT_CODE,
    }


def _portable_files(workdir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(workdir.rglob("*")):
        if not path.is_file() or path.name.endswith(".lock"):
            continue
        payload = path.read_bytes()
        row: dict[str, Any] = {
            "path": path.relative_to(workdir).as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        if path.suffix in {".json", ".jsonl"}:
            if path.suffix == ".jsonl":
                row["json_rows"] = [
                    json.loads(line) for line in payload.decode("utf-8").splitlines()
                    if line.strip()
                ]
            else:
                row["json"] = json.loads(payload)
        rows.append(row)
    return rows


def _audit_greedy_mode(root: Path, mode: str) -> dict[str, Any]:
    workdir = root / mode
    fault = _run_fault(mode, workdir)
    budget = 0 if mode.startswith("baseline_") else 1
    evaluator_calls = {"count": 0}

    def forbidden_evaluator(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        evaluator_calls["count"] += 1
        raise AssertionError("durable receipt was not reused")

    error = None
    result = None
    try:
        with patch(
            "frontier_science.algorithms.evolve.evaluate_candidate",
            side_effect=forbidden_evaluator,
        ):
            result = greedy_rewrite(
                find_task(TASK, include_uncertified=True),
                fixture_llm_for_budget(0),
                budget=budget,
                timeout_s=20,
                workdir=workdir,
                seed=260727,
                resume=True,
                log_fn=lambda _line: None,
            )
    except Exception as exc:  # noqa: BLE001
        error = "%s: %s" % (type(exc).__name__, exc)

    events = load_trajectory(workdir / "trajectory.jsonl") if result is not None else []
    snapshot = (
        result.summary.get("evaluation_ledger_snapshot") if result is not None else None
    ) or {}
    expected_events = budget + 1
    checks = {
        "worker_exited_at_injected_fault": fault["expected_fault_exit"],
        "resume_completed": result is not None and error is None,
        "resume_made_zero_evaluator_calls": evaluator_calls["count"] == 0,
        "trajectory_is_complete": bool(
            len(events) == expected_events
            and [row["step"] for row in events] == list(range(expected_events))
        ),
        "logical_oracle_budget_is_exact": bool(
            events and events[-1]["oracle_calls"] == expected_events
        ),
        "one_request_and_receipt_per_evaluated_event": bool(
            snapshot.get("request_count") == expected_events
            and snapshot.get("receipt_count") == expected_events
            and snapshot.get("open_request_ids") == []
        ),
        "trajectory_receipt_ids_are_unique": bool(
            len({
                (row.get("algorithm_metadata") or {}).get("evaluation_request_id")
                for row in events
            }) == expected_events
        ),
    }
    return {
        "mode": mode,
        "fault_process": fault,
        "resume_error": error,
        "resume_evaluator_call_count": evaluator_calls["count"],
        "trajectory": events,
        "evaluation_ledger_snapshot": snapshot,
        "checks": checks,
        "files": _portable_files(workdir),
    }


def _audit_direct_mode(root: Path, mode: str) -> dict[str, Any]:
    workdir = root / mode
    fault = _run_fault(mode, workdir)
    ledger = EvaluationLedger(workdir)
    label = (
        "receipt_before_attempt_completion"
        if mode == "receipt_before_attempt_completion"
        else "request_before_receipt"
    )
    request = direct_request(label)
    evaluator_calls = {"count": 0}

    def evaluator() -> dict[str, Any]:
        evaluator_calls["count"] += 1
        if mode == "receipt_before_attempt_completion":
            raise AssertionError("completed receipt was not reused")
        return {"combined_score": 0.55, "valid": 1.0}

    error = None
    result = None
    try:
        result = ledger.evaluate_once(request, evaluator)
    except Exception as exc:  # noqa: BLE001
        error = "%s: %s" % (type(exc).__name__, exc)
    snapshot = ledger.snapshot()
    expected_calls = 0 if mode == "receipt_before_attempt_completion" else 1
    expected_attempts = 1 if mode == "receipt_before_attempt_completion" else 2
    checks = {
        "worker_exited_at_injected_fault": fault["expected_fault_exit"],
        "recovery_completed": result is not None and error is None,
        "expected_recovery_evaluator_calls": evaluator_calls["count"] == expected_calls,
        "one_logical_request": snapshot.get("request_count") == 1,
        "one_durable_receipt": snapshot.get("receipt_count") == 1,
        "attempt_lineage_retained": bool(
            snapshot.get("attempt_count") == expected_attempts
            and snapshot.get("incomplete_attempt_count") == 1
        ),
        "no_open_logical_request": snapshot.get("open_request_ids") == [],
    }
    return {
        "mode": mode,
        "fault_process": fault,
        "recovery_error": error,
        "recovery_evaluator_call_count": evaluator_calls["count"],
        "result": result,
        "evaluation_ledger_snapshot": snapshot,
        "checks": checks,
        "files": _portable_files(workdir),
    }


def _audit_run_lease(root: Path) -> dict[str, Any]:
    workdir = root / "concurrent_run_lease"
    command = [
        sys.executable, str(WORKER), "--mode", "hold_run_lease",
        "--workdir", str(workdir),
    ]
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready = process.stdout.readline().strip() if process.stdout is not None else ""
    rejected = False
    error = None
    try:
        with RunLease(workdir):
            pass
    except Exception as exc:  # noqa: BLE001
        rejected = "already leased" in str(exc)
        error = "%s: %s" % (type(exc).__name__, exc)
    finally:
        process.terminate()
        try:
            _stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            _stdout, stderr = process.communicate(timeout=10)
    checks = {
        "child_acquired_lease": ready == "READY",
        "concurrent_writer_rejected": rejected,
        "lease_released_when_process_terminated": False,
    }
    try:
        with RunLease(workdir):
            checks["lease_released_when_process_terminated"] = True
    except Exception:
        pass
    return {
        "mode": "concurrent_run_lease",
        "command": command,
        "child_ready": ready,
        "child_returncode": process.returncode,
        "child_stderr": stderr,
        "concurrent_error": error,
        "checks": checks,
    }


def _audit_tamper_rejection(root: Path) -> dict[str, Any]:
    workdir = root / "tamper_rejection"
    ledger = EvaluationLedger(workdir)
    request = direct_request("tamper_rejection")
    receipt = ledger.evaluate_once(
        request, lambda: {"combined_score": 0.5, "valid": 1.0}
    )
    path = workdir / "evaluation_ledger/receipts" / (
        receipt["request_id"] + ".json"
    )
    original_sha256 = _sha256(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["metrics"]["combined_score"] = 1.0
    path.write_text(json.dumps(document), encoding="utf-8")
    error = None
    rejected = False
    try:
        EvaluationLedger(workdir).evaluate_once(request, lambda: {})
    except Exception as exc:  # noqa: BLE001
        rejected = "receipt content binding" in str(exc)
        error = "%s: %s" % (type(exc).__name__, exc)
    return {
        "mode": "tamper_rejection",
        "request_id": receipt["request_id"],
        "original_receipt_sha256": original_sha256,
        "tampered_receipt_sha256": _sha256(path),
        "observed_error": error,
        "checks": {
            "tamper_changes_receipt_hash": _sha256(path) != original_sha256,
            "tampered_receipt_rejected": rejected,
        },
    }


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="frontier_science_recovery_audit_"
    ) as temporary:
        root = Path(temporary)
        scenarios = [
            _audit_greedy_mode(root, mode) for mode in GREEDY_MODES
        ]
        scenarios.extend([
            _audit_direct_mode(root, "request_before_receipt"),
            _audit_direct_mode(root, "receipt_before_attempt_completion"),
            _audit_run_lease(root),
            _audit_tamper_rejection(root),
        ])

    issues = []
    for scenario in scenarios:
        failed = [
            name for name, passed in scenario.get("checks", {}).items()
            if passed is not True
        ]
        if failed:
            issues.append("%s: %s" % (scenario["mode"], ", ".join(failed)))
    report: dict[str, Any] = {
        "schema_version": 1,
        "trust_status": "EVALUATION_RECOVERY_FAULT_INJECTION_AUDIT",
        "evidence_scope": (
            "PROCESS_CRASH_DURABLE_RECEIPT_LOGICAL_EXACTLY_ONCE_OUTCOME_AND_"
            "ORACLE_BUDGET_FOR_DETERMINISTIC_LOCAL_EVALUATORS_NOT_PHYSICAL_"
            "EXACTLY_ONCE_LIVE_LAB_EXECUTION"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "worker": {"path": str(WORKER.relative_to(ROOT)), "sha256": _sha256(WORKER)},
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "checks": {
            "all_fault_scenarios_passed": not issues,
            "four_search_commit_windows_exercised": all(
                any(row["mode"] == mode for row in scenarios) for mode in GREEDY_MODES
            ),
            "request_before_receipt_retry_is_reason_coded": any(
                row["mode"] == "request_before_receipt"
                and row.get("recovery_evaluator_call_count") == 1
                for row in scenarios
            ),
            "receipt_before_attempt_completion_reuses_result": any(
                row["mode"] == "receipt_before_attempt_completion"
                and row.get("recovery_evaluator_call_count") == 0
                for row in scenarios
            ),
            "concurrent_run_writer_is_rejected": any(
                row["mode"] == "concurrent_run_lease"
                and all(row["checks"].values())
                for row in scenarios
            ),
            "receipt_tampering_is_rejected": any(
                row["mode"] == "tamper_rejection"
                and all(row["checks"].values())
                for row in scenarios
            ),
        },
        "issues": issues,
        "limitations": [
            "The fault workers use SIG-like abrupt os._exit process death, not whole-host power loss or filesystem corruption.",
            "A crash before receipt commit may repeat deterministic computation; it remains one logical request, receipt, scientific outcome and oracle-budget unit.",
            "Physical exactly-once execution requires an idempotency-aware remote instrument or laboratory service and is not established here.",
            "The end-to-end runner fault injection uses LennardJonesCluster as a protocol fixture and is not model-performance or scientific-discovery evidence.",
        ],
    }
    issues.extend(
        name for name, passed in report["checks"].items() if passed is not True
    )
    finalize_report_trust(report, not issues)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "scenario_count": report["scenario_count"],
        "checks": report["checks"],
        "issues": report["issues"],
        "execution_passed": report["execution_passed"],
        "trusted_evidence": report["trusted_evidence"],
    }, indent=2))
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
