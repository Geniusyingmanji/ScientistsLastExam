from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from sle.certification import certification_status, load_certification
from sle.evaluate import INVALID_SCORE, evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import discover_task_dirs, find_task, list_tasks
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


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
        # Discovery remains candidate or quarantined after the branch split.
        # Removing optimization packages must not certify unreviewed discovery.
        self.assertEqual(tasks, [])
        self.assertEqual(len(list_tasks(None)), len(discover_task_dirs()))
        self.assertTrue(all(s.metadata.get("scientific_role") == "discovery"
                            for s in list_tasks(None)))

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
        # These discovery packages remain available for historical replay, but
        # known saturation/shortcuts exclude them from the current frontier.
        self.assertEqual(
            {task for task, record in records.items()
             if record.get("status") == "quarantined"},
            {
                "CausalDiscovery/SurvivorshipConfoundedDesign",
                "SystemsBiology/EnzymeKineticsLaw",
                "Gravitation/PTAHellingsDowns",
                "Oceanography/AMOCTippingRefusal",
                "ParticlePhysics/LookElsewhereAnomaly",
                "Mathematics/BlackBoxGroupIdentification",
            },
        )

    def test_certified_tasks_have_stable_citation_ids(self):
        records = load_certification()["tasks"]
        for spec in list_tasks():
            ids = records[spec.task_id].get("citation_ids", [])
            self.assertTrue(ids, spec.task_id)
            self.assertTrue(all(":" in identifier for identifier in ids), spec.task_id)


class ScientificInvariantTests(unittest.TestCase):







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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
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









if __name__ == "__main__":
    unittest.main()
