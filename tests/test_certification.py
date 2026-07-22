from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from frontier_science.certification import certification_status, load_certification
from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
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
        self.assertEqual(len(list_tasks(None)), 51)

    def test_manifest_explicitly_covers_inventory(self):
        inventory_ids = {spec.task_id for spec in list_tasks(None)}
        manifest_ids = set(load_certification()["tasks"])
        self.assertEqual(manifest_ids, inventory_ids)

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

    def test_active_law_exact_mechanisms_and_abstentions_score_one(self):
        oracle = load_oracle("DynamicalSystems/ActiveLawDiscovery")
        self.assertEqual(len(oracle.DEVELOPMENT_SPECS), 7)
        self.assertEqual(len(oracle.VALIDATION_SPECS), 6)
        for specs in (oracle.DEVELOPMENT_SPECS, oracle.VALIDATION_SPECS):
            for spec in specs:
                world = oracle._world(spec)
                if world["kind"] == "in_library":
                    support = np.abs(world["coefficients"]) > 0.0
                    metrics = oracle._mechanism_metrics(
                        world, world["coefficients"], support, False
                    )
                    self.assertAlmostEqual(metrics["mechanism_score"], 1.0)
                    self.assertAlmostEqual(
                        oracle._prediction_score(world, world["coefficients"]), 1.0
                    )
                else:
                    zeros = np.zeros_like(world["coefficients"])
                    metrics = oracle._mechanism_metrics(
                        world, zeros, np.zeros_like(zeros, dtype=bool), True
                    )
                    self.assertAlmostEqual(metrics["mechanism_score"], 1.0)
                    self.assertTrue(metrics["correct_abstention"])

        def always_abstain(n_states, term_names, experiment, _budget):
            experiment(np.zeros(n_states), np.zeros(8), 8)
            shape = (len(term_names), n_states)
            return {
                "coefficients": np.zeros(shape),
                "support": np.zeros(shape),
                "confidence": 0.0,
                "abstain": True,
            }

        baseline = oracle.evaluate(always_abstain)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertNotIn("mechanism_score", search_visible_metrics(baseline))
        self.assertNotIn("robustness_score", search_visible_metrics(baseline))
        self.assertNotIn("per_world", search_visible_metrics(baseline))

    def test_active_law_budget_violation_fails_closed(self):
        spec = find_task(
            "DynamicalSystems/ActiveLawDiscovery", include_uncertified=True
        )
        source = """
import numpy as np
def discover_law(n_states, term_names, experiment, budget_units):
    try:
        for _ in range(budget_units + 1):
            experiment(np.zeros(n_states), np.zeros(16), 16)
    except Exception:
        pass
    shape = (len(term_names), n_states)
    return {"coefficients": np.zeros(shape), "support": np.zeros(shape),
            "confidence": 0.0, "abstain": True}
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=30)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertTrue(all(not row["valid"] for row in metrics["per_world"]))
        self.assertTrue(all(
            "budget exceeded" in row["reason"] for row in metrics["per_world"]
        ))

    def test_reaction_v2_exact_mechanisms_refusal_and_metric_sealing(self):
        oracle = load_oracle("ChemicalKinetics/ReactionMechanismFitting")
        self.assertEqual(oracle.N_SPECIES, 4)
        self.assertEqual(oracle.N_REACTIONS, 12)
        self.assertEqual(len(oracle.DEVELOPMENT_SPECS), 6)
        self.assertEqual(len(oracle.HELDOUT_SPECS), 5)
        for specs in (oracle.DEVELOPMENT_SPECS, oracle.HELDOUT_SPECS):
            for spec in specs:
                world = oracle._world(spec)
                if world["kind"] == "in_library":
                    metrics = oracle._mechanism_metrics(
                        world,
                        world["log_a"],
                        world["activation_energy"],
                        world["support"],
                        False,
                    )
                    self.assertAlmostEqual(metrics["mechanism_score"], 1.0)
                    self.assertAlmostEqual(oracle._prediction_score(
                        world,
                        world["log_a"],
                        world["activation_energy"],
                        world["support"],
                        False,
                    ), 1.0)
                    self.assertAlmostEqual(oracle._prediction_score(
                        world,
                        world["log_a"],
                        world["activation_energy"],
                        world["support"],
                        True,
                    ), 1.0)
                else:
                    zeros = np.zeros(oracle.N_REACTIONS)
                    metrics = oracle._mechanism_metrics(
                        world, zeros, zeros,
                        np.zeros(oracle.N_REACTIONS, dtype=bool), True,
                    )
                    self.assertAlmostEqual(metrics["mechanism_score"], 1.0)
                    self.assertTrue(metrics["correct_refusal"])

        def always_abstain(species, pairs, experiment, _budget):
            experiment(
                405.0, np.full(len(species), 1.0 / len(species)),
                np.asarray((0.0, 0.02, 0.08, 0.3, 1.0, 4.0)), [0],
            )
            return {
                "support": np.zeros(len(pairs)),
                "log_pre_exponential": np.zeros(len(pairs)),
                "activation_energy_j_mol": np.zeros(len(pairs)),
                "confidence": 0.0,
                "abstain": True,
            }

        baseline = oracle.evaluate(always_abstain)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertAlmostEqual(baseline["combined_score"], 0.0)
        self.assertAlmostEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 0.0)
        shown = search_visible_metrics(baseline)
        self.assertNotIn("mechanism_score", shown)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("development_prediction_score", shown)
        self.assertNotIn("per_world", shown)

    def test_reaction_v2_partial_assays_are_deterministic_and_charged(self):
        oracle = load_oracle("ChemicalKinetics/ReactionMechanismFitting")
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        initial = np.asarray((0.52, 0.27, 0.14, 0.07))
        times = np.asarray((0.0, 0.005, 0.015, 0.05, 0.15, 0.5, 2.0, 10.0))
        first = oracle._Laboratory(world)
        second = oracle._Laboratory(world)
        one = first.experiment(345.0, initial, times, [1])
        repeated = second.experiment(345.0, initial, times, [1])
        self.assertEqual(one["concentrations"].shape, (8, 1))
        self.assertEqual(one["budget_cost"], 3)
        self.assertTrue(np.array_equal(one["concentrations"], repeated["concentrations"]))
        two = first.experiment(465.0, initial, times, [2, 3])
        self.assertEqual(two["concentrations"].shape, (8, 2))
        self.assertEqual(two["budget_cost"], 5)
        self.assertEqual(first.used, 8)
        self.assertTrue(np.allclose(
            np.sum(oracle._simulate(world, 405.0, initial, times), axis=1),
            1.0,
            atol=1e-12,
        ))

    def test_reaction_v2_budget_violation_fails_closed(self):
        spec = find_task(
            "ChemicalKinetics/ReactionMechanismFitting", include_uncertified=True
        )
        source = """
import numpy as np
def discover_mechanism(species, pairs, experiment, budget_units):
    times = np.linspace(0.0, 10.0, 8)
    initial = np.full(len(species), 1.0 / len(species))
    try:
        for _ in range(3):
            experiment(405.0, initial, times, [0, 1])
    except Exception:
        pass
    return {"support": np.zeros(len(pairs)),
            "log_pre_exponential": np.zeros(len(pairs)),
            "activation_energy_j_mol": np.zeros(len(pairs)),
            "confidence": 0.0, "abstain": True}
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=60)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertTrue(all(not row["valid"] for row in metrics["per_world"]))
        self.assertTrue(all(
            "budget exceeded" in row["reason"] for row in metrics["per_world"]
        ))

    def test_reaction_v2_nonfinite_and_inconsistent_claims_fail_closed(self):
        oracle = load_oracle("ChemicalKinetics/ReactionMechanismFitting")
        common = {
            "support": np.zeros(oracle.N_REACTIONS),
            "log_pre_exponential": np.zeros(oracle.N_REACTIONS),
            "activation_energy_j_mol": np.zeros(oracle.N_REACTIONS),
            "confidence": 0.0,
            "abstain": True,
        }
        candidates = []
        for update in (
            {"confidence": np.nan},
            {"support": np.zeros(oracle.N_REACTIONS - 1)},
            {"support": np.full(oracle.N_REACTIONS, 0.5)},
            {"support": np.r_[1.0, np.zeros(oracle.N_REACTIONS - 1)]},
            {"abstain": False},
        ):
            result = dict(common)
            result.update(update)
            candidates.append(result)
        for result in candidates:
            metrics = oracle.evaluate(
                lambda *_args, result=result: result
            )
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(not row["valid"] for row in metrics["per_world"]))

    def test_gravity_v2_exact_sources_refusal_physics_and_metric_sealing(self):
        oracle = load_oracle("Geophysics/GravityInversion")
        self.assertEqual(len(oracle.DEVELOPMENT_SPECS), 6)
        self.assertEqual(len(oracle.HELDOUT_SPECS), 5)
        for specs in (oracle.DEVELOPMENT_SPECS, oracle.HELDOUT_SPECS):
            for spec in specs:
                world = oracle._world(spec)
                if world["kind"] == "in_library":
                    mechanism = oracle._body_matching_metrics(
                        world, world["bodies"], False
                    )
                    self.assertAlmostEqual(mechanism["mechanism_score"], 1.0)
                    self.assertAlmostEqual(
                        oracle._prediction_score(world, world["bodies"], False),
                        1.0,
                    )
                    self.assertAlmostEqual(
                        oracle._prediction_score(world, world["bodies"], True),
                        1.0,
                    )
                else:
                    mechanism = oracle._body_matching_metrics(
                        world, np.empty((0, 5)), True
                    )
                    self.assertAlmostEqual(mechanism["mechanism_score"], 1.0)
                    self.assertTrue(mechanism["correct_refusal"])

        # The field is linear in density and odd under density-sign reversal.
        body = np.asarray((4300.0, 1400.0, 1200.0, 600.0, 350.0))
        stations = np.linspace(-500.0, 10500.0, 41)
        positive = oracle.rectangle_field([body], stations, 300.0)
        negative = oracle.rectangle_field(
            [body * np.asarray((1.0, 1.0, 1.0, 1.0, -1.0))],
            stations,
            300.0,
        )
        self.assertTrue(np.allclose(positive, -negative, atol=1e-12))

        def always_abstain(profile, depth, measure, _budget):
            del depth
            measure(np.linspace(profile[0], profile[1], 8), 500.0)
            return {"bodies": [], "confidence": 0.0, "abstain": True}

        baseline = oracle.evaluate(always_abstain)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertAlmostEqual(baseline["combined_score"], 0.0)
        self.assertAlmostEqual(baseline["robustness_score"], 0.0)
        shown = search_visible_metrics(baseline)
        self.assertNotIn("mechanism_score", shown)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("development_prediction_score", shown)
        self.assertNotIn("per_world", shown)

    def test_gravity_v2_surveys_are_deterministic_and_charged(self):
        oracle = load_oracle("Geophysics/GravityInversion")
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        stations = np.linspace(0.0, 10000.0, 20)
        first = oracle._Survey(world)
        second = oracle._Survey(world)
        one = first.measure(stations, 800.0)
        repeated = second.measure(stations, 800.0)
        self.assertEqual(one["gravity_mgal"].shape, (20,))
        self.assertEqual(one["budget_cost"], 6)
        self.assertTrue(np.array_equal(
            one["gravity_mgal"], repeated["gravity_mgal"]
        ))
        two = first.measure(np.linspace(0.0, 10000.0, 8), 0.0)
        self.assertEqual(two["budget_cost"], 3)
        self.assertEqual(first.used, 9)
        self.assertGreater(
            float(np.sqrt(np.mean(one["gravity_mgal"] ** 2))),
            10.0 * float(np.mean(one["noise_std_mgal"])),
        )

    def test_gravity_v2_budget_violation_fails_closed(self):
        spec = find_task("Geophysics/GravityInversion", include_uncertified=True)
        source = """
import numpy as np
def discover_bodies(profile, depth, measure, budget_units):
    del profile, depth, budget_units
    try:
        for _ in range(5):
            measure(np.linspace(0.0, 10000.0, 20), 500.0)
    except Exception:
        pass
    return {"bodies": [], "confidence": 0.0, "abstain": True}
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=90)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertTrue(all(not row["valid"] for row in metrics["per_world"]))
        self.assertTrue(all(
            "budget exceeded" in row["reason"] for row in metrics["per_world"]
        ))

    def test_gravity_v2_nonfinite_shape_bounds_and_abstention_fail_closed(self):
        oracle = load_oracle("Geophysics/GravityInversion")
        common = {"bodies": [], "confidence": 0.0, "abstain": True}
        candidates = []
        for update in (
            {"confidence": np.nan},
            {"bodies": [[1.0, 2.0]]},
            {"bodies": [[4000.0, 1200.0, 800.0, 400.0, np.nan]]},
            {"bodies": [[100.0, 1200.0, 800.0, 400.0, 300.0]]},
            {"bodies": [[4000.0, 1200.0, 800.0, 400.0, 20.0]]},
            {"bodies": [[4000.0, 1200.0, 800.0, 400.0, 300.0]]},
            {"abstain": False},
        ):
            result = dict(common)
            result.update(update)
            candidates.append(result)
        for result in candidates:
            metrics = oracle.evaluate(
                lambda *_args, result=result: result
            )
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(not row["valid"] for row in metrics["per_world"]))

    def test_optimal_experiment_design_reference_and_sealed_shift(self):
        oracle = load_oracle("BayesianInference/OptimalExperimentDesign")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 6)
        self.assertEqual(len(oracle.VALIDATION_INSTANCES), 4)
        for instance in oracle.INSTANCES:
            reference = instance["reference"]
            n_parameters = instance["matrix"].shape[1]
            self.assertTrue(reference["converged"])
            self.assertLessEqual(
                reference["maximum_sensitivity"],
                n_parameters * (1.0 + oracle.REFERENCE_TOLERANCE),
            )
            self.assertEqual(
                np.linalg.matrix_rank(instance["matrix"]), n_parameters
            )

        def uniform(candidate_points, _feature_matrix, n_measurements):
            return np.rint(np.linspace(
                0, len(candidate_points) - 1, n_measurements
            )).astype(int)

        metrics = oracle.evaluate(uniform)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertGreater(metrics["combined_score"], 0.7)
        self.assertIn("robustness_score", metrics)
        self.assertNotIn("robustness_score", search_visible_metrics(metrics))
        self.assertNotIn("per_instance", search_visible_metrics(metrics))

        # D-optimal allocations are invariant to a nonsingular parameter transform.  Verify
        # both the selected-design efficiency and the numerical whitening used by the oracle.
        rng = np.random.default_rng(20260721)
        original = oracle.DEVELOPMENT_INSTANCES[0]["matrix"]
        transform = rng.normal(size=(original.shape[1], original.shape[1]))
        transform += np.eye(original.shape[1])
        transformed = original @ transform
        whitened_original = oracle._scaled_columns(original)
        whitened_transformed = oracle._scaled_columns(transformed)
        gram_original = whitened_original @ whitened_original.T
        gram_transformed = whitened_transformed @ whitened_transformed.T
        self.assertTrue(np.allclose(
            gram_original, gram_transformed, rtol=1e-8, atol=1e-8
        ))

    def test_optimal_experiment_design_nonfinite_indices_fail_closed(self):
        spec = find_task(
            "BayesianInference/OptimalExperimentDesign", include_uncertified=True
        )
        source = """
import numpy as np
def select_designs(candidate_points, feature_matrix, n_measurements):
    return np.full(n_measurements, np.nan)
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=20)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["validation_feasibility_rate"], 0.0)
        self.assertTrue(all(not row["valid"] for row in metrics["per_instance"]))

    def test_gate_synthesis_unitarity_phase_and_metric_sealing(self):
        oracle = load_oracle("QuantumControl/GateSynthesis")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        for instance in oracle.INSTANCES:
            pulse = np.zeros((instance["n_steps"], len(instance["controls"])))
            unitary = oracle._propagate(
                instance["drift"], instance["controls"], pulse, instance["dt"]
            )
            self.assertTrue(np.allclose(
                unitary.conj().T @ unitary,
                np.eye(len(unitary)), atol=1e-11, rtol=0.0,
            ))
            self.assertAlmostEqual(
                oracle._process_fidelity(
                    instance["target"], np.exp(0.37j) * instance["target"]
                ),
                1.0,
                places=12,
            )

        baseline = oracle.evaluate(
            lambda _drift, controls, _target, n_steps, _dt, _limit: np.zeros(
                (n_steps, len(controls))
            )
        )
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["valid"], 1.0)
        shown = search_visible_metrics(baseline)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("heldout_policy_score", shown)
        self.assertNotIn("per_instance", shown)

    def test_gate_synthesis_nonfinite_and_out_of_bound_fail_closed(self):
        oracle = load_oracle("QuantumControl/GateSynthesis")
        nonfinite = oracle.evaluate(
            lambda _drift, controls, _target, n_steps, _dt, _limit: np.full(
                (n_steps, len(controls)), np.nan
            )
        )
        outside = oracle.evaluate(
            lambda _drift, controls, _target, n_steps, _dt, limit: np.full(
                (n_steps, len(controls)), limit + 1.0
            )
        )
        for metrics in (nonfinite, outside):
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_opf_v2_reference_order_security_and_metric_sealing(self):
        oracle = load_oracle("PowerSystems/OptimalPowerFlow")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        for instance in oracle.INSTANCES:
            baseline = oracle._dispatch_metrics(instance, instance["baseline_dispatch"])
            nominal = oracle._dispatch_metrics(
                instance, instance["nominal_reference_dispatch"]
            )
            secure = oracle._dispatch_metrics(
                instance, instance["security_reference_dispatch"]
            )
            self.assertLessEqual(
                instance["nominal_reference_cost"],
                instance["security_reference_cost"] + 1e-7,
            )
            self.assertLessEqual(
                instance["security_reference_cost"], instance["baseline_cost"] + 1e-7
            )
            self.assertLessEqual(
                baseline["contingency_max_loading_ratio"], 1.0 + 1e-7
            )
            self.assertGreater(
                nominal["contingency_max_loading_ratio"], 1.0 + 1e-3
            )
            self.assertLessEqual(
                secure["contingency_max_loading_ratio"], 1.0 + 1e-7
            )

        def proportional(_n_bus, _generator_buses, demand, p_min, p_max, *_args):
            remaining = np.sum(demand) - np.sum(p_min)
            return p_min + remaining * (p_max - p_min) / np.sum(p_max - p_min)

        metrics = oracle.evaluate(proportional)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["mean_contingency_feasibility_rate"], 1.0)
        shown = search_visible_metrics(metrics)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("heldout_policy_score", shown)
        self.assertNotIn("per_instance", shown)

    def test_opf_v2_nonfinite_and_unbalanced_fail_closed(self):
        oracle = load_oracle("PowerSystems/OptimalPowerFlow")
        nonfinite = oracle.evaluate(
            lambda _n_bus, generator_buses, *_args: np.full(
                len(generator_buses), np.nan
            )
        )
        unbalanced = oracle.evaluate(
            lambda _n_bus, generator_buses, *_args: np.zeros(
                len(generator_buses)
            )
        )
        for metrics in (nonfinite, unbalanced):
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_truss_v2_topology_references_and_metric_sealing(self):
        oracle = load_oracle("StructuralEngineering/TrussWeightMinimization")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        for instance in oracle.INSTANCES:
            undirected = [
                tuple(sorted(map(int, pair))) for pair in instance["members"]
            ]
            self.assertEqual(len(undirected), len(set(undirected)))
            baseline = oracle._scenario_analysis(
                instance, instance["baseline_areas"]
            )
            nominal = oracle._scenario_analysis(
                instance, instance["nominal_reference_areas"]
            )
            self.assertTrue(baseline["feasible"])
            self.assertTrue(nominal["feasible"])
            for loads in instance["load_cases"]:
                mechanics = oracle._case_analysis(
                    instance, instance["baseline_areas"], loads
                )
                self.assertLessEqual(
                    mechanics["stiffness_symmetry_error"], 1e-10
                )
                self.assertLessEqual(
                    mechanics["force_equilibrium_error_lbs"], 1e-6
                )
            self.assertTrue(all(
                oracle._scenario_analysis(
                    instance, instance["baseline_areas"], shift, shift["name"]
                )["feasible"]
                for shift in oracle.SHIFT_SPECS
            ))
            self.assertTrue(all(
                oracle._scenario_analysis(
                    instance, instance["robust_reference_areas"], shift,
                    shift["name"],
                )["feasible"]
                for shift in oracle.SHIFT_SPECS
            ))
            self.assertTrue(any(
                not oracle._scenario_analysis(
                    instance, instance["nominal_reference_areas"], shift,
                    shift["name"],
                )["feasible"]
                for shift in oracle.SHIFT_SPECS
            ))

        def all_max(_nodes, members, _fixed, _loads, _modulus, _density,
                    _tension, _compression, _displacement, _area_min, area_max,
                    _inertia):
            return np.full(len(members), area_max)

        metrics = oracle.evaluate(all_max)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["mean_shifted_case_feasibility_rate"], 1.0)
        shown = search_visible_metrics(metrics)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("heldout_policy_score", shown)
        self.assertNotIn("per_instance", shown)

    def test_truss_v2_nonfinite_bounds_and_nominal_infeasibility_fail_closed(self):
        oracle = load_oracle("StructuralEngineering/TrussWeightMinimization")
        nonfinite = oracle.evaluate(
            lambda _nodes, members, *_args: np.full(len(members), np.nan)
        )
        outside = oracle.evaluate(
            lambda _nodes, members, *_args: np.full(len(members), -1.0)
        )
        minimum = oracle.evaluate(
            lambda _nodes, members, _fixed, _loads, _modulus, _density,
            _tension, _compression, _displacement, area_min, _area_max,
            _inertia: np.full(len(members), area_min)
        )
        for metrics in (nonfinite, outside, minimum):
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_antenna_v2_reference_tradeoff_invariance_and_metric_sealing(self):
        oracle = load_oracle("Electromagnetics/AntennaArraySynthesis")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        for instance in oracle.INSTANCES:
            self.assertEqual(
                sum(row["name"].startswith("element_failure_")
                    for row in instance["shift_scenarios"]),
                len(instance["positions_lambda"]),
            )
            self.assertGreater(
                instance["nominal_reference_metrics"]["quality_db"],
                instance["baseline_nominal_metrics"]["quality_db"],
            )
            self.assertGreater(
                instance["robust_reference_quality_db"],
                instance["baseline_robust_quality_db"],
            )
            translated = instance["positions_lambda"] + 3.17
            angles = instance["sidelobe_angles_deg"]
            original = abs(oracle._steering_matrix(
                instance["positions_lambda"], angles
            ) @ instance["nominal_reference_weights"])
            shifted = abs(oracle._steering_matrix(
                translated, angles
            ) @ instance["nominal_reference_weights"])
            self.assertTrue(np.allclose(original, shifted, atol=1e-12, rtol=0.0))

        def uniform(positions, steering, *_args):
            target = oracle._steering_matrix(positions, [steering])[0]
            return np.conj(target) / len(positions)

        baseline = oracle.evaluate(uniform)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        shown = search_visible_metrics(baseline)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("heldout_policy_score", shown)
        self.assertNotIn("per_instance", shown)

    def test_antenna_v2_zero_nonfinite_shape_and_excitation_fail_closed(self):
        oracle = load_oracle("Electromagnetics/AntennaArraySynthesis")
        zero = oracle.evaluate(
            lambda positions, *_args: np.zeros(len(positions), dtype=complex)
        )
        nonfinite = oracle.evaluate(
            lambda positions, *_args: np.full(len(positions), np.nan + 0j)
        )
        wrong = oracle.evaluate(lambda *_args: np.ones(1, dtype=complex))
        excessive = oracle.evaluate(
            lambda positions, *_args: np.eye(
                1, len(positions), dtype=complex
            )[0]
        )
        for metrics in (zero, nonfinite, wrong, excessive):
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

    def test_heat_exchanger_v2_references_physics_and_metric_sealing(self):
        oracle = load_oracle("Thermodynamics/HeatExchangerDesign")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 4)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 2)
        for instance in oracle.INSTANCES:
            baseline = oracle._baseline_archive(instance["problem"])
            nominal = oracle.REFERENCE_ARCHIVES[instance["name"]]
            robust = oracle.ROBUST_REFERENCE_ARCHIVES[instance["name"]]
            self.assertEqual(nominal.shape, (oracle.MAX_ARCHIVE_SIZE, 5))
            self.assertEqual(robust.shape, (oracle.MAX_ARCHIVE_SIZE, 5))
            self.assertTrue(np.array_equal(
                nominal,
                oracle._reference_archive(instance, "nominal"),
            ))
            anchors = oracle.CALIBRATED_ANCHORS[instance["name"]]
            self.assertGreater(
                anchors["reference_exact_hypervolume"],
                anchors["baseline_exact_hypervolume"],
            )
            self.assertGreater(
                anchors["reference_proxy_hypervolume"],
                anchors["baseline_proxy_hypervolume"],
            )
            _, baseline_exact, baseline_shifts = oracle._evaluate_archive(
                instance, baseline
            )
            _, nominal_exact, _ = oracle._evaluate_archive(instance, nominal)
            _, robust_exact, robust_shifts = oracle._evaluate_archive(instance, robust)
            self.assertTrue(all(row["feasible"] for row in baseline_exact))
            self.assertTrue(all(row["feasible"] for row in nominal_exact))
            self.assertTrue(all(row["feasible"] for row in robust_exact))
            self.assertTrue(all(
                all(row["feasible"] for row in records)
                for records in baseline_shifts + robust_shifts
            ))
            self.assertLessEqual(max(
                row["boundary_residual_k"]
                for records in (baseline_exact, nominal_exact, robust_exact)
                for row in records
            ), 1e-5)

            # Adding a dominated duplicate cannot improve two-objective hypervolume.
            records = list(nominal_exact)
            dominated = dict(records[0])
            dominated["heat_duty_w"] = 0.5 * records[0]["heat_duty_w"]
            dominated["annualized_cost_usd"] = 2.0 * records[0]["annualized_cost_usd"]
            augmented = records + [dominated, dict(records[0])]
            self.assertAlmostEqual(
                oracle._hypervolume(instance, records),
                oracle._hypervolume(instance, augmented),
                places=12,
            )

        def baseline_policy(problem):
            return oracle._baseline_archive(problem)

        metrics = oracle.evaluate(baseline_policy)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["feasibility_rate"], 1.0)
        shown = search_visible_metrics(metrics)
        for key in (
            "development_proxy_score", "heldout_exact_score",
            "robustness_score", "development_false_promotion_rate",
            "development_proxy_exact_rank_correlation", "per_instance",
        ):
            self.assertNotIn(key, shown)

    def test_heat_exchanger_v2_malformed_archives_fail_closed(self):
        oracle = load_oracle("Thermodynamics/HeatExchangerDesign")

        def invalid_policy(kind):
            def policy(problem):
                archive = oracle._baseline_archive(problem).copy()
                if kind == "nonfinite":
                    archive[0, 0] = np.nan
                elif kind == "wrong_shape":
                    return archive[:, :4]
                elif kind == "too_short":
                    return archive[:3]
                elif kind == "out_of_bounds":
                    archive[:, 0] = -1.0
                elif kind == "nonintegral":
                    archive[:, 2] += 0.5
                elif kind == "not_divisible":
                    archive[:, 4] = 4.0
                    archive[:, 2] = 25.0
                else:
                    raise AssertionError(kind)
                return archive
            return policy

        for kind in (
            "nonfinite", "wrong_shape", "too_short", "out_of_bounds",
            "nonintegral", "not_divisible",
        ):
            metrics = oracle.evaluate(invalid_policy(kind))
            self.assertEqual(metrics["valid"], 0.0, kind)
            self.assertEqual(metrics["combined_score"], 0.0, kind)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ), kind)

    def test_nmr_v2_exact_reference_refusal_and_metric_sealing(self):
        oracle = load_oracle("Spectroscopy/NMRSpectrumFitting")
        self.assertEqual(len(oracle.DEVELOPMENT_INSTANCES), 6)
        self.assertEqual(len(oracle.HELDOUT_INSTANCES), 4)
        self.assertEqual(
            sum(row["kind"] == "in_library" for row in oracle.INSTANCES), 6
        )

        def exact(x, spectrum):
            matches = [
                instance for instance in oracle.INSTANCES
                if np.array_equal(x, instance["x"])
                and np.array_equal(spectrum, instance["spectrum"])
            ]
            self.assertEqual(len(matches), 1)
            return oracle._reference_result(matches[0])

        reference = oracle.evaluate(exact)
        self.assertEqual(reference["valid"], 1.0)
        self.assertAlmostEqual(reference["combined_score"], 1.0)
        self.assertAlmostEqual(reference["robustness_score"], 1.0)
        self.assertAlmostEqual(reference["development_reconstruction_score"], 1.0)
        self.assertAlmostEqual(reference["heldout_reconstruction_score"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(reference["heldout_false_discovery_rate"], 0.0)

        def always_abstain(_x, _spectrum):
            return {
                "centers": [], "lorentzian_hwhm": [], "gaussian_sigma": [],
                "amplitudes": [], "lineshapes": [], "confidence": 0.0,
                "abstain": True,
            }

        baseline = oracle.evaluate(always_abstain)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertAlmostEqual(baseline["combined_score"], 0.0)
        self.assertAlmostEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 0.0)
        shown = search_visible_metrics(reference)
        self.assertNotIn("mechanism_score", shown)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("development_reconstruction_score", shown)
        self.assertNotIn("per_instance", shown)

    def test_nmr_v2_nonfinite_shape_bounds_and_labels_fail_closed(self):
        oracle = load_oracle("Spectroscopy/NMRSpectrumFitting")
        common = {
            "centers": [5.0], "lorentzian_hwhm": [0.05],
            "gaussian_sigma": [0.0], "amplitudes": [1.0],
            "lineshapes": ["lorentzian"], "confidence": 1.0,
            "abstain": False,
        }
        candidates = []
        for updates in (
            {"centers": [np.nan]},
            {"amplitudes": []},
            {"amplitudes": [-1.0]},
            {"lorentzian_hwhm": [1.0]},
            {"lorentzian_hwhm": [0.0], "gaussian_sigma": [0.0]},
            {"lorentzian_hwhm": [0.05], "gaussian_sigma": [0.001]},
            {"lineshapes": ["voigt"]},
            {"confidence": np.nan},
            {"abstain": True},
        ):
            result = dict(common)
            result.update(updates)
            candidates.append(result)
        for candidate in candidates:
            metrics = oracle.evaluate(
                lambda _x, _spectrum, result=candidate: result
            )
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_instance"]
            ))

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

    def test_neutron_diffusion_operator_is_symmetric_and_reference_is_reproducible(self):
        oracle = load_oracle("NuclearEngineering/NeutronDiffusionCriticality")
        uniform = np.full(oracle.N_ZONES, oracle.AVG_ENRICH_MAX)
        k_uniform = oracle._compute_keff(uniform)
        k_reference = oracle._compute_keff(oracle.REFERENCE_LOADING)
        self.assertAlmostEqual(float(np.mean(oracle.REFERENCE_LOADING)),
                               oracle.AVG_ENRICH_MAX, places=12)
        self.assertAlmostEqual(k_uniform, 0.9841790542, places=8)
        self.assertAlmostEqual(k_reference, 1.0591815191, places=8)
        self.assertAlmostEqual(k_reference - k_uniform, 0.0750024649, places=8)

        _, _, _, _, diffusion, absorption, _ = oracle._cross_sections(
            np.repeat(oracle.REFERENCE_LOADING,
                      oracle.N_MESH // oracle.N_ZONES)
        )
        h = oracle.SLAB_WIDTH / (oracle.N_MESH + 1)
        interface = 2 * diffusion[:-1] * diffusion[1:] / (
            diffusion[:-1] + diffusion[1:]
        )
        left = np.concatenate(([diffusion[0]], interface))
        right = np.concatenate((interface, [diffusion[-1]]))
        matrix = np.diag((left + right) / h**2 + absorption)
        matrix += np.diag(-interface / h**2, 1)
        matrix += np.diag(-interface / h**2, -1)
        self.assertTrue(np.allclose(matrix, matrix.T, atol=1e-14))

    def test_seismic_refraction_is_translation_invariant_and_layer_identifiable(self):
        oracle = load_oracle("Geophysics/SeismicInversion")
        profile = np.array([1800.0, 2350.0, 3000.0, 3850.0, 5000.0])
        offsets = np.linspace(200.0, 12000.0, 200)
        times = oracle.first_arrival_times(profile, offsets)
        perturbed = profile.copy()
        perturbed[2] += 120.0
        shifted_times = oracle.first_arrival_times(perturbed, offsets)
        self.assertGreater(float(np.max(np.abs(times - shifted_times))), 1e-4)

        sc = oracle.SCENARIOS[1]
        reconstructed_offsets = np.abs(sc["receivers"] - sc["sources"])
        self.assertTrue(np.allclose(reconstructed_offsets, sc["offsets"], atol=1e-12))
        self.assertTrue(np.allclose(
            oracle.first_arrival_times(sc["true_v"], reconstructed_offsets),
            sc["clean_times"],
            atol=1e-12,
        ))
        jacobian = []
        for layer in range(sc["n_layers"]):
            step = 1e-3 * sc["true_v"][layer]
            upper = sc["true_v"].copy()
            lower = sc["true_v"].copy()
            upper[layer] += step
            lower[layer] -= step
            jacobian.append((
                oracle.first_arrival_times(upper, reconstructed_offsets)
                - oracle.first_arrival_times(lower, reconstructed_offsets)
            ) / (2.0 * step))
        self.assertEqual(
            np.linalg.matrix_rank(np.column_stack(jacobian), tol=1e-12),
            sc["n_layers"],
        )

    def test_seismic_truth_and_baseline_scores_are_calibrated(self):
        oracle = load_oracle("Geophysics/SeismicInversion")
        for sc in oracle.SCENARIOS:
            truth = oracle._score_profile(sc, sc["true_v"])
            baseline = oracle._score_profile(sc, oracle._constant_velocity(sc))
            self.assertGreater(truth["development_score"], 0.99)
            self.assertAlmostEqual(truth["mechanism_score"], 1.0, places=12)
            self.assertAlmostEqual(truth["holdout_prediction_score"], 1.0, places=12)
            self.assertAlmostEqual(baseline["development_score"], 0.0, places=12)
            self.assertAlmostEqual(baseline["mechanism_score"], 0.0, places=12)
            self.assertAlmostEqual(baseline["holdout_prediction_score"], 0.0, places=12)

    def test_pendulum_down_is_stable_and_upright_is_unstable(self):
        oracle = load_oracle("ControlTheory/InvertedPendulumSwingUp")
        plant = oracle._plant_tuple()
        step = 1e-6

        def acceleration(theta):
            state = np.array([0.0, 0.0, theta, 0.0])
            return oracle.cart_pole_derivative(state, 0.0, plant)[3]

        down_derivative = (acceleration(step) - acceleration(-step)) / (2 * step)
        upright_derivative = (
            acceleration(np.pi + step) - acceleration(np.pi - step)
        ) / (2 * step)
        self.assertLess(down_derivative, 0.0)
        self.assertGreater(upright_derivative, 0.0)

    def test_pendulum_rk4_preserves_hanging_equilibrium(self):
        oracle = load_oracle("ControlTheory/InvertedPendulumSwingUp")
        state = np.zeros(4)
        for _ in range(100):
            state = oracle._rk4_step(state, 0.0, oracle._plant_tuple())
        self.assertTrue(np.allclose(state, np.zeros(4), atol=1e-12))


if __name__ == "__main__":
    unittest.main()
