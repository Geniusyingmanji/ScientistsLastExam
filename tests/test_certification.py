from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from frontier_science.certification import certification_status, load_certification
from frontier_science.evaluate import evaluate_candidate
from frontier_science.registry import find_task, list_tasks


def load_oracle(task_id: str):
    spec = find_task(task_id, include_uncertified=True)
    path = spec.task_dir / "verification/evaluator.py"
    module_spec = importlib.util.spec_from_file_location("test_oracle_" + spec.task_dir.name, path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class CertificationPolicyTests(unittest.TestCase):
    def test_default_registry_is_certified_only(self):
        tasks = list_tasks()
        self.assertEqual(len(tasks), 7)
        self.assertTrue(all(certification_status(s.task_id) == "certified" for s in tasks))
        self.assertEqual(len(list_tasks(None)), 50)

    def test_quarantined_clone_group_is_not_default_visible(self):
        default_ids = {s.task_id for s in list_tasks()}
        records = load_certification()["tasks"]
        clone_ids = {k for k, v in records.items() if v.get("duplicate_group") == "generic_trig_8d_v1"}
        self.assertEqual(len(clone_ids), 5)
        self.assertTrue(clone_ids.isdisjoint(default_ids))
        self.assertTrue(all(certification_status(task) == "quarantined" for task in clone_ids))

    def test_certified_tasks_have_stable_citation_ids(self):
        records = load_certification()["tasks"]
        for spec in list_tasks():
            ids = records[spec.task_id].get("citation_ids", [])
            self.assertTrue(ids, spec.task_id)
            self.assertTrue(all(":" in identifier for identifier in ids), spec.task_id)


class ScientificInvariantTests(unittest.TestCase):
    def test_lennard_jones_rigid_motion_invariance(self):
        oracle = load_oracle("Chemistry/LennardJonesCluster")
        rng = np.random.default_rng(3)
        x = rng.normal(size=(13, 3))
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        y = x @ q + np.array([4.0, -2.0, 1.5])
        self.assertAlmostEqual(oracle.lj_energy(x), oracle.lj_energy(y), places=9)

    def test_spin_glass_global_flip_invariance(self):
        oracle = load_oracle("Physics/SpinGlassGroundState")
        j = oracle.make_instance(32, 0)
        s = np.where(np.arange(32) % 2, 1.0, -1.0)
        self.assertAlmostEqual(oracle.energy(j, s), oracle.energy(j, -s), places=12)
        for key, bits in oracle.REFERENCE_WITNESSES.items():
            n, seed = key
            witness = np.array([1.0 if bit == "1" else -1.0 for bit in bits])
            self.assertEqual(witness.shape, (n,))
            self.assertAlmostEqual(oracle.energy(oracle.make_instance(n, seed), witness),
                                   oracle.REFERENCE[key]["e_best"], places=5)

    def test_poisson_manufactured_solution_residual_converges(self):
        oracle = load_oracle("ScientificComputing/PoissonSolver2D")
        u, f, h = oracle.u_true_grid(), oracle.f_grid(), oracle._h()
        padded = np.pad(u, 1)
        discrete = (4 * u - padded[:-2, 1:-1] - padded[2:, 1:-1]
                    - padded[1:-1, :-2] - padded[1:-1, 2:]) / h**2
        self.assertLess(np.linalg.norm(discrete - f) / np.linalg.norm(f), 0.03)

    def test_matrix_tensor_accepts_schoolbook_and_rejects_perturbation(self):
        oracle = load_oracle("Algorithm/MatrixMultiplicationRank")
        m = n = p = 2
        rank = m * n * p
        u = np.zeros((rank, m * n)); v = np.zeros((rank, n * p)); w = np.zeros((m * p, rank))
        r = 0
        for i in range(m):
            for k in range(n):
                for j in range(p):
                    u[r, i*n+k] = v[r, k*p+j] = w[i*p+j, r] = 1
                    r += 1
        self.assertTrue(oracle.verify_decomposition(u, v, w, m, n, p)[0])
        u[0, 0] += 0.1
        self.assertFalse(oracle.verify_decomposition(u, v, w, m, n, p)[0])

    def test_cap_verifier_accepts_hypercube_and_rejects_line(self):
        oracle = load_oracle("Mathematics/CapSet")
        cube = [[(x >> i) & 1 for i in range(4)] for x in range(16)]
        self.assertTrue(oracle.verify_cap(cube, 4)[0])
        self.assertFalse(oracle.verify_cap([[0, 0], [1, 0], [2, 0]], 2)[0])

    def test_circle_packing_geometry(self):
        oracle = load_oracle("Optimization/CirclePacking")
        centers = np.array([[1, 1], [3, 1], [1, 3], [3, 3]], dtype=float)
        self.assertTrue(oracle.check_packing(4, centers, 4)["valid"])
        centers[1] = [2.5, 1]
        self.assertFalse(oracle.check_packing(4, centers, 4)["valid"])

    def test_thin_film_zero_thickness_matches_bare_interface(self):
        oracle = load_oracle("Photonics/MultilayerThinFilm")
        spectrum = oracle._reflectance_spectrum([0], [0.0])
        self.assertTrue(np.allclose(spectrum, oracle._R_BARE, atol=1e-12))

    def test_interventional_scm_is_acyclic_and_exact_model_scores_one(self):
        oracle = load_oracle("CausalDiscovery/InterventionalSCM")
        for index, seed in enumerate(oracle.WORLD_SEEDS):
            coefficients, order, noise = oracle._make_world(
                seed, null=index == oracle.NULL_WORLD
            )
            ordered = coefficients[np.ix_(order, order)]
            self.assertTrue(np.allclose(np.tril(ordered), 0.0))
            adjacency = np.abs(coefficients) > 1e-12
            edge_f1, coefficient_score, mechanism = oracle._mechanism_metrics(
                coefficients, adjacency, coefficients
            )
            self.assertAlmostEqual(edge_f1, 1.0)
            self.assertAlmostEqual(coefficient_score, 1.0)
            self.assertAlmostEqual(mechanism, 1.0)
            self.assertAlmostEqual(
                oracle._prediction_score(coefficients, coefficients), 1.0
            )
            samples = oracle._simulate(
                coefficients, order, noise, 16, seed, intervention=(3, 1.25)
            )
            self.assertTrue(np.all(samples[:, 3] == 1.25))

    def test_interventional_scm_budget_violation_fails_closed(self):
        spec = find_task("CausalDiscovery/InterventionalSCM", include_uncertified=True)
        source = """
import numpy as np
def discover_mechanism(n, observe, intervene, budget):
    try:
        for _ in range(budget + 1):
            observe(32)
    except Exception:
        pass
    return {"adjacency": np.zeros((n,n)), "coefficients": np.zeros((n,n)),
            "abstain": True, "confidence": 0.0}
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=20)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertTrue(all(not row["valid"] for row in metrics["per_world"]))
        self.assertTrue(all("budget exceeded" in row["reason"] for row in metrics["per_world"]))

    def test_lyapunov_oracle_measures_closed_loop_feedback(self):
        oracle = load_oracle("DynamicalSystems/LyapunovControl")
        # Cancellation plus damping makes the sampled closed loop locally stable. Its exact
        # exponent differs slightly from -gain because feedback is held for each RK4 step;
        # an open-loop-only variational equation would instead report strong instability.
        gain = 1.0

        def controller(state):
            x, y, z = np.asarray(state, dtype=float)
            plant = np.array([
                oracle.SIGMA * (y - x),
                x * (oracle.RHO - z) - y,
                x * y - oracle.BETA * z,
            ])
            return -plant - gain * np.array([x, y, z])

        mle, _ = oracle._compute_mle(controller, n_steps=2000,
                                     initial_state=np.zeros(3), burn_in_steps=0)
        self.assertLess(mle, -0.8)
        self.assertGreater(mle, -1.1)

    def test_lyapunov_oracle_rejects_nonfinite_control(self):
        oracle = load_oracle("DynamicalSystems/LyapunovControl")
        with self.assertRaisesRegex(ValueError, "three finite values"):
            oracle._compute_mle(lambda _state: np.array([np.nan, 0.0, 0.0]),
                                n_steps=10, burn_in_steps=0)


if __name__ == "__main__":
    unittest.main()
