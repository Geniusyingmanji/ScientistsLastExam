"""Recovery model invariants, confounds, resolution certificates and protocol."""
from __future__ import annotations

import copy
import unittest
import numpy as np
from scipy.integrate import solve_ivp

from benchmarks.Biology.EnzymeRecoveryDesign.model import (
    activity, observable, canonical_pools, order_two_certificate, RESOLUTION,
)
from benchmarks.Biology.EnzymeRecoveryDesign.verification.episode import create_environment, _pool_equivalences
from benchmarks.Biology.EnzymeRecoveryDesign.verification.reference import (
    assay, abstain, fixed_optical, solve, no_query, always_max_order_fit,
)


class RecoveryScienceTests(unittest.TestCase):
    def test_analytic_activity_matches_independent_loading_and_recovery_ode(self):
        model = {"k_loss": 0.035, "pools": [{"fraction": 0.3, "kon": 0.6, "koff": 0.08},
                                          {"fraction": 0.2, "kon": 1.1, "koff": 0.7}]}
        dose, loading, washout = 1.4, 3.2, 5.5
        def rhs(t, y):
            return [p["kon"] * dose * (p["fraction"] - y[j]) - p["koff"] * y[j]
                    for j, p in enumerate(model["pools"])] + [-model["k_loss"] * dose * y[2]]
        loaded = solve_ivp(rhs, (0, loading), [0, 0, 1], rtol=1e-11, atol=1e-13).y[:, -1]
        recovered = [loaded[j] * np.exp(-p["koff"] * washout) for j, p in enumerate(model["pools"])]
        self.assertAlmostEqual(float(activity(model, dose, loading, washout)), loaded[2] * (1 - sum(recovered)), places=10)

    def test_activity_bounds_and_washout_monotonicity(self):
        for seed in range(24):
            model = create_environment(seed)._model
            values = activity(model, 3.0, 6.0, np.linspace(0, 40, 80))
            self.assertTrue(np.all((values >= 0) & (values <= 1)))
            self.assertTrue(np.all(np.diff(values) >= -1e-12))

    def test_one_loading_curve_confounds_sensor_and_biology_but_controls_separate(self):
        biological = {"k_loss": 0.0, "pools": [{"fraction": 0.2, "kon": 0.12, "koff": 0.2}]}
        clean = {"gain": 1.0, "offset": 0.0, "carryover": 0.0, "tau": 5.0}
        dose, loading = 1.0, 2.0
        amplitude = 1 - float(activity(biological, dose, loading, 0.0))
        contaminated = dict(clean, carryover=-amplitude / (0.5 * (1 - np.exp(-loading / 5.0))))
        inert = {"k_loss": 0.0, "pools": []}
        for time in np.linspace(0, 40, 31):
            args = assay(dose, loading, time)
            self.assertAlmostEqual(float(observable(biological, clean, args)), float(observable(inert, contaminated, args)), places=12)
        for kind in ("blank", "orthogonal"):
            args = assay(dose, loading, 0.0, control="blank" if kind == "blank" else "specimen",
                         readout="orthogonal" if kind == "orthogonal" else "optical")
            self.assertGreater(abs(float(observable(biological, clean, args) - observable(inert, contaminated, args))), 0.03)
        # This confound is at ONE loading condition. Broad optical loading
        # designs are a valid independent route and are not prohibited.
        args = assay(3.0, 0.3, 0.0)
        self.assertGreater(abs(float(observable(biological, clean, args) - observable(inert, contaminated, args))), 0.001)

    def test_one_exponential_never_gets_two_pool_certificate(self):
        for rate in np.geomspace(0.005, 3.0, 15):
            model = {"k_loss": 0.04, "pools": [{"fraction": 0.8, "kon": 1.5, "koff": float(rate)}]}
            self.assertLessEqual(order_two_certificate(model), 0.0)

    def test_certificate_bound_covers_arbitrary_four_sample_errors(self):
        rng = np.random.default_rng(42)
        for _ in range(1000):
            original = rng.uniform(0.5, 1.0) - rng.uniform(0.1, 0.5) * np.exp(-rng.uniform(0.01, 2.0) * np.arange(4))
            perturbed = original + rng.uniform(-RESOLUTION, RESOLUTION, size=4)
            d0, d1, d2 = np.diff(perturbed)
            bound = 2 * RESOLUTION * (abs(d0) + abs(d2) + 2 * abs(d1)) + 8 * RESOLUTION ** 2
            self.assertLessEqual(abs(d0 * d2 - d1 * d1), bound + 1e-12)

    def test_resolved_and_unresolved_worlds_are_not_optimizer_failure_labels(self):
        self.assertEqual(_pool_equivalences(create_environment(5)._model)[0], {2})
        self.assertGreater(order_two_certificate(create_environment(5)._model), 0)
        self.assertEqual(_pool_equivalences(create_environment(0)._model)[0], set())
        self.assertLessEqual(order_two_certificate(create_environment(0)._model), 0)

    def test_identical_pool_splitting_preserves_canonical_order_and_score(self):
        environment = create_environment(9)
        model = copy.deepcopy(environment._model)
        pool = model["pools"][0]
        pool["fraction"] /= 2
        model["pools"].append(copy.deepcopy(pool))
        self.assertEqual(len(canonical_pools(model["pools"])), 1)
        claim = {"decision": "discover", "irreversible_loss": model["k_loss"] > 0,
                 "pool_count": 1, "model": model, "evidence_ids": []}
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertAlmostEqual(metrics["prediction_score"], 1.0)
        self.assertEqual(metrics["mechanism_recovery"]["value"], 1.0)
        wrong = copy.deepcopy(claim)
        wrong["pool_count"] = 2  # Claims TWO resolved populations, contradicts its own exact duplicate model.
        with self.assertRaises(ValueError):
            create_environment(9).validate_claim(wrong)

    def test_failed_oracle_search_cannot_reject_a_positive_lower_order_witness(self):
        environment = create_environment(9)
        environment._allowed_counts = set()  # Simulate an inconclusive oracle approximation search.
        model = copy.deepcopy(environment._model)
        claim = {"decision": "discover", "irreversible_loss": model["k_loss"] > 0,
                 "pool_count": 1, "model": model, "evidence_ids": []}
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertEqual(metrics["mechanism_recovery"]["numerator"], 2)

    def test_candidate_zero_order_witness_can_settle_inconclusive_oracle_search(self):
        environment = create_environment(2)
        environment._allowed_counts = set()
        model = copy.deepcopy(environment._model)
        claim = {"decision": "discover", "irreversible_loss": model["k_loss"] > 0,
                 "pool_count": 0, "model": model, "evidence_ids": []}
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertEqual(metrics["mechanism_recovery"]["numerator"], 2)
        self.assertEqual(metrics["mechanism_recovery"]["denominator"], 2)

    def test_unresolved_order_is_excluded_from_accuracy_denominator(self):
        environment = create_environment(0)
        self.assertEqual(environment._allowed_counts, set())
        model = copy.deepcopy(environment._model)
        claim = {"decision": "partial", "irreversible_loss": model["k_loss"] > 0,
                 "pool_count": None, "model": model, "evidence_ids": []}
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertEqual(metrics["mechanism_recovery"]["numerator"], 1)
        self.assertEqual(metrics["mechanism_recovery"]["denominator"], 1)
        self.assertEqual(metrics["order_resolvability_rate"]["numerator"], 0)
        self.assertEqual(metrics["order_refusal_rate"]["numerator"], 1)
        self.assertNotIn("combined_score", metrics)

    def test_always_max_order_fit_does_not_receive_order_credit_for_no_pool_world(self):
        environment = create_environment(2)
        claim = always_max_order_fit(environment.public_problem(), environment.experiment)
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertEqual(claim["pool_count"], 2)
        self.assertEqual(metrics["false_discovery_rate"]["numerator"], 1)
        self.assertLessEqual(metrics["mechanism_recovery"]["numerator"], 1)


class RecoveryProtocolTests(unittest.TestCase):
    def test_public_contract_does_not_reveal_private_world(self):
        self.assertEqual(create_environment(0).public_problem(), create_environment(99).public_problem())

    def test_invalid_public_inputs_do_not_charge(self):
        environment = create_environment(0)
        for value in (True, -1, float("inf"), float("nan"), 10 ** 1000):
            args = assay()
            args["dose"] = value
            with self.assertRaises(ValueError):
                environment.experiment("assay", args)
        self.assertEqual(environment._spent, 0)

    def test_budget_and_rescue_are_charged(self):
        environment = create_environment(0)
        self.assertEqual(environment.action_cost("assay", assay(rescue=0.2)), 2)
        self.assertEqual(environment.action_cost("assay", assay(readout="orthogonal", rescue=0.2)), 4)
        for _ in range(48):
            environment.experiment("assay", assay())
        with self.assertRaises(ValueError):
            environment.experiment("assay", assay())
        self.assertEqual(environment._spent, 48)

    def test_confirmation_is_history_independent_and_claim_is_immutable(self):
        a, b = create_environment(0), create_environment(0)
        b.experiment("assay", assay())
        claim = abstain(a.public_problem())
        self.assertEqual(a.confirm(claim), b.confirm(claim))
        with self.assertRaises(ValueError):
            a.experiment("assay", assay())
        with self.assertRaises(ValueError):
            a.confirm(no_query(a.public_problem()))
        changed = copy.deepcopy(a.confirm(claim))
        changed["observations"][0]["value"] += 1
        with self.assertRaises(ValueError):
            a.evaluate(claim, changed)

    def test_all_abstain_and_zero_denominators(self):
        environment = create_environment(0)
        claim = abstain(environment.public_problem())
        metrics = environment.evaluate(claim, environment.confirm(claim))
        self.assertNotIn("combined_score", metrics)
        self.assertEqual(metrics["prediction_score"], 0)
        self.assertEqual(metrics["mechanism_recovery"]["numerator"], 0)
        self.assertIsNone(metrics["false_discovery_rate"]["value"])
        self.assertEqual(metrics["false_discovery_rate"]["denominator"], 0)

    def test_reference_and_strong_fixed_are_valid_and_exactly_cost_matched(self):
        for policy in (solve, fixed_optical):
            environment = create_environment(5)
            claim = policy(environment.public_problem(), environment.experiment)
            environment.validate_claim(claim)
            metrics = environment.evaluate(claim, environment.confirm(claim))
            self.assertEqual(metrics["experiment_budget_used"], 48)
            self.assertLess(metrics["confirmation_rmse"], 0.08)


if __name__ == "__main__":
    unittest.main()
