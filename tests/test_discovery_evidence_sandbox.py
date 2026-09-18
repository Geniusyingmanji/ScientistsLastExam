"""Real Linux worker tests for no-GT discovery and sealed measurement access."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from _sandbox_tools import skip_unless_sandbox
from benchmarks.ComputerScience.MeasurementAudit.verification.episode import create_environment
from sle.evidence_episode import EvidenceEpisodeSession, run_discovery_policy
from sle.scientific_episode import SandboxAnalysis, validate_episode_report
from sle.secure_eval import CandidateProxy


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks/ComputerScience/MeasurementAudit"
TASK = "DiscoveryEvidence/MeasurementAudit"


@skip_unless_sandbox()
def test_discovery_candidate_multiturn_replication_and_real_isolation(tmp_path, monkeypatch):
    bundle = tmp_path.resolve() / "private_observations"
    shutil.copytree(str(PACKAGE / "fixtures/protocol"), str(bundle))
    secret = tmp_path / "operator_credentials.txt"
    secret.write_text("private-test-sentinel-not-a-real-credential")
    monkeypatch.setenv("SLE_DISCOVERY_PRIVATE_SENTINEL", "must-not-enter-candidate-environment")
    actions = json.loads((PACKAGE / "examples/discovery_actions.json").read_text())
    candidate = tmp_path / "discovery_candidate.py"
    candidate.write_text('''
def solve(context, act):
    import os
    import errno
    import socket
    from pathlib import Path
    assert context["problem"]["evaluation_mode"] == "evidence_only"
    assert "SLE_DISCOVERY_PRIVATE_SENTINEL" not in os.environ
    for path in %r:
        assert not Path(path).exists(), "private host path exposed"
    # The network namespace removes connectivity; it need not forbid creating
    # an unconnected socket. Use the documentation-only TEST-NET address.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(1)
        try:
            connection.connect(("198.51.100.1", 443))
        except OSError as exc:
            assert exc.errno in (errno.ENETUNREACH, errno.EACCES, errno.EPERM), repr(exc)
        else:
            raise AssertionError("network connection was allowed")
    try:
        pid = os.fork()
    except PermissionError:
        pass
    else:
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)
        raise AssertionError("process creation was allowed")
    early = act({"action": "experiment", "tool": "summarize", "arguments": {
        "partition": "replication", "column": "signal", "statistic": "mean",
        "group_column": None, "group_values": None}})
    assert early == {"ok": False, "error": "replication_requires_commit"}
    one = act({"action": "analyze", "code": "discovery_session_marker = 41; result = discovery_session_marker"})
    assert one["analysis"]["result"] == 41
    two = act({"action": "analyze", "code": "result = discovery_session_marker + 1"})
    assert two["analysis"]["result"] == 42
    actions = %r
    for action in actions[:-1]:
        response = act(action)
        assert response["ok"], response
    return actions[-1]["claim"]
''' % ([str(bundle), str(bundle / "measurements.csv"), str(secret), str(ROOT / "benchmarks"),
        str(ROOT / "benchmarks/Biology/EnzymeRecoveryDesign/verification/episode.py")], actions))
    analysis = SandboxAnalysis(TASK, 45)
    try:
        environment = create_environment(0, bundle_path=bundle)
        session = EvidenceEpisodeSession(environment, analysis=analysis, max_steps=16, wall_seconds=60)
        with CandidateProxy(candidate, "solve", timeout_s=45) as worker:
            report = run_discovery_policy(session, worker)
    finally:
        analysis.close()
    assert report["status"] == "completed", report.get("error")
    assert report["resources"]["experiment_calls"] == 2
    assert report["resources"]["experiment_units"] == 32
    assert report["resources"]["analysis_calls"] == 2
    assert report["binding"]["evaluation_mode"] == "evidence_only"
    assert report["binding"]["measurement_data"]["ground_truth"] == "absent"
    assert report["frontier_eligible"] is False
    replicas = report["confirmation"]["observations"]
    assert len(replicas) == 1
    assert replicas[0]["observation"]["partition"] == "replication"
    assert replicas[0]["evidence_id"] == "experiment-0002"
    assert not any(event["kind"] == "action" for event in report["events"]
                   if event["seq"] > next(item["seq"] for item in report["events"] if item["kind"] == "commit"))
    validate_episode_report(report)


@skip_unless_sandbox()
def test_discovery_analysis_persists_only_inside_one_episode(tmp_path, monkeypatch):
    secret = tmp_path / "private_measurement_manifest.json"
    secret.write_text('{"sealed": true}')
    monkeypatch.setenv("SLE_DISCOVERY_PRIVATE_SENTINEL", "private-value")
    first = SandboxAnalysis(TASK, 30)
    try:
        initial = first(
            "from pathlib import Path\n"
            "import os\n"
            "episode_marker = 17\n"
            "Path('/tmp/discovery-analysis-marker.txt').write_text('private session state')\n"
            "result = {'secret_visible': Path(%r).exists(), 'env_visible': 'SLE_DISCOVERY_PRIVATE_SENTINEL' in os.environ}"
            % str(secret), {}, [])
        assert initial["result"] == {"secret_visible": False, "env_visible": False}
        repeated = first("result = episode_marker + 3", {}, [])
        assert repeated["result"] == 20
    finally:
        first.close()
    second = SandboxAnalysis(TASK, 30)
    try:
        fresh = second(
            "from pathlib import Path\n"
            "result = {'variable_present': 'episode_marker' in globals(), "
            "'file_present': Path('/tmp/discovery-analysis-marker.txt').exists(), "
            "'private_files_shared': any('verification' in name or 'measurements.csv' in name for name in public_files)}",
            {}, [])
        assert fresh["result"] == {"variable_present": False, "file_present": False,
                                    "private_files_shared": False}
    finally:
        second.close()
