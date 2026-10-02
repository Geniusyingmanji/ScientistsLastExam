"""Relocatable interpreter libraries are mounted individually without host paths."""
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from sle.secure_eval import _elf_dependency_mount_args, _is_system_library_destination


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


@pytest.mark.parametrize("name", [
    "/lib/libsysconf-alipay.so", "/usr/lib/libc.so.6", "/lib/libm-2.32.so",
    "/usr/lib/libstdc++.so.6.0.28", "/lib/ld-linux-x86-64.so.2",
    "/usr/lib/ld-musl-x86_64.so.1", "/lib64/libc.so.6",
    "/usr/lib64/libm.so.6", "/usr/local/lib/libpython3.10.so.1.0",
])
def test_system_library_flat_layout_accepts_conventional_shared_objects(name):
    assert _is_system_library_destination(Path(name))


@pytest.mark.parametrize("name", [
    "/lib/settings.json", "/usr/lib/private.txt", "/lib/ld-secrets.txt",
    "/lib/libfoo.so.backup", "/usr/lib/libfoo.so.1.secret", "/lib/lib.so",
    "/lib/subdirectory/libfoo.so", "/usr/lib/private/libfoo.so",
    "/home/operator/libfoo.so", "/etc/libfoo.so", "/lib/libfoo",
])
def test_system_library_flat_layout_rejects_unrelated_files_and_paths(name):
    assert not _is_system_library_destination(Path(name))


def _mock_system_library_resolution(executable, destination, source):
    """Represent a system dependency without writing to the real host /lib."""
    real_resolve, real_is_file = Path.resolve, Path.is_file

    def resolve(path, *args, **kwargs):
        if path == destination:
            return source
        if path == source:
            return source
        return real_resolve(path, *args, **kwargs)

    def is_file(path):
        return True if path == source else real_is_file(path)

    result = CompletedProcess([], 0, "%s => %s (0x123)\n" % (destination.name, destination), "")
    return (
        patch("sle.secure_eval.shutil.which", return_value="/usr/bin/ldd"),
        patch("sle.secure_eval.subprocess.run", return_value=result),
        patch.object(Path, "resolve", resolve),
        patch.object(Path, "is_file", is_file),
    )


@pytest.mark.parametrize("destination,source", [
    ("/lib/libsysconf-alipay.so", "/lib/libsysconf-alipay.so"),
    ("/lib/libsysconf-alipay.so", "/usr/lib/libsysconf-alipay.so"),
    ("/usr/lib/libm.so.6", "/usr/lib64/libm-2.32.so"),
])
def test_flat_system_dependencies_are_individual_read_only_mounts(tmp_path, destination, source):
    executable = tmp_path / "python"
    executable.write_bytes(b"\x7fELFfixture")
    destination, source = Path(destination), Path(source)
    patches = _mock_system_library_resolution(executable, destination, source)
    with patches[0], patches[1], patches[2], patches[3]:
        mounts = _elf_dependency_mount_args((executable,))
    assert mounts[-3:] == ("--ro-bind", str(source), str(destination))
    assert mounts.count("--ro-bind") == 1
    assert "--bind" not in mounts
    # Creating an empty destination directory is harmless; binding the host
    # directory would expose unrelated system files and must never happen.
    bound_sources = [mounts[i + 1] for i, item in enumerate(mounts) if item == "--ro-bind"]
    assert bound_sources == [str(source)]
    assert "/lib" not in bound_sources and "/usr/lib" not in bound_sources


def test_system_library_symlink_cannot_expose_private_host_file(tmp_path):
    executable = tmp_path / "python"
    executable.write_bytes(b"\x7fELFfixture")
    private = tmp_path / "libprivate.so"
    private.write_bytes(b"private host data")
    patches = _mock_system_library_resolution(executable, Path("/lib/libsysconf-alipay.so"), private)
    with patches[0], patches[1], patches[2], patches[3], pytest.raises(RuntimeError, match="system library escapes its trusted directory"):
        _elf_dependency_mount_args((executable,))
