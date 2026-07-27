#!/usr/bin/env python3
"""Child-process fault injector for evaluation-ledger recovery audits."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.algorithms.evolve import greedy_rewrite  # noqa: E402
from frontier_science.evaluation_ledger import EvaluationLedger, RunLease  # noqa: E402
from frontier_science.llm import LLMConfig  # noqa: E402
from frontier_science.registry import find_task  # noqa: E402


FAULT_EXIT_CODE = 86
TASK = "Chemistry/LennardJonesCluster"


class FixtureLLM:
    def __init__(self, replies: list[str]) -> None:
        self.replies = iter(replies)
        self.last_usage = {}
        self.config = LLMConfig(
            wire="chat",
            base_url="https://recovery-audit.invalid/v1",
            model="recovery-fixture",
            max_output_tokens=20,
            temperature=0.0,
            timeout_seconds=1,
        )

    def complete(self, _prompt: str, system: str | None = None) -> str:
        self.last_usage = {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "estimated_cost_usd": None,
        }
        return next(self.replies)


def fixture_llm_for_budget(budget: int) -> FixtureLLM:
    spec = find_task(TASK, include_uncertified=True)
    baseline = spec.initial_program_path.read_text(encoding="utf-8")
    reply = "```python\n%s\n```" % baseline
    return FixtureLLM([reply] * int(budget))


def direct_request(label: str) -> dict[str, object]:
    return {
        "kind": "recovery_fault_fixture",
        "task_id": "Fixture/Recovery",
        "label": label,
        "step": 1,
        "candidate_sha256": (label.encode("utf-8").hex() + "0" * 64)[:64],
    }


def _exit_now() -> None:
    os._exit(FAULT_EXIT_CODE)


def _run_greedy_fault(mode: str, workdir: Path) -> None:
    evolve_module = importlib.import_module("frontier_science.algorithms.evolve")
    real_append = evolve_module.append_event
    budget = 0 if mode.startswith("baseline_") else 1
    calls = {"count": 0}

    def fault_append(path, event):
        calls["count"] += 1
        target = 1 if budget == 0 else 2
        if calls["count"] != target:
            return real_append(path, event)
        if mode.endswith("after_trajectory"):
            real_append(path, event)
        _exit_now()

    spec = find_task(TASK, include_uncertified=True)
    with patch.object(evolve_module, "append_event", side_effect=fault_append):
        greedy_rewrite(
            spec,
            fixture_llm_for_budget(budget),
            budget=budget,
            timeout_s=20,
            workdir=workdir,
            seed=260727,
            log_fn=lambda _line: None,
        )
    raise RuntimeError("fault worker unexpectedly completed")


def _run_direct_fault(mode: str, workdir: Path) -> None:
    ledger = EvaluationLedger(workdir)
    label = (
        "receipt_before_attempt_completion"
        if mode == "receipt_before_attempt_completion"
        else "request_before_receipt"
    )
    request = direct_request(label)
    if mode == "request_before_receipt":
        ledger.evaluate_once(request, lambda: _exit_now())
        raise RuntimeError("request fault worker unexpectedly completed")

    real_finish = ledger._finish_attempt

    def finish_then_fault(attempt, *, wall_seconds, outcome):
        if outcome == "receipt_committed":
            _exit_now()
        return real_finish(attempt, wall_seconds=wall_seconds, outcome=outcome)

    ledger._finish_attempt = finish_then_fault
    ledger.evaluate_once(
        request, lambda: {"combined_score": 0.6, "valid": 1.0}
    )
    raise RuntimeError("receipt fault worker unexpectedly completed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=(
        "baseline_before_trajectory",
        "baseline_after_trajectory",
        "proposal_before_trajectory",
        "proposal_after_trajectory",
        "request_before_receipt",
        "receipt_before_attempt_completion",
        "hold_run_lease",
    ))
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    workdir = args.workdir.resolve()
    if args.mode == "hold_run_lease":
        with RunLease(workdir):
            print("READY", flush=True)
            time.sleep(10.0)
        return 0
    if args.mode in {"request_before_receipt", "receipt_before_attempt_completion"}:
        _run_direct_fault(args.mode, workdir)
    else:
        _run_greedy_fault(args.mode, workdir)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
