from __future__ import annotations

import importlib.util
import itertools
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Chemistry/ForceFieldCalibration"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load(TASK / "verification/evaluator.py", "force_field_oracle")
BASELINE = _load(TASK / "solution.py", "force_field_baseline")


class ForceFieldCalibrationTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "MolecularDynamics/ForceFieldCalibration", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_pair_energy_forces_obey_physical_invariances(self):
        rng = np.random.default_rng(13)
        coordinates = ORACLE._triangle_coordinates(2.75, 3.35, 4.82)
        rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        translation = np.asarray((3.4, -1.2, 0.8))
        for family, parameters in (
            ("mie", np.asarray((0.105, 2.93))),
            ("morse", np.asarray((0.112, 1.72, 3.08))),
        ):
            energy, forces = ORACLE._pair_energy_forces(
                family, parameters, coordinates
            )
            transformed_energy, transformed_forces = ORACLE._pair_energy_forces(
                family, parameters, coordinates @ rotation + translation
            )
            self.assertAlmostEqual(energy, transformed_energy, places=12)
            self.assertTrue(
                np.allclose(transformed_forces, forces @ rotation, atol=2e-12)
            )
            self.assertTrue(np.allclose(np.sum(forces, axis=0), 0.0, atol=2e-14))
            finite_difference = np.zeros_like(forces)
            step = 1.0e-6
            for particle in range(3):
                for axis in range(3):
                    plus = coordinates.copy()
                    minus = coordinates.copy()
                    plus[particle, axis] += step
                    minus[particle, axis] -= step
                    finite_difference[particle, axis] = -(
                        ORACLE._pair_energy_forces(family, parameters, plus)[0]
                        - ORACLE._pair_energy_forces(family, parameters, minus)[0]
                    ) / (2.0 * step)
            self.assertTrue(np.allclose(forces, finite_difference, atol=2e-8))

    def test_public_problem_is_label_blind_and_identical_across_worlds(self):
        problems = [
            ORACLE._public_problem(ORACLE._make_world(spec_value))
            for spec_value in ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS
        ]
        self.assertTrue(all(problem == problems[0] for problem in problems[1:]))
        rendered = repr(problems[0]).lower()
        for forbidden in (
            "development", "heldout", "buckingham", "three_body",
            "state_dependent", "noise_scale", "seed", "kind",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("nominal_energy_noise_sigma_ev", problems[0])
        self.assertIn("nominal_force_noise_sigma_ev_per_a", problems[0])
        self.assertEqual(
            problems[0]["second_virial_bounds_cm3_mol"],
            list(ORACLE.SECOND_VIRIAL_BOUNDS_CM3_MOL),
        )
        self.assertNotIn("energy_noise_sigma_ev", problems[0])
        self.assertNotIn("force_noise_sigma_ev_per_a", problems[0])

    def test_boyle_temperature_is_a_second_virial_root(self):
        for family, parameters in (
            ("mie", np.asarray((0.105, 2.93))),
            ("morse", np.asarray((0.112, 1.72, 3.08))),
        ):
            temperature = ORACLE._boyle_temperature(family, parameters)
            value = ORACLE._second_virial_curve(
                family, parameters, (temperature,)
            )[0]
            below, above = ORACLE._second_virial_curve(
                family, parameters, (temperature - 40.0, temperature + 40.0)
            )
            self.assertLess(abs(value), 1e-7)
            self.assertLess(below, 0.0)
            self.assertGreater(above, 0.0)

            def independent_energy(distance):
                if family == "mie":
                    epsilon, sigma = parameters
                    ratio = sigma / distance
                    return 4.0 * epsilon * (ratio**12 - ratio**6)
                depth, inverse_range, equilibrium = parameters
                exponential = np.exp(
                    -inverse_range * (distance - equilibrium)
                )
                return depth * (exponential**2 - 2.0 * exponential)

            def independent_virial(candidate_temperature):
                def integrand(distance):
                    exponent = np.clip(
                        -independent_energy(distance)
                        / (ORACLE.BOLTZMANN_EV_PER_K * candidate_temperature),
                        -700.0, 50.0,
                    )
                    return float(np.expm1(exponent) * distance * distance)

                integral, _ = quad(
                    integrand, 0.0, np.inf, epsabs=1.0e-8,
                    epsrel=2.0e-10, limit=600,
                )
                return -2.0 * np.pi * integral * ORACLE.ANGSTROM3_TO_CM3_PER_MOL

            independent_temperature = brentq(
                independent_virial,
                ORACLE.BOYLE_TEMPERATURE_BOUNDS_K[0],
                ORACLE.BOYLE_TEMPERATURE_BOUNDS_K[1],
            )
            self.assertLess(abs(independent_temperature - temperature), 1.0)

    def test_reference_submits_self_consistent_virial_curves(self):
        for spec_value in (
            ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS
        ):
            world = ORACLE._make_world(spec_value)
            problem = ORACLE._public_problem(world)
            if world["kind"] not in ORACLE.PAIR_FAMILIES:
                continue
            laboratory = ORACLE._Laboratory(world, problem)
            submission = ORACLE._reference_agent(problem, laboratory.query)
            values = ORACLE._validate_submission(
                submission, problem, laboratory
            )
            temperatures = np.asarray(
                problem["virial_temperature_grid_k"], dtype=float
            )
            parameter_vector = np.asarray([
                values["parameters"][name]
                for name, _ in ORACLE.PARAMETER_SPECS[values["selected"]]
            ])
            recomputed = ORACLE._second_virial_curve(
                values["selected"], parameter_vector, temperatures
            )
            submitted = np.asarray([
                values["virial_curve"][str(float(temperature))]
                for temperature in temperatures
            ])
            self.assertTrue(np.allclose(submitted, recomputed, atol=1e-10))

    def test_public_parameter_corners_fit_virial_submission_bounds(self):
        extrema = []
        for family in ORACLE.PAIR_FAMILIES:
            bounds = [
                parameter_bounds
                for _, parameter_bounds in ORACLE.PARAMETER_SPECS[family]
            ]
            for parameters in itertools.product(*[
                (parameter_bounds[0], parameter_bounds[1])
                for parameter_bounds in bounds
            ]):
                values = ORACLE._second_virial_curve(
                    family,
                    np.asarray(parameters, dtype=float),
                    ORACLE.VIRIAL_TEMPERATURE_GRID_K,
                )
                self.assertTrue(np.all(np.isfinite(values)))
                self.assertGreaterEqual(
                    float(np.min(values)),
                    ORACLE.SECOND_VIRIAL_BOUNDS_CM3_MOL[0],
                )
                self.assertLessEqual(
                    float(np.max(values)),
                    ORACLE.SECOND_VIRIAL_BOUNDS_CM3_MOL[1],
                )
                extrema.extend(values.tolist())
        self.assertLess(min(extrema), -1000.0)
        self.assertGreater(max(extrema), 20.0)

    def test_public_parameter_corners_have_admissible_boyle_roots(self):
        roots = []
        for family in ORACLE.PAIR_FAMILIES:
            bounds = [
                parameter_bounds
                for _, parameter_bounds in ORACLE.PARAMETER_SPECS[family]
            ]
            for parameters in itertools.product(*[
                (parameter_bounds[0], parameter_bounds[1])
                for parameter_bounds in bounds
            ]):
                root = ORACLE._boyle_temperature(
                    family, np.asarray(parameters, dtype=float)
                )
                self.assertGreaterEqual(
                    root, ORACLE.BOYLE_TEMPERATURE_BOUNDS_K[0]
                )
                self.assertLessEqual(
                    root, ORACLE.BOYLE_TEMPERATURE_BOUNDS_K[1]
                )
                roots.append(root)
        self.assertLess(min(roots), 1200.0)
        self.assertGreater(max(roots), 24000.0)

    def test_public_parameter_grid_has_admissible_boyle_roots(self):
        roots = []
        for family in ORACLE.PAIR_FAMILIES:
            axes = [
                np.linspace(parameter_bounds[0], parameter_bounds[1], 5)
                for _, parameter_bounds in ORACLE.PARAMETER_SPECS[family]
            ]
            for parameters in itertools.product(*axes):
                root = ORACLE._boyle_temperature(
                    family, np.asarray(parameters, dtype=float)
                )
                self.assertGreaterEqual(
                    root, ORACLE.BOYLE_TEMPERATURE_BOUNDS_K[0]
                )
                self.assertLessEqual(
                    root, ORACLE.BOYLE_TEMPERATURE_BOUNDS_K[1]
                )
                roots.append(root)
        self.assertLess(min(roots), 1100.0)
        self.assertGreater(max(roots), 24000.0)

    def test_hypothesis_weights_use_a_proper_brier_score(self):
        true_hypothesis = "morse"
        uniform = {name: 1.0 / 3.0 for name in ORACLE.HYPOTHESES}
        informed = {"mie": 0.1, "morse": 0.8, "unsupported": 0.1}
        wrong = {"mie": 0.8, "morse": 0.1, "unsupported": 0.1}
        self.assertGreater(
            ORACLE._brier_quality(informed, true_hypothesis),
            ORACLE._brier_quality(uniform, true_hypothesis),
        )
        self.assertGreater(
            ORACLE._brier_quality(uniform, true_hypothesis),
            ORACLE._brier_quality(wrong, true_hypothesis),
        )
        self.assertEqual(
            ORACLE._brier_quality(
                {"mie": 0.0, "morse": 1.0, "unsupported": 0.0},
                true_hypothesis,
            ),
            1.0,
        )

    def test_retained_hypotheses_require_material_probability(self):
        with self.assertRaises(ValueError):
            ORACLE._validate_weight_state(
                {
                    "weights": {
                        "mie": 1.0 - 1.0e-13,
                        "morse": 0.0,
                        "unsupported": 1.0e-13,
                    },
                    "retained": ["mie", "unsupported"],
                },
                "ghost state",
            )
        with self.assertRaises(ValueError):
            ORACLE._validate_weight_state(
                {
                    "weights": {"mie": 0.99, "morse": 0.01,
                                "unsupported": 0.0},
                    "retained": ["mie"],
                },
                "omitted nonzero state",
            )
        weights, retained = ORACLE._validate_weight_state(
            {
                "weights": {"mie": 0.98, "morse": 0.01,
                            "unsupported": 0.01},
                "retained": list(ORACLE.HYPOTHESES),
            },
            "material state",
        )
        self.assertEqual(set(retained), set(ORACLE.HYPOTHESES))
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_selected_model_must_match_maximum_final_weight(self):
        world = ORACLE._make_world(ORACLE.DEVELOPMENT_SPECS[0])
        problem = ORACLE._public_problem(world)
        laboratory = ORACLE._Laboratory(world, problem)
        screening, _ = ORACLE._reference_configurations()
        observation = laboratory.query(
            screening,
            problem["first_query_temperature_k"],
            {
                "weights": {
                    "mie": 1.0 / 3.0,
                    "morse": 1.0 / 3.0,
                    "unsupported": 1.0 / 3.0,
                },
                "retained": list(ORACLE.HYPOTHESES),
            },
        )
        submission = {
            "hypothesis_weights": {
                "mie": 0.10, "morse": 0.80, "unsupported": 0.10,
            },
            "retained_hypotheses": list(ORACLE.HYPOTHESES),
            "selected_model": "unsupported",
            "parameters": {},
            "parameter_intervals": {},
            "second_virial_cm3_mol_by_temperature": {},
            "boyle_temperature_k": None,
            "boyle_temperature_above_threshold": None,
            "confidence": 0.5,
            "abstain": True,
            "evidence_ids": [observation["observation_id"]] + list(
                observation["configuration_ids"]
            ),
        }
        with self.assertRaises(ValueError):
            ORACLE._validate_submission(submission, problem, laboratory)

    def test_first_screen_is_ambiguous_and_reference_discriminates(self):
        for spec_value in ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS:
            world = ORACLE._make_world(spec_value)
            problem = ORACLE._public_problem(world)
            screening, _ = ORACLE._reference_configurations()
            laboratory = ORACLE._Laboratory(world, problem)
            laboratory.query(
                screening,
                ORACLE.FIRST_QUERY_TEMPERATURE_K,
                {
                    "weights": {
                        "mie": 1.0 / 3.0,
                        "morse": 1.0 / 3.0,
                        "unsupported": 1.0 / 3.0,
                    },
                    "retained": list(ORACLE.HYPOTHESES),
                },
            )
            posterior = laboratory.posterior()
            self.assertLess(
                abs(posterior["mie"] - posterior["morse"]), 0.72
            )

        result = ORACLE.evaluate(ORACLE._reference_agent)
        self.assertGreater(result["combined_score"], 0.93)
        self.assertGreater(result["heldout_policy_score"], 0.93)
        self.assertGreater(result["robustness_score"], 0.93)
        self.assertGreater(result["heldout_robustness_score"], 0.93)
        self.assertEqual(result["development_supported_claim_coverage"], 1.0)
        self.assertEqual(result["heldout_supported_claim_coverage"], 1.0)
        self.assertEqual(result["development_supported_correct_model_rate"], 1.0)
        self.assertEqual(result["heldout_supported_correct_model_rate"], 1.0)
        self.assertEqual(result["development_unsupported_refusal_rate"], 1.0)
        self.assertEqual(result["heldout_unsupported_refusal_rate"], 1.0)
        self.assertEqual(result["development_false_discovery_rate"], 0.0)
        self.assertEqual(result["heldout_false_discovery_rate"], 0.0)
        self.assertEqual(result["development_interval_coverage"], 1.0)
        self.assertEqual(result["heldout_interval_coverage"], 1.0)
        self.assertEqual(result["development_premature_elimination_rate"], 0.0)
        self.assertEqual(result["heldout_premature_elimination_rate"], 0.0)

    def test_entire_first_query_envelope_is_hypothesis_ambiguous(self):
        for side in np.linspace(
            ORACLE.FIRST_QUERY_DISTANCE_BOUNDS_A[0],
            ORACLE.FIRST_QUERY_DISTANCE_BOUNDS_A[1],
            7,
        ):
            coordinates = np.asarray([
                ORACLE._triangle_coordinates(side, side, side)
            ])
            for spec_value in (
                ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS
            ):
                world = ORACLE._make_world(spec_value)
                problem = ORACLE._public_problem(world)
                laboratory = ORACLE._Laboratory(world, problem)
                laboratory.query(
                    coordinates,
                    ORACLE.FIRST_QUERY_TEMPERATURE_K,
                    {
                        "weights": {
                            "mie": 1.0 / 3.0,
                            "morse": 1.0 / 3.0,
                            "unsupported": 1.0 / 3.0,
                        },
                        "retained": list(ORACLE.HYPOTHESES),
                    },
                )
                posterior = laboratory.posterior()
                self.assertLess(
                    abs(posterior["mie"] - posterior["morse"]), 0.08
                )

    def test_discriminating_design_beats_narrow_repeated_sampling(self):
        def acquire(world, narrow):
            problem = ORACLE._public_problem(world)
            laboratory = ORACLE._Laboratory(world, problem)
            observations = []
            screening = np.asarray([
                ORACLE._triangle_coordinates(3.18, 3.18, 3.18)
            ])
            observations.append(laboratory.query(
                screening,
                450.0,
                {
                    "weights": {
                        "mie": 1.0 / 3.0,
                        "morse": 1.0 / 3.0,
                        "unsupported": 1.0 / 3.0,
                    },
                    "retained": list(ORACLE.HYPOTHESES),
                },
            ))
            if narrow:
                triples = (
                    (3.02, 3.02, 3.02), (3.08, 3.08, 3.08),
                    (3.14, 3.14, 3.14), (3.22, 3.22, 3.22),
                    (3.30, 3.30, 3.30), (3.38, 3.38, 3.38),
                    (3.46, 3.46, 3.46), (3.04, 3.18, 3.42),
                )
                configurations = np.asarray([
                    ORACLE._triangle_coordinates(*triple)
                    for triple in triples
                ])
                batches = (
                    (configurations, 450.0),
                    (configurations, 450.0),
                    (configurations[:7], 450.0),
                )
            else:
                _, configurations = ORACLE._reference_configurations()
                batches = (
                    (configurations[:8], 180.0),
                    (configurations[8:16], 450.0),
                    (configurations[16:], 900.0),
                )
            for configurations, temperature in batches:
                weights = ORACLE._reference_report_weights(
                    ORACLE._diagnostic_weights(observations, problem)
                )
                observations.append(laboratory.query(
                    configurations,
                    temperature,
                    {"weights": weights, "retained": list(ORACLE.HYPOTHESES)},
                ))
            return ORACLE._acquisition_metrics(laboratory)

        for spec_value in ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS:
            world = ORACLE._make_world(spec_value)
            narrow = acquire(world, narrow=True)
            discriminating = acquire(world, narrow=False)
            self.assertLess(narrow["design_coverage"], 0.40)
            self.assertEqual(discriminating["design_coverage"], 1.0)
            self.assertGreater(
                discriminating["acquisition_quality"]
                - narrow["acquisition_quality"],
                0.35,
            )

    def test_baseline_is_valid_zero_and_science_metrics_are_sealed(self):
        direct = ORACLE.evaluate(BASELINE.calibrate_forcefield)
        self.assertEqual(direct["valid"], 1.0)
        self.assertEqual(direct["combined_score"], 0.0)
        self.assertEqual(direct["robustness_score"], 0.0)
        self.assertEqual(direct["development_supported_claim_coverage"], 0.0)
        visible = search_visible_metrics(direct)
        self.assertEqual(
            set(visible), {"combined_score", "valid", "feasibility_rate"}
        )
        self.assertNotIn("per_world", visible)
        self.assertNotIn("development_hypothesis_score", visible)
        self.assertNotIn("development_robust_prediction_score", visible)

    def test_every_always_refuse_policy_is_normalized_to_zero(self):
        def confident_refusal(problem, query):
            side = 3.18
            coordinates = np.asarray([
                [[-side / 2.0, 0.0, 0.0], [side / 2.0, 0.0, 0.0],
                 [0.0, np.sqrt(3.0) * side / 2.0, 0.0]],
            ])
            observation = query(
                coordinates,
                450.0,
                {
                    "weights": {
                        "mie": 1.0 / 3.0,
                        "morse": 1.0 / 3.0,
                        "unsupported": 1.0 / 3.0,
                    },
                    "retained": list(ORACLE.HYPOTHESES),
                },
            )
            return {
                "hypothesis_weights": {
                    "mie": 0.0, "morse": 0.0, "unsupported": 1.0,
                },
                "retained_hypotheses": ["unsupported"],
                "selected_model": "unsupported",
                "parameters": {},
                "parameter_intervals": {},
                "second_virial_cm3_mol_by_temperature": {},
                "boyle_temperature_k": None,
                "boyle_temperature_above_threshold": None,
                "confidence": 1.0,
                "abstain": True,
                "evidence_ids": [observation["observation_id"]] + list(
                    observation["configuration_ids"]
                ),
            }

        result = ORACLE.evaluate(confident_refusal)
        self.assertEqual(result["valid"], 1.0)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["robustness_score"], 0.0)
        self.assertEqual(result["heldout_policy_score"], 0.0)
        self.assertEqual(result["heldout_robustness_score"], 0.0)
        self.assertLess(
            result["development_raw_joint_score"],
            result["development_abstention_baseline"],
        )

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_secure_baseline_matches_direct_evaluation(self):
        spec = find_task(
            "MolecularDynamics/ForceFieldCalibration", include_uncertified=True
        )
        secure = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        direct = ORACLE.evaluate(BASELINE.calibrate_forcefield)
        direct["raw_score"] = direct["combined_score"]
        self.assertEqual(secure, direct)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_overspend_fails_closed_even_when_candidate_catches_error(self):
        result = self.evaluate_source(
            """
            import numpy as np
            def calibrate_forcefield(problem, query):
                side = 3.18
                c = np.array([[[-side/2,0,0],[side/2,0,0],
                               [0,np.sqrt(3)*side/2,0]]])
                state = {'weights': {'mie':1/3,'morse':1/3,'unsupported':1/3},
                         'retained':['mie','morse','unsupported']}
                first = query(c, 450.0, state)
                try:
                    for _ in range(problem['query_budget_units'] + 1):
                        query(c, 450.0, state)
                except Exception:
                    pass
                return {'hypothesis_weights': {'mie':0,'morse':0,'unsupported':1},
                        'retained_hypotheses':['unsupported'],
                        'selected_model':'unsupported','parameters':{},
                        'parameter_intervals':{},
                        'second_virial_cm3_mol_by_temperature':{},
                        'boyle_temperature_k':None,
                        'boyle_temperature_above_threshold':None,
                        'confidence':0.0,'abstain':True,
                        'evidence_ids':[first['observation_id']] + first['configuration_ids']}
            """
        )
        self.assertEqual(result["valid"], 0.0, result)
        self.assertEqual(result["combined_score"], 0.0, result)
        self.assertTrue(all(
            row["failure_kind"] == "query_protocol_or_candidate_execution_failure"
            for row in result["per_world"][: len(ORACLE.DEVELOPMENT_SPECS)]
        ))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_eliminated_hypothesis_cannot_be_restored(self):
        result = self.evaluate_source(
            """
            import numpy as np
            def calibrate_forcefield(problem, query):
                side = 3.18
                c = np.array([[[-side/2,0,0],[side/2,0,0],
                               [0,np.sqrt(3)*side/2,0]]])
                first = query(c, 450.0, {
                    'weights': {'mie':0.5,'morse':0.5,'unsupported':0.0},
                    'retained':['mie','morse']})
                try:
                    query(c, 450.0, {
                        'weights': {'mie':1/3,'morse':1/3,'unsupported':1/3},
                        'retained':['mie','morse','unsupported']})
                except Exception:
                    pass
                return {'hypothesis_weights': {'mie':0.5,'morse':0.5,'unsupported':0},
                        'retained_hypotheses':['mie','morse'],
                        'selected_model':'mie',
                        'parameters': {'epsilon_ev':0.1,'sigma_a':2.9},
                        'parameter_intervals': {'epsilon_ev':[0.09,0.11],
                                                'sigma_a':[2.8,3.0]},
                        'second_virial_cm3_mol_by_temperature': {
                            str(float(t)): 0.0
                            for t in problem['virial_temperature_grid_k']},
                        'boyle_temperature_k':4000.0,
                        'boyle_temperature_above_threshold':False,
                        'confidence':0.5,'abstain':False,
                        'evidence_ids':[first['observation_id']] + first['configuration_ids']}
            """
        )
        self.assertEqual(result["valid"], 0.0, result)
        self.assertEqual(result["combined_score"], 0.0, result)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_fabricated_evidence_and_malformed_intervals_fail_closed(self):
        for mode in ("evidence", "interval"):
            with self.subTest(mode=mode):
                result = self.evaluate_source(
                    """
                    import numpy as np
                    def calibrate_forcefield(problem, query):
                        side = 3.18
                        c = np.array([[[-side/2,0,0],[side/2,0,0],
                                       [0,np.sqrt(3)*side/2,0]]])
                        first = query(c, 450.0, {
                            'weights': {'mie':1/3,'morse':1/3,'unsupported':1/3},
                            'retained':['mie','morse','unsupported']})
                        value = {
                            'hypothesis_weights': {'mie':1/3,'morse':1/3,
                                                   'unsupported':1/3},
                            'retained_hypotheses':['mie','morse','unsupported'],
                            'selected_model':'mie',
                            'parameters': {'epsilon_ev':0.1,'sigma_a':2.9},
                            'parameter_intervals': {'epsilon_ev':[0.09,0.11],
                                                    'sigma_a':[2.8,3.0]},
                            'second_virial_cm3_mol_by_temperature': {
                                str(float(t)): 0.0
                                for t in problem['virial_temperature_grid_k']},
                            'boyle_temperature_k':4000.0,
                            'boyle_temperature_above_threshold':False,
                            'confidence':0.5,'abstain':False,
                            'evidence_ids':[first['observation_id']] + first['configuration_ids']}
                        if %r == 'evidence':
                            value['evidence_ids'] = ['fabricated']
                        else:
                            value['parameter_intervals']['sigma_a'] = [3.0, 2.8]
                        return value
                    """ % mode
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0, result)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_candidate_worlds_use_fresh_processes(self):
        result = self.evaluate_source(
            """
            import numpy as np
            calls = 0
            def calibrate_forcefield(problem, query):
                global calls
                calls += 1
                if calls != 1:
                    raise RuntimeError('session leaked')
                side = 3.18
                c = np.array([[[-side/2,0,0],[side/2,0,0],
                               [0,np.sqrt(3)*side/2,0]]])
                first = query(c, 450.0, {
                    'weights': {'mie':1/3,'morse':1/3,'unsupported':1/3},
                    'retained':['mie','morse','unsupported']})
                return {'hypothesis_weights': {'mie':0,'morse':0,'unsupported':1},
                        'retained_hypotheses':['unsupported'],
                        'selected_model':'unsupported','parameters':{},
                        'parameter_intervals':{},
                        'second_virial_cm3_mol_by_temperature':{},
                        'boyle_temperature_k':None,
                        'boyle_temperature_above_threshold':None,
                        'confidence':0.0,'abstain':True,
                        'evidence_ids':[first['observation_id']] + first['configuration_ids']}
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_instance_call_count"], 12)
        self.assertEqual(result["candidate_instance_valid_rate"], 1.0)

    def test_public_contract_does_not_expose_hidden_worlds_or_splits(self):
        public = "\n".join(
            (TASK / path).read_text(encoding="utf-8")
            for path in (
                "Task.md", "solution.py", "frontier_eval/constraints.txt",
            )
        ).lower()
        for forbidden in (
            "52011", "62003", "development_specs", "heldout_specs",
            "noise_scale", "three_body_coefficient_ev_a9",
            "temperature_coefficient", "_reference_agent",
        ):
            self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()
