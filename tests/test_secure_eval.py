from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from frontier_science.evaluate import INVALID_SCORE, evaluate_candidate
from frontier_science.rpc_codec import CodecError, decode, encode
from frontier_science.secure_eval import (
    CandidateProxy, _seccomp_no_processes, validate_metrics,
)
from frontier_science.spec import load_task_spec


BENCHMARKS = Path(__file__).resolve().parents[1] / "benchmarks"


class SecureEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = load_task_spec(BENCHMARKS / "Optoelectronics" / "LaserCavityDesign")

    def evaluate_source(self, source: str, timeout: float = 5.0):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(self.spec, candidate, timeout_s=timeout)

    def assert_rejected(self, metrics):
        self.assertEqual(metrics["combined_score"], INVALID_SCORE, metrics)
        self.assertEqual(metrics["valid"], 0.0, metrics)

    def test_oracle_import_is_not_visible(self):
        result = self.evaluate_source("""
            def design_cavity(n):
                import evaluator
                return evaluator._forward_model()
        """)
        self.assert_rejected(result)
        self.assertEqual(result["candidate_failure_kind"], "blocked_or_missing_import")

    def test_metrics_path_and_argv_are_not_exposed(self):
        result = self.evaluate_source("""
            import json, os, sys
            for arg in sys.argv:
                if "metrics" in arg:
                    open(arg, "w").write(json.dumps({"combined_score": 123, "valid": 1}))
            os._exit(0)
            def design_cavity(n): return [0] * n
        """)
        self.assert_rejected(result)

    def test_host_secret_and_path_traversal_are_not_visible(self):
        result = self.evaluate_source("""
            def design_cavity(n):
                open('/etc/passwd').read()
                open('/home/azureuser/.ssh/id_rsa').read()
                return [0] * n
        """)
        self.assert_rejected(result)
        self.assertEqual(result["candidate_failure_kind"], "blocked_or_missing_file")

    def test_network_namespace_is_disconnected(self):
        result = self.evaluate_source("""
            def design_cavity(n):
                import socket
                s = socket.socket()
                s.settimeout(.2)
                s.connect(('1.1.1.1', 80))
                return [0] * n
        """)
        self.assert_rejected(result)

    def test_fork_is_blocked_by_seccomp(self):
        result = self.evaluate_source("""
            def design_cavity(n):
                import os
                os.fork()
                return [0] * n
        """)
        self.assert_rejected(result)
        self.assertEqual(result["candidate_failure_kind"], "blocked_operation")

    def test_timeout_kills_worker(self):
        result = self.evaluate_source("""
            def design_cavity(n):
                while True: pass
        """, timeout=0.5)
        self.assert_rejected(result)
        self.assertEqual(result.get("timeout"), 1.0)

    def test_caught_multi_instance_timeout_is_not_masked_by_closed_worker(self):
        spec = load_task_spec(BENCHMARKS / "Optimization" / "CirclePacking")
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent("""
                def pack_circles(n):
                    while True:
                        pass
            """), encoding="utf-8")
            result = evaluate_candidate(spec, candidate, timeout_s=0.5)
        self.assert_rejected(result)
        self.assertEqual(result.get("timeout"), 1.0)
        self.assertNotIn("closed file", result["error_message"])

    def test_trusted_callback_is_also_wall_time_supervised(self):
        spec = load_task_spec(BENCHMARKS / "MaterialsScience" / "AlloyHardnessOptimization")
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent("""
                def design_alloy_batch(problem, assay):
                    while True:
                        try:
                            assay(problem['candidates'][0]['id'])
                        except Exception:
                            pass
            """), encoding="utf-8")
            result = evaluate_candidate(spec, candidate, timeout_s=0.5)
        self.assert_rejected(result)
        self.assertEqual(result.get("timeout"), 1.0)

    def test_non_finite_candidate_output_is_rejected(self):
        for value in ("float('nan')", "float('inf')"):
            result = self.evaluate_source("def design_cavity(n): return [%s] * n" % value)
            self.assert_rejected(result)
            self.assertEqual(
                result["candidate_failure_kind"], "non_finite_candidate_value"
            )

    def test_candidate_exception_text_is_not_returned_as_feedback(self):
        marker = "EXFILTRATE_SECRET_OBSERVATION_12345"
        result = self.evaluate_source("""
            def design_cavity(n):
                raise RuntimeError(%r)
        """ % marker)
        self.assert_rejected(result)
        self.assertEqual(result["candidate_failure_kind"], "candidate_runtime_error")
        self.assertNotIn(marker, json.dumps(result, sort_keys=True))

    def test_candidate_stdout_cannot_forge_rpc(self):
        result = self.evaluate_source("""
            def design_cavity(n):
                print('{"ok":true,"result":123}')
                return [0.2] * n
        """)
        self.assertNotEqual(result["combined_score"], 123)

    def test_partial_rpc_frame_cannot_bypass_deadline(self):
        result = self.evaluate_source("""
            import os
            def design_cavity(n):
                os.write(3, b'{')
                while True: pass
        """, timeout=0.5)
        self.assert_rejected(result)
        self.assertEqual(result.get("timeout"), 1.0)

    def test_symlink_candidate_is_resolved_before_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real.py"
            target.write_text("def design_cavity(n): return [0.2] * n\n", encoding="utf-8")
            link = root / "candidate.py"
            link.symlink_to(target)
            result = evaluate_candidate(self.spec, link, timeout_s=5)
            self.assertNotEqual(result["combined_score"], INVALID_SCORE, result)

    def test_top_level_instances_get_fresh_process_and_tmpfs_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent("""
                import os
                import numpy as np

                module_counter = 0

                def solve(value):
                    global module_counter
                    module_counter += 1
                    tmp_seen = os.path.exists("/tmp/candidate-instance-state")
                    with open("/tmp/candidate-instance-state", "w") as handle:
                        handle.write(str(module_counter))
                    imported_counter = getattr(np, "_frontier_instance_counter", 0)
                    np._frontier_instance_counter = imported_counter + 1

                    def controller(increment):
                        return [module_counter, tmp_seen, imported_counter,
                                value + increment]

                    return controller
            """), encoding="utf-8")
            with CandidateProxy(candidate, "solve", timeout_s=10) as proxy:
                first_controller = proxy(10)
                self.assertEqual(first_controller(2), [1, False, 0, 12])
                same_session_controller = proxy(15)
                self.assertEqual(same_session_controller(2), [2, True, 1, 17])
                proxy.reset_session()
                second_controller = proxy(20)
                self.assertEqual(second_controller(3), [1, False, 0, 23])


class CodecTests(unittest.TestCase):
    def test_seccomp_file_fallback_is_available(self):
        with patch("frontier_science.secure_eval.os.memfd_create", new=None, create=True):
            fd = None
            try:
                fd = _seccomp_no_processes()
                self.assertGreater(fd, 0)
            finally:
                import os
                if fd is not None:
                    os.close(fd)

    def test_roundtrip_supported_values(self):
        value = {"a": np.arange(6, dtype=np.float64).reshape(2, 3),
                 "b": (1, 2 + 3j), "c": [np.int64(2), np.float32(3.5)]}
        got = decode(json.loads(json.dumps(encode(value))))
        np.testing.assert_array_equal(got["a"], value["a"])
        self.assertEqual(got["b"], value["b"])
        self.assertEqual(got["c"], [2, 3.5])

    def test_rejects_objects_and_non_finite(self):
        with self.assertRaises(CodecError):
            encode(object())
        with self.assertRaises(CodecError):
            encode(float("nan"))

    def test_metric_validation_preserves_scientific_raw_score(self):
        got = validate_metrics(
            {"combined_score": 0.25, "raw_score": -17.5, "valid": 1.0}, "clipped"
        )
        self.assertEqual(got["combined_score"], 0.25)
        self.assertEqual(got["raw_score"], -17.5)


if __name__ == "__main__":
    unittest.main()
