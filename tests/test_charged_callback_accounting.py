"""Charged callbacks are counted, and the count reaches the trusted record.

Most discovery tasks charge per measurement and enforce the budget inside the oracle. A
candidate that exhausts it and lets the oracle's RuntimeError propagate is classified. The
candidate that catches that error and submits anyway is not: it scored identically to an
honest one, and nothing in the record said the budget was gone.

The harness cannot enforce a limit no task declares - inventing one would false-fail correct
candidates whose oracle charges a different unit - so the count is published unconditionally
and `callback_budget_exhausted` names the class when an oracle's own budget error surfaces.

These tests run the real CandidateProxy, the real RPC protocol and the real callback loop. Only
the bubblewrap command is replaced: the sandbox is the boundary between the oracle and this
proxy, so replacing the command exercises every line of accounting without it. bubblewrap is
non-functional on this host, so the bwrap-based suite in test_secure_eval.py cannot run here.
"""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from sle.secure_eval import CandidateProxy, sanitized_candidate_failure

REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "sle" / "candidate_worker.py"
BUDGET_CALLS = 4


@pytest.fixture(autouse=True)
def _pinned_threads():
    """The 4-CPU cgroup quota does not match the 128 reported cores; pin before timing."""
    with patch.dict(os.environ, {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}):
        yield


def _launcher(directory: Path) -> Path:
    """A stand-in for the bwrap command that starts the real worker under this interpreter."""
    path = directory / "launcher.py"
    path.write_text(
        "import runpy, sys\n"
        "sys.path.insert(0, %r)\n"
        "sys.argv[0] = %r\n"
        "runpy.run_path(%r, run_name='__main__')\n"
        % (str(REPO), str(WORKER), str(WORKER)),
        encoding="utf-8",
    )
    return path


def run_charged_candidate(source: str, budget_calls: int = BUDGET_CALLS):
    """Return (charged_callback_calls, failure_or_None) for one candidate source."""
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        candidate = directory / "candidate.py"
        candidate.write_text(textwrap.dedent(source), encoding="utf-8")
        launcher = _launcher(directory)
        served = {"calls": 0}

        def charged_measurement(_argument):
            served["calls"] += 1
            if served["calls"] > budget_calls:
                raise RuntimeError("measurement budget exceeded")
            return {"energy": -1.0 * served["calls"]}

        def command(_candidate, entrypoint, _seccomp_fd, packages=()):
            return [sys.executable, str(launcher),
                    "--candidate", str(candidate), "--entrypoint", entrypoint]

        with patch("sle.secure_eval._sandbox_command", side_effect=command), \
             patch("sle.secure_eval._seccomp_no_processes",
                   side_effect=lambda: os.open(os.devnull, os.O_RDONLY)):
            proxy = CandidateProxy(candidate, "solve", 30.0)
            try:
                proxy({"measure": charged_measurement})
                failure = proxy.failure
            except Exception as exc:  # the oracle would see this and record it
                failure = exc
            count = proxy.charged_callback_calls
            proxy.close(kill=True)
    return count, failure


HONEST = """
    def solve(problem):
        for _ in range(3):
            problem['measure'](1)
        return 1
"""

SWALLOWS_AND_SUBMITS = """
    def solve(problem):
        for _ in range(12):
            try:
                problem['measure'](1)
            except Exception:
                pass
        return 1
"""

CRASHES_EARLY = """
    def solve(problem):
        problem['measure'](1)
        raise ValueError('boom')
"""

PROPAGATES_BUDGET_ERROR = """
    def solve(problem):
        for _ in range(12):
            problem['measure'](1)
        return 1
"""


def test_counter_separates_a_swallowed_budget_from_an_honest_run():
    """The defect: both succeed, and only the count tells them apart."""
    honest_count, honest_failure = run_charged_candidate(HONEST)
    swallowed_count, swallowed_failure = run_charged_candidate(SWALLOWS_AND_SUBMITS)
    assert honest_failure is None and swallowed_failure is None
    assert honest_count == 3
    assert swallowed_count == 12
    assert swallowed_count > honest_count


def test_count_matches_the_oracles_own_accounting_when_requests_are_rejected():
    """A rejected request is still a charged callback, so the count must include it."""
    count, _failure = run_charged_candidate(SWALLOWS_AND_SUBMITS)
    assert count == 12  # 4 served inside the budget + 8 refused by it


def test_an_honest_candidate_is_never_refused_by_the_counter():
    """The count is observability, not a limit: no task declares one yet."""
    for calls in (1, 3, BUDGET_CALLS):
        count, failure = run_charged_candidate(
            "def solve(problem):\n"
            "    for _ in range(%d):\n"
            "        problem['measure'](1)\n"
            "    return 1\n" % calls)
        assert failure is None
        assert count == calls


def test_budget_exhaustion_is_classified_as_budget_not_as_a_crash():
    """An oracle's own budget error must not read as candidate_runtime_error."""
    _count, failure = run_charged_candidate(PROPAGATES_BUDGET_ERROR)
    assert failure is not None
    metrics = sanitized_candidate_failure(failure)
    assert metrics["candidate_failure_kind"] == "callback_budget_exhausted"
    assert metrics["error_message"] == "candidate invalid: callback_budget_exhausted"
    # The oracle's message is not forwarded; only the class is.
    assert "measurement" not in metrics["error_message"]


def test_a_crash_before_the_budget_is_still_a_runtime_error():
    """The new branch must not swallow genuine crashes."""
    count, failure = run_charged_candidate(CRASHES_EARLY)
    assert count == 1
    assert failure is not None
    assert sanitized_candidate_failure(failure)["candidate_failure_kind"] == (
        "candidate_runtime_error")


def test_a_non_budget_error_mentioning_neither_word_stays_a_runtime_error():
    for message in ("assay-budget contract mismatch", "invalid trace"):
        kind = sanitized_candidate_failure(RuntimeError(message))["candidate_failure_kind"]
        assert kind == "candidate_runtime_error", message
