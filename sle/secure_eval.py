"""Trusted oracle driver and isolated candidate RPC process."""

from __future__ import annotations

import functools
import importlib.metadata
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
import sysconfig
import tempfile
import time
from pathlib import Path
from typing import Any

from .oracle_package_pins import candidate_distribution_pins
from .rpc_codec import decode, encode

INVALID_SCORE = -1e18
PACKAGE_DIR = Path(__file__).resolve().parent

# Packages every candidate may import.
BASE_CANDIDATE_PACKAGES = ("numpy", "numpy.libs", "scipy", "scipy.libs")

# Domain toolkits a task may additionally expose to its candidate by listing them in
# ``frontier_eval/candidate_packages.txt``. The allowlist is fixed in trusted code so a task
# package can never name an arbitrary host entry; each entry must also be a bare package path,
# and the value is only ever read from the task's own (agent-readonly) eval directory.
#
# Deliberately absent: verification-side anchors such as ``pymatching``. A task whose reference
# decoder is the scoring anchor must not be able to hand that anchor to the candidate.
# Wheels built by auditwheel put their bundled shared objects in a *sibling* ``<name>.libs``
# directory and reach it through a relative RPATH, so that sibling must be mounted alongside
# the package or every compiled extension fails to load.
ALLOWED_CANDIDATE_PACKAGES = {
    "rdkit": ("rdkit", "rdkit.libs", "PIL", "pillow.libs"),
    "sympy": ("sympy", "mpmath"),
    # The ViennaRNA distribution installs an `RNA` module alongside a `ViennaRNA` package; both
    # are needed for the import to resolve.
    "ViennaRNA": ("RNA", "ViennaRNA"),
    # nmrsim pulls in a real dependency chain: sparse for the Hamiltonian COO arrays, numba and
    # llvmlite behind sparse, and importlib_metadata plus typing_extensions for version lookup.
    # Listing only the obvious ones produced a bare blocked_or_missing_import with no hint of
    # which module was missing, so the full chain is enumerated here.
    "nmrsim": ("nmrsim", "sparse", "numba", "llvmlite", "numpy_groupies",
               "importlib_metadata", "typing_extensions.py", "zipp"),
    "networkx": ("networkx",),
    "qutip": ("qutip", "packaging"),
    "astropy": (
        "astropy", "astropy.libs", "erfa", "pyerfa.libs", "packaging",
        "yaml", "_yaml", "PyYAML.libs",
    ),
}

def _candidate_runtime() -> tuple[Path, Path, Path | None]:
    """Resolve the exact trusted CPython runtime used by candidate extensions.

    Only the base interpreter executable, standard library and libpython are exposed.
    The trusted virtualenv itself is never mounted; selected package directories are
    mounted separately below.
    """
    if sys.implementation.name != "cpython":
        raise RuntimeError("candidate runtime requires CPython")
    executable = Path(sys.executable).resolve()
    stdlib_value = sysconfig.get_path("stdlib")
    soabi = str(sysconfig.get_config_var("SOABI") or "")
    abi_prefix = "cpython-%d%d" % sys.version_info[:2]
    if not executable.is_file() or not stdlib_value or not soabi.startswith(abi_prefix):
        raise RuntimeError("trusted CPython executable or ABI is unavailable")
    stdlib = Path(stdlib_value).resolve()
    if not stdlib.is_dir():
        raise RuntimeError("trusted CPython standard library is unavailable")
    libpython = None
    libdir = sysconfig.get_config_var("LIBDIR")
    ldlibrary = sysconfig.get_config_var("LDLIBRARY")
    if libdir and ldlibrary:
        candidate = (Path(str(libdir)) / str(ldlibrary)).resolve()
        if candidate.is_file():
            libpython = candidate
    return executable, stdlib, libpython


def _site_package_roots() -> list[Path]:
    """Site-package roots active in the trusted interpreter, in import order."""
    roots: list[Path] = []
    for value in sys.path:
        if not value:
            continue
        path = Path(value)
        if path.name not in {"site-packages", "dist-packages"} or not path.is_dir():
            continue
        resolved = path.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return roots


@functools.lru_cache(maxsize=8)
def _hidden_package_mount_args(source: Path, destination: str) -> tuple[str, ...]:
    """Hide package stores nested below an otherwise required runtime tree.

    ``python -S`` only prevents automatic site initialization. Candidate code can still append
    an explicit host path to ``sys.path``, so package contents must be absent from the mount
    namespace itself. Each discovered package store is over-mounted with a fresh empty tmpfs.
    """
    root = source.resolve()
    if not root.is_dir():
        return ()
    args: list[str] = []
    for current, directories, _files in os.walk(str(root), followlinks=False):
        for name in tuple(directories):
            is_package_store = name in {"site-packages", "dist-packages"}
            is_bundled_installer = name == "_bundled" and Path(current).name == "ensurepip"
            if not (is_package_store or is_bundled_installer):
                continue
            package_root = Path(current) / name
            relative = package_root.relative_to(root)
            args += ["--tmpfs", str(Path(destination) / relative)]
            directories.remove(name)
    return tuple(args)


def _is_below(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            pass
    return False


def _is_system_library_destination(path: Path) -> bool:
    multiarch = str(sysconfig.get_config_var("MULTIARCH") or "")
    library_directories = {
        Path("/lib64"), Path("/usr/lib64"), Path("/usr/local/lib")
    }
    if multiarch:
        library_directories.update({Path("/lib") / multiarch, Path("/usr/lib") / multiarch})
    if path.parent in library_directories:
        return True
    return path.parent in {Path("/lib"), Path("/usr/lib")} and path.name.startswith("ld-")


@functools.lru_cache(maxsize=16)
def _elf_dependency_mount_args(sources: tuple[Path, ...]) -> tuple[str, ...]:
    """Mount only shared libraries required by trusted runtime and package ELF objects."""
    exposed_roots = tuple(path.resolve() for path in sources if path.is_dir())
    exposed_files = {path.resolve() for path in sources if path.is_file()}
    elf_files: list[Path] = []
    for source in sources:
        candidates: list[Path] = []
        if source.is_dir():
            if source.name.endswith(".libs"):
                continue
            for current, directories, files in os.walk(str(source), followlinks=False):
                directories[:] = [
                    name for name in directories
                    if name not in {"site-packages", "dist-packages"}
                    and not name.endswith(".libs")
                    and not (name == "_bundled" and Path(current).name == "ensurepip")
                ]
                candidates.extend(
                    Path(current) / name for name in files if ".so" in name
                )
        else:
            candidates.append(source)
        for candidate in candidates:
            try:
                with candidate.open("rb") as stream:
                    is_elf = stream.read(4) == b"\x7fELF"
                if candidate.is_file() and is_elf:
                    resolved = candidate.resolve()
                    if resolved not in elf_files:
                        elf_files.append(resolved)
            except OSError:
                continue
    if not elf_files:
        raise RuntimeError("candidate runtime has no ELF executable")
    ldd = shutil.which("ldd")
    if not ldd:
        raise RuntimeError("candidate runtime requires ldd to resolve shared libraries")
    completed = subprocess.run(
        [ldd, *(str(path) for path in elf_files)],
        capture_output=True,
        text=True,
        timeout=30,
        env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"},
    )
    output = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0 or "=> not found" in output:
        raise RuntimeError("candidate runtime shared-library resolution failed")
    libraries: list[tuple[Path, Path]] = []
    for raw in output.splitlines():
        fields = raw.strip().split()
        if not fields:
            continue
        value = fields[fields.index("=>") + 1] if "=>" in fields else fields[0]
        if not value.startswith("/"):
            continue
        destination = Path(value)
        source = destination.resolve()
        if (
            not source.is_file()
            or source in exposed_files
            or _is_below(source, exposed_roots)
        ):
            continue
        if not _is_system_library_destination(destination):
            raise RuntimeError(
                "candidate runtime dependency is outside trusted library directories"
            )
        pair = (source, destination)
        for mounted_source, mounted_destination in libraries:
            if mounted_destination == destination and mounted_source != source:
                raise RuntimeError("candidate runtime dependency resolves inconsistently")
        if pair not in libraries:
            libraries.append(pair)
    directories: set[Path] = set()
    for _source, destination in libraries:
        parent = destination.parent
        while parent != Path("/"):
            directories.add(parent)
            parent = parent.parent
    args: list[str] = []
    for directory in sorted(directories, key=lambda path: (len(path.parts), str(path))):
        args += ["--dir", str(directory)]
    for source, destination in libraries:
        args += ["--ro-bind", str(source), str(destination)]
    return tuple(args)


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


def read_candidate_packages(task_dir: Path) -> tuple[str, ...]:
    """Resolve the extra site-packages directories a task exposes to its candidate.

    Reads ``frontier_eval/candidate_packages.txt`` (one toolkit name per line, ``#`` comments
    allowed) and expands each name through ``ALLOWED_CANDIDATE_PACKAGES``. An unknown name is a
    task-packaging error and fails closed rather than silently running without the toolkit,
    which would otherwise show up as an unexplained candidate ImportError.
    """
    listing = Path(task_dir) / "frontier_eval" / "candidate_packages.txt"
    toolkits: list[str] = []
    lines = listing.read_text(encoding="utf-8").splitlines() if listing.is_file() else ()
    for raw in lines:
        name = raw.split("#", 1)[0].strip()
        if not name:
            continue
        if name not in ALLOWED_CANDIDATE_PACKAGES:
            raise RuntimeError(
                "task requests candidate package %r which is not in the trusted allowlist" % name
            )
        if name not in toolkits:
            toolkits.append(name)
    for distribution, expected_version in candidate_distribution_pins(
        sys.version_info[:2], toolkits
    ).items():
        try:
            installed_version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                "trusted candidate package %r is not installed" % distribution
            ) from exc
        if installed_version != expected_version:
            raise RuntimeError(
                "trusted candidate package %r has version %s, expected %s"
                % (distribution, installed_version, expected_version)
            )
    resolved: list[str] = []
    for name in toolkits:
        for directory in ALLOWED_CANDIDATE_PACKAGES[name]:
            if directory not in resolved:
                resolved.append(directory)
    return tuple(resolved)


@functools.lru_cache(maxsize=1)
def _proc_mount_args() -> tuple[str, ...]:
    """Prefer a fresh procfs. Some container hosts forbid that mount.

    A synthetic procfs is sufficient when a private procfs is unavailable. Its sole
    ``self/exe`` link lets the dynamic loader expand ``$ORIGIN`` for relocatable CPython
    builds without exposing the host process table.
    """
    fallback = (
        "--tmpfs", "/proc", "--dir", "/proc/self",
        "--symlink", "/runtime/bin/python", "/proc/self/exe",
    )
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return ("--proc", "/proc")
    probe = [
        bwrap, "--unshare-all", "--die-with-parent",
        *_elf_dependency_mount_args((Path("/usr/bin/true"),)),
        "--dir", "/runtime", "--dir", "/runtime/bin",
        "--ro-bind", "/usr/bin/true", "/runtime/bin/true",
    ]
    probe += ["--proc", "/proc", "--dev", "/dev", "--", "/runtime/bin/true"]
    try:
        result = subprocess.run(probe, capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return fallback
    if result.returncode == 0:
        return ("--proc", "/proc")
    return fallback


def _sandbox_command(candidate: Path, entrypoint: str, seccomp_fd: int,
                     packages: tuple[str, ...] = ()) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("secure evaluation requires bubblewrap (bwrap)")
    runtime_python, runtime_stdlib, runtime_libpython = _candidate_runtime()
    runtime_version = "%d.%d" % sys.version_info[:2]
    package_mounts: list[tuple[Path, str]] = []
    mounted: set[str] = set()
    requested = BASE_CANDIDATE_PACKAGES + tuple(packages)
    for root in _site_package_roots():
        for package in requested:
            if "/" in package or package in (".", ".."):
                raise RuntimeError("candidate package name must be a bare path")
            src = root / package
            if src.exists() and package not in mounted:
                resolved = src.resolve()
                try:
                    resolved.relative_to(root)
                except ValueError as exc:
                    raise RuntimeError("candidate package directory escapes its site root") from exc
                package_mounts.append((resolved, "/packages/" + package))
                mounted.add(package)
    dependency_sources = [runtime_python, runtime_stdlib]
    if runtime_libpython is not None:
        dependency_sources.append(runtime_libpython)
    dependency_sources.extend(source for source, _destination in package_mounts)
    cmd = [
        bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--seccomp", str(seccomp_fd),
        "--uid", "65534", "--gid", "65534", "--hostname", "frontier-candidate", "--as-pid-1",
        *_elf_dependency_mount_args(tuple(dependency_sources)),
        *_proc_mount_args(), "--dev", "/dev", "--tmpfs", "/tmp",
        "--dir", "/runner", "--dir", "/runner/sle", "--dir", "/work", "--dir", "/packages",
        "--dir", "/runtime", "--dir", "/runtime/bin", "--dir", "/runtime/lib",
        "--ro-bind", str(runtime_python), "/runtime/bin/python",
        "--ro-bind", str(runtime_stdlib), "/runtime/lib/python" + runtime_version,
        *_hidden_package_mount_args(
            runtime_stdlib, "/runtime/lib/python" + runtime_version
        ),
        "--ro-bind", str(PACKAGE_DIR / "candidate_worker.py"), "/runner/sle/candidate_worker.py",
        "--ro-bind", str(PACKAGE_DIR / "rpc_codec.py"), "/runner/sle/rpc_codec.py",
        # Free submission-shape validation the candidate may import. It reveals no score, no
        # hidden world and no reference value, so it costs nothing and leaks nothing.
        "--ro-bind", str(PACKAGE_DIR / "contract_lint.py"), "/runner/sle/contract_lint.py",
        "--ro-bind", str(PACKAGE_DIR / "__init__.py"), "/runner/sle/__init__.py",
        "--ro-bind", str(candidate), "/work/candidate.py",
    ]
    if runtime_libpython is not None:
        cmd += [
            "--ro-bind", str(runtime_libpython),
            "/runtime/lib/" + runtime_libpython.name,
        ]
    for source, destination in package_mounts:
        if source.is_dir():
            cmd += ["--dir", destination]
        cmd += ["--ro-bind", str(source), destination]
    cmd += [
        "--chdir", "/work", "--setenv", "HOME", "/tmp", "--setenv", "TMPDIR", "/tmp",
        "--setenv", "PYTHONPATH", "/runner:/packages", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
        "--setenv", "PYTHONHOME", "/runtime", "--setenv", "PYTHONNOUSERSITE", "1",
        "--setenv", "PYTHONHASHSEED", "0", "--setenv", "PATH", "/runtime/bin",
        "--", "/runtime/bin/python", "-S", "/runner/sle/candidate_worker.py",
        "--candidate", "/work/candidate.py", "--entrypoint", entrypoint,
    ]
    return cmd


class CandidateProxy:
    def __init__(self, candidate: Path, entrypoint: str, timeout_s: float,
                 memory_mb: int = 4096, packages: tuple[str, ...] = ()):
        self.deadline = time.monotonic() + timeout_s
        self.failure: Exception | None = None
        self.candidate = Path(candidate)
        self.entrypoint = str(entrypoint)
        self.memory_mb = int(memory_mb)
        self.packages = tuple(packages)
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
                _sandbox_command(self.candidate, self.entrypoint, seccomp_fd, self.packages),
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
        if self.proc is None:
            return ""
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


def load_oracle(task_dir: Path, *, with_trusted_context: bool = False):
    path = task_dir / "verification/evaluator.py"
    unique = "sle_oracle_%x" % hash(str(path))
    spec = importlib.util.spec_from_file_location(unique, str(path))
    if spec is None or spec.loader is None:
        raise ImportError("cannot load task oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entrypoint = "evaluate_with_context" if with_trusted_context else "evaluate"
    evaluate = getattr(module, entrypoint, None)
    if not callable(evaluate):
        raise TypeError("oracle %s is not callable" % entrypoint)
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
                     timeout_s: float,
                     trusted_context: dict[str, Any] | None = None) -> dict[str, Any]:
    oracle = load_oracle(
        task_dir, with_trusted_context=trusted_context is not None
    )
    with CandidateProxy(
        candidate, entrypoint, timeout_s, packages=read_candidate_packages(task_dir)
    ) as proxy:
        result = (
            oracle(proxy, trusted_context)
            if trusted_context is not None
            else oracle(proxy)
        )
        if proxy.failure is not None:
            raise proxy.failure
    return validate_metrics(result, score_mode)
