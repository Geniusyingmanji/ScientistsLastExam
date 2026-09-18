"""Boundary regressions found during review of framework PRs 102, 103 and 105."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from scripts import audit_tasks, saturation_audit
from sle import evaluate, secure_eval
from sle.metric_visibility import public_error_message
from sle.runtime_identity import TrustedRuntime, current_runtime_descriptor


@pytest.mark.parametrize("label", [
    "truth_morse", "heldout_3", "0123456789abcdef", "candidate_secret_42",
    "invalid_submission,truth_morse",
])
def test_identifier_shaped_secrets_are_not_public_failure_categories(label):
    assert public_error_message({"error_message": "candidate invalid: " + label}) == (
        "evaluation rejected; details retained in trusted diagnostics")


@pytest.mark.parametrize("declared", [float("nan"), float("inf"), -float("inf")])
def test_timeout_declaration_must_be_finite(tmp_path, declared):
    wrapper = tmp_path / "run_eval.py"
    wrapper.write_text("EVAL_TIMEOUT_S = 300\n")
    assert audit_tasks._timeout_issues({"eval_time_seconds": declared}, wrapper, "T/t")


@pytest.mark.parametrize("source", [
    "EVAL_TIMEOUT_S = 300\nEVAL_TIMEOUT_S = 1\n",
    "EVAL_TIMEOUT_S = 300\nEVAL_TIMEOUT_S = get_timeout()\n",
    "EVAL_TIMEOUT_S = 1e309\n",
])
def test_timeout_uses_final_finite_binding(tmp_path, source):
    wrapper = tmp_path / "run_eval.py"
    wrapper.write_text(source)
    assert audit_tasks._timeout_issues({"eval_time_seconds": 5}, wrapper, "T/t")


@pytest.mark.parametrize("metrics", [
    {"combined_score": float("nan"), "valid": 1},
    {"combined_score": float("inf"), "valid": 1},
    {"combined_score": True, "valid": 1},
    {"combined_score": 1, "valid": 0},
    {"combined_score": 1},
    {"combined_score": 1, "valid": True},
    {"combined_score": 1, "valid": 1, "infrastructure_failure": 1},
    {"combined_score": -1e18, "valid": 1},
    {"combined_score": 2, "valid": 1},
])
def test_saturation_requires_a_valid_finite_reference(tmp_path, metrics):
    spec = SimpleNamespace(task_id="T/t", task_dir=tmp_path, entrypoint="solve",
                           metadata={"score_mode": "clipped"})
    with patch.object(saturation_audit, "reference_path", return_value=tmp_path / "ref.py"), \
            patch.object(saturation_audit, "_load", return_value=SimpleNamespace(solve=lambda: 0)), \
            patch.object(saturation_audit, "load_oracle", return_value=lambda _: metrics):
        row = saturation_audit.audit_task(spec)
    assert row["status"] == saturation_audit.NOT_MEASURED
    json.dumps(row, allow_nan=False)


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), -1, 1, True])
def test_invalid_saturation_tolerance_is_rejected(tolerance):
    with pytest.raises(ValueError, match="tolerance"):
        saturation_audit.audit_task(None, tolerance=tolerance)


def test_uncapped_saturation_does_not_execute_a_reference(tmp_path):
    spec = SimpleNamespace(task_id="T/t", task_dir=tmp_path,
                           metadata={"score_mode": "uncapped"})
    with patch.object(saturation_audit, "reference_path") as reference, \
            patch.object(saturation_audit, "load_oracle") as oracle:
        row = saturation_audit.audit_task(spec)
    assert row["status"] == saturation_audit.NOT_MEASURED
    assert "uncapped" in row["detail"]
    reference.assert_not_called()
    oracle.assert_not_called()


def test_non_pilot_failure_preserves_callback_diagnostics(tmp_path):
    proxy = Mock(callback_invocations=3, failure=None)
    proxy.__enter__ = Mock(return_value=proxy)
    proxy.__exit__ = Mock(return_value=False)
    oracle = Mock(side_effect=secure_eval.CandidateError("candidate crash"))
    diagnostics = {}
    with patch.object(secure_eval, "CandidateProxy", return_value=proxy), \
            patch.object(secure_eval, "load_oracle", return_value=oracle), \
            patch.object(secure_eval, "read_candidate_packages", return_value=()):
        with pytest.raises(secure_eval.CandidateError):
            secure_eval.trusted_evaluate(tmp_path / "NonPilot", tmp_path / "candidate.py",
                                        "solve", "clipped", 5, diagnostics=diagnostics)
    assert diagnostics == {"callback_invocations": 3}


@pytest.mark.parametrize("calls", [0, 7, -1, True, 2.5, "7"])
def test_consumer_validates_and_preserves_envelope_diagnostics(tmp_path, calls):
    candidate = tmp_path / "candidate.py"
    candidate.write_text("def solve(p): return {}\n")
    spec = SimpleNamespace(task_id="T/t", task_dir=tmp_path, entrypoint="solve", metadata={})
    runtime = TrustedRuntime("unused", current_runtime_descriptor(()))
    science = {"combined_score": 0.5, "valid": 1.0}

    def launch(cmd, **kwargs):
        envelope = {"schema_version": 1, "trusted_evaluator_runtime_sha256":
                    runtime.fingerprint_sha256, "metrics": science, "callback_invocations": calls}
        Path(cmd[cmd.index("--result") + 1]).write_text(json.dumps(envelope))
        return SimpleNamespace(returncode=0, communicate=lambda **kw: (None, ""))

    diagnostics = {}
    with patch.object(evaluate.subprocess, "Popen", side_effect=launch):
        result = evaluate.evaluate_candidate(spec, candidate, trusted_runtime=runtime,
                                             diagnostics=diagnostics)
    if type(calls) is int and calls >= 0:
        assert diagnostics == {"callback_invocations": calls}
        assert result == {**science, "raw_score": 0.5}
    else:
        assert result["infrastructure_failure"] == 1
        assert diagnostics == {}
