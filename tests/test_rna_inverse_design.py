from __future__ import annotations

import functools
import importlib.util
import math
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

from frontier_science.evaluate import evaluate_candidate
from frontier_science.metric_visibility import search_visible_metrics
from frontier_science.registry import find_task


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/RNAEngineering/RNAInverseDesign"


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("rna_inverse_design_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE = _load_oracle()


class RNAInverseDesignTests(unittest.TestCase):
    def evaluate_source(self, source, timeout=90):
        spec = find_task(
            "RNAEngineering/RNAInverseDesign", include_uncertified=True
        )
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            return evaluate_candidate(spec, candidate, timeout_s=timeout)

    @staticmethod
    def _enumerate_structures(length, min_hairpin):
        @functools.lru_cache(maxsize=None)
        def recurse(left, right):
            if left > right:
                return ((),)
            structures = list(recurse(left, right - 1))
            for partner in range(left, right - min_hairpin):
                for prefix in recurse(left, partner - 1):
                    for inside in recurse(partner + 1, right - 1):
                        structures.append(tuple(sorted(
                            prefix + inside + ((partner, right),)
                        )))
            return tuple(structures)

        return recurse(0, length - 1)

    def _brute_force_fold(self, sequence, min_hairpin=3):
        structures = self._enumerate_structures(len(sequence), min_hairpin)
        valid = []
        energies = []
        weights = []
        rt = ORACLE.GAS_CONSTANT_KCAL * ORACLE.TEMPERATURE_KELVIN
        for pairs in structures:
            energy = ORACLE._structure_energy(
                sequence, pairs, ORACLE.PAIR_ENERGIES, 1.0
            )
            if math.isfinite(energy):
                valid.append(pairs)
                energies.append(energy)
                weights.append(math.exp(-energy / rt))
        partition = float(sum(weights))
        probabilities = np.zeros((len(sequence), len(sequence)), dtype=float)
        for pairs, weight in zip(valid, weights):
            for left, right in pairs:
                probabilities[left, right] += weight / partition
                probabilities[right, left] += weight / partition
        return partition, min(energies), probabilities

    def test_exact_dynamic_program_matches_exhaustive_enumeration(self):
        problem = {
            "pair_energies": dict(ORACLE.PAIR_ENERGIES),
            "temperature_kelvin": ORACLE.TEMPERATURE_KELVIN,
            "gas_constant_kcal": ORACLE.GAS_CONSTANT_KCAL,
            "loop_initiation_kcal": ORACLE.LOOP_INITIATION_KCAL,
            "min_hairpin": ORACLE.MIN_HAIRPIN,
        }
        for sequence in ("GCAAAAGC", "GCGAAACGC", "AUGCAUGCA", "GCGCAACGCG"):
            with self.subTest(sequence=sequence):
                exact = ORACLE._fold(sequence, problem)
                partition, mfe, probabilities = self._brute_force_fold(sequence)
                self.assertAlmostEqual(
                    exact["partition"] / partition, 1.0, places=11
                )
                self.assertAlmostEqual(exact["mfe_energy"], mfe, places=12)
                self.assertTrue(np.allclose(
                    exact["pair_probabilities"], probabilities,
                    atol=2e-12, rtol=2e-12,
                ))
                self.assertAlmostEqual(
                    ORACLE._structure_energy(
                        sequence, exact["mfe_pairs"], ORACLE.PAIR_ENERGIES, 1.0
                    ),
                    mfe,
                    places=12,
                )

    def test_target_probability_and_ensemble_correctness_are_independent(self):
        instance = ORACLE.DEVELOPMENT_INSTANCES[0]
        problem = ORACLE._problem(instance)
        sequence = ORACLE._baseline_sequence(problem)
        metrics = ORACLE._sequence_metrics(sequence, problem)
        self.assertEqual(metrics["proxy_compatibility"], 1.0)
        self.assertLess(metrics["target_probability"], 1e-7)
        self.assertLess(metrics["exact_utility"], 0.002)
        self.assertGreater(metrics["ensemble_defect"], 0.3)

    def test_baseline_reference_headroom_and_shift_recomputation(self):
        anchors = ORACLE._anchors()
        for instance in ORACLE.INSTANCES:
            with self.subTest(instance=instance["name"]):
                problem = ORACLE._problem(instance)
                baseline = ORACLE._baseline_sequence(problem)
                reference = ORACLE.REFERENCE_SEQUENCES[instance["name"]]
                ORACLE._validate_sequence(baseline, problem)
                ORACLE._validate_sequence(reference, problem)
                row = anchors[instance["name"]]
                self.assertGreater(
                    row["reference"]["exact_utility"],
                    row["baseline"]["exact_utility"] + 0.10,
                )
                self.assertEqual(
                    ORACLE._sequence_metrics(reference, problem), row["reference"]
                )
                for shift, (_, reference_shift) in zip(
                    ORACLE.SHIFT_SPECS, row["shifts"]
                ):
                    self.assertEqual(
                        ORACLE._sequence_metrics(reference, problem, shift),
                        reference_shift,
                    )
                    self.assertGreater(
                        reference_shift["exact_utility"],
                        ORACLE._sequence_metrics(baseline, problem, shift)["exact_utility"]
                        + 0.10,
                    )

        baseline_result = ORACLE.evaluate(
            lambda problem: {"sequence": ORACLE._baseline_sequence(problem)}
        )
        reference_result = ORACLE.evaluate(ORACLE._reference_policy)
        self.assertEqual(baseline_result["valid"], 1.0)
        self.assertEqual(baseline_result["combined_score"], 0.0)
        self.assertEqual(baseline_result["heldout_policy_score"], 0.0)
        self.assertEqual(reference_result["combined_score"], 1.0)
        self.assertEqual(reference_result["heldout_policy_score"], 1.0)
        self.assertEqual(reference_result["robustness_score"], 1.0)

    def test_world_panel_contract_and_hidden_fields(self):
        self.assertEqual(len(ORACLE.DEVELOPMENT_INSTANCES), 5)
        self.assertEqual(len(ORACLE.HELDOUT_INSTANCES), 3)
        self.assertGreaterEqual(len({
            row["family"] for row in ORACLE.INSTANCES
        }), 8)
        self.assertEqual(len(ORACLE.SHIFT_SPECS), 4)
        for instance in ORACLE.INSTANCES:
            problem = ORACLE._problem(instance)
            self.assertNotIn("name", problem)
            self.assertNotIn("family", problem)
            self.assertNotIn("split", problem)
            self.assertNotIn("reference", problem)
            self.assertNotIn("shifts", problem)
            pairs = ORACLE._parse_structure(problem["target_structure"])
            self.assertGreaterEqual(len(pairs), 6)
            self.assertTrue(all(
                right - left > problem["min_hairpin"] for left, right in pairs
            ))

    def test_secure_baseline_is_valid_zero_and_metrics_are_sealed(self):
        spec = find_task(
            "RNAEngineering/RNAInverseDesign", include_uncertified=True
        )
        metrics = evaluate_candidate(spec, spec.initial_program_path, timeout_s=90)
        self.assertEqual(metrics["valid"], 1.0, metrics)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["candidate_problem_call_count"], 8)
        self.assertEqual(metrics["candidate_problem_valid_rate"], 1.0)
        visible = search_visible_metrics(metrics)
        for key in (
            "development_exact_utility",
            "development_target_probability",
            "development_proxy_compatibility",
            "development_proxy_false_promotion_rate",
            "robustness_score",
            "heldout_policy_score",
            "per_instance",
        ):
            self.assertNotIn(key, visible)

    def test_all_instances_get_fresh_process_imports_and_tmpfs(self):
        result = self.evaluate_source(
            """
            from pathlib import Path
            CALLS = 0
            def design_rna(problem):
                global CALLS
                CALLS += 1
                marker = Path('/tmp/rna_seen')
                if CALLS != 1 or marker.exists():
                    return {'sequence': 'X' * problem['length']}
                marker.write_text('seen')
                sequence = list(('ACGU' * ((problem['length'] + 3) // 4))[:problem['length']])
                for index, base in problem['fixed_bases']:
                    sequence[index] = base
                return {'sequence': ''.join(sequence)}
            """
        )
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["candidate_problem_valid_rate"], 1.0, result)
        self.assertEqual(result["candidate_problem_call_count"], 8, result)

    def test_malformed_length_alphabet_fixed_gc_and_motif_fail_closed(self):
        bodies = (
            "return {}",
            "return {'sequence': 'A'}",
            "return {'sequence': 'X' * problem['length']}",
            "return {'sequence': 'A' * problem['length']}",
            "return {'sequence': bytes(problem['length'])}",
            "sequence = list(('ACGU' * ((problem['length'] + 3) // 4))[:problem['length']]); "
            "index, base = problem['fixed_bases'][0]; "
            "sequence[index] = 'C' if base != 'C' else 'A'; "
            "return {'sequence': ''.join(sequence)}",
        )
        for body in bodies:
            with self.subTest(body=body):
                result = self.evaluate_source(
                    """
                    def design_rna(problem):
                        %s
                    """ % body.replace("\n", "\n    ")
                )
                self.assertEqual(result["valid"], 0.0, result)
                self.assertLessEqual(result["combined_score"], 0.0, result)
                if "per_instance" in result:
                    self.assertLess(result["candidate_problem_valid_rate"], 1.0)
                    self.assertTrue(all(
                        not row["valid"] for row in result["per_instance"][:5]
                    ))
                else:
                    self.assertEqual(
                        result.get("candidate_failure_kind"),
                        "candidate_runtime_error",
                    )


if __name__ == "__main__":
    unittest.main()
