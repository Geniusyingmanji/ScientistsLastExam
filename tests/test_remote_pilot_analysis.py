"""Mock transport/protocol tests; these do not establish Linux sandbox validity."""
import io
import json
import shlex
from unittest.mock import MagicMock, patch

import pytest

from scripts import remote_pilot_analysis as bridge


READY = {"ready": True, "protocol": bridge.PROTOCOL,
         "versions": {"python": "mock", "numpy": "mock", "scipy": "mock"},
         "source_binding": {"task_id": bridge.TASK_ID},
         "source_commit": "a" * 40, "bridge_sha256": "b" * 64}


def test_server_routes_code_only_to_sandbox_and_reports_identity():
    source = io.BytesIO(bridge._encode({"code": "raise Exception('not locally executed')",
                                      "problem": {"public": True}, "history": []}))
    output = io.BytesIO()
    sandbox = MagicMock(return_value={"ok": True, "stdout": "", "result": "mock-analysis"})
    with patch.object(bridge.sys, "platform", "linux"), patch.object(bridge, "_new_sandbox", return_value=sandbox), \
            patch.object(bridge, "_identity", return_value=READY):
        assert bridge.server(source, output) == 0
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert rows == [READY, {"ok": True, "analysis": {"ok": True, "stdout": "", "result": "mock-analysis"}}]
    sandbox.assert_called_once_with("raise Exception('not locally executed')", {"public": True}, [])
    sandbox.close.assert_called_once()


def test_non_linux_server_fails_without_local_execution():
    output = io.BytesIO()
    with patch.object(bridge.sys, "platform", "darwin"), patch.object(bridge, "_new_sandbox") as factory:
        assert bridge.server(io.BytesIO(), output) == 1
    factory.assert_not_called()
    assert json.loads(output.getvalue())["ready"] is False


@pytest.mark.parametrize("frame", [
    b'{"code":"x","code":"y","problem":{},"history":[]}\n',
    b'{"code":"x","problem":{"x":NaN},"history":[]}\n',
    b'{"code":"x","problem":{"x":1e999},"history":[]}\n',
    b'{"code":"x","problem":{},"history":[],"path":"/private"}\n',
    b'[]\n', b'{}', b'\xff\n', b'x' * (bridge.MAX_FRAME_BYTES + 1),
])
def test_server_rejects_bad_frames_before_sandbox_callback(frame):
    sandbox, output = MagicMock(), io.BytesIO()
    with patch.object(bridge.sys, "platform", "linux"), patch.object(bridge, "_new_sandbox", return_value=sandbox), \
            patch.object(bridge, "_identity", return_value=READY):
        assert bridge.server(io.BytesIO(frame), output) == 1
    sandbox.assert_not_called()
    sandbox.close.assert_called_once()
    assert json.loads(output.getvalue().splitlines()[-1])["ok"] is False


def test_client_command_quotes_operator_paths_and_code_is_only_stdin():
    process = MagicMock()
    process.poll.return_value = None
    worktree = "/var/tmp/a path; $(touch never)"
    with patch.object(bridge.subprocess, "Popen", return_value=process) as popen, \
            patch.object(bridge.os, "set_blocking"), \
            patch.object(bridge.RemoteAnalysis, "_read_object", side_effect=[READY, {"ok": True, "analysis": {"ok": False, "stdout": "", "error": "ValueError"}}]) as read, \
            patch.object(bridge.RemoteAnalysis, "_write_frame") as write:
        client = bridge.RemoteAnalysis("g450", worktree, "/usr/bin/python3")
        assert client.ready == READY
        code = "result = '$(touch NEVER); secrets are not shell arguments'"
        assert client(code, {}, []) == {"ok": False, "stdout": "", "error": "ValueError"}
        argv = popen.call_args.args[0]
        assert argv[:-1] == ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--", "g450"]
        assert shlex.split(argv[-1]) == ["cd", worktree, "&&", "exec", "/usr/bin/python3", "-u",
                                            worktree + "/scripts/remote_pilot_analysis.py", "--serve"]
        assert code not in argv[-1]
        assert popen.call_args.kwargs["shell"] is False
        assert popen.call_args.kwargs["stderr"] == bridge.subprocess.DEVNULL
        assert bridge._decode(write.call_args.args[0])["code"] == code
        assert write.call_args.args[1] == read.call_args.args[0]  # One RPC deadline, not two budgets.
        client.close()
        client.close()
    process.terminate.assert_called_once()
    process.stdin.close.assert_called_once()
    process.stdout.close.assert_called_once()


def test_ssh_startup_error_never_falls_back_to_host_analysis():
    with patch.object(bridge.subprocess, "Popen", side_effect=OSError("ssh unavailable")), \
            patch.object(bridge, "_new_sandbox") as host_sandbox:
        with pytest.raises(OSError, match="ssh unavailable"):
            bridge.RemoteAnalysis("g450", "/var/tmp/test", "python3")
    host_sandbox.assert_not_called()


def test_invalid_ready_closes_own_process():
    process = MagicMock()
    process.poll.return_value = None
    with patch.object(bridge.subprocess, "Popen", return_value=process), \
            patch.object(bridge.os, "set_blocking"), \
            patch.object(bridge.RemoteAnalysis, "_read_object", return_value={"ready": False, "error": "sandbox unavailable"}):
        with pytest.raises(bridge.RemoteAnalysisError, match="did not become ready"):
            bridge.RemoteAnalysis("g450", "/var/tmp/test", "python3")
    process.terminate.assert_called_once()


def test_rpc_failure_closes_transport_without_retry():
    process = MagicMock()
    process.poll.return_value = None
    with patch.object(bridge.subprocess, "Popen", return_value=process), \
            patch.object(bridge.os, "set_blocking"), \
            patch.object(bridge.RemoteAnalysis, "_read_object", side_effect=[READY, {"ok": False, "error": "CandidateError"}]) as read, \
            patch.object(bridge.RemoteAnalysis, "_write_frame") as write:
        client = bridge.RemoteAnalysis("g450", "/var/tmp/test", "python3")
        with pytest.raises(bridge.RemoteAnalysisError, match="sandbox analysis failed"):
            client("result = 1", {}, [])
        with pytest.raises(bridge.RemoteAnalysisError, match="closed"):
            client("result = 2", {}, [])
    assert read.call_count == 2  # Handshake plus exactly one response.
    write.assert_called_once()
    process.terminate.assert_called_once()


def test_read_bound_rejects_oversize_before_parsing():
    client = object.__new__(bridge.RemoteAnalysis)
    client.process = MagicMock()
    with patch.object(bridge.time, "monotonic", return_value=0), \
            patch.object(bridge.select, "select", return_value=([1], [], [])), \
            patch.object(bridge.os, "read", side_effect=[b"x" * 65536] * 32 + [b"x"]):
        with pytest.raises(bridge.RemoteAnalysisError, match="exceeds 2 MiB"):
            client._read_object(1)


def test_partial_reads_do_not_refresh_deadline():
    client = object.__new__(bridge.RemoteAnalysis)
    client.process = MagicMock()
    with patch.object(bridge.time, "monotonic", side_effect=[0, 0.8, 1.1]), \
            patch.object(bridge.select, "select", return_value=([1], [], [])) as select_call, \
            patch.object(bridge.os, "read", side_effect=[b'{"', b"x"]):
        with pytest.raises(TimeoutError):
            client._read_object(1)
    assert select_call.call_args_list[0].args[-1] == 1
    assert select_call.call_args_list[1].args[-1] == pytest.approx(0.2)


@pytest.mark.parametrize("options", [
    {"host": "-oProxyCommand=unsafe"}, {"worktree": "relative/path"},
    {"timeout_s": 181}, {"timeout_s": float("nan")}, {"timeout_s": True},
])
def test_invalid_transport_settings_fail_before_spawning(options):
    kwargs = {"host": "g450", "worktree": "/var/tmp/test", "python": "python3", **options}
    with patch.object(bridge.subprocess, "Popen") as popen:
        with pytest.raises(ValueError):
            bridge.RemoteAnalysis(**kwargs)
    popen.assert_not_called()
