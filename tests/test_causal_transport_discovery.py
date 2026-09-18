"""Identifiability, quantitative model and contract checks for transport pilot."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np


TASK = Path(__file__).resolve().parents[1] / "benchmarks/ComputerScience/CausalTransportDiscovery"


def load(name):
    spec = importlib.util.spec_from_file_location("transport_" + name, TASK / "verification" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CausalTransportDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episode, cls.reference = load("episode"), load("reference")

    def run_policy(self, seed, name):
        env = self.episode.create_environment(seed)
        used, calls = [0], [0]

        def experiment(tool, args):
            used[0] += env.action_cost(tool, args)
            calls[0] += 1
            self.assertLessEqual(used[0], env.budget_units)
            return env.experiment(tool, args)

        claim = self.reference.POLICIES[name](env.public_problem(), experiment)
        env.validate_claim(claim)
        metrics = env.evaluate(claim, env.confirm(claim))
        json.dumps(metrics, allow_nan=False)
        return env, claim, metrics, used[0], calls[0]

    def test_source_equivalent_worlds_require_discordant_experiments(self):
        a, b = self.episode.create_environment(4), self.episode.create_environment(5)
        self.assertEqual(a.public_problem(), b.public_problem())
        self.assertFalse(np.array_equal(a._coefficients, b._coefficients))
        for x in (-1, 1):
            for dose in (0, 0.2, 0.6, 1):
                args = {"site": "source", "x": x, "dose": dose, "n": 128, "assay_n": 128}
                self.assertEqual(a.experiment("trial", args), b.experiment("trial", args))

    def test_inaccessible_pair_has_identical_public_state_and_every_tool(self):
        a, b = self.episode.create_environment(0), self.episode.create_environment(1)
        self.assertEqual(a.public_problem(), b.public_problem())
        self.assertFalse(np.array_equal(a._coefficients[1], b._coefficients[1]))
        for site in a.public_problem()["sites"]:
            for x in (-1, 1):
                survey = {"site": site, "x": x, "n": 32}
                self.assertEqual(a.experiment("survey", survey), b.experiment("survey", survey))
                for dose in (0, 0.25, 0.65, 1):
                    trial = {"site": site, "x": x, "dose": dose, "n": 32, "assay_n": 16}
                    self.assertEqual(a.experiment("trial", trial), b.experiment("trial", trial))
        weights = np.array(a.public_problem()["target_populations"][0]["cell_weights"])
        self.assertGreater(float(np.linalg.norm(weights.dot(a._coefficients - b._coefficients))), 0.001)

    def test_dose_basis_bounds_ensure_valid_bernoulli_means(self):
        b = self.episode.basis(np.linspace(0, 1, 301))
        self.assertTrue(np.all(b >= 0))
        self.assertTrue(np.all(b.sum(axis=1) <= 1 + 1e-12))
        for seed in range(30):
            env = self.episode.create_environment(seed)
            means = 0.5 + env._coefficients.dot(b.T)
            self.assertTrue(np.all((means >= 0.15 - 1e-12) & (means <= 0.85 + 1e-12)))
            np.testing.assert_array_equal(means[:, 0], np.full(4, 0.5))

    def test_biomarkers_and_outcomes_stay_paired_and_sampling_is_explicit(self):
        env = self.episode.create_environment(2)
        args = {"site": "bridge-a", "x": 1, "dose": 0.6, "n": 128, "assay_n": 32}
        observed = env.experiment("trial", args)
        self.assertEqual(sum(r["z"] is not None for r in observed["records"]), 32)
        self.assertEqual(observed["assay_probability"], 0.25)
        self.assertTrue(all(r["y"] in (0, 1) for r in observed["records"]))
        self.assertEqual(env.action_cost("trial", args), 224)

    def test_generator_has_multiple_modifier_sets_and_no_site_label_answer(self):
        sets = set()
        for seed in range(60):
            env = self.episode.create_environment(seed)
            if env._blocked is None:
                terms = np.array([[x, z, x * z] for x, z in self.episode.CELLS]).T.dot(env._coefficients) / 4
                sets.add(tuple(np.linalg.norm(terms, axis=1) > 1e-8))
            other = self.episode.create_environment(seed ^ 1)
            self.assertEqual(env._site_probabilities, other._site_probabilities)
        self.assertGreaterEqual(len(sets), 5)

    def test_fixed_controls_do_not_spend_budget_on_unused_surveys(self):
        for name in ("fixed", "fixed_full_factorial", "random"):
            env = self.episode.create_environment(2)
            tools = []

            def experiment(tool, args):
                tools.append(tool)
                return env.experiment(tool, args)

            self.reference.POLICIES[name](env.public_problem(), experiment)
            self.assertNotIn("survey", tools)

    def test_all_scientific_controls_use_exactly_the_same_budget(self):
        for seed in (0, 2):
            for name in ("reference", "fixed", "fixed_full_factorial", "random", "source_only", "source_extrapolation"):
                with self.subTest(seed=seed, name=name):
                    _, _, _, cost, calls = self.run_policy(seed, name)
                    self.assertEqual(cost, 12000)
                    self.assertLess(calls, 64)

    def test_reference_rejects_unsupported_budget_before_sampling(self):
        env = self.episode.create_environment(2)
        problem = env.public_problem()
        problem["budget_units"] = 6000
        with self.assertRaises(ValueError):
            self.reference.solve(problem, lambda *a: self.fail("unsupported budget should not sample"))

    def test_prior_zero_and_vacuous_bounds_do_not_meet_joint_precision(self):
        for name in ("prior_zero", "bounds_only", "abstain"):
            rows = [self.run_policy(seed, name)[2] for seed in range(8)]
            self.assertEqual(sum(row["joint_success"]["numerator"] for row in rows), 0)

    def test_covariance_must_be_finite_symmetric_positive_semidefinite(self):
        env, claim, _, _, _ = self.run_policy(2, "fixed")
        for matrix in ([[1, 0, 0], [0, -1, 0], [0, 0, 1]],
                       [[1, 0.2, 0], [0, 1, 0], [0, 0, 1]],
                       [[float("nan"), 0, 0], [0, 1, 0], [0, 0, 1]]):
            bad = copy.deepcopy(claim)
            bad["curves"][0]["covariance"] = matrix
            with self.assertRaises(ValueError):
                env.validate_claim(bad)

    def test_reference_and_strong_fixed_recover_estimable_curves_but_are_not_certified(self):
        for name in ("reference", "fixed", "fixed_full_factorial"):
            rows = [self.run_policy(seed, name)[2] for seed in range(8)]
            self.assertLess(float(np.mean([row["curve_rmse"] for row in rows])), 0.09)
            self.assertTrue(all(row["discovery_coverage"]["value"] == 1 for row in rows))

    def test_partial_claim_does_not_guess_an_inaccessible_curve(self):
        _, claim, metrics, _, _ = self.run_policy(0, "reference")
        self.assertEqual(claim["decision"], "partial")
        self.assertIsNone(claim["curves"][1]["coefficients"])
        self.assertIsNone(claim["modifiers"])
        self.assertEqual(metrics["unsupported_point_claim_rate"]["numerator"], 0)
        self.assertEqual(metrics["correct_refusal_rate"]["value"], 1)
        self.assertEqual(metrics["mechanism_recovery"]["denominator"], 0)

    def test_bounds_only_and_abstention_never_earn_discovery_credit(self):
        for name in ("bounds_only", "abstain"):
            _, _, metrics, cost, _ = self.run_policy(0, name)
            self.assertEqual(cost, 0)
            self.assertEqual(metrics["discovery_coverage"]["numerator"], 0)
            self.assertIsNone(metrics["curve_rmse"])
            self.assertIsNone(metrics["population_prediction_rmse"])
        _, _, metrics, _, _ = self.run_policy(0, "bounds_only")
        self.assertEqual(metrics["population_bound_coverage"]["value"], 1)
        self.assertGreater(metrics["mean_population_bound_width"], 0.1)

    def test_source_data_do_not_authorize_target_point_extrapolation(self):
        _, claim, metrics, _, _ = self.run_policy(0, "source_only")
        self.assertEqual(claim["decision"], "partial")
        self.assertEqual(metrics["discovery_coverage"]["numerator"], 2)
        _, _, unsafe, _, _ = self.run_policy(0, "source_extrapolation")
        self.assertEqual(unsafe["unsupported_point_claim_rate"]["value"], 1)

    def test_confirmation_is_independent_and_contains_observations_not_truth(self):
        a, b = self.episode.create_environment(2), self.episode.create_environment(2)
        claim = self.reference.abstain(a.public_problem(), None)
        for _ in range(7):
            a.experiment("survey", {"site": "bridge-a", "x": 1, "n": 32})
        self.assertEqual(a.confirm(claim), b.confirm(claim))
        observed = np.array(a.confirm(claim)["cell_observed_means"])
        truth = 0.5 + a._coefficients.dot(self.episode.basis(a.confirm(claim)["doses"]).T)
        self.assertFalse(np.array_equal(observed, truth))
        fake = copy.deepcopy(a.confirm(claim))
        fake["cell_observed_means"][0][0] += 0.1
        with self.assertRaises(ValueError):
            a.evaluate(claim, fake)

    def test_cost_is_public_and_validation_never_consumes_a_cohort(self):
        a, b = self.episode.create_environment(2), self.episode.create_environment(2)
        args = {"site": "bridge-a", "x": 1, "dose": 0.6, "n": 128, "assay_n": 32}
        for key, value in (("dose", float("nan")), ("dose", 10 ** 1000), ("x", True),
                           ("x", 0), ("n", 7), ("n", 257), ("assay_n", 129)):
            with self.assertRaises(ValueError):
                a.action_cost("trial", dict(args, **{key: value}))
        self.assertEqual(a.experiment("trial", args), b.experiment("trial", args))

    def test_claim_shape_rejects_nonfinite_and_illformed_values_only(self):
        env, claim, _, _, _ = self.run_policy(2, "fixed")
        for key, value in (("decision", "yes"), ("curves", []), ("modifiers", ["X", "X"]), ("modifiers", [{}])):
            with self.assertRaises(ValueError):
                env.validate_claim(dict(claim, **{key: value}))
        broken = copy.deepcopy(claim)
        broken["curves"][0]["coefficients"][0] = float("nan")
        with self.assertRaises(ValueError):
            env.validate_claim(broken)
        wrong = copy.deepcopy(claim)
        wrong["curves"][0]["coefficients"] = [0.0, 0.0, 0.0]
        env.validate_claim(wrong)

    def test_replay_is_identical_and_public_objects_are_copies(self):
        first = self.run_policy(2, "reference")
        second = self.run_policy(2, "reference")
        self.assertEqual(first[1:], second[1:])
        public = first[0].public_problem()
        public["target_populations"][0]["cell_weights"][0] = 99
        self.assertLess(first[0].public_problem()["target_populations"][0]["cell_weights"][0], 1)


if __name__ == "__main__":
    unittest.main()
