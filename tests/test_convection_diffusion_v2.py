from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/Engineering/ConvectionDiffusionOpt"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _oracle():
    return _load(
        TASK / "verification/evaluator.py", "convection_diffusion_v2_test_oracle"
    )


def _calibration():
    return _load(
        ROOT / "scripts/calibrate_convection_diffusion_v2.py",
        "convection_diffusion_v2_test_calibration",
    )


def _independent_solve(parameters, positions, strengths, grid_n):
    n = int(grid_n)
    spacing = 1.0 / (n - 1)
    kx, ky, vx, vy, loss = map(float, parameters)
    coordinates = np.linspace(0.0, 1.0, n)
    xx, yy = np.meshgrid(coordinates, coordinates, indexing="ij")
    source = np.zeros((n, n))
    for position, strength in zip(positions, strengths):
        source += float(strength) * np.exp(
            -0.5 * ((xx - position[0]) ** 2 + (yy - position[1]) ** 2)
            / 0.055**2
        )
    source[[0, -1], :] = 0.0
    source[:, [0, -1]] = 0.0
    matrix = lil_matrix((n * n, n * n))
    rhs = source.ravel().copy()
    for i in range(n):
        for j in range(n):
            row = i * n + j
            if i in (0, n - 1) or j in (0, n - 1):
                matrix[row, row] = 1.0
                rhs[row] = 0.0
                continue
            matrix[row, row] = (
                2.0 * kx / spacing**2 + 2.0 * ky / spacing**2
                + abs(vx) / spacing + abs(vy) / spacing + loss
            )
            matrix[row, (i - 1) * n + j] = (
                -kx / spacing**2 - max(vx, 0.0) / spacing
            )
            matrix[row, (i + 1) * n + j] = (
                -kx / spacing**2 + min(vx, 0.0) / spacing
            )
            matrix[row, i * n + j - 1] = (
                -ky / spacing**2 - max(vy, 0.0) / spacing
            )
            matrix[row, i * n + j + 1] = (
                -ky / spacing**2 + min(vy, 0.0) / spacing
            )
    return np.asarray(spsolve(matrix.tocsc(), rhs)).reshape((n, n))


class _ReferencePolicy:
    def __init__(self, oracle):
        self.oracle = oracle
        self.index = 0

    def __call__(self, *_args):
        specs = list(self.oracle.DEVELOPMENT_SPECS) + list(
            self.oracle.HELDOUT_SPECS
        )
        world = self.oracle._world(specs[self.index])
        self.index += 1
        return self.oracle._reference_submission(world)


class ConvectionDiffusionV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _oracle()
        cls.calibration = _calibration()

    def test_baseline_reference_and_metric_sealing(self):
        oracle = self.oracle
        baseline = oracle.evaluate(lambda *_args: {
            "parameters": np.zeros(5),
            "source_positions": np.zeros((4, 2)),
            "source_strengths": np.zeros(4),
            "confidence": 0.0,
            "abstain": True,
        })
        reference = oracle.evaluate(_ReferencePolicy(oracle))
        self.assertTrue(oracle.CONVECTION_DIFFUSION_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_SPECS), 6)
        self.assertEqual(len(oracle.HELDOUT_SPECS), 5)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(reference["valid"], 1.0)
        for key in (
            "combined_score", "heldout_policy_score", "robustness_score",
            "heldout_robustness_score", "mechanism_score",
            "heldout_mechanism_score",
        ):
            self.assertAlmostEqual(reference[key], 1.0)
        visible = search_visible_metrics(reference)
        self.assertEqual(
            set(visible), {"combined_score", "valid", "feasibility_rate", "raw_score"}
        )

    def test_public_solver_matches_independent_equation_assembly(self):
        oracle = self.oracle
        rng = np.random.default_rng(20260723)
        for grid_n in (13, 19):
            parameters = (
                oracle.PARAMETER_BOUNDS[:, 0]
                + rng.uniform(size=5)
                * (oracle.PARAMETER_BOUNDS[:, 1] - oracle.PARAMETER_BOUNDS[:, 0])
            )
            positions = rng.uniform(0.10, 0.90, size=(3, 2))
            strengths = rng.uniform(0.2, 1.6, size=3)
            production = oracle.solve_public(
                parameters, positions, strengths, grid_n
            )
            independent = _independent_solve(
                parameters, positions, strengths, grid_n
            )
            self.assertLess(
                float(np.max(np.abs(production - independent))), 2.0e-12
            )

    def test_charged_laboratory_is_deterministic_and_counts_budget(self):
        oracle = self.oracle
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        first = oracle._ThermalLaboratory(world)
        second = oracle._ThermalLaboratory(world)
        query_one, query_two = self.calibration.EXPERIMENT_PLAN
        first_one = first.observe(*query_one)
        second_one = second.observe(*query_one)
        first_two = first.observe(*query_two)
        self.assertTrue(np.array_equal(
            first_one["temperature"], second_one["temperature"]
        ))
        self.assertEqual(first_one["budget_cost"], 7)
        self.assertEqual(first_two["budget_cost"], 5)
        self.assertEqual(first_two["budget_used"], 12)
        with self.assertRaises(RuntimeError):
            first.observe(*query_two)
        self.assertTrue(first.violated)

    def test_malformed_artifacts_fail_closed(self):
        oracle = self.oracle
        factories = (
            lambda *_args: None,
            lambda *_args: {
                "parameters": np.full(5, np.nan),
                "source_positions": np.full((4, 2), 0.5),
                "source_strengths": np.ones(4),
                "confidence": 0.5, "abstain": False,
            },
            lambda *_args: {
                "parameters": np.mean(oracle.PARAMETER_BOUNDS, axis=1),
                "source_positions": np.full((4, 2), 0.5),
                "source_strengths": np.ones(4),
                "confidence": 0.5, "abstain": False,
            },
            lambda *_args: {
                "parameters": np.mean(oracle.PARAMETER_BOUNDS, axis=1),
                "source_positions": np.full((4, 2), 0.4),
                "source_strengths": np.full(4, 3.0),
                "confidence": 0.5, "abstain": False,
            },
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["raw_score"], 0.0)

    def test_calibration_invariants(self):
        report = self.calibration.calibrate()
        self.assertTrue(report["execution_passed"])
        classical = report["truth_blind_two_experiment_policy"]
        one = report["truth_blind_one_experiment_policy"]
        self.assertGreater(classical["combined_score"], 0.80)
        self.assertLess(classical["combined_score"], 0.97)
        self.assertGreater(classical["heldout_policy_score"], 0.80)
        self.assertLess(classical["heldout_policy_score"], 0.97)
        self.assertLess(one["combined_score"], 1.0e-8)
        self.assertLess(one["heldout_policy_score"], 1.0e-8)
        self.assertEqual(classical["development_mean_budget_units"], 12.0)
        self.assertEqual(classical["heldout_mean_budget_units"], 12.0)
        for key in (
            "identifiability_checks", "single_experiment_ambiguity_checks",
            "unsupported_resolvability_checks", "independent_equation_checks",
        ):
            self.assertTrue(all(row["passed"] for row in report[key]))

    def test_caught_overbudget_secure_evaluation_fails_closed(self):
        spec = find_task(
            "HeatTransfer/ConvectionDiffusionOpt", include_uncertified=True
        )
        source = textwrap.dedent("""
            import numpy as np

            def design_thermal_policy(
                grid_shape, parameter_names, parameter_bounds,
                design_specification, experiment, budget_units,
            ):
                del grid_shape, parameter_bounds, design_specification, budget_units
                source_positions = np.asarray(((0.2, 0.5), (0.5, 0.5), (0.8, 0.5)))
                source_strengths = np.asarray((1.5, 1.25, 1.4))
                sensors = np.asarray([(x, 0.5) for x in np.linspace(0.08, 0.92, 24)])
                try:
                    experiment(source_positions, source_strengths, sensors)
                    experiment(source_positions, source_strengths, sensors)
                except Exception:
                    pass
                return {
                    'parameters': np.zeros(len(parameter_names)),
                    'source_positions': np.zeros((4, 2)),
                    'source_strengths': np.zeros(4),
                    'confidence': 0.0, 'abstain': True,
                }
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=180)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(
            metrics["error_message"],
            "candidate invalid: invalid_experiment_request",
        )
        self.assertEqual(metrics["candidate_world_call_count"], 11)

    def test_all_worlds_get_fresh_candidate_process_and_tmpfs(self):
        spec = find_task(
            "HeatTransfer/ConvectionDiffusionOpt", include_uncertified=True
        )
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def design_thermal_policy(
                grid_shape, parameter_names, parameter_bounds,
                design_specification, experiment, budget_units,
            ):
                global module_counter
                del grid_shape, parameter_bounds, design_specification, budget_units
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/convection-world-state')
                with open('/tmp/convection-world-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_convection_world_counter', 0)
                np._convection_world_counter = imported_counter + 1
                experiment(
                    np.asarray(((0.25, 0.25),)), np.asarray((1.0,)),
                    np.asarray(((0.25, 0.25), (0.25, 0.75),
                                (0.75, 0.25), (0.75, 0.75))),
                )
                confidence = (
                    0.1 * module_counter + 0.2 * int(tmp_seen)
                    + 0.3 * imported_counter
                )
                return {
                    'parameters': np.zeros(len(parameter_names)),
                    'source_positions': np.zeros((4, 2)),
                    'source_strengths': np.zeros(4),
                    'confidence': confidence, 'abstain': True,
                }
        """)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=180)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["candidate_world_call_count"], 11)
        self.assertEqual(metrics["candidate_world_valid_rate"], 1.0)
        self.assertTrue(all(
            math.isclose(row["confidence"], 0.1) for row in metrics["per_world"]
        ))

    def test_legacy_driver_uses_v2_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics_path = Path(tmp) / "metrics.json"
            process = subprocess.run(
                [
                    sys.executable, str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate", str(TASK / "solution.py"),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=str(ROOT), check=False, capture_output=True, text=True,
                timeout=120,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["raw_score"], 0.0)
        self.assertNotIn("error_message", metrics)


if __name__ == "__main__":
    unittest.main()
