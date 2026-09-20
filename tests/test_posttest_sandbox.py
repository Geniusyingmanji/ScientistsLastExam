"""Real Linux RPC coverage for schema 2; no API or real scientific data."""
import hashlib
import platform
from pathlib import Path

import pytest

from sle.posttest_episode import PostTestEvidenceSession, run_posttest_policy
from sle.scientific_episode import validate_episode_report
from sle.secure_eval import CandidateProxy
from tests.test_evidence_episode import ObservationsOnly


pytestmark = pytest.mark.skipif(
    platform.system() != "Linux",
    reason="requires the real Linux candidate sandbox; a local skip is not a passed isolation check",
)


def test_real_candidate_completes_two_freezes_without_private_files_or_credentials(tmp_path, monkeypatch):
    private = tmp_path / "trusted-control-plane"
    private.mkdir(mode=0o700)
    credentials = private / "fake-credential.txt"
    credentials.write_text("invented-canary-not-a-credential", encoding="utf-8")
    measurements = private / "manual-private-table.csv"
    measurements.write_text("value\n999\n", encoding="utf-8")
    monkeypatch.setenv("SLE_POSTTEST_TEST_CANARY", "invented-private-environment-canary")
    hidden_paths = [str(private), str(credentials), str(measurements),
                    str(Path(__file__).resolve().parents[1] / "benchmarks")]
    candidate = tmp_path / "posttest_candidate.py"
    candidate.write_text("PRIVATE_PATHS = " + repr(hidden_paths) + "\n" + '''
def solve(context, act):
    import os
    import sys
    from pathlib import Path
    assert sys.platform.startswith("linux")
    assert all(not Path(path).exists() for path in PRIVATE_PATHS)
    assert "SLE_POSTTEST_TEST_CANARY" not in os.environ
    assert context["problem"]["discovery_contract"]["ground_truth_required"] is False
    assert "private_world_seed" not in context
    for name in ("positive", "null"):
        response = act({"action": "hypothesize", "hypothesis": {
            "id": name, "statement": "An invented operational prediction: " + name,
            "rationale": "Distinguish two predeclared ranges in a manual fixture.",
            "assumptions": ["Only this artificial observation."],
            "alternatives": ["The competing predeclared range."],
        }})
        assert response["ok"]
    predictions = [
        {"hypothesis_id": "positive", "interval": [0.2, 0.4], "falsifiers": [[-0.1, 0.1]]},
        {"hypothesis_id": "null", "interval": [-0.1, 0.1], "falsifiers": [[0.2, 0.4]]},
    ]
    assert act({"action": "plan_test", "test": {
        "id": "sealed", "phase": "replication", "tool": "measure",
        "arguments": {"partition": "replication"},
        "rationale": "Compare a future fixture observation with both predeclared ranges.",
        "measurement": {"path": ["value"], "reducer": "scalar"},
        "predictions": predictions,
    }})["ok"]
    committed = act({"action": "commit", "claim": {
        "claims": [{"hypothesis_id": "positive", "conclusion": "inconclusive",
            "support": [], "counterevidence": [], "tests": ["sealed"],
            "limitations": ["Await the fixture observation; no scientific finding claimed."]}],
        "replication_tests": ["sealed"], "limitations": ["Manual protocol fixture."],
    }})
    assert committed["ok"] and committed["episode_complete"] is False
    assert committed["next_action"] == "submit_interpretation"
    assert len(committed["results"]["observations"]) == 1
    observation = committed["results"]["observations"][0]
    value = observation["observation"]["value"]
    responses = []
    for prediction in predictions:
        low, high = prediction["interval"]
        responses.append({"hypothesis_id": prediction["hypothesis_id"],
            "assessment": "compatible" if low <= value <= high else "incompatible",
            "explanation": "Compare the returned fixture value with the unchanged interval."})
    interpretation = {
        "plan_sha256": committed["plan_sha256"], "results_sha256": committed["results_sha256"],
        "test_responses": [{"test_id": "sealed", "evidence_id": observation["evidence_id"],
                            "predictions": responses}],
        "conclusions": [{"hypothesis_id": "positive", "disposition": "retain",
            "statement": "The artificial observation is compatible with the positive range.",
            "scope": ["This one manually authored observation."],
            "limitations": ["No population, causal or novelty inference."],
            "rationale": "The observed scalar lies in the predeclared range.",
            "evidence": [{"evidence_id": observation["evidence_id"], "role": "prospective_test"}]}],
        "posthoc_hypotheses": [], "limitations": ["Protocol validation only."],
    }
    final = act({"action": "submit_interpretation", "interpretation": interpretation})
    assert final["ok"] and final["episode_complete"] is True
    return None
''', encoding="utf-8")
    environment = ObservationsOnly()
    session = PostTestEvidenceSession(environment, max_steps=5, wall_seconds=30,
                                     binding={"task_id": environment.task_id,
                                              "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest()})
    with CandidateProxy(candidate, "solve", timeout_s=30) as worker:
        report = run_posttest_policy(session, worker)
        assert worker.callback_invocations == 5
        assert worker.failure is None
    assert report["status"] == "completed" and report["schema_version"] == 2
    assert report["resources"]["steps"] == report["resources"]["max_steps"] == 5
    assert report["resources"]["experiment_calls"] == report["resources"]["experiment_units"] == 1
    assert environment.calls == [{"partition": "replication"}]
    assert report["claim"]["claims"][0]["conclusion"] == "inconclusive"
    assert report["interpretation"]["plan_sha256"] == report["plan_sha256"]
    assert report["interpretation"]["results_sha256"] == report["results_sha256"]
    assert report["metrics"]["discovery_score"] is None
    assert report["metrics"]["semantic_review"]["status"] == "unassessed"
    assert all(row["matches_measurement_check"] for row in
               report["metrics"]["candidate_interpretation"]["test_responses"])
    assert validate_episode_report(report)["scientific_validity"] == "not_assessed"


@pytest.mark.parametrize("forbidden", [
    {"action": "analyze", "code": "raise AssertionError('post-test code must never execute')"},
    {"action": "experiment", "tool": "measure", "arguments": {"partition": "replication"}},
])
def test_real_candidate_cannot_execute_new_tools_after_plan_freeze(tmp_path, forbidden):
    candidate = tmp_path / "forbidden_posttest_candidate.py"
    candidate.write_text("FORBIDDEN = " + repr(forbidden) + "\n" + '''
def solve(context, act):
    committed = act({"action": "commit", "claim": {
        "claims": [], "replication_tests": [], "limitations": ["Manual null fixture."]}})
    assert committed["ok"] and committed["episode_complete"] is False
    rejected = act(FORBIDDEN)
    assert rejected == {"ok": False, "error": "interpretation_phase_is_read_only"}
    return None
''', encoding="utf-8")
    environment = ObservationsOnly()
    analysis_calls = []

    def forbidden_analysis(*args):
        analysis_calls.append(args)
        raise AssertionError("post-test analysis was executed")

    session = PostTestEvidenceSession(environment, max_steps=2, wall_seconds=30, analysis=forbidden_analysis)
    with CandidateProxy(candidate, "solve", timeout_s=30) as worker:
        report = run_posttest_policy(session, worker)
        assert worker.callback_invocations == 2
        assert worker.failure is None
    assert report["status"] == "invalid_candidate"
    assert report["error"] == "interpretation_phase_is_read_only"
    assert report["plan"] and report["results"]
    assert report["interpretation"] is None and report["metrics"] is None
    assert report["resources"]["steps"] == 2
    assert report["resources"]["experiment_calls"] == report["resources"]["analysis_calls"] == 0
    assert environment.calls == analysis_calls == []
    assert validate_episode_report(report)["scientific_validity"] == "not_assessed"
