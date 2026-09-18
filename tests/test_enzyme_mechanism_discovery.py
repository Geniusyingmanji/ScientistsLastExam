"""Scientific and protocol regressions for the candidate enzyme episode."""
from __future__ import annotations

import copy
import json
import unittest

import numpy as np
from scipy.integrate import solve_ivp

from benchmarks.Biology.EnzymeMechanismDiscovery import model
from benchmarks.Biology.EnzymeMechanismDiscovery.verification.episode import create_environment
from benchmarks.Biology.EnzymeMechanismDiscovery.verification.reference import (
    abstain_control, fixed_design_control, initial_rate_control, no_query_control, solve,
)


def design(pulse=None):
    return {"initial": {"substrate": 2.4, "product": 0.7, "enzyme": 0.8},
            "times": [0.1, 0.8, 1.9, 3.0, 4.7, 8.0],
            "channels": list(model.CHANNELS), "pulse": pulse}


class EnzymeScientificTests(unittest.TestCase):
    def test_mass_balance_and_nonnegative_species_survive_each_pulse(self):
        parameters = create_environment(5)._parameters
        for species in ("substrate", "product", "enzyme"):
            case = design({"time": 3.0, "species": species, "amount": 1.2})
            trajectory = model.simulate(parameters, case)
            expected = np.array([3.1 + (1.2 if t >= 3.0 and species != "enzyme" else 0.0)
                                 for t in case["times"]])
            np.testing.assert_allclose(trajectory.sum(axis=1), expected, atol=2e-7)
            self.assertGreaterEqual(float(trajectory.min()), -1e-8)

    def test_solver_matches_independent_four_state_integration(self):
        parameters = create_environment(5)._parameters
        case = design()
        p = parameters

        def derivative(t, y):
            s, x, product, enzyme = y
            v1 = p["kcat"] * enzyme * s / (p["km"] * (1 + product / p["ki"]) + s + s * s / p["ks"])
            v2 = p["k2"] * x
            return [-v1, v1 - v2, v2, -p["kd"] * enzyme]

        independent = solve_ivp(derivative, (0.0, 8.0), [2.4, 0.0, 0.7, 0.8],
                                t_eval=case["times"], rtol=1e-11, atol=1e-13)
        np.testing.assert_allclose(model.simulate(p, case), independent.y[:3].T, atol=8e-7)

    def test_initial_rates_cannot_reveal_decay_or_intermediate_turnover(self):
        left, right = create_environment(5), create_environment(5)
        left._parameters["kd"] = None
        right._parameters["kd"] = 0.2
        left._parameters["k2"] = 0.3
        right._parameters["k2"] = 1.2
        self.assertEqual(left.public_problem(), right.public_problem())
        for substrate in (0.2, 1.0, 5.5):
            for product in (0.0, 2.0):
                arguments = {"initial": {"substrate": substrate, "product": product, "enzyme": 1.0}}
                self.assertEqual(left.experiment("initial_rate", arguments), right.experiment("initial_rate", arguments))
        a = model.simulate(left._parameters, design())
        b = model.simulate(right._parameters, design())
        self.assertGreater(float(np.sqrt(((a - b) ** 2).mean())), 0.15)

    def test_product_perturbation_breaks_the_initial_feedback_confound(self):
        left, right = create_environment(5), create_environment(5)
        right._parameters["ki"] = None
        for substrate in (0.3, 1.0, 4.0):
            self.assertEqual(model.rate(left._parameters, substrate, 0.0, 1.0),
                             model.rate(right._parameters, substrate, 0.0, 1.0))
        self.assertGreater(abs(model.rate(left._parameters, 1.0, 2.0, 1.0) -
                               model.rate(right._parameters, 1.0, 2.0, 1.0)), 0.1)

    def test_truth_blind_witness_recovers_all_eight_compositions_within_budget(self):
        # Each public generator composition occurs once; no answer is supplied
        # to the witness. This is attainability evidence, not model difficulty.
        seen = set()
        for seed in (0, 2, 3, 5, 7, 10, 11, 22):
            environment = create_environment(seed)
            seen.add(environment._mechanism)
            claim = solve(environment.public_problem(), environment.experiment)
            environment.validate_claim(claim)
            metrics = environment.evaluate(claim, environment.confirm(claim))
            self.assertEqual(metrics["mechanism_recovery"]["numerator"], 1, seed)
            self.assertLess(metrics["confirmation_rmse_mM"], 0.025, seed)
            self.assertLessEqual(metrics["experiment_budget_used"], environment.budget_units)
        self.assertEqual(len(seen), 8)

    def test_static_control_misses_decay_in_paired_world(self):
        environment = create_environment(5)
        claim = initial_rate_control(environment.public_problem(), environment.experiment)
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertNotIn("enzyme_decay", claim["mechanism"])
        self.assertEqual(metrics["mechanism_recovery"]["numerator"], 0)
        self.assertEqual(metrics["false_discovery_rate"]["numerator"], 1)
        self.assertGreater(metrics["confirmation_rmse_mM"], 0.025)

    def test_fixed_and_adaptive_controls_have_equal_charged_cost(self):
        costs = []
        for policy in (solve, fixed_design_control):
            environment = create_environment(5)
            claim = policy(environment.public_problem(), environment.experiment)
            environment.validate_claim(claim)
            costs.append(environment._spent)
        self.assertEqual(costs, [104, 104])


class EnzymeProtocolTests(unittest.TestCase):
    def test_public_problem_contains_no_seed_or_answer_and_is_independent_copy(self):
        left, right = create_environment(1), create_environment(5)
        self.assertEqual(left.public_problem(), right.public_problem())
        public = left.public_problem()
        public["active_parameter_ranges"]["kcat"][0] = -9
        self.assertGreater(left.public_problem()["active_parameter_ranges"]["kcat"][0], 0)
        self.assertNotIn("seed", json.dumps(left.public_problem()))

    def test_cost_accounts_for_samples_channels_and_pulses(self):
        environment = create_environment(5)
        self.assertEqual(environment.action_cost("time_course", design()), 22)
        self.assertEqual(environment.action_cost("time_course", design({"time": 3.0, "species": "enzyme", "amount": 0.5})), 26)
        self.assertEqual(environment.action_cost("initial_rate", {"initial": design()["initial"]}), 3)

    def test_invalid_experiments_are_rejected_without_spending(self):
        environment = create_environment(5)
        mutations = [
            ("times", []), ("times", [1.0, 1.0]), ("times", [float("nan")]),
            ("times", [True]), ("times", [0.0]), ("times", [8.1]),
            ("times", [10 ** 1000]),
            ("channels", []), ("channels", ["product", "product"]),
            ("channels", ["enzyme"]), ("channels", [{}]),
            ("pulse", {"time": 8.0, "species": "enzyme", "amount": 0.5}),
            ("pulse", {"time": 3.0, "species": "enzyme", "amount": float("inf")}),
            ("initial", {"substrate": 0.0, "product": 0.0, "enzyme": 1.0}),
        ]
        for key, value in mutations:
            case = design()
            case[key] = value
            with self.assertRaises(ValueError):
                environment.experiment("time_course", case)
        self.assertEqual(environment._spent, 0)
        self.assertEqual(environment._evidence, {})

    def test_budget_exhaustion_is_atomic_and_queries_after_commit_are_closed(self):
        environment = create_environment(5)
        args = {"initial": design()["initial"]}
        for _ in range(72):
            environment.experiment("initial_rate", args)
        self.assertEqual(environment._spent, 216)
        with self.assertRaises(ValueError):
            environment.experiment("initial_rate", args)
        self.assertEqual(len(environment._evidence), 72)
        environment.confirm(abstain_control(environment.public_problem()))
        with self.assertRaises(ValueError):
            environment.experiment("initial_rate", args)

    def test_confirmation_noise_and_design_do_not_depend_on_exploration_history(self):
        untouched, explored = create_environment(5), create_environment(5)
        explored.experiment("time_course", design())
        for _ in range(10):
            explored.experiment("initial_rate", {"initial": design()["initial"]})
        claim = no_query_control(untouched.public_problem())
        self.assertEqual(untouched.confirm(claim), explored.confirm(claim))

    def test_commit_is_immutable_and_confirmation_cannot_be_forged(self):
        environment = create_environment(5)
        claim = no_query_control(environment.public_problem())
        confirmation = environment.confirm(claim)
        self.assertEqual(confirmation, environment.confirm(copy.deepcopy(claim)))
        modified = copy.deepcopy(claim)
        modified["parameters"]["kcat"] += 0.1
        with self.assertRaises(ValueError):
            environment.confirm(modified)
        with self.assertRaises(ValueError):
            environment.evaluate(modified, confirmation)
        confirmation["experiments"][0]["observations"][0]["substrate"] += 1
        with self.assertRaises(ValueError):
            environment.evaluate(claim, confirmation)
        self.assertNotEqual(confirmation, environment.confirm(claim))

    def test_invalid_claims_cannot_forge_evidence_or_parameters(self):
        environment = create_environment(5)
        base = no_query_control(environment.public_problem())
        cases = []
        for value in (float("nan"), float("inf"), True, 100.0, None, 10 ** 1000):
            claim = copy.deepcopy(base)
            claim["parameters"]["kcat"] = value
            cases.append(claim)
        for key, value in (("evidence_ids", ["assay-0001"]), ("mechanism", ["unknown"]),
                           ("mechanism", ["enzyme_decay", "enzyme_decay"]), ("decision", "perhaps")):
            claim = copy.deepcopy(base)
            claim[key] = value
            cases.append(claim)
        claim = copy.deepcopy(base)
        claim["parameters"]["kd"] = 0.1
        cases.append(claim)
        for claim in cases:
            with self.assertRaises(ValueError):
                environment.validate_claim(claim)
        self.assertIsNone(environment._committed)

    def test_all_abstain_is_zero_and_undefined_denominators_are_null(self):
        environment = create_environment(5)
        claim = abstain_control(environment.public_problem())
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["discovery_coverage"]["numerator"], 0)
        for key in ("false_discovery_rate", "module_false_discovery_rate", "correct_refusal_rate"):
            self.assertEqual(metrics[key]["denominator"], 0)
            self.assertIsNone(metrics[key]["value"])
        json.dumps(metrics, allow_nan=False)

    def test_fdr_denominators_count_claims_and_positive_modules_separately(self):
        environment = create_environment(22)  # No optional modules.
        claim = no_query_control(environment.public_problem())
        claim["mechanism"] = list(model.MODULES)
        claim["parameters"].update(ki=1.0, ks=3.0, kd=0.12)
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertEqual(metrics["false_discovery_rate"]["numerator"], 1)
        self.assertEqual(metrics["false_discovery_rate"]["denominator"], 1)
        self.assertEqual(metrics["module_false_discovery_rate"]["numerator"], 3)
        self.assertEqual(metrics["module_false_discovery_rate"]["denominator"], 3)


if __name__ == "__main__":
    unittest.main()
