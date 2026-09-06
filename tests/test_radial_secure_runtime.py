from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from _sandbox_tools import skip_unless_sandbox

from sle.evaluate import INVALID_SCORE, evaluate_candidate
from sle.oracle_package_pins import candidate_distribution_pins, setup_requirements
from sle.secure_eval import read_candidate_packages
from sle.spec import load_task_spec


ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "benchmarks" / "Physics" / "RadialVelocityPlanets"


class RadialVelocityPackageContractTests(unittest.TestCase):
    @staticmethod
    def pinned_versions():
        base = (
            {"numpy": "1.26.4", "scipy": "1.14.1"}
            if sys.version_info[:2] == (3, 12)
            else {"numpy": "1.24.4", "scipy": "1.10.1"}
        )
        return {
            **base,
            "astropy": "5.2.2",
            "pyerfa": "2.0.0.3",
            "PyYAML": "6.0.2",
            "packaging": "26.2",
        }

    def test_candidate_toolkit_dependency_pins_are_complete(self):
        expected = {
            "rdkit": {"Pillow": "10.4.0"},
            "sympy": {"mpmath": "1.3.0"},
            "nmrsim": {
                "sparse": "0.15.5",
                "numba": "0.58.1",
                "llvmlite": "0.41.1",
                "numpy-groupies": "0.9.22",
                "importlib-metadata": "8.5.0",
                "typing-extensions": "4.12.2",
                "zipp": "3.20.2",
            },
            "qutip": {"packaging": "26.2"},
            "astropy": {
                "pyerfa": "2.0.0.3",
                "PyYAML": "6.0.2",
                "packaging": "26.2",
            },
        }
        base = set(candidate_distribution_pins(sys.version_info[:2]))
        for toolkit, dependencies in expected.items():
            with self.subTest(toolkit=toolkit):
                pins = candidate_distribution_pins(sys.version_info[:2], (toolkit,))
                self.assertEqual(
                    {name: version for name, version in pins.items() if name not in base | {toolkit}},
                    dependencies,
                )

    def test_full_oracle_setup_rejects_uncertified_python_before_resolution(self):
        with self.assertRaisesRegex(
            RuntimeError, "full oracle setup supports only certified Python 3.8"
        ):
            setup_requirements((3, 12))

        completed = subprocess.run(
            ["bash", "scripts/setup_oracle_env.sh", "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, "ORACLE_PYTHON": "/usr/bin/python3.12"},
        )
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("full oracle setup supports only certified Python 3.8", completed.stderr)
        self.assertNotIn("oracle interpreter:", completed.stdout)

    def test_candidate_package_version_mismatch_fails_closed(self):
        versions = self.pinned_versions()
        versions["astropy"] = "7.0.0"
        with patch(
            "sle.secure_eval.importlib.metadata.version",
            side_effect=lambda distribution: versions[distribution],
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "trusted candidate package 'astropy' has version 7.0.0, expected 5.2.2",
            ):
                read_candidate_packages(TASK_DIR)

    def test_base_candidate_package_version_mismatch_fails_closed(self):
        versions = self.pinned_versions()
        versions["numpy"] = "0.0"
        with patch(
            "sle.secure_eval.importlib.metadata.version",
            side_effect=lambda distribution: versions[distribution],
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "trusted candidate package 'numpy' has version 0.0, expected",
            ):
                read_candidate_packages(TASK_DIR)

    def test_astropy_numeric_dependency_version_mismatch_fails_closed(self):
        for distribution, expected in (("pyerfa", "2.0.0.3"), ("PyYAML", "6.0.2")):
            with self.subTest(distribution=distribution):
                versions = self.pinned_versions()
                versions[distribution] = "0.0"
                with patch(
                    "sle.secure_eval.importlib.metadata.version",
                    side_effect=lambda package: versions[package],
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "trusted candidate package %r has version 0.0, expected %s"
                        % (distribution, expected),
                    ):
                        read_candidate_packages(TASK_DIR)

    def test_missing_astropy_numeric_dependency_fails_closed(self):
        versions = self.pinned_versions()

        def installed_version(distribution):
            if distribution == "PyYAML":
                raise importlib.metadata.PackageNotFoundError(distribution)
            return versions[distribution]

        with patch(
            "sle.secure_eval.importlib.metadata.version",
            side_effect=installed_version,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "trusted candidate package 'PyYAML' is not installed",
            ):
                read_candidate_packages(TASK_DIR)

    def test_oracle_setup_check_returns_nonzero_for_a_version_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            fake_python = Path(temporary) / "python"
            fake_python.write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                case "$*" in
                  *"setup_requirements"*) echo "numpy==1.24.4" ;;
                  *"get_path('purelib')"*) echo "/tmp/fake-site" ;;
                  *"importlib.metadata"*) echo "0.0" ;;
                  *"-V"*) echo "Python 3.8.20" ;;
                  *) exit 0 ;;
                esac
            """), encoding="utf-8")
            fake_python.chmod(0o755)
            completed = subprocess.run(
                ["bash", "scripts/setup_oracle_env.sh", "--check"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env={**os.environ, "ORACLE_PYTHON": str(fake_python)},
            )

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("MISMATCH 0.0 (expected 1.24.4)", completed.stdout)


@skip_unless_sandbox("bwrap")
class RadialVelocitySecureRuntimeTests(unittest.TestCase):
    def test_baseline_can_import_the_pinned_astropy_in_the_candidate_sandbox(self):
        try:
            astropy_version = importlib.metadata.version("astropy")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("the trusted test interpreter does not provide astropy")
        if astropy_version != "5.2.2":
            self.skipTest("the trusted test interpreter does not provide astropy 5.2.2")

        spec = load_task_spec(TASK_DIR)
        with patch.dict(
            os.environ,
            {"FRONTIER_SCIENCE_TRUSTED_PYTHON": sys.executable},
        ):
            result = evaluate_candidate(
                spec,
                TASK_DIR / "solution.py",
                timeout_s=180,
            )

        self.assertNotEqual(result["combined_score"], INVALID_SCORE, result)
        self.assertNotIn("infrastructure_failure", result, result)
        self.assertEqual(result["valid"], 1.0, result)

    def test_oracle_setup_checks_the_pinned_astropy_version(self):
        try:
            astropy_version = importlib.metadata.version("astropy")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("the trusted test interpreter does not provide astropy")
        if astropy_version != "5.2.2":
            self.skipTest("the trusted test interpreter does not provide astropy 5.2.2")

        completed = subprocess.run(
            ["bash", "scripts/setup_oracle_env.sh", "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "ORACLE_PYTHON": sys.executable},
        )

        self.assertRegex(completed.stdout, r"(?m)^\s*astropy\s+present\s+5\.2\.2$")
        self.assertRegex(completed.stdout, r"(?m)^\s*numpy\s+present\s+1\.24\.4$")
        self.assertRegex(completed.stdout, r"(?m)^\s*scipy\s+present\s+1\.10\.1$")
        self.assertRegex(completed.stdout, r"(?m)^\s*erfa\s+present\s+2\.0\.0\.3$")
        self.assertRegex(completed.stdout, r"(?m)^\s*yaml\s+present\s+6\.0\.2$")

    def test_candidate_gets_the_trusted_abi_without_the_oracle_virtualenv(self):
        try:
            astropy_version = importlib.metadata.version("astropy")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("the trusted test interpreter does not provide astropy")
        if astropy_version != "5.2.2":
            self.skipTest("the trusted test interpreter does not provide astropy 5.2.2")

        trusted_soabi = sysconfig.get_config_var("SOABI")
        trusted_prefix = str(Path(sys.prefix).resolve())
        source = """
            def detect_planets(_observation):
                import astropy
                import os
                import sys
                import sysconfig

                if sys.executable != "/runtime/bin/python":
                    raise RuntimeError("wrong candidate executable")
                if sysconfig.get_config_var("SOABI") != %r:
                    raise RuntimeError("wrong candidate ABI")
                if astropy.__version__ != "5.2.2":
                    raise RuntimeError("wrong astropy version")
                if os.path.exists(%r):
                    raise RuntimeError("trusted virtualenv is visible")
                try:
                    import pymatching
                except ImportError:
                    pass
                else:
                    raise RuntimeError("unrequested oracle package is visible")
                return {"abstain": True}
        """ % (trusted_soabi, trusted_prefix)
        spec = load_task_spec(TASK_DIR)
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            with patch.dict(
                os.environ,
                {"FRONTIER_SCIENCE_TRUSTED_PYTHON": sys.executable},
            ):
                result = evaluate_candidate(spec, candidate, timeout_s=180)

        self.assertNotIn("infrastructure_failure", result, result)
        self.assertEqual(result["valid"], 1.0, result)


if __name__ == "__main__":
    unittest.main()
