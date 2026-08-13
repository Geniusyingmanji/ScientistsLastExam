from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from sle.certification import certification_status, load_certification
from sle.evaluate import INVALID_SCORE, evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task, list_tasks


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
        # Two of the seven - SpinGlassGroundState and PoissonSolver2D - were retired along with
        # the other saturated tasks. Certification says the task is sound; it says nothing about
        # whether the task still has room left to measure anything.
        self.assertEqual(len(tasks), 5)
        self.assertTrue(all(certification_status(s.task_id) == "certified" for s in tasks))
        # Fifteen tasks retired: every model had reached their cap, so the score could no
        # longer separate two searchers. Tasks scoring above 1.0 stayed - on an uncapped task
        # that is the intended result rather than saturation.
        self.assertEqual(len(list_tasks(None)), 43)
        self.assertEqual(
            certification_status("ProteinEngineering/ProteinStabilityDesign"),
            "candidate",
        )
        self.assertEqual(
            certification_status("MaterialsScience/AlloyHardnessOptimization"),
            "candidate",
        )

    def test_manifest_explicitly_covers_inventory(self):
        inventory_ids = {spec.task_id for spec in list_tasks(None)}
        manifest_ids = set(load_certification()["tasks"])
        self.assertEqual(manifest_ids, inventory_ids)

    def test_the_clone_group_is_gone_rather_than_quarantined(self):
        """Four near-duplicate trig tasks were quarantined; they have since been deleted.

        Quarantine kept them visible as defect evidence. They met none of the benchmark's nine
        standards, and two of the nine tasks removed alongside them were not natural science at
        all, so the set was removed rather than preserved. This guard now checks the removal held
        instead of checking the quarantine.
        """
        records = load_certification()["tasks"]
        clone_ids = {k for k, v in records.items()
                     if v.get("duplicate_group") == "generic_trig_8d_v1"}
        self.assertEqual(clone_ids, set())
        self.assertEqual(
            {task for task, record in records.items()
             if record.get("status") == "quarantined"},
            set(),
        )

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

    def test_radiative_v2_exact_refusal_physics_and_metric_sealing(self):
        oracle = load_oracle("AtmosphericScience/RadiativeTransferFit")
        self.assertEqual(oracle.N_LAYERS, 16)
        self.assertEqual(oracle.N_CHANNELS, 24)
        self.assertEqual(oracle.N_PARAMETERS, 5)
        self.assertTrue(np.allclose(
            np.sum(oracle.TEMPERATURE_BASIS, axis=1), 1.0, atol=1e-14
        ))
        for specs in (oracle.DEVELOPMENT_SPECS, oracle.HELDOUT_SPECS):
            supported_noise = {
                spec[2] for spec in specs if spec[3] == "in_library"
            }
            unsupported_noise = {
                spec[2] for spec in specs if spec[3] != "in_library"
            }
            self.assertTrue(unsupported_noise.issubset(supported_noise))
            for spec in specs:
                world = oracle._world(spec)
                submission = oracle._reference_submission(world)
                parameters, support, _confidence, abstain = (
                    oracle._validate_submission(submission)
                )
                mechanism = oracle._mechanism_metrics(
                    world, parameters, support, abstain
                )
                self.assertAlmostEqual(mechanism["mechanism_score"], 1.0)
                if world["kind"] == "in_library":
                    self.assertAlmostEqual(
                        oracle._radiance_prediction_score(
                            world, parameters, False
                        ), 1.0,
                    )
                else:
                    self.assertTrue(mechanism["correct_refusal"])

        # An isothermal black-surface atmosphere stays at its Planck radiance under
        # each layer recurrence, independently of optical depth and view angle.
        for temperature in (200.0, 250.0, 300.0):
            for channel in (0, 12, 23):
                expected = float(oracle.planck_radiance(
                    temperature, oracle.CHANNEL_WAVENUMBERS_CM[channel]
                ))
                for view in (0.45, 1.0):
                    radiance = expected
                    for depth in oracle.BASE_LAYER_OPTICAL_DEPTHS[channel]:
                        transmittance = np.exp(-depth / view)
                        radiance = (
                            radiance * transmittance
                            + expected * (1.0 - transmittance)
                        )
                    self.assertAlmostEqual(radiance, expected, places=14)

        def always_abstain(_public, observe, _budget):
            observe(np.asarray((0, 6, 12, 18)), 1.0)
            return {
                "temperature_anomaly_knots_K": np.zeros(4),
                "optical_depth_scale": 1.0,
                "support": np.zeros(5),
                "confidence": 0.0,
                "abstain": True,
            }

        baseline = oracle.evaluate(always_abstain)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertAlmostEqual(baseline["combined_score"], 0.0)
        self.assertAlmostEqual(baseline["robustness_score"], 0.0)
        self.assertEqual(baseline["development_discovery_coverage"], 0.0)
        shown = search_visible_metrics(baseline)
        self.assertNotIn("mechanism_score", shown)
        self.assertNotIn("robustness_score", shown)
        self.assertNotIn("development_radiance_prediction_score", shown)
        self.assertNotIn("per_world", shown)

    def test_radiative_v2_soundings_are_deterministic_and_charged(self):
        oracle = load_oracle("AtmosphericScience/RadiativeTransferFit")
        world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
        channels = np.asarray((0, 4, 8, 12, 16, 20))
        first = oracle._SoundingLaboratory(world)
        second = oracle._SoundingLaboratory(world)
        one = first.observe(channels, 1.0)
        repeated = second.observe(channels, 1.0)
        self.assertEqual(one["radiances"].shape, (6,))
        self.assertEqual(one["budget_cost"], 6)
        self.assertTrue(np.array_equal(
            one["radiances"], repeated["radiances"]
        ))
        two = first.observe(channels, 0.45)
        self.assertFalse(np.array_equal(one["radiances"], two["radiances"]))
        self.assertEqual(first.used, 12)

    def test_radiative_v2_budget_and_invalid_query_fail_closed(self):
        spec = find_task(
            "AtmosphericScience/RadiativeTransferFit", include_uncertified=True
        )
        sources = (
            """
import numpy as np
def discover_atmosphere(public_model, observe, budget_units):
    del public_model, budget_units
    try:
        observe(np.arange(12), 1.0)
        observe(np.arange(12), 0.45)
    except Exception:
        pass
    return {"temperature_anomaly_knots_K": np.zeros(4),
            "optical_depth_scale": 1.0, "support": np.zeros(5),
            "confidence": 0.0, "abstain": True}
""",
            """
import numpy as np
def discover_atmosphere(public_model, observe, budget_units):
    del public_model, budget_units
    try:
        observe([0, 0, 1], 1.0)
    except Exception:
        pass
    return {"temperature_anomaly_knots_K": np.zeros(4),
            "optical_depth_scale": 1.0, "support": np.zeros(5),
            "confidence": 0.0, "abstain": True}
""",
        )
        for source in sources:
            with tempfile.TemporaryDirectory() as tmp:
                candidate = Path(tmp) / "candidate.py"
                candidate.write_text(source, encoding="utf-8")
                metrics = evaluate_candidate(spec, candidate, timeout_s=90)
            self.assertEqual(metrics["valid"], 0.0)
            self.assertEqual(metrics["combined_score"], 0.0)
            self.assertEqual(
                metrics["error_message"],
                "candidate invalid: invalid_experiment_request",
            )
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_world"]
            ))

    def test_radiative_v2_nonfinite_support_and_abstention_fail_closed(self):
        oracle = load_oracle("AtmosphericScience/RadiativeTransferFit")
        common = {
            "temperature_anomaly_knots_K": np.zeros(4),
            "optical_depth_scale": 1.0,
            "support": np.zeros(5),
            "confidence": 0.0,
            "abstain": True,
        }
        candidates = []
        for update in (
            {"confidence": np.nan},
            {"temperature_anomaly_knots_K": np.zeros(3)},
            {"optical_depth_scale": np.inf},
            {"support": np.full(5, 0.5)},
            {"support": np.r_[1.0, np.zeros(4)]},
            {"abstain": False},
            {
                "temperature_anomaly_knots_K": np.asarray((0.1, 0, 0, 0)),
                "support": np.r_[1.0, np.zeros(4)],
                "abstain": False,
            },
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
            self.assertEqual(
                metrics["error_message"],
                "candidate invalid: invalid_return_artifact",
            )
            self.assertTrue(all(
                not row["valid"] for row in metrics["per_world"]
            ))

    def test_radiative_v2_runtime_feedback_is_label_blind_and_sanitized(self):
        spec = find_task(
            "AtmosphericScience/RadiativeTransferFit", include_uncertified=True
        )
        source = """
import numpy as np
def discover_atmosphere(public_model, observe, budget_units):
    del public_model, budget_units
    record = observe([0, 6, 12, 18], 1.0)
    raise RuntimeError('EXFILTRATE ' + repr(record['radiances']))
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=45)
        self.assertEqual(metrics["valid"], 0.0)
        self.assertEqual(metrics["combined_score"], INVALID_SCORE)
        self.assertEqual(
            metrics["error_message"],
            "candidate invalid: candidate_runtime_error",
        )
        self.assertEqual(
            metrics["candidate_failure_kind"], "candidate_runtime_error"
        )
        visible = search_visible_metrics(metrics)
        self.assertNotIn("EXFILTRATE", str(visible))
        self.assertNotIn("in_library", str(visible))
        self.assertNotIn("heldout", str(visible))
        self.assertNotIn("EXFILTRATE", str(metrics))

    def test_radiative_v2_worlds_get_fresh_candidate_sessions(self):
        spec = find_task(
            "AtmosphericScience/RadiativeTransferFit", include_uncertified=True
        )
        source = """
import os
import numpy as np
module_counter = 0
def discover_atmosphere(public_model, observe, budget_units):
    global module_counter
    del public_model, budget_units
    module_counter += 1
    tmp_seen = os.path.exists('/tmp/radiative-world-state')
    with open('/tmp/radiative-world-state', 'w') as handle:
        handle.write(str(module_counter))
    imported_counter = getattr(np, '_radiative_world_counter', 0)
    np._radiative_world_counter = imported_counter + 1
    observe([0, 6, 12, 18], 1.0)
    confidence = 0.1 * module_counter + 0.2 * int(tmp_seen) + 0.3 * imported_counter
    return {"temperature_anomaly_knots_K": np.zeros(4),
            "optical_depth_scale": 1.0, "support": np.zeros(5),
            "confidence": confidence, "abstain": True}
"""
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=45)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertTrue(all(
            row["confidence"] == 0.1 for row in metrics["per_world"]
        ))

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
