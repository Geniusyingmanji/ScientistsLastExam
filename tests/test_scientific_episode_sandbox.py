"""Real Linux boundary tests; never substitute in-process exec for the agent."""
from pathlib import Path

from _sandbox_tools import skip_unless_sandbox
from sle.scientific_episode import (
    EpisodeSession, SandboxAnalysis, create_environment, run_policy,
    validate_episode_report,
)
from sle.secure_eval import CandidateProxy


TASK = "CausalDiscovery/SurvivorshipAuditDesign"


@skip_unless_sandbox()
def test_analysis_is_persistent_but_cannot_read_host_or_fork(tmp_path):
    secret = tmp_path / "private-world.txt"
    secret.write_text("hidden-ground-truth")
    analysis = SandboxAnalysis(TASK, 30)
    try:
        one = analysis("x = 41; result = x", {"public": 1}, [])
        assert one["result"] == 41
        two = analysis("result = x + 1", {"public": 1}, [])
        assert two["result"] == 42
        absent = analysis("from pathlib import Path\nresult = Path(%r).exists()" % str(secret), {}, [])
        assert absent["result"] is False
        fork = analysis("import os\nos.fork()", {}, [])
        assert fork["ok"] is False and fork["error"] == "PermissionError"
    finally:
        analysis.close()


@skip_unless_sandbox()
def test_program_candidate_uses_public_callbacks_and_cannot_inspect_environment(tmp_path):
    candidate = tmp_path / "candidate.py"
    candidate.write_text('''
def solve(problem, experiment):
    from pathlib import Path
    assert not Path(%r).exists()
    value = experiment("trial", {"stratum": 0, "treatment": 1, "n": 32, "audit_n": 8})
    assert value["n_enrolled"] == 32
    return {"abstain": True, "confidence": 0.5}
''' % str(Path(__file__).resolve().parents[1] / "benchmarks"))
    with CandidateProxy(candidate, "solve", timeout_s=30) as worker:
        session = EpisodeSession(create_environment(TASK, 123), max_steps=4)
        report = run_policy(session, worker)
    assert report["status"] == "completed"
    assert report["resources"]["experiment_units"] == 64
    assert report["metrics"]["discovery_coverage"] == 0
    validate_episode_report(report)
