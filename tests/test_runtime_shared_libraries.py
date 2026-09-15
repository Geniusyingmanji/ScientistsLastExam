"""Relocatable interpreter libraries are mounted individually without host paths."""
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from sle.secure_eval import _elf_dependency_mount_args


def test_trusted_runtime_library_is_resolved_and_relocated_individually(tmp_path):
    runtime = tmp_path / "python/lib"
    runtime.mkdir(parents=True)
    executable = tmp_path / "python/bin/python"
    executable.parent.mkdir()
    executable.write_bytes(b"\x7fELFfixture")
    library = runtime / "libtcl.so"
    library.write_bytes(b"\x7fELFlibrary")
    calls = []
    def ldd(command, **kwargs):
        calls.append((command, kwargs))
        return CompletedProcess(command, 0, "libtcl.so => %s (0x123)\n" % library, "")
    with patch("sle.secure_eval.shutil.which", return_value="/usr/bin/ldd"), patch("sle.secure_eval.subprocess.run", side_effect=ldd):
        mounts = _elf_dependency_mount_args((executable,), (runtime,))
    assert calls[0][1]["env"]["LD_LIBRARY_PATH"] == str(runtime)
    assert mounts[-3:] == ("--ro-bind", str(library), "/runtime/lib/libtcl.so")
    assert str(runtime) not in mounts
    assert str(tmp_path / "python") not in mounts


def test_runtime_library_symlink_cannot_escape_trusted_directory(tmp_path):
    runtime = tmp_path / "lib"
    runtime.mkdir()
    executable = tmp_path / "python"
    executable.write_bytes(b"\x7fELFfixture")
    outside = tmp_path / "private.so"
    outside.write_bytes(b"\x7fELFprivate")
    (runtime / "escape.so").symlink_to(outside)
    result = CompletedProcess([], 0, "escape.so => %s (0x123)\n" % (runtime / "escape.so"), "")
    with patch("sle.secure_eval.shutil.which", return_value="/usr/bin/ldd"), patch("sle.secure_eval.subprocess.run", return_value=result), pytest.raises(RuntimeError, match="escapes its trusted directory"):
        _elf_dependency_mount_args((executable,), (runtime,))


def test_unrelated_host_library_is_still_rejected(tmp_path):
    executable = tmp_path / "python"
    executable.write_bytes(b"\x7fELFfixture")
    outside = tmp_path / "private.so"
    outside.write_bytes(b"\x7fELFprivate")
    result = CompletedProcess([], 0, "private.so => %s (0x123)\n" % outside, "")
    with patch("sle.secure_eval.shutil.which", return_value="/usr/bin/ldd"), patch("sle.secure_eval.subprocess.run", return_value=result), pytest.raises(RuntimeError, match="outside trusted library directories"):
        _elf_dependency_mount_args((executable,))


def test_missing_exposed_dependency_still_fails_closed(tmp_path):
    executable = tmp_path / "python"
    executable.write_bytes(b"\x7fELFfixture")
    result = CompletedProcess([], 0, "libmissing.so => not found\n", "")
    with patch("sle.secure_eval.shutil.which", return_value="/usr/bin/ldd"), patch("sle.secure_eval.subprocess.run", return_value=result), pytest.raises(RuntimeError, match="shared-library resolution failed"):
        _elf_dependency_mount_args((executable,))


def test_only_masked_elf_is_excluded_from_dependency_resolution(tmp_path):
    executable = tmp_path / "python"
    executable.write_bytes(b"\x7fELFfixture")
    package = tmp_path / "numba"
    package.mkdir()
    hidden = package / "tbbpool.so"
    visible = package / "serial.so"
    for path in (hidden, visible):
        path.write_bytes(b"\x7fELFfixture")
    with patch("sle.secure_eval.shutil.which", return_value="/usr/bin/ldd"), patch("sle.secure_eval.subprocess.run", return_value=CompletedProcess([], 0, "", "")) as run:
        _elf_dependency_mount_args((executable, package), (), (hidden,))
    scanned = run.call_args.args[0]
    assert str(hidden) not in scanned
    assert str(visible) in scanned
    assert str(executable) in scanned
