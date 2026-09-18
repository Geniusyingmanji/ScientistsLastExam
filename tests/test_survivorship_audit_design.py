"""Scientific invariants for the unregistered, uncalibrated audit episode pilot."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path
import statistics
import unittest

import numpy as np


TASK = Path(__file__).resolve().parents[1] / "benchmarks/ComputerScience/SurvivorshipAuditDesign"


def _load(name):
    spec = importlib.util.spec_from_file_location("audit_" + name, TASK / "verification" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SurvivorshipAuditDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episode = _load("episode")
        cls.reference = _load("reference")

    def _run(self, seed, candidate):
        environment = self.episode.create_environment(seed)
        used = 0

        def experiment(tool, args):
            nonlocal used
            used += environment.action_cost(tool, args)
            self.assertLessEqual(used, environment.budget_units)
            return environment.experiment(tool, args)

        claim = candidate(environment.public_problem(), experiment)
        environment.validate_claim(claim)
        confirmation = environment.confirm(claim)
        return environment, claim, environment.evaluate(claim, confirmation), used

    def test_public_contract_and_artifacts_are_json_and_do_not_expose_truth(self):
        environment = self.episode.create_environment(1200)
        problem = environment.public_problem()
        self.assertEqual(problem["budget_units"], 12000)
        self.assertEqual(set(problem["action_schemas"]), {"trial"})
        for key in ("seed", "effects", "population_effect", "selection_parameters", "variant"):
            self.assertNotIn(key, problem)
        claim = {"abstain": True, "confidence": 0.0}
        json.dumps(problem, allow_nan=False)
        json.dumps(environment.confirm(claim), allow_nan=False)
        json.dumps(environment.evaluate(claim, environment.confirm(claim)), allow_nan=False)
        problem["target_weights"][0] = 100
        self.assertEqual(environment.public_problem()["target_weights"][0], 0.1)

    def test_cost_validates_only_public_inputs_and_does_not_consume_randomness(self):
        args = {"stratum": 2, "treatment": 1, "n": 512, "audit_n": 240}
        a, b = self.episode.create_environment(1200), self.episode.create_environment(1200)
        for _ in range(10):
            self.assertEqual(a.action_cost("trial", args), 1472)
        self.assertEqual(a.experiment("trial", args), b.experiment("trial", args))
        for seed in (1201, 1202, 9900):
            self.assertEqual(self.episode.create_environment(seed).action_cost("trial", args), 1472)

    def test_malformed_actions_rejected_before_any_observation(self):
        good = {"stratum": 2, "treatment": 1, "n": 512, "audit_n": 240}
        wrong = [{}, None, {**good, "extra": 0}]
        for key, values in {"stratum": [-1, 4, True, "1", 1.0], "treatment": [2, False],
                            "n": [31, 513, float("nan")], "audit_n": [-1, 513]}.items():
            wrong.extend({**good, key: value} for value in values)
        env = self.episode.create_environment(1200)
        for args in wrong:
            with self.subTest(args=args), self.assertRaises(ValueError):
                env.action_cost("trial", args)
        with self.assertRaises(ValueError):
            env.action_cost("truth", good)
        self.assertEqual(env.experiment("trial", good), self.episode.create_environment(1200).experiment("trial", good))

    def test_audit_accounting_and_inclusion_probabilities(self):
        env = self.episode.create_environment(1200)
        for slots in (0, 4, 512):
            args = {"stratum": 1, "treatment": 1, "n": 512, "audit_n": slots}
            obs = env.experiment("trial", args)
            self.assertEqual(obs["n_returned"] + obs["n_missing"], 512)
            self.assertEqual(obs["n_returned"], len(obs["survivor_outcomes"]))
            self.assertEqual(obs["n_audited"], len(obs["audited_outcomes"]))
            self.assertEqual(obs["n_audited"], min(slots, obs["n_missing"]))
            self.assertEqual(obs["audit_inclusion_probability"], obs["n_audited"] / obs["n_missing"])
            self.assertEqual(env.action_cost("trial", args), 512 + 4 * slots)

    def test_return_rate_shortcut_cannot_distinguish_opposite_or_null_effects(self):
        claims = []
        for seed in (1200, 1201, 1202):
            _, claim, _, _ = self._run(seed, self.reference.survival_contrast)
            claims.append(claim)
        self.assertEqual(claims[0], claims[1])
        self.assertEqual(claims[1], claims[2])
        environments = [self.episode.create_environment(seed) for seed in (1200, 1201, 1202)]
        self.assertGreater(environments[0]._population_effect, 0)
        self.assertEqual(environments[1]._population_effect, 0)
        self.assertLess(environments[2]._population_effect, 0)

    def test_population_truth_is_weighted_heterogeneous_effect_not_a_global_sign(self):
        for seed in range(1200, 1212):
            env = self.episode.create_environment(seed)
            self.assertAlmostEqual(float(np.dot(env.public_problem()["target_weights"], env._effects)), env._population_effect)
            self.assertGreater(float(np.std(env._effects)), 0.1)

    def test_random_followup_estimator_is_unbiased_across_repeated_cohorts(self):
        env = self.episode.create_environment(1200)
        estimates, survivor_estimates = [], []
        for _ in range(400):
            obs = env.experiment("trial", {"stratum": 0, "treatment": 1, "n": 512, "audit_n": 100})
            estimates.append(self.reference.audit_mean(obs)[0])
            survivor_estimates.append(statistics.mean(obs["survivor_outcomes"]))
        truth = env._mu[0] + env._effects[0]
        monte_carlo_se = statistics.stdev(estimates) / math.sqrt(len(estimates))
        self.assertLess(abs(statistics.mean(estimates) - truth), 3.5 * monte_carlo_se)
        self.assertGreater(abs(statistics.mean(survivor_estimates) - truth), 0.25)

    def test_complete_followup_equals_the_full_cohort_mean(self):
        env = self.episode.create_environment(1200)
        obs = env.experiment("trial", {"stratum": 0, "treatment": 1, "n": 512, "audit_n": 512})
        mean, variance = self.reference.audit_mean(obs)
        all_outcomes = obs["survivor_outcomes"] + obs["audited_outcomes"]
        self.assertAlmostEqual(mean, statistics.mean(all_outcomes))
        self.assertAlmostEqual(variance, statistics.variance(all_outcomes) / 512)

    def test_reference_has_materially_lower_quantitative_error_than_unadjusted_controls(self):
        # Construction diagnostic, deliberately not a frontier difficulty claim.
        panels = {}
        for name in ("propose", "survivors_only", "survival_contrast", "no_query"):
            panels[name] = [self._run(seed, getattr(self.reference, name))[2] for seed in range(1200, 1230)]
        def error(name):
            return statistics.mean(r["population_absolute_error"] for r in panels[name] if r["population_absolute_error"] is not None)
        self.assertLess(error("propose"), error("survivors_only") / 3)
        self.assertLess(error("propose"), error("survival_contrast") / 3)
        self.assertLess(error("propose"), error("no_query") / 3)
        self.assertGreater(statistics.mean(r["discovery_coverage"] for r in panels["propose"]), 0.8)

    def test_reference_respects_budget_and_replays_exactly(self):
        _, a, metrics_a, spent_a = self._run(1200, self.reference.propose)
        _, b, metrics_b, spent_b = self._run(1200, self.reference.propose)
        self.assertEqual(spent_a, 11776)
        self.assertEqual(spent_a, spent_b)
        self.assertEqual(a, b)
        self.assertEqual(metrics_a, metrics_b)

    def test_matched_budget_controls_spend_as_much_as_the_reference(self):
        for name in ("survivors_only_matched_budget", "survival_contrast_matched_budget"):
            _, _, _, used = self._run(1200, self.reference.POLICIES[name])
            self.assertEqual(used, 11776)
        for name in self.reference.POLICIES:
            self.assertTrue(callable(self.reference.POLICIES[name]))

    def test_fresh_exploratory_cohorts_and_reserved_confirmation(self):
        a, b = self.episode.create_environment(1200), self.episode.create_environment(1200)
        args = {"stratum": 0, "treatment": 1, "n": 512, "audit_n": 240}
        self.assertNotEqual(a.experiment("trial", args), a.experiment("trial", args))
        for _ in range(9):
            a.experiment("trial", args)
        claim = {"abstain": True, "confidence": 0.0}
        self.assertEqual(a.confirm(claim), b.confirm(claim))
        # Confirmation cannot be adaptively changed by choosing a different claim.
        changed_claim = self.reference.no_query(b.public_problem(), None)
        self.assertEqual(a.confirm(claim), a.confirm(changed_claim))
        self.assertNotEqual(a.confirm(claim)["population_effect"], a._population_effect)

    def test_claim_validation_checks_shape_not_hidden_correctness(self):
        env = self.episode.create_environment(1200)
        claim = self.reference.no_query(env.public_problem(), None)
        for effect in (-100.0, 0.0, 100.0):
            wrong = copy.deepcopy(claim)
            wrong["population_effect"] = effect
            env.validate_claim(wrong)
        invalid = [None, {}, {"abstain": "yes", "confidence": 0.95}, {"abstain": True, "confidence": float("nan")},
                   {"abstain": True, "confidence": False}, {"abstain": True, "confidence": 0, "extra": 1}]
        for key, value in [("population_effect", True), ("population_effect", float("inf")), ("confidence", 0.90),
                           ("population_interval", [1, -1]), ("stratum_effects", [1, 2]),
                           ("stratum_intervals", [[0, 1]] * 3), ("effect_class", [])]:
            invalid.append({**claim, key: value})
        for item in invalid:
            with self.subTest(claim=item), self.assertRaises(ValueError):
                env.validate_claim(item)

    def test_axes_have_correct_denominators_and_blanket_abstention_has_no_recovery(self):
        _, _, abstain, _ = self._run(1201, lambda p, e: {"abstain": True, "confidence": 0.0})
        self.assertEqual(abstain["mechanism_recovery"], 0)
        self.assertEqual(abstain["effect_estimation_score"], 0)
        self.assertEqual(abstain["discovery_coverage_numerator"], 0)
        self.assertEqual(abstain["false_discovery_denominator"], 0)
        self.assertIsNone(abstain["false_discovery_rate"])
        self.assertEqual(abstain["correct_refusal_denominator"], 0)
        self.assertIsNone(abstain["correct_refusal_rate"])
        self.assertNotIn("combined_score", abstain)
        _, _, false, _ = self._run(1201, self.reference.no_query)
        self.assertEqual(false["false_discovery_numerator"], 1)
        self.assertEqual(false["false_discovery_denominator"], 1)
        self.assertEqual(false["null_false_positive_numerator"], 1)
        self.assertEqual(false["null_false_positive_denominator"], 1)

    def test_wrong_interval_cannot_turn_correct_sign_into_a_supported_claim(self):
        env, claim, _, _ = self._run(1200, self.reference.propose)
        self.assertFalse(claim["abstain"])
        claim["population_interval"] = [-100, 100]
        metrics = env.evaluate(claim, env.confirm(claim))
        self.assertEqual(metrics["mechanism_recovery"], 0)
        self.assertEqual(metrics["confirmation_success"], 0)
        self.assertEqual(metrics["population_interval_coverage"], 1)

    def test_corrupted_confirmation_is_an_evaluator_error_not_scientific_failure(self):
        env = self.episode.create_environment(1200)
        claim = self.reference.no_query(env.public_problem(), None)
        confirmation = env.confirm(claim)
        confirmation["population_effect"] += 1
        with self.assertRaises(ValueError):
            env.evaluate(claim, confirmation)

    def test_extreme_finite_but_wrong_estimates_do_not_overflow_the_evaluator(self):
        env = self.episode.create_environment(1200)
        claim = self.reference.no_query(env.public_problem(), None)
        claim.update(population_effect=1e308, population_interval=[-1e308, 1e308],
                     stratum_effects=[-1e308] * 4, stratum_intervals=[[-1e308, 1e308]] * 4)
        metrics = env.evaluate(claim, env.confirm(claim))
        json.dumps(metrics, allow_nan=False)
        self.assertEqual(metrics["mechanism_recovery"], 0)
        claim["population_effect"] = 10 ** 1000
        with self.assertRaises(ValueError):
            env.validate_claim(claim)


if __name__ == "__main__":
    unittest.main()
