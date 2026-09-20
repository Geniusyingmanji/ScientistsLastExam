#!/usr/bin/env python3
"""SSH transport to the existing Linux analysis sandbox; no local execution fallback.

Only JSON containing candidate code, public problem and observed history crosses
stdin. The SSH command contains operator-supplied locations, never candidate code.
This bridge does not make model requests or load an observation bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import select
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "sle-remote-analysis-v1"
TASK_ID = "DiscoveryEvidence/MeasurementAudit"
MAX_FRAME_BYTES = 2 * 1024 * 1024  # Includes the terminating newline.


class RemoteAnalysisError(RuntimeError):
    pass


def _encode(value):
    try:
        frame = (json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise RemoteAnalysisError("invalid finite JSON") from exc
    if len(frame) > MAX_FRAME_BYTES:
        raise RemoteAnalysisError("JSON frame exceeds 2 MiB")
    return frame


def _decode(frame):
    if not frame or len(frame) > MAX_FRAME_BYTES or not frame.endswith(b"\n"):
        raise RemoteAnalysisError("missing or oversized JSON frame")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(_value):
        raise ValueError("nonfinite JSON")
    try:
        result = json.loads(frame.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
        if not isinstance(result, dict):
            raise ValueError("JSON object required")
        _encode(result)  # Also rejects overflowed numbers such as 1e999.
        return result
    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
        raise RemoteAnalysisError("invalid JSON protocol frame") from exc


def _request(value):
    if (set(value) != {"code", "problem", "history"}
            or not isinstance(value["code"], str) or len(value["code"]) > 100000
            or not isinstance(value["problem"], dict) or not isinstance(value["history"], list)):
        raise RemoteAnalysisError("invalid analysis request")
    return value


def _analysis_result(value):
    if not isinstance(value, dict) or type(value.get("ok")) is not bool:
        raise RemoteAnalysisError("invalid sandbox response")
    required = {"ok", "stdout", "result" if value["ok"] else "error"}
    if (set(value) != required or not isinstance(value["stdout"], str)
            or (not value["ok"] and not isinstance(value["error"], str))):
        raise RemoteAnalysisError("invalid sandbox response")
    return value


def _new_sandbox():
    sys.path.insert(0, str(ROOT))
    from sle.scientific_episode import SandboxAnalysis
    return SandboxAnalysis("MeasurementAudit", timeout_s=600)


def _identity():
    from importlib import metadata
    from sle.scientific_episode import source_binding
    def version(name):
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            return None
    return {"ready": True, "protocol": PROTOCOL,
            "versions": {"python": platform.python_version(), "numpy": version("numpy"), "scipy": version("scipy")},
            "source_binding": source_binding("MeasurementAudit"),
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                       text=True, timeout=10).strip(),
            "bridge_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def server(stdin=None, stdout=None):
    """Trusted remote broker. Candidate code only reaches SandboxAnalysis."""
    source = sys.stdin.buffer if stdin is None else stdin
    sink = sys.stdout.buffer if stdout is None else stdout
    analysis = None
    ready = False
    try:
        if sys.platform != "linux":
            raise RemoteAnalysisError("Linux sandbox required")
        analysis = _new_sandbox()  # Fail closed before reporting readiness.
        sink.write(_encode(_identity()))
        sink.flush()
        ready = True
        while True:
            frame = source.readline(MAX_FRAME_BYTES + 1)
            if not frame:
                return 0
            request = _request(_decode(frame))
            result = _analysis_result(analysis(request["code"], request["problem"], request["history"]))
            sink.write(_encode({"ok": True, "analysis": result}))
            sink.flush()
    except Exception as exc:
        # Do not print exception messages, host paths, environment or credentials.
        sink.write(_encode({"ok" if ready else "ready": False, "error": type(exc).__name__}))
        sink.flush()
        return 1
    finally:
        if analysis is not None:
            analysis.close()


class RemoteAnalysis:
    """Analysis callback with a single <=180 s deadline for each full RPC.

    Startup has the same bound. Deadlines are not renewed for partial reads or
    writes. Model thinking between calls does not reset the remote sandbox's
    own 600-second lifetime. stderr goes to DEVNULL so it cannot fill a pipe.
    """
    def __init__(self, host, worktree, python, timeout_s=180):
        self.process = None
        self.closed = False
        self.ready = None
        if (isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float))
                or not math.isfinite(timeout_s) or not 0 < timeout_s <= 180):
            raise ValueError("RPC timeout must be positive and at most 180 seconds")
        if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@:-]*", host):
            raise ValueError("invalid SSH host")
        for value in (worktree, python):
            if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
                raise ValueError("invalid remote location")
        if not worktree.startswith("/"):
            raise ValueError("remote worktree must be absolute")
        self.timeout_s = float(timeout_s)
        command = "cd {} && exec {} -u {} --serve".format(
            shlex.quote(worktree), shlex.quote(python),
            shlex.quote(worktree.rstrip("/") + "/scripts/remote_pilot_analysis.py"))
        argv = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--", host, command]
        deadline = time.monotonic() + self.timeout_s
        try:
            self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, bufsize=0, shell=False)
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
            ready = self._read_object(deadline)
            if (set(ready) != {"ready", "protocol", "versions", "source_binding", "source_commit", "bridge_sha256"}
                    or ready.get("ready") is not True or ready.get("protocol") != PROTOCOL
                    or not isinstance(ready.get("versions"), dict)
                    or set(ready["versions"]) != {"python", "numpy", "scipy"}
                    or any(value is not None and not isinstance(value, str) for value in ready["versions"].values())
                    or not isinstance(ready.get("source_binding"), dict)
                    or ready["source_binding"].get("task_id") != TASK_ID
                    or not isinstance(ready.get("source_commit"), str)
                    or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", ready["source_commit"])
                    or not isinstance(ready.get("bridge_sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", ready["bridge_sha256"])):
                raise RemoteAnalysisError("remote analysis sandbox did not become ready")
            self.ready = ready  # Operator validates source/runtime identity before paid calls.
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _remaining(deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("remote analysis transport deadline")
        return remaining

    def _read_object(self, deadline):
        chunks = bytearray()
        fd = self.process.stdout.fileno()
        while True:
            if not select.select([fd], [], [], self._remaining(deadline))[0]:
                raise TimeoutError("remote analysis transport deadline")
            chunk = os.read(fd, min(65536, MAX_FRAME_BYTES + 1 - len(chunks)))
            if not chunk:
                raise RemoteAnalysisError("remote analysis transport closed")
            chunks.extend(chunk)
            if len(chunks) > MAX_FRAME_BYTES:
                raise RemoteAnalysisError("remote JSON frame exceeds 2 MiB")
            if b"\n" in chunk:
                if chunks.find(b"\n") != len(chunks) - 1:
                    raise RemoteAnalysisError("unexpected output after JSON frame")
                return _decode(bytes(chunks))

    def _write_frame(self, frame, deadline):
        fd = self.process.stdin.fileno()
        view = memoryview(frame)
        while view:
            if not select.select([], [fd], [], self._remaining(deadline))[1]:
                raise TimeoutError("remote analysis transport deadline")
            count = os.write(fd, view[:65536])
            if count <= 0:
                raise RemoteAnalysisError("remote analysis transport closed")
            view = view[count:]

    def __call__(self, code, problem, transcript):
        if self.closed:
            raise RemoteAnalysisError("remote analysis is closed")
        request = _request({"code": code, "problem": problem, "history": transcript})
        frame = _encode(request)
        deadline = time.monotonic() + self.timeout_s
        try:
            self._write_frame(frame, deadline)
            response = self._read_object(deadline)
            if set(response) != {"ok", "analysis"} or response["ok"] is not True:
                raise RemoteAnalysisError("remote sandbox analysis failed")
            return _analysis_result(response["analysis"])
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
            for pipe in (self.process.stdin, self.process.stdout):
                if pipe is not None:
                    pipe.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", required=True)
    parser.parse_args()
    raise SystemExit(server())
