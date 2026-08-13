from __future__ import annotations

import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from sle.evaluate import evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Biology/GeneNetworkIntervention"


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("gene_network_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load_oracle()


class GeneNetworkInterventionTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "SystemsBiology/GeneNetworkIntervention", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    def test_world_panel_and_exact_mechanism_refusal_prediction(self):
        self.assertEqual(len(ORACLE.DEVELOPMENT_SPECS), 6)
        self.assertEqual(len(ORACLE.HELDOUT_SPECS), 5)
        self.assertGreaterEqual(
            sum(spec[2] == "in_library" for spec in ORACLE.DEVELOPMENT_SPECS), 4
        )
        self.assertGreaterEqual(
            sum(spec[2] == "in_library" for spec in ORACLE.HELDOUT_SPECS), 3
        )
        for specs in (ORACLE.DEVELOPMENT_SPECS, ORACLE.HELDOUT_SPECS):
            for spec in specs:
                world = ORACLE._world(spec)
                returned = ORACLE._truth_submission(world)
                values = ORACLE._validate_submission(returned)
                mechanism = ORACLE._mechanism_metrics(
                    world, values[0], values[1], values[2], values[3], values[6]
                )
                self.assertAlmostEqual(mechanism["mechanism_quality"], 1.0)
                if world["kind"] == "in_library":
                    self.assertAlmostEqual(
                        ORACLE._prediction_score(
                            world, values[0], values[2], values[3]
                        ),
                        1.0,
                        places=10,
                    )
                    self.assertGreater(
                        ORACLE._decision_score(world, values[4], shifted=False), 0.999
                    )
                else:
                    self.assertTrue(mechanism["correct_refusal"])

    def test_public_rk4_matches_independent_solve_ivp(self):
        for spec in ORACLE.DEVELOPMENT_SPECS[:4]:
            world = ORACLE._world(spec)
            rng = np.random.default_rng(world["seed"] + 31)
            controls = np.zeros((40, ORACLE.N_GENES), dtype=float)
            targets = rng.choice(ORACLE.N_GENES, size=2, replace=False)
            controls[:, targets] = rng.uniform(-1.5, 1.5, size=(40, 2))
            initial = ORACLE._steady_state(world)[:ORACLE.N_GENES]
            observed = ORACLE._simulate(world, controls, initial_state=initial)

            state = initial.copy()
            independent = [state.copy()]
            for control in controls:
                weights = np.asarray(world["weights"], dtype=float)
                biases = np.asarray(world["biases"], dtype=float)
                decays = np.asarray(world["decays"], dtype=float)

                def independent_rhs(_, value):
                    linear = biases + (2.0 * value - 1.0) @ weights + control
                    sigmoid = 1.0 / (1.0 + np.exp(-np.clip(linear, -40.0, 40.0)))
                    return decays * (sigmoid - value)

                result = solve_ivp(
                    independent_rhs,
                    (0.0, ORACLE.DT),
                    state,
                    method="DOP853",
                    rtol=1e-11,
                    atol=1e-13,
                )
                self.assertTrue(result.success)
                state = result.y[:, -1]
                independent.append(state.copy())
            self.assertLess(
                float(np.max(np.abs(observed - np.asarray(independent)))), 2e-7
            )

    def test_vectorized_intervention_normalization_matches_scalar_solver(self):
        world = ORACLE._world(ORACLE.DEVELOPMENT_SPECS[0])
        plans = np.asarray(list(ORACLE._plan_grid()), dtype=float)
        selected = plans[[0, 1, 9, 37, len(plans) - 1]]
        for shifted in (False, True):
            batched = ORACLE._batch_phenotype_utilities(
                world, selected, shifted=shifted
            )
            scalar = np.asarray([
                ORACLE._phenotype_utility(world, plan, shifted=shifted)
                for plan in selected
            ])
            self.assertTrue(np.allclose(batched, scalar, atol=1e-12, rtol=0.0))

    def test_sealed_intervention_transfer_is_distinct_and_bounded(self):
        differences = []
        for spec in ORACLE.DEVELOPMENT_SPECS + ORACLE.HELDOUT_SPECS:
            world = ORACLE._world(spec)
            if world["kind"] != "in_library":
                continue
            plan, _ = ORACLE._reference_plan(world, shifted=False)
            nominal = ORACLE._decision_score(world, plan, shifted=False)
            shifted = ORACLE._decision_score(world, plan, shifted=True)
            self.assertTrue(0.0 <= nominal <= 1.0)
            self.assertTrue(0.0 <= shifted <= 1.0)
            differences.append(abs(nominal - shifted))
        self.assertGreater(max(differences), 1e-3)

    def test_sealed_prediction_never_perturbs_protected_readout(self):
        for seed in (73101, 83101, 99991):
            for schedule in ORACLE._sealed_schedules(seed):
                self.assertTrue(
                    np.all(schedule[:, ORACLE.READOUT_INDEX] == 0.0)
                )

    def test_baseline_is_valid_zero_and_science_metrics_are_sealed(self):
        spec = find_task(
            "SystemsBiology/GeneNetworkIntervention", include_uncertified=True
        )
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["robustness_score"], 0.0, metrics)
        self.assertEqual(metrics["candidate_world_call_count"], 11)
        visible = search_visible_metrics(metrics)
        for key in (
            "development_mechanism_score",
            "development_prediction_score",
            "development_decision_utility",
            "robustness_score",
            "heldout_policy_score",
            "per_world",
        ):
            self.assertNotIn(key, visible)

    def test_budget_violation_fails_closed_when_candidate_catches_error(self):
        result = self.evaluate_source(
            """
            import numpy as np
            def discover_gene_network(names, perturb, objective, budget):
                try:
                    for _ in range(budget + 1):
                        perturb(np.zeros(len(names)), 20)
                except Exception:
                    pass
                n = len(names)
                return {"weights": np.zeros((n,n)), "support": np.zeros((n,n)),
                        "biases": np.full(n,-0.3), "decay_rates": np.full(n,0.6),
                        "intervention": np.zeros(n), "confidence": 0.0,
                        "abstain": True}
            """
        )
        self.assertEqual(result["valid"], 0.0, result)
        self.assertEqual(result["combined_score"], 0.0, result)
        self.assertTrue(all(not row["valid"] for row in result["per_world"][:6]))
        self.assertTrue(all(
            row["failure_kind"] == "budget_exceeded"
            for row in result["per_world"][:6]
        ))

    def test_experiment_cannot_directly_perturb_protected_readout(self):
        result = self.evaluate_source(
            """
            import numpy as np
            def discover_gene_network(names, perturb, objective, budget):
                controls = np.zeros(len(names))
                controls[objective["readout_index"]] = 1.0
                try:
                    perturb(controls, 20)
                except Exception:
                    pass
                n = len(names)
                return {"weights": np.zeros((n,n)), "support": np.zeros((n,n)),
                        "biases": np.full(n,-0.3), "decay_rates": np.full(n,0.6),
                        "intervention": np.zeros(n), "confidence": 0.0,
                        "abstain": True}
            """
        )
        self.assertEqual(result["valid"], 0.0, result)
        self.assertTrue(all(
            row["failure_kind"] == "invalid_experiment"
            for row in result["per_world"][:6]
        ))

    def test_malformed_nonfinite_bounds_and_protected_target_fail_closed(self):
        sources = (
            "return {}",
            "return {'weights': np.full((n,n), np.nan), 'support': np.zeros((n,n)), 'biases': np.zeros(n), 'decay_rates': np.ones(n), 'intervention': np.zeros(n), 'confidence': 0.5, 'abstain': False}",
            "return {'weights': np.zeros((n,n), dtype=bool), 'support': np.zeros((n,n)), 'biases': np.zeros(n), 'decay_rates': np.ones(n), 'intervention': np.zeros(n), 'confidence': 0.5, 'abstain': False}",
            "return {'weights': np.zeros((n,n), dtype=complex), 'support': np.zeros((n,n)), 'biases': np.zeros(n), 'decay_rates': np.ones(n), 'intervention': np.zeros(n), 'confidence': 0.5, 'abstain': False}",
            "return {'weights': np.zeros((n,n)), 'support': np.zeros((n,n)), 'biases': np.zeros(n), 'decay_rates': np.ones(n), 'intervention': np.array([0.,0.,0.,1.]), 'confidence': 0.5, 'abstain': False}",
            "return {'weights': np.zeros((n,n)), 'support': np.zeros((n,n)), 'biases': np.zeros(n), 'decay_rates': np.ones(n), 'intervention': np.array([1.,1.,1.,0.]), 'confidence': 0.5, 'abstain': False}",
        )
        for body in sources:
            with self.subTest(body=body):
                result = self.evaluate_source(
                    """
                    import numpy as np
                    def discover_gene_network(names, perturb, objective, budget):
                        n = len(names)
                        %s
                    """ % body
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertEqual(result["combined_score"], 0.0, result)

    def test_nonfinite_and_boolean_experiment_inputs_fail_closed_when_caught(self):
        for expression in (
            "np.full((20, n), np.nan)",
            "np.zeros((20, n), dtype=bool)",
            "np.zeros((20, n), dtype=complex)",
        ):
            with self.subTest(expression=expression):
                result = self.evaluate_source(
                    """
                    import numpy as np
                    def discover_gene_network(names, perturb, objective, budget):
                        n = len(names)
                        try:
                            perturb(%s, 20)
                        except Exception:
                            pass
                        return {"weights": np.zeros((n,n)),
                                "support": np.zeros((n,n)),
                                "biases": np.full(n,-0.3),
                                "decay_rates": np.full(n,0.6),
                                "intervention": np.zeros(n), "confidence": 0.0,
                                "abstain": True}
                    """ % expression
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertTrue(all(
                    row["failure_kind"] == "invalid_experiment"
                    for row in result["per_world"][:6]
                ))

    def test_all_worlds_get_fresh_candidate_process_imports_and_tmpfs(self):
        result = self.evaluate_source(
            """
            import os
            import numpy as np
            module_counter = 0
            def discover_gene_network(names, perturb, objective, budget):
                global module_counter
                module_counter += 1
                imported = getattr(np, '_gene_world_counter', 0)
                np._gene_world_counter = imported + 1
                seen = os.path.exists('/tmp/gene-world-state')
                with open('/tmp/gene-world-state', 'w') as handle:
                    handle.write('seen')
                if module_counter != 1 or imported != 0 or seen:
                    raise RuntimeError('candidate state leaked across worlds')
                n = len(names)
                perturb(np.zeros(n), 20)
                return {"weights": np.zeros((n,n)), "support": np.zeros((n,n)),
                        "biases": np.full(n,-0.3), "decay_rates": np.full(n,0.6),
                        "intervention": np.zeros(n), "confidence": 0.0,
                        "abstain": True}
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_world_call_count"], 11)
        self.assertEqual(result["candidate_world_valid_rate"], 1.0)

    def test_public_problem_does_not_expose_world_truth_or_split_labels(self):
        text = (TASK / "Task.md").read_text(encoding="utf-8")
        constraints = (TASK / "frontier_eval/constraints.txt").read_text(
            encoding="utf-8"
        )
        solution = (TASK / "solution.py").read_text(encoding="utf-8")
        public = "\n".join((text, constraints, solution)).lower()
        for forbidden in (
            "73101", "83101", "development_specs", "heldout_specs",
            "hidden_to_observed", "transfer_weight_scale", "_reference_plan",
        ):
            self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()
