from __future__ import annotations

import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "benchmarks/QuantumChemistry/HartreeFockSCF"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HartreeFockV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle = _load(
            TASK / "verification/evaluator.py", "hartree_fock_v2_test_oracle"
        )
        cls.baseline = _load(
            TASK / "solution.py", "hartree_fock_v2_test_baseline"
        )
        cls.calibration = _load(
            ROOT / "scripts/calibrate_hartree_fock_v2.py",
            "hartree_fock_v2_test_calibration",
        )

    def test_baseline_reference_headroom_stability_and_metric_sealing(self):
        oracle = self.oracle
        baseline = oracle.evaluate(self.baseline.solve_restricted_hf)
        reference = oracle.evaluate(oracle.reference_policy)

        self.assertTrue(oracle.HARTREE_FOCK_V2)
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 3)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["feasibility_rate"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["development_stability_rate"], 0.75)
        self.assertLess(baseline["heldout_stability_rate"], 1.0)
        self.assertGreater(baseline["heldout_policy_score"], 0.80)
        self.assertLess(baseline["heldout_policy_score"], 0.90)

        self.assertEqual(reference["valid"], 1.0)
        self.assertGreater(reference["combined_score"], 0.999)
        self.assertGreater(reference["robustness_score"], 0.999)
        self.assertGreater(reference["heldout_policy_score"], 0.99)
        self.assertGreater(reference["heldout_robustness_score"], 0.99)
        self.assertEqual(reference["development_stability_rate"], 1.0)
        self.assertEqual(reference["heldout_stability_rate"], 1.0)
        self.assertEqual(reference["candidate_problem_call_count"], 28)

        baseline_rows = {row["name"]: row for row in baseline["per_instance"]}
        reference_rows = {row["name"]: row for row in reference["per_instance"]}
        for name, minimum_gap, maximum_baseline_curvature in (
            ("dev_h8_ring_symmetry_breaking_sto3g", 0.03, -0.20),
            ("heldout_h4_ring_symmetry_breaking_sto3g", 0.05, -0.20),
        ):
            self.assertGreater(
                baseline_rows[name]["energy_error_hartree"], minimum_gap
            )
            self.assertLess(
                baseline_rows[name]["minimum_stability_curvature"],
                maximum_baseline_curvature,
            )
            self.assertFalse(baseline_rows[name]["internally_stable"])
            self.assertGreater(
                reference_rows[name]["minimum_stability_curvature"], 0.05
            )
            self.assertTrue(reference_rows[name]["internally_stable"])

        visible = search_visible_metrics(reference)
        for key in (
            "robustness_score", "heldout_policy_score",
            "heldout_robustness_score", "development_shifted_score",
            "development_representation_invariance_score",
            "development_stability_rate", "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_independent_equations_reproduce_all_reference_conditions(self):
        oracle = self.oracle
        calibration = self.calibration
        for instance in oracle.INSTANCES:
            for shifted, coefficients, expected_energy in (
                (False, instance["reference_coefficients"],
                 instance["reference_energy"]),
                (True, instance["shifted_reference_coefficients"],
                 instance["shifted_reference_energy"]),
            ):
                problem = oracle._public_problem(instance, shifted=shifted)
                row = calibration._independent_diagnostics(problem, coefficients)
                self.assertLess(
                    abs(row["energy_hartree"] - expected_energy), 2.0e-10
                )
                self.assertLess(row["overlap_orthonormality_error"], 2.0e-8)
                self.assertLess(row["electron_count_error"], 2.0e-8)
                self.assertLess(row["density_idempotency_error"], 2.0e-8)
                self.assertLess(row["scf_residual"], 5.0e-8)

    def test_representation_changes_preserve_energy_and_mapped_density(self):
        oracle = self.oracle
        for instance in oracle.INSTANCES:
            nominal_problem = oracle._public_problem(instance)
            nominal = oracle._evaluate_problem(
                oracle.reference_policy,
                nominal_problem,
                instance["reference_energy"],
            )
            nominal_density = (
                2.0 * nominal["coefficients"] @ nominal["coefficients"].T
            )
            for transform in (
                instance["permutation_transform"],
                instance["dense_transform"],
            ):
                transformed_problem = oracle._transform_problem(
                    nominal_problem, transform
                )
                transformed = oracle._evaluate_problem(
                    oracle.reference_policy,
                    transformed_problem,
                    instance["reference_energy"],
                )
                mapped = transform @ transformed["coefficients"]
                mapped_density = 2.0 * mapped @ mapped.T
                self.assertLess(
                    abs(
                        nominal["energy_hartree"]
                        - transformed["energy_hartree"]
                    ),
                    2.0e-8,
                )
                self.assertLess(
                    np.linalg.norm(mapped_density - nominal_density)
                    / np.linalg.norm(nominal_density),
                    2.0e-5,
                )

    def test_better_than_stored_reference_is_accepted_and_clipped(self):
        oracle = self.oracle
        instance = oracle.DEVELOPMENT_INSTANCES[0]
        problem = oracle._public_problem(instance)
        deliberately_looser_reference = instance["reference_energy"] + 1.0e-4
        result = oracle._evaluate_problem(
            oracle.reference_policy,
            problem,
            deliberately_looser_reference,
        )
        self.assertLess(
            result["energy_hartree"], deliberately_looser_reference
        )
        self.assertEqual(result["energy_score"], 1.0)
        self.assertTrue(result["valid"])

    def test_invalid_artifacts_fail_closed(self):
        oracle = self.oracle

        def baseline(problem):
            return self.baseline.solve_restricted_hf(problem)

        factories = (
            lambda problem: np.zeros((
                len(problem["overlap"]),
                int(problem["occupied_orbital_count"]) + 1,
            )),
            lambda problem: np.full((
                len(problem["overlap"]),
                int(problem["occupied_orbital_count"]),
            ), np.nan),
            lambda problem: baseline(problem).astype(complex) + 1.0e-3j,
            lambda problem: 1.01 * baseline(problem),
            lambda problem: np.zeros((
                len(problem["overlap"]),
                int(problem["occupied_orbital_count"]),
            )),
        )
        for factory in factories:
            metrics = oracle.evaluate(factory)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(metrics["feasibility_rate"], 0.0)
            self.assertTrue(all(
                not row["valid"]
                for row in metrics["per_instance"]
                if row["split"] == "development"
            ))

    def test_sealed_failure_does_not_change_nominal_score_or_validity(self):
        oracle = self.oracle
        baseline_policy = self.baseline.solve_restricted_hf
        nominal_shapes = {
            tuple(instance["overlap"].shape) for instance in oracle.INSTANCES
        }

        def nominal_only(problem):
            # Geometry shifts have a different nuclear repulsion/coordinate pair;
            # dense transforms change the overlap diagonal.  Deliberately reject
            # every non-nominal representation while preserving all nominal calls.
            for instance in oracle.INSTANCES:
                nominal = oracle._public_problem(instance)
                if (
                    problem["overlap"].shape in nominal_shapes
                    and np.array_equal(problem["overlap"], nominal["overlap"])
                    and np.array_equal(
                        problem["core_hamiltonian"],
                        nominal["core_hamiltonian"],
                    )
                ):
                    return baseline_policy(problem)
            raise ValueError("sealed representation intentionally unsupported")

        baseline = oracle.evaluate(baseline_policy)
        metrics = oracle.evaluate(nominal_only)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], baseline["combined_score"])
        self.assertEqual(metrics["raw_score"], baseline["raw_score"])
        self.assertEqual(metrics["robustness_score"], 0.0)
        self.assertTrue(all(row["valid"] for row in metrics["per_instance"]))
        self.assertTrue(all(
            not row["shifted_valid"]
            for row in metrics["per_instance"]
        ))

    def test_all_twenty_eight_calls_get_fresh_sandbox_sessions(self):
        spec = find_task(
            "QuantumChemistry/HartreeFockSCF", include_uncertified=True
        )
        source = textwrap.dedent("""
            import os
            import numpy as np

            module_counter = 0

            def solve_restricted_hf(problem):
                global module_counter
                module_counter += 1
                tmp_seen = os.path.exists('/tmp/hf-instance-state')
                with open('/tmp/hf-instance-state', 'w') as handle:
                    handle.write(str(module_counter))
                imported_counter = getattr(np, '_hf_instance_counter', 0)
                np._hf_instance_counter = imported_counter + 1

                overlap = np.asarray(problem['overlap'], dtype=float)
                core = np.asarray(problem['core_hamiltonian'], dtype=float)
                eri = np.asarray(
                    problem['electron_repulsion_integrals'], dtype=float
                )
                occupied = int(problem['occupied_orbital_count'])
                values, vectors = np.linalg.eigh(overlap)
                orthogonalizer = (
                    vectors * (1.0 / np.sqrt(values))
                ) @ vectors.T
                if module_counter != 1 or tmp_seen or imported_counter != 0:
                    return orthogonalizer[:, :occupied + 1]

                _, rotation = np.linalg.eigh(
                    orthogonalizer @ core @ orthogonalizer
                )
                coefficients = orthogonalizer @ rotation[:, :occupied]
                focks = []
                errors = []
                for _ in range(100):
                    density = 2.0 * coefficients @ coefficients.T
                    coulomb = np.einsum(
                        'rs,pqrs->pq', density, eri, optimize=True
                    )
                    exchange = np.einsum(
                        'rs,prqs->pq', density, eri, optimize=True
                    )
                    fock = core + coulomb - 0.5 * exchange
                    error = fock @ density @ overlap - overlap @ density @ fock
                    focks.append(fock.copy())
                    errors.append(error.ravel().copy())
                    if len(focks) > 8:
                        focks.pop(0)
                        errors.pop(0)
                    if len(focks) >= 2:
                        count = len(focks)
                        pulay = np.empty((count + 1, count + 1))
                        for i in range(count):
                            for j in range(count):
                                pulay[i, j] = np.dot(errors[i], errors[j])
                        pulay[:count, count] = -1.0
                        pulay[count, :count] = -1.0
                        pulay[count, count] = 0.0
                        rhs = np.zeros(count + 1)
                        rhs[count] = -1.0
                        try:
                            weights = np.linalg.solve(pulay, rhs)[:count]
                            fock = sum(
                                weights[i] * focks[i]
                                for i in range(count)
                            )
                        except np.linalg.LinAlgError:
                            pass
                    _, rotation = np.linalg.eigh(
                        orthogonalizer @ fock @ orthogonalizer
                    )
                    updated = orthogonalizer @ rotation[:, :occupied]
                    updated_density = 2.0 * updated @ updated.T
                    coefficients = updated
                    if (
                        np.linalg.norm(updated_density - density) < 1e-10
                        and np.linalg.norm(error) < 1e-9
                    ):
                        break
                return coefficients
        """)
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=60)

        self.assertEqual(metrics["candidate_problem_call_count"], 28)
        self.assertEqual(metrics["candidate_instance_valid_rate"], 1.0)
        self.assertNotIn("module state leak", metrics.get("error_message", ""))
        self.assertTrue(all(
            "wrong shape" not in row.get("reason", "")
            for row in metrics["per_instance"]
        ))


if __name__ == "__main__":
    unittest.main()
