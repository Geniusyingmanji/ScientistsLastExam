"""Certificate pins for LyapunovDecayCertificate."""
from __future__ import annotations

import copy
import importlib.util
import itertools
import json
import subprocess
import tempfile
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/Engineering/LyapunovDecayCertificate"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _char_poly(mode):
    trace = mode[0][0] + mode[1][1] + mode[2][2]
    m01 = mode[0][0] * mode[1][1] - mode[0][1] * mode[1][0]
    m02 = mode[0][0] * mode[2][2] - mode[0][2] * mode[2][0]
    m12 = mode[1][1] * mode[2][2] - mode[1][2] * mode[2][1]
    det = (
        mode[0][0] * (mode[1][1] * mode[2][2] - mode[1][2] * mode[2][1])
        - mode[0][1] * (mode[1][0] * mode[2][2] - mode[1][2] * mode[2][0])
        + mode[0][2] * (mode[1][0] * mode[2][1] - mode[1][1] * mode[2][0])
    )
    return (Fraction(1), -trace, m01 + m02 + m12, -det)


def _permute(mode, perm):
    return [[mode[perm[i]][perm[j]] for j in range(3)] for i in range(3)]


def _is_cyclic(gram):
    return (
        gram[0][0] == gram[1][1] == gram[2][2]
        and gram[0][1] == gram[0][2] == gram[1][2]
        and gram[0][1] != 0
    )


class LyapunovDecayCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "lyapunov_oracle")
        cls.baseline = _load(TASK / "solution.py", "lyapunov_baseline")
        cls.reference = _load(
            TASK / "verification/reference_lyapunov.py", "lyapunov_reference"
        )
        cls.constant = _load(
            TASK / "references/constant_probe.py", "lyapunov_constant"
        )
        cls.grid = _load(TASK / "references/grid_probe.py", "lyapunov_grid")
        cls.cyclic = _load(
            TASK / "references/cyclic_probe.py", "lyapunov_cyclic"
        )

    def test_shortcut_candidates_run_without_sibling_files(self):
        instance = self.evaluator.public_instance(self.evaluator.INSTANCES[0])
        for name in ("cyclic_probe.py", "grid_probe.py"):
            with self.subTest(candidate=name), tempfile.TemporaryDirectory() as directory:
                candidate = Path(directory) / "candidate.py"
                candidate.write_bytes((TASK / "references" / name).read_bytes())
                result = subprocess.run(
                    [sys.executable, "-I", "-c",
                     "import json,runpy,sys; "
                     "f=runpy.run_path(sys.argv[1])['build_lyapunov']; "
                     "print(json.dumps(f(json.load(sys.stdin))))", str(candidate)],
                    input=json.dumps(instance), text=True, capture_output=True, timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("alpha", json.loads(result.stdout))

    def test_instances_are_three_dimensional(self):
        for instance in self.evaluator.INSTANCES:
            self.assertEqual(self.evaluator.STATE_DIMENSION, 3)
            modes = self.evaluator._parse_modes(instance["mode_matrices"])
            self.assertGreaterEqual(len(modes), 3)
            for mode in modes:
                self.assertEqual(len(mode), 3)
                self.assertEqual(len(mode[0]), 3)
            public = self.evaluator.public_instance(instance)
            self.assertEqual(public["state_dimension"], 3)

    def test_published_modes_are_not_permutation_conjugates(self):
        for instance in self.evaluator.INSTANCES:
            modes = self.evaluator._parse_modes(instance["mode_matrices"])
            polys = [_char_poly(mode) for mode in modes]
            with self.subTest(instance=instance["name"]):
                self.assertEqual(len(set(polys)), len(polys))
                for left, right in itertools.combinations(modes, 2):
                    for perm in itertools.permutations(range(3)):
                        self.assertNotEqual(_permute(left, perm), right)

    def test_identity_is_a_lyapunov_function_but_a_shear_proves_more(self):
        instance = self.evaluator.INSTANCES[0]
        modes = self.evaluator._parse_modes(instance["mode_matrices"])
        identity = [
            [Fraction(1), Fraction(0), Fraction(0)],
            [Fraction(0), Fraction(1), Fraction(0)],
            [Fraction(0), Fraction(0), Fraction(1)],
        ]
        holds, _ = self.evaluator.certificate_holds(modes, identity, Fraction(1, 10000))
        self.assertTrue(holds)
        fails, _ = self.evaluator.certificate_holds(modes, identity, Fraction(2, 5))
        self.assertFalse(fails)
        # Two distinct planes, not the cyclic line p12=p13=p23.
        sheared = [
            [Fraction(1), Fraction(1, 3), Fraction(-1, 2)],
            [Fraction(1, 3), Fraction(1), Fraction(0)],
            [Fraction(-1, 2), Fraction(0), Fraction(1)],
        ]
        self.assertFalse(_is_cyclic(sheared))
        better, _ = self.evaluator.certificate_holds(modes, sheared, Fraction(2, 5))
        self.assertTrue(better)

    def test_reference_optimizes_rate_for_its_returned_gram(self):
        instance = self.evaluator.INSTANCES[0]
        result = self.reference.build_lyapunov(self.evaluator.public_instance(instance))
        modes = self.evaluator._parse_modes(instance["mode_matrices"])
        gram = [
            [Fraction(*result["p11"]), Fraction(*result["p12"]), Fraction(*result["p13"])],
            [Fraction(*result["p12"]), Fraction(*result["p22"]), Fraction(*result["p23"])],
            [Fraction(*result["p13"]), Fraction(*result["p23"]), Fraction(*result["p33"])],
        ]
        rate = Fraction(*result["alpha"])
        self.assertTrue(self.evaluator.certificate_holds(modes, gram, rate)[0])
        self.assertFalse(
            self.evaluator.certificate_holds(modes, gram, rate + Fraction(1, 10000))[0]
        )

    def test_catalog_contains_cyclic_symmetric_grams(self):
        cyclic = [gram for gram in self.reference.CATALOG if _is_cyclic(gram)]
        self.assertGreater(len(cyclic), 0)
        self.assertLess(len(cyclic), len(self.reference.CATALOG))

    def test_public_modes_do_not_alias_the_oracle_instances(self):
        instance = self.evaluator.INSTANCES[0]
        original = copy.deepcopy(instance["mode_matrices"])
        try:
            public = self.evaluator.public_instance(instance)
            public["mode_matrices"][0][0][0][0] = 99999
            self.assertEqual(instance["mode_matrices"], original)
        finally:
            instance["mode_matrices"] = original

    def test_floats_are_rejected_and_score_zero(self):
        def floats(_instance):
            return {
                "p11": 1.0, "p12": 0.0, "p13": 0.0,
                "p22": 1.0, "p23": 0.0, "p33": 1.0,
                "alpha": 0.0001,
            }

        metrics = self.evaluator.evaluate(floats)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_two_by_two_keys_without_the_third_row_score_zero(self):
        def old_shape(_instance):
            return {"p11": 1, "p12": 0, "p22": 1, "alpha": [1, 10000]}

        metrics = self.evaluator.evaluate(old_shape)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_identity_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.build_lyapunov)
        reference = self.evaluator.evaluate(self.reference.build_lyapunov)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(reference["combined_score"], 0.3)
        self.assertLess(reference["combined_score"], 0.8)

    def test_constant_grid_and_cyclic_line_cannot_beat_reference(self):
        reference = self.evaluator.evaluate(self.reference.build_lyapunov)
        constant = self.evaluator.evaluate(self.constant.build_lyapunov)
        grid = self.evaluator.evaluate(self.grid.build_lyapunov)
        cyclic = self.evaluator.evaluate(self.cyclic.build_lyapunov)
        self.assertGreater(reference["combined_score"], constant["combined_score"])
        self.assertGreater(reference["combined_score"], grid["combined_score"])
        self.assertGreater(
            reference["combined_score"] - grid["combined_score"], 0.05
        )
        self.assertEqual(cyclic["valid"], 1.0)
        self.assertLess(cyclic["combined_score"], reference["combined_score"])
        self.assertLess(
            cyclic["combined_score"], 0.8 * reference["combined_score"]
        )

    def test_malformed_submissions_score_zero_without_raising(self):
        metrics = self.evaluator.evaluate(lambda *_args: "not a mapping")
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)

    def test_this_is_not_a_pendulum_controller_or_a_bell_certificate(self):
        from sle.registry import find_task
        spec = find_task("ControlTheory/LyapunovDecayCertificate", include_uncertified=True)
        pendulum = find_task("ControlTheory/InvertedPendulumSwingUp", include_uncertified=True)
        bell = find_task("QuantumFoundations/BellBoundCertificate", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "build_lyapunov")
        self.assertNotEqual(spec.task_dir, pendulum.task_dir)
        self.assertNotEqual(spec.task_dir, bell.task_dir)


if __name__ == "__main__":
    unittest.main()
