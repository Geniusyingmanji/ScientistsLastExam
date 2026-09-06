from __future__ import annotations

import hashlib
import os
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from sle import evaluate
from sle.algorithms import common
from sle.algorithms.evolve import greedy_rewrite
from sle.registry import find_task
from sle.runtime_identity import (
    TrustedRuntime,
    current_runtime_descriptor,
    task_runtime_distributions,
    validate_runtime_descriptor,
)


class _Client:
    config = type("Config", (), {
        "wire": "chat", "base_url": "https://example.invalid/v1", "model": "fixture",
        "max_output_tokens": 1, "temperature": 0, "reasoning_effort": None,
        "timeout_seconds": 1, "extra_headers": {}, "input_cost_per_million": None,
        "output_cost_per_million": None,
    })()


class _Spec:
    task_id = "Science/Example"


class TrustedRuntimeIdentityTests(unittest.TestCase):
    @staticmethod
    def _resign_descriptor(descriptor):
        identity = {
            key: value for key, value in descriptor.items()
            if key != "fingerprint_sha256"
        }
        payload = json.dumps(
            identity, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        descriptor["fingerprint_sha256"] = hashlib.sha256(payload).hexdigest()
        return descriptor

    def test_unconfigured_evaluator_uses_invoking_virtualenv_entrypoint(self):
        entrypoint = "/tmp/example-oracle/bin/python"
        with patch.dict(os.environ, {}, clear=True), patch.object(
            evaluate.sys, "executable", entrypoint
        ):
            self.assertEqual(evaluate._trusted_python(), entrypoint)

    def test_runtime_fingerprint_is_path_free_and_install_location_invariant(self):
        with patch("sle.runtime_identity.importlib.metadata.version", return_value="1.2.3"):
            first = current_runtime_descriptor(("example-package",))
            with patch("sle.runtime_identity.sys.executable", "/another/host/python"):
                second = current_runtime_descriptor(("example-package",))
        self.assertEqual(first, second)
        rendered = json.dumps(first, sort_keys=True)
        self.assertNotIn("executable", rendered)
        self.assertNotIn("/another/host", rendered)
        self.assertEqual(len(first["fingerprint_sha256"]), 64)

    def test_runtime_descriptor_rejects_host_path_and_nul_fields(self):
        mutations = {
            "distribution name": lambda row: row["distributions"].update(
                {"host/path": "1.0"}
            ),
            "implementation": lambda row: row.update({"implementation": "cpython/host"}),
            "python_version": lambda row: row.update({"python_version": "3.8.20\0host"}),
            "cache_tag": lambda row: row.update({"cache_tag": "cpython\\host"}),
            "soabi": lambda row: row.update({"soabi": "/host/cpython-38"}),
        }
        for label, mutate in mutations.items():
            with self.subTest(field=label):
                descriptor = current_runtime_descriptor(())
                mutate(descriptor)
                self._resign_descriptor(descriptor)
                with self.assertRaisesRegex(ValueError, "path-free"):
                    validate_runtime_descriptor(descriptor)

    def test_manifest_separates_path_free_search_and_trusted_evaluator_runtimes(self):
        descriptor = current_runtime_descriptor(())
        runtime = TrustedRuntime("/secret/host/oracle/bin/python", descriptor)
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            common, "task_contract_sha256", return_value="a" * 64
        ), patch.object(
            common, "task_package_sha256", return_value="b" * 64
        ), patch.object(
            common, "runtime_source_sha256", return_value="c" * 64
        ):
            manifest = common.ensure_run_manifest(
                Path(temporary), spec=_Spec(), llm=_Client(),
                algorithm="greedy_rewrite", seed=0, feedback_mode="normal",
                resume=False, trusted_runtime=runtime,
            )
        rendered = json.dumps(manifest, sort_keys=True)
        self.assertEqual(manifest["trusted_evaluator_runtime"], descriptor)
        self.assertNotIn("executable", manifest["runtime_environment"])
        self.assertNotIn("/secret/host", rendered)

    def test_greedy_run_freezes_runtime_into_manifest_request_and_evaluator_call(self):
        descriptor = current_runtime_descriptor(())
        runtime = TrustedRuntime("/private/oracle/bin/python", descriptor)
        calls = []

        def evaluate_candidate(_spec, _candidate, timeout_s, *, trusted_runtime=None):
            calls.append((timeout_s, trusted_runtime))
            return {"combined_score": 0.1, "valid": 1.0}

        spec = find_task("LennardJonesCluster")
        with tempfile.TemporaryDirectory() as temporary, patch(
            "sle.algorithms.evolve.resolve_trusted_runtime", return_value=runtime
        ), patch(
            "sle.algorithms.evolve.evaluate_candidate", side_effect=evaluate_candidate
        ):
            workdir = Path(temporary)
            greedy_rewrite(
                spec, _Client(), budget=0, timeout_s=20, workdir=workdir,
                log_fn=lambda _line: None,
            )
            manifest = json.loads((workdir / "run_manifest.json").read_text())
            request_path = next((workdir / "evaluation_ledger/requests").glob("*.json"))
            request = json.loads(request_path.read_text())["request"]
            receipt_path = next((workdir / "evaluation_ledger/receipts").glob("*.json"))
            receipt = json.loads(receipt_path.read_text())
            trajectory = json.loads((workdir / "trajectory.jsonl").read_text())

        self.assertEqual(manifest["trusted_evaluator_runtime"], descriptor)
        self.assertEqual(
            request["trusted_evaluator_runtime_sha256"], runtime.fingerprint_sha256
        )
        self.assertNotIn("trusted_evaluator_runtime_sha256", receipt["metrics"])
        self.assertNotIn("trusted_evaluator_runtime_sha256", trajectory["metrics"])
        self.assertEqual(calls, [(20, runtime)])

    def test_task_runtime_identity_includes_declared_transitive_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            (task / "verification").mkdir()
            (task / "verification/requirements.txt").write_text(
                "qutip==4.7.6\n", encoding="utf-8"
            )
            names = task_runtime_distributions(task)
        self.assertEqual(names, ("numpy", "packaging", "qutip", "scipy"))

    def test_pymatching_runtime_identity_includes_trusted_oracle_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            (task / "verification").mkdir()
            (task / "verification/requirements.txt").write_text(
                "pymatching==2.4.0\n", encoding="utf-8"
            )
            names = task_runtime_distributions(task)
        self.assertEqual(names, (
            "contourpy", "cycler", "fonttools", "importlib-resources",
            "kiwisolver", "matplotlib", "networkx", "numpy", "packaging",
            "pillow", "pymatching", "pyparsing", "python-dateutil", "scipy",
            "six", "zipp",
        ))

    def test_nmrsim_runtime_identity_includes_trusted_oracle_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary)
            (task / "verification").mkdir()
            (task / "verification/requirements.txt").write_text(
                "nmrsim==0.6.0\n", encoding="utf-8"
            )
            names = task_runtime_distributions(task)
        self.assertEqual(names, (
            "contourpy", "cycler", "fonttools", "importlib-metadata",
            "importlib-resources", "kiwisolver", "llvmlite", "matplotlib",
            "nmrsim", "numba", "numpy", "numpy-groupies", "packaging",
            "pillow", "pyparsing", "python-dateutil", "scipy", "six", "sparse",
            "typing-extensions", "zipp",
        ))

    def test_runtime_change_is_a_resume_binding_failure(self):
        first_descriptor = current_runtime_descriptor(())
        second_descriptor = deepcopy(first_descriptor)
        second_descriptor["fingerprint_sha256"] = "f" * 64
        first = TrustedRuntime("/one/python", first_descriptor)
        second = TrustedRuntime("/two/python", second_descriptor)
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            common, "task_contract_sha256", return_value="a" * 64
        ), patch.object(
            common, "task_package_sha256", return_value="b" * 64
        ), patch.object(
            common, "runtime_source_sha256", return_value="c" * 64
        ):
            workdir = Path(temporary)
            common.ensure_run_manifest(
                workdir, spec=_Spec(), llm=_Client(), algorithm="greedy_rewrite",
                seed=0, feedback_mode="normal", resume=False,
                trusted_runtime=first,
            )
            with self.assertRaisesRegex(ValueError, "manifest"):
                common.ensure_run_manifest(
                    workdir, spec=_Spec(), llm=_Client(), algorithm="greedy_rewrite",
                    seed=0, feedback_mode="normal", resume=True,
                    trusted_runtime=second,
                )

    def test_legacy_manifest_with_evaluator_state_cannot_resume(self):
        descriptor = current_runtime_descriptor(())
        runtime = TrustedRuntime("/one/python", descriptor)
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            common, "task_contract_sha256", return_value="a" * 64
        ), patch.object(
            common, "task_package_sha256", return_value="b" * 64
        ), patch.object(
            common, "runtime_source_sha256", return_value="c" * 64
        ):
            workdir = Path(temporary)
            common.ensure_run_manifest(
                workdir, spec=_Spec(), llm=_Client(), algorithm="greedy_rewrite",
                seed=0, feedback_mode="normal", resume=False,
                trusted_runtime=runtime,
            )
            path = workdir / "run_manifest.json"
            legacy = json.loads(path.read_text())
            legacy.pop("trusted_evaluator_runtime")
            path.write_text(json.dumps(legacy), encoding="utf-8")
            (workdir / "evaluation_ledger").mkdir()
            with self.assertRaisesRegex(ValueError, "manifest"):
                common.ensure_run_manifest(
                    workdir, spec=_Spec(), llm=_Client(), algorithm="greedy_rewrite",
                    seed=0, feedback_mode="normal", resume=True,
                    trusted_runtime=runtime,
                )

    def test_driver_runtime_mismatch_fails_as_infrastructure(self):
        spec = find_task("LennardJonesCluster")
        actual = evaluate.resolve_trusted_runtime(spec.task_dir)
        mismatched_descriptor = deepcopy(actual.descriptor)
        mismatched_descriptor["fingerprint_sha256"] = "0" * 64
        result = evaluate.evaluate_candidate(
            spec, spec.initial_program_path, timeout_s=20,
            trusted_runtime=TrustedRuntime(actual.executable, mismatched_descriptor),
        )
        self.assertEqual(result.get("infrastructure_failure"), 1.0)
        self.assertEqual(result["error_message"], "trusted evaluator runtime binding mismatch")


if __name__ == "__main__":
    unittest.main()
