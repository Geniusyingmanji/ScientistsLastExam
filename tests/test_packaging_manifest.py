"""The packaging manifest has to agree with the pins the runtime actually enforces.

The repository is a benchmark, not a library, so nothing imports `pyproject.toml` and nothing
would notice it drifting. Drift here is not cosmetic: the file is where a reader learns that the
certified NumPy/SciPy pair is a host prerequisite at all, and where the Python version story is
written down. Before it existed, `sle eval` failed on every task of a host whose SciPy was not
the certified one, and the only place the expected version appeared was a runtime error message.

These tests pin the properties the manifest is responsible for, not its wording, and they read
the pins out of `sle.oracle_package_pins` rather than restating them.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from sle.oracle_package_pins import BASE_CANDIDATE_PINS, setup_requirements

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: pytest and jupyterlab both pull tomli in.
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "pyproject.toml"
HOST_REQUIREMENTS = ROOT / "requirements-host.txt"


def _manifest() -> dict:
    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)


def _pins(entries) -> dict[str, str]:
    return dict(entry.split("==", 1) for entry in entries)


def _requirement_name(entry: str) -> str:
    return re.split(r"[=<>;\[\s]", entry, maxsplit=1)[0].strip()


def _requirement_version(entry: str) -> str:
    requirement, _, _marker = entry.partition(";")
    return requirement.split("==", 1)[1].strip()


class PackagingManifestTests(unittest.TestCase):
    def test_manifest_is_parseable_and_declares_the_benchmark(self):
        manifest = _manifest()
        self.assertEqual(manifest["project"]["name"], "scientists-last-exam")
        # A benchmark with nothing to import has no runtime dependencies. An entry here would
        # be an install requirement for every consumer of a repository they only clone.
        self.assertEqual(manifest["project"]["dependencies"], [])

    def test_certified_python_floor_matches_what_the_code_enforces(self):
        requires = _manifest()["project"]["requires-python"]
        self.assertEqual(requires, ">=3.8")
        # The floor is not decoration: it is the only interpreter `setup_requirements` accepts.
        self.assertIn("3.8", requires)
        with self.assertRaisesRegex(RuntimeError, "only certified Python 3.8"):
            setup_requirements((3, 12))
        self.assertIsInstance(setup_requirements((3, 8)), tuple)

    def test_host_extra_carries_the_certified_base_pair(self):
        manifest = _manifest()
        self.assertEqual(
            _pins(manifest["project"]["optional-dependencies"]["host"]),
            BASE_CANDIDATE_PINS[(3, 8)],
        )

    def test_oracle_extra_matches_the_one_certified_setup_transaction(self):
        """One map drives the setup script; this extra must not become a second one."""
        manifest = _manifest()
        extra = manifest["project"]["optional-dependencies"]["oracle"]
        self.assertEqual(_pins(extra), _pins(setup_requirements((3, 8))))
        # And it is a genuinely complete transaction, not a subset that happens to match.
        self.assertEqual(len(extra), len(setup_requirements((3, 8))))

    def test_host_requirements_select_the_line_for_the_running_interpreter(self):
        """The file exists for the markers a static extra cannot carry."""
        import sys

        entries = [line.split("#", 1)[0].strip()
                   for line in HOST_REQUIREMENTS.read_text(encoding="utf-8").splitlines()]
        entries = [entry for entry in entries if entry]
        self.assertTrue(entries)
        # Every entry is version-pinned and marked; an unmarked one would apply a 3.8 pin to 3.12.
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertIn("==", entry)
                self.assertIn("python_version", entry)
        selected = {_requirement_name(entry): _requirement_version(entry)
                    for entry in entries if _marker_matches(entry, sys.version_info[:2])}
        self.assertEqual(selected, BASE_CANDIDATE_PINS[sys.version_info[:2]])

    def test_repository_package_wins_over_an_installed_namesake(self):
        """`from scripts.x import y` is how every test and the docs reach the scripts.

        Without scripts/__init__.py this directory is a PEP 420 namespace portion and loses to
        the regular package the same name that pyarrow and gguf install - the failure was 39
        collection errors on the documented `pytest tests/ -q` command.
        """
        import scripts

        self.assertNotEqual(scripts.__file__, None, "scripts is a namespace portion, not a package")
        self.assertEqual(Path(scripts.__file__).resolve().parent, ROOT / "scripts")

    def test_pytest_is_told_the_repository_root(self):
        self.assertEqual(_manifest()["tool"]["pytest"]["ini_options"]["pythonpath"], ["."])


def _marker_matches(entry: str, version: tuple[int, int]) -> bool:
    """Evaluate the one marker shape this file uses, without adding a dependency for it."""
    marker = entry.split(";", 1)[1].strip()
    match = re.fullmatch(r'python_version\s*(<|>=|==)\s*"(\d+)\.(\d+)"', marker)
    if match is None:
        raise AssertionError("unexpected marker in requirements-host.txt: %r" % marker)
    operator, major, minor = match.groups()
    wanted = (int(major), int(minor))
    return {"<": version < wanted, ">=": version >= wanted, "==": version == wanted}[operator]


if __name__ == "__main__":
    unittest.main()
