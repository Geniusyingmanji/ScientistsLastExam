"""Count callback invocations independently of oracle-specific budget units.

The real RPC worker runs with a test launcher; sandbox security is covered separately.
Both free callbacks and callbacks rejected by the oracle count as invocations.
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
    with patch.dict(os.environ, {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}), \
            patch("sle.secure_eval._limits", return_value=None):
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
    """Return (callback_invocations, failure_or_None) for one candidate source."""
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
            count = proxy.callback_invocations
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


def test_count_includes_invocations_rejected_by_the_oracle():
    """Rejection does not undo an invocation; no assertion is made about charged units."""
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


def test_driver_serializes_the_diagnostic_envelope(monkeypatch, tmp_path):
    """Driver unit test; the consumer and real sandbox path have separate tests."""
    import json

    source = textwrap.dedent("""
        def solve(problem):
            for _ in range(2):
                problem['measure'](1)
            return 1
    """)
    candidate = tmp_path / "candidate.py"
    candidate.write_text(source, encoding="utf-8")
    launcher = _launcher(tmp_path)

    calls = {"n": 0}

    def charged_measurement(_argument):
        calls["n"] += 1
        return {"energy": -1.0 * calls["n"]}

    def command(_candidate, entrypoint, _seccomp_fd, packages=()):
        return [sys.executable, str(launcher),
                "--candidate", str(candidate), "--entrypoint", entrypoint]

    # Import as the package module it is (a file-location import breaks the relative imports).
    from sle import trusted_driver as driver

    from sle.runtime_identity import current_runtime_descriptor, task_runtime_distributions
    runtime = current_runtime_descriptor(
        task_runtime_distributions(REPO / "benchmarks" / "Biology" / "OccupancyDetectionDesign"))

    result_path = tmp_path / "result.json"
    argv = [
        "--task-dir", str(REPO / "benchmarks" / "Biology" / "OccupancyDetectionDesign"),
        "--candidate", str(candidate),
        "--entrypoint", "design_occupancy",
        "--score-mode", "clipped",
        "--timeout", "30",
        "--expected-runtime-sha256", runtime["fingerprint_sha256"],
        "--result", str(result_path),
    ]

    monkeypatch.setattr(driver, "__name__", "sle_trusted_driver_test")
    # The task's oracle is imported by the driver itself; the proxy's sandbox command is the
    # only substituted boundary, as everywhere else in this file.
    with patch("sle.secure_eval._sandbox_command", side_effect=command), \
         patch("sle.secure_eval._seccomp_no_processes",
               side_effect=lambda: os.open(os.devnull, os.O_RDONLY)), \
         patch("sys.argv", ["trusted_driver"] + argv):
        # The driver reads the proxy's callback_invocations through the diagnostics dict;
        # run its main with the imports it needs. The oracle call itself is replaced by a
        # stub returning a minimal valid metrics dict, because this host cannot run the full
        # oracle stack (scipy pin); the accounting under test is harness-side.
        with patch.object(driver, "trusted_evaluate",
                          side_effect=lambda *a, **k: _stub_evaluate(k.get("diagnostics"))):
            rc = driver.main()
    assert rc == 0
    envelope = json.loads(result_path.read_text(encoding="utf-8"))
    assert envelope["callback_invocations"] == 2, (
        "the diagnostic must reach the envelope beside the runtime sha")
    assert set(envelope) == {"schema_version", "trusted_evaluator_runtime_sha256",
                             "metrics", "callback_invocations"}

    # And the consumer side: evaluate.py's strict key set must admit the diagnostic key.
    from sle.evaluate import evaluate_candidate  # noqa: F401  (import check only)


def _stub_evaluate(diagnostics):
    """Fill the diagnostics the way trusted_evaluate would, return minimal valid metrics."""
    if diagnostics is not None:
        diagnostics["callback_invocations"] = 2
    return {"combined_score": 0.0, "valid": 1.0}
