"""Trusted oracle driver and isolated candidate RPC process."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import resource
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .rpc_codec import decode, encode

INVALID_SCORE = -1e18
PACKAGE_DIR = Path(__file__).resolve().parent


def _candidate_python() -> Path:
    """Use the host interpreter's major/minor when it is available under /usr.

    The current benchmark environment is Python 3.8, but this avoids silently
    coupling the sandbox protocol to that exact minor version.
    """
    preferred = Path("/usr/bin/python%d.%d" % sys.version_info[:2])
    return preferred if preferred.is_file() else Path("/usr/bin/python3")


def _site_package_roots() -> list[Path]:
    version = "%d.%d" % sys.version_info[:2]
    candidates = [
        Path.home() / ".local/lib" / ("python" + version) / "site-packages",
        Path("/usr/local/lib") / ("python" + version) / "dist-packages",
        Path("/usr/lib") / ("python" + version) / "dist-packages",
    ]
    return [path for path in candidates if path.is_dir()]


class CandidateError(RuntimeError):
    pass


def sanitized_candidate_failure(error: BaseException | str) -> dict[str, Any]:
    """Map candidate-controlled failures to a finite, label-blind taxonomy.

    Candidate exceptions can contain arbitrary text, including values observed through a
    trusted callback.  Returning that text as iterative feedback would create a high-bandwidth
    channel around metric sealing.  Classification happens in trusted code and only the fixed
    category is persisted or exposed to search.
    """
    message = str(error)
    if isinstance(error, TimeoutError) or "candidate timeout" in message:
        kind = "candidate_timeout"
    elif "ModuleNotFoundError" in message or "ImportError" in message:
        kind = "blocked_or_missing_import"
    elif "Operation not permitted" in message:
        kind = "blocked_operation"
    elif "FileNotFoundError" in message or "PermissionError" in message:
        kind = "blocked_or_missing_file"
    elif "non-finite" in message or "NaN" in message or "infinity" in message:
        kind = "non_finite_candidate_value"
    elif (
        "could not convert string to" in message
        or "invalid literal for int" in message
        or "not enough values to unpack" in message
        or "too many values to unpack" in message
    ):
        kind = "candidate_callback_schema_error"
    elif "response too large" in message:
        kind = "candidate_response_too_large"
    elif "candidate worker exited" in message:
        kind = "candidate_worker_exit"
    else:
        kind = "candidate_runtime_error"
    result: dict[str, Any] = {
        "combined_score": INVALID_SCORE,
        "valid": 0.0,
        "error_message": "candidate invalid: " + kind,
        "candidate_failure_kind": kind,
    }
    if kind == "candidate_timeout":
        result["timeout"] = 1.0
    return result


def _limits(cpu_seconds: int, memory_bytes: int):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        os.setsid()
    return apply


def _seccomp_no_processes() -> int:
    """Return a memfd containing a classic-BPF seccomp program.

    bwrap installs it immediately before exec. Denying fork/vfork/clone/clone3 keeps
    untrusted code single-process and single-threaded; numeric libraries are configured
    for one thread, so benchmark candidates do not need these syscalls.
    """
    # BPF_LD|BPF_W|BPF_ABS; BPF_JMP|BPF_JEQ|BPF_K; BPF_RET|BPF_K.
    load_nr, jump_eq, ret = 0x20, 0x15, 0x06
    seccomp_allow = 0x7FFF0000
    seccomp_errno_eperm = 0x00050000 | 1
    syscalls = (56, 57, 58, 435)  # x86_64: clone, fork, vfork, clone3
    filters = [(load_nr, 0, 0, 0)]
    for syscall_nr in syscalls:
        filters.extend(((jump_eq, 0, 1, syscall_nr), (ret, 0, 0, seccomp_errno_eperm)))
    filters.append((ret, 0, 0, seccomp_allow))
    program = b"".join(struct.pack("=HBBI", *item) for item in filters)
    memfd_create = getattr(os, "memfd_create", None)
    if memfd_create is not None:
        fd = memfd_create("frontier-science-seccomp", 0)
    else:  # Python/platform fallback; unlink keeps the descriptor anonymous.
        fd, path = tempfile.mkstemp(prefix="frontier-science-seccomp-")
        os.unlink(path)
    os.write(fd, program)
    os.lseek(fd, 0, os.SEEK_SET)
    return fd


def _sandbox_command(candidate: Path, entrypoint: str, seccomp_fd: int) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("secure evaluation requires bubblewrap (bwrap)")
    cmd = [
        bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--seccomp", str(seccomp_fd),
        "--uid", "65534", "--gid", "65534", "--hostname", "frontier-candidate", "--as-pid-1",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--dir", "/runner", "--dir", "/runner/frontier_science", "--dir", "/work",
        "--ro-bind", str(PACKAGE_DIR / "candidate_worker.py"), "/runner/frontier_science/candidate_worker.py",
        "--ro-bind", str(PACKAGE_DIR / "rpc_codec.py"), "/runner/frontier_science/rpc_codec.py",
        "--ro-bind", str(PACKAGE_DIR / "__init__.py"), "/runner/frontier_science/__init__.py",
        "--ro-bind", str(candidate), "/work/candidate.py",
    ]
    mounted: set[str] = set()
    for root in _site_package_roots():
        for package in ("numpy", "numpy.libs", "scipy", "scipy.libs"):
            src = root / package
            if src.exists() and package not in mounted:
                cmd += ["--dir", "/packages/" + package, "--ro-bind", str(src), "/packages/" + package]
                mounted.add(package)
    cmd += [
        "--chdir", "/work", "--setenv", "HOME", "/tmp", "--setenv", "TMPDIR", "/tmp",
        "--setenv", "PYTHONPATH", "/runner:/packages", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
        "--setenv", "PYTHONHASHSEED", "0", "--setenv", "PATH", "/usr/bin:/bin",
        "--", str(_candidate_python()), "/runner/frontier_science/candidate_worker.py",
        "--candidate", "/work/candidate.py", "--entrypoint", entrypoint,
    ]
    return cmd


class CandidateProxy:
    def __init__(self, candidate: Path, entrypoint: str, timeout_s: float,
                 memory_mb: int = 4096):
        self.deadline = time.monotonic() + timeout_s
        self.failure: Exception | None = None
        self.candidate = Path(candidate)
        self.entrypoint = str(entrypoint)
        self.memory_mb = int(memory_mb)
        self.proc = None
        self._stdout_buffer = b""
        self._start_worker()

    def _start_worker(self) -> None:
        """Start a fresh sandbox session for one top-level task instance.

        Remote callables returned by that instance continue to use this worker.  An explicit
        ``reset_session`` replaces it at the next scientific instance boundary, preventing
        module globals, imported-module attributes and the private tmpfs from leaking order.
        """
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("candidate timeout")
        self._stdout_buffer = b""
        seccomp_fd = _seccomp_no_processes()
        try:
            self.proc = subprocess.Popen(
                _sandbox_command(self.candidate, self.entrypoint, seccomp_fd),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1, pass_fds=(seccomp_fd,), env={
                    "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
                }, preexec_fn=_limits(max(1, int(math.ceil(remaining))),
                                      self.memory_mb * 1024 * 1024),
            )
        finally:
            os.close(seccomp_fd)
        try:
            ready = self._read_line()
            status = json.loads(ready)
            if not status.get("ready"):
                raise CandidateError(status.get("error", "worker failed to initialize"))
        except Exception as exc:
            detail = self._stderr()
            self.close(kill=True)
            if isinstance(exc, (CandidateError, TimeoutError)):
                raise
            raise CandidateError("worker failed to initialize: %s" % detail) from exc

    def _read_line(self) -> str:
        assert self.proc.stdout is not None
        fd = self.proc.stdout.fileno()
        while b"\n" not in self._stdout_buffer:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                self.close(kill=True)
                raise TimeoutError("candidate timeout")
            readable, _, _ = select.select([fd], [], [], remaining)
            if not readable:
                self.close(kill=True)
                raise TimeoutError("candidate timeout")
            chunk = os.read(fd, 65536)
            if not chunk:
                returncode = self.proc.poll()
                if returncode == -getattr(signal, "SIGXCPU", 24):
                    self.close(kill=True)
                    raise TimeoutError("candidate timeout (CPU limit)")
                raise CandidateError("candidate worker exited: %s" % self._stderr())
            self._stdout_buffer += chunk
            if len(self._stdout_buffer) > 100 * 1024 * 1024:
                raise CandidateError("candidate response too large")
        line, self._stdout_buffer = self._stdout_buffer.split(b"\n", 1)
        try:
            return line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CandidateError("candidate response is not UTF-8") from exc

    def _stderr(self) -> str:
        if self.proc.poll() is None:
            return ""
        assert self.proc.stderr is not None
        if self.proc.stderr.closed:
            return ""
        return self.proc.stderr.read()[-4000:]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._invoke("entrypoint", *args, **kwargs)

    def reset_session(self) -> None:
        """Give the next oracle instance a new process, imports and private tmpfs.

        Evaluators call this only at scientific instance/world boundaries.  Calls within an
        instance (for example controller time steps or returned remote callables) deliberately
        remain in one session.
        """
        if self.failure is not None:
            raise self.failure
        self.close()
        self._start_worker()

    def _decode_result(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._decode_result(v) for v in value]
        if isinstance(value, dict):
            tag = value.get("__fs_type__")
            if tag == "remote_callable":
                if set(value) != {"__fs_type__", "id"} or not isinstance(value["id"], str):
                    raise CandidateError("invalid callable handle")
                return RemoteCandidateCallable(self, value["id"])
            if tag == "tuple":
                return tuple(self._decode_result(v) for v in value.get("items", []))
            if tag == "mapping":
                return {self._decode_result(pair[0]): self._decode_result(pair[1])
                        for pair in value.get("items", [])}
            if tag in {"ndarray", "complex"}:
                return decode(value)
            return {k: self._decode_result(v) for k, v in value.items()}
        return decode(value)

    def _invoke(self, target: str, *args: Any, **kwargs: Any) -> Any:
        # Some multi-instance oracles catch a candidate exception so they can emit
        # per-instance diagnostics. Preserve the first worker failure: calling a dead
        # worker again must not replace a timeout with BrokenPipe/closed-file noise.
        if self.failure is not None:
            raise self.failure
        callbacks: dict[str, Any] = {}

        def encode_call(value: Any) -> Any:
            if callable(value):
                callback_id = "cb%d" % len(callbacks)
                callbacks[callback_id] = value
                return {"__fs_type__": "callback", "id": callback_id}
            if isinstance(value, list):
                return [encode_call(v) for v in value]
            if isinstance(value, tuple):
                return {"__fs_type__": "tuple", "items": [encode_call(v) for v in value]}
            if isinstance(value, dict):
                if all(isinstance(k, str) for k in value):
                    return {k: encode_call(v) for k, v in value.items()}
                return {"__fs_type__": "mapping", "items": [
                    [encode_call(k), encode_call(v)] for k, v in value.items()
                ]}
            return encode(value)

        request = json.dumps({"target": target, "args": encode_call(list(args)),
                              "kwargs": encode_call(kwargs)},
                             allow_nan=False, separators=(",", ":"))
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write(request + "\n")
            self.proc.stdin.flush()
            while True:
                response = json.loads(self._read_line())
                if not isinstance(response, dict) or response.get("type") != "callback":
                    break
                callback_id = response.get("id")
                callback = callbacks.get(callback_id)
                callback_response: dict[str, Any] = {"type": "callback_result", "id": callback_id}
                try:
                    if callback is None:
                        raise CandidateError("unknown callback handle")
                    cb_args = decode(response.get("args", []))
                    cb_kwargs = decode(response.get("kwargs", {}))
                    if not isinstance(cb_args, list) or not isinstance(cb_kwargs, dict):
                        raise CandidateError("invalid callback arguments")
                    callback_response.update({"ok": True, "result": encode(callback(*cb_args, **cb_kwargs))})
                except Exception as exc:
                    callback_response.update({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)})
                self.proc.stdin.write(json.dumps(callback_response, allow_nan=False,
                                                 separators=(",", ":")) + "\n")
                self.proc.stdin.flush()
            if not isinstance(response, dict) or not response.get("ok"):
                raise CandidateError(str(response.get("error", "candidate call failed")))
            return self._decode_result(response.get("result"))
        except TimeoutError as exc:
            if self.failure is None:
                self.failure = exc
            raise
        except (BrokenPipeError, OSError, json.JSONDecodeError, CandidateError,
                ValueError, TypeError) as exc:
            error = exc if isinstance(exc, CandidateError) else CandidateError(str(exc))
            if self.failure is None:
                self.failure = error
            raise self.failure

    def close(self, kill: bool = False) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL if kill else signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=1)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if stream is not None and not stream.closed:
                stream.close()
        self.proc = None

    def __enter__(self) -> "CandidateProxy":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class RemoteCandidateCallable:
    def __init__(self, owner: CandidateProxy, handle: str):
        self.owner = owner
        self.handle = handle

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.owner._invoke(self.handle, *args, **kwargs)


def load_oracle(task_dir: Path):
    path = task_dir / "verification/evaluator.py"
    unique = "frontier_science_oracle_%x" % hash(str(path))
    spec = importlib.util.spec_from_file_location(unique, str(path))
    if spec is None or spec.loader is None:
        raise ImportError("cannot load task oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evaluate = getattr(module, "evaluate")
    if not callable(evaluate):
        raise TypeError("oracle evaluate is not callable")
    return evaluate


def validate_metrics(value: Any, score_mode: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("oracle returned non-dict metrics")
    # A JSON round-trip prevents custom objects and rejects NaN/Inf recursively.
    try:
        safe = json.loads(json.dumps(
            value, allow_nan=False,
            default=lambda _: (_ for _ in ()).throw(TypeError("non-JSON metric value")),
        ))
    except (TypeError, ValueError) as exc:
        raise ValueError("metrics contain non-finite or non-JSON values") from exc
    score = safe.get("combined_score")
    valid = safe.get("valid")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(float(score)):
        raise ValueError("invalid combined_score")
    if not isinstance(valid, (int, float)) or isinstance(valid, bool) or not math.isfinite(float(valid)):
        raise ValueError("invalid valid flag")
    if float(valid) not in (0.0, 1.0):
        raise ValueError("valid must be 0 or 1")
    if score_mode == "clipped" and not (INVALID_SCORE <= float(score) <= 1.0 + 1e-9):
        raise ValueError("clipped score outside allowed range")
    if "raw_score" in safe:
        raw_score = safe["raw_score"]
        if (not isinstance(raw_score, (int, float)) or isinstance(raw_score, bool)
                or not math.isfinite(float(raw_score))):
            raise ValueError("invalid raw_score")
        safe["raw_score"] = float(raw_score)
    safe["combined_score"] = float(score)
    safe["valid"] = float(valid)
    # Preserve an oracle-supplied raw scientific objective.  It may deliberately
    # differ from the normalized benchmark score; only synthesize it when absent.
    safe.setdefault("raw_score", float(score))
    return safe


def trusted_evaluate(task_dir: Path, candidate: Path, entrypoint: str, score_mode: str,
                     timeout_s: float) -> dict[str, Any]:
    oracle = load_oracle(task_dir)
    with CandidateProxy(candidate, entrypoint, timeout_s) as proxy:
        result = oracle(proxy)
        if proxy.failure is not None:
            raise proxy.failure
    return validate_metrics(result, score_mode)
