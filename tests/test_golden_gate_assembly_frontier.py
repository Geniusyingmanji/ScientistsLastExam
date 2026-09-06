from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks" / "Biology" / "GoldenGateAssemblyFrontier"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVALUATOR = _load(
    "golden_gate_evaluator_for_test", TASK / "verification" / "evaluator.py"
)
SOLUTION = _load("golden_gate_solution_for_test", TASK / "solution.py")
REFERENCE = _load(
    "golden_gate_reference_for_test", TASK / "verification" / "reference_solver.py"
)


class GoldenGateAssemblyFrontierTests(unittest.TestCase):
    def test_canonical_python38_imports_and_executes_the_baseline(self):
        python38 = shutil.which("python3.8")
        if python38 is None:
            self.skipTest("canonical Python 3.8 interpreter is not installed")
        program = f"""
import importlib.util, json
from pathlib import Path
task = Path({str(TASK)!r})
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
evaluator = load('golden_gate_py38_evaluator', task / 'verification' / 'evaluator.py')
solution = load('golden_gate_py38_solution', task / 'solution.py')
result = evaluator.evaluate(solution.design_assembly)
print(json.dumps({{'combined_score': result['combined_score'], 'valid': result['valid']}}))
"""
        completed = subprocess.run(
            [python38, "-c", program],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout), {"combined_score": 0.0, "valid": 1.0}
        )

    def test_source_data_hash_orientation_and_condition_cells_are_pinned(self):
        path = TASK / "data" / "pryor_ligation_counts_v1.json"
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(), EVALUATOR.DATA_SHA256
        )
        source = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(source["canonical_overhangs"]), 24)
        self.assertEqual(source["source"]["license"], "CC BY 4.0")

        expected_correct_cells = {
            "BsaI-HFv2": 635,
            "BsmBI-v2": 783,
            "Esp3I": 763,
            "BbsI-HF": 494,
        }
        for condition, expected in expected_correct_cells.items():
            with self.subTest(condition=condition):
                counts = source["conditions"][condition]["counts"]
                self.assertEqual(counts["AAAA>TTTT"], expected)
                self.assertEqual(counts["TTTT>AAAA"], expected)
                self.assertEqual(EVALUATOR.reverse_complement("AAAA"), "TTTT")

    def test_tampered_ligation_data_fails_before_world_construction(self):
        payload = (TASK / "data" / "pryor_ligation_counts_v1.json").read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            tampered = Path(temporary) / "counts.json"
            tampered.write_bytes(payload + b" ")
            EVALUATOR._source_data.cache_clear()
            with (
                patch.object(EVALUATOR, "DATA_PATH", tampered),
                self.assertRaisesRegex(RuntimeError, "data hash differs"),
            ):
                EVALUATOR._public_problem(EVALUATOR._DEVELOPMENT_PROFILES[0])
        EVALUATOR._source_data.cache_clear()

    def test_builder_source_replay_receipt_is_bound_and_not_overclaimed(self):
        source = json.loads(
            (TASK / "data" / "pryor_ligation_counts_v1.json").read_text(
                encoding="utf-8"
            )
        )
        receipt = json.loads(
            (
                TASK / "references" / "pryor_ligation_counts_replay_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["builder_source_replay_status"], "pass")
        self.assertEqual(receipt["independent_source_replay_status"], "pending")
        self.assertEqual(receipt["derived_output_sha256"], EVALUATOR.DATA_SHA256)
        self.assertIn("not an independent scientific review", receipt["claim_limit"])
        self.assertEqual(len(receipt["source_tables"]), 4)
        for row in receipt["source_tables"]:
            with self.subTest(condition=row["condition"]):
                condition = source["conditions"][row["condition"]]
                self.assertEqual(row["source_url"], condition["url"])
                self.assertEqual(row["source_sha256"], condition["xlsx_sha256"])
                self.assertEqual(
                    (row["matrix_rows"], row["matrix_columns"]), (256, 256)
                )
                self.assertEqual(row["orientation_check"], "pass")
                self.assertTrue(row["mirror_exact_cell_match"])

    def test_published_bidirectional_pool_formula_is_recomputed_independently(self):
        source = EVALUATOR._source_data()
        counts = source["conditions"]["BsaI-HFv2"]["counts"]
        sites = ["AAAA", "AACC"]

        def count(left, right):
            return counts.get(f"{left}>{right}", 0)

        ends = sites + [EVALUATOR.reverse_complement(site) for site in sites]
        site = sites[1]
        complement = EVALUATOR.reverse_complement(site)
        correct = count(site, complement) + count(complement, site)
        total = sum(count(site, other) for other in ends)
        total += sum(count(complement, other) for other in ends)
        expected = correct / total
        self.assertAlmostEqual(
            EVALUATOR.site_probability(site, sites, counts), expected, places=15
        )
        expected_log = sum(
            math.log(EVALUATOR.site_probability(value, sites, counts))
            for value in sites
        )
        self.assertAlmostEqual(
            EVALUATOR.log_fidelity(sites, counts), expected_log, places=15
        )

        with_unused = dict(counts)
        with_unused["TACA>AAAA"] = 10**9
        self.assertEqual(
            EVALUATOR.log_fidelity(sites, counts),
            EVALUATOR.log_fidelity(sites, with_unused),
        )

    def test_baseline_is_a_real_exact_assembly_for_every_world(self):
        profiles = EVALUATOR._DEVELOPMENT_PROFILES + EVALUATOR._HELDOUT_PROFILES
        for profile in profiles:
            with self.subTest(instance=profile["id"]):
                problem = EVALUATOR._public_problem(profile)
                submission = SOLUTION.design_assembly(copy.deepcopy(problem))
                value, error = EVALUATOR._validate(problem, submission)
                self.assertIsNone(error)
                self.assertTrue(math.isfinite(value))
                self.assertEqual(
                    len(submission["fragments"]), problem["fragment_count"]
                )
                reconstructed = submission["fragments"][0] + "".join(
                    fragment[problem["overhang_length"] :]
                    for fragment in submission["fragments"][1:]
                )
                self.assertEqual(reconstructed, problem["target_sequence"])

    def test_each_world_resets_candidate_state_and_hides_split_identity(self):
        class StatefulCandidate:
            def __init__(self):
                self.calls_since_reset = 0
                self.reset_count = 0
                self.public_keys = []

            def reset_session(self):
                self.calls_since_reset = 0
                self.reset_count += 1

            def __call__(self, problem):
                self.public_keys.append(set(problem))
                self.calls_since_reset += 1
                if self.calls_since_reset != 1:
                    return {}
                return SOLUTION.design_assembly(problem)

        candidate = StatefulCandidate()
        result = EVALUATOR.evaluate(candidate)
        self.assertEqual(candidate.reset_count, 5)
        self.assertEqual(result["feasibility_rate"], 1.0)
        self.assertTrue(
            all("instance_id" not in keys for keys in candidate.public_keys)
        )

    def test_heldout_completion_and_validity_are_reported_independently(self):
        def candidate_with_valid_heldout():
            calls = {"count": 0}

            def candidate(problem):
                calls["count"] += 1
                if calls["count"] <= 3:
                    return {}
                return SOLUTION.design_assembly(problem)

            return candidate

        invalid_development = EVALUATOR.evaluate(candidate_with_valid_heldout())
        self.assertEqual(invalid_development["valid"], 0.0)
        self.assertEqual(invalid_development["development_valid_count"], 0)
        self.assertEqual(invalid_development["development_invalid_count"], 3)
        self.assertEqual(invalid_development["heldout_complete"], 1.0)
        self.assertEqual(invalid_development["heldout_valid_count"], 2)
        self.assertEqual(invalid_development["heldout_invalid_count"], 0)
        self.assertEqual(invalid_development["heldout_feasibility_rate"], 1.0)

        calls = {"count": 0}

        def candidate_with_invalid_heldout(problem):
            calls["count"] += 1
            if calls["count"] > 3:
                return {}
            return SOLUTION.design_assembly(problem)

        invalid_heldout = EVALUATOR.evaluate(candidate_with_invalid_heldout)
        self.assertEqual(invalid_heldout["valid"], 1.0)
        self.assertEqual(invalid_heldout["development_valid_count"], 3)
        self.assertEqual(invalid_heldout["heldout_complete"], 1.0)
        self.assertEqual(invalid_heldout["heldout_valid_count"], 0)
        self.assertEqual(invalid_heldout["heldout_invalid_count"], 2)
        self.assertEqual(invalid_heldout["heldout_feasibility_rate"], 0.0)

    def test_empty_mutated_and_restriction_incompatible_artifacts_fail_closed(self):
        problem = EVALUATOR._public_problem(EVALUATOR._DEVELOPMENT_PROFILES[0])
        valid = SOLUTION.design_assembly(copy.deepcopy(problem))
        one_fragment = {
            "enzyme": valid["enzyme"],
            "fragments": [problem["target_sequence"]],
            "overhangs": [],
        }
        mutated = copy.deepcopy(valid)
        first = mutated["fragments"][0]
        mutated["fragments"][0] = ("A" if first[0] != "A" else "C") + first[1:]
        wrong_overlap = copy.deepcopy(valid)
        wrong_overlap["overhangs"][0] = EVALUATOR.reverse_complement(
            wrong_overlap["overhangs"][0]
        )
        blocked = copy.deepcopy(valid)
        blocked["enzyme"] = next(
            name
            for name, condition in problem["conditions"].items()
            if EVALUATOR._contains_site(
                problem["target_sequence"], condition["recognition_site"]
            )
        )
        too_short = copy.deepcopy(valid)
        too_short["fragments"][0] = too_short["fragments"][0][
            : problem["fragment_length_bounds"][0] - 1
        ]
        cases = (
            ({}, "exactly enzyme"),
            (one_fragment, "fragment count"),
            (mutated, "reconstruct"),
            (wrong_overlap, "overhang does not match"),
            (blocked, "internal restriction site"),
            (too_short, "fragment length"),
        )
        for submission, message in cases:
            with self.subTest(message=message):
                value, error = EVALUATOR._validate(problem, submission)
                self.assertIsNone(value)
                self.assertIn(message, error)

    def test_reverse_complement_duplicate_cannot_be_hidden_in_real_fragments(self):
        problem = EVALUATOR._public_problem(EVALUATOR._DEVELOPMENT_PROFILES[0])
        submission = SOLUTION.design_assembly(copy.deepcopy(problem))
        cuts = []
        position = 0
        for fragment in submission["fragments"][:-1]:
            position += len(fragment) - (EVALUATOR.OVERHANG_LENGTH if cuts else 0)
            cuts.append(position - EVALUATOR.OVERHANG_LENGTH)
        identities = [
            EVALUATOR.canonical_overhang(overhang)
            for overhang in submission["overhangs"]
        ]
        replacement = None
        minimum, maximum = problem["fragment_length_bounds"]
        target = problem["target_sequence"]
        for index, current in enumerate(cuts):
            previous = cuts[index - 1] if index else 0
            following = cuts[index + 1] if index + 1 < len(cuts) else len(target)
            for candidate in range(previous + minimum - 4, previous + maximum - 3):
                left_length = candidate - previous + 4
                right_length = (
                    following - candidate + 4
                    if index + 1 < len(cuts)
                    else following - candidate
                )
                identity = EVALUATOR.canonical_overhang(
                    target[candidate : candidate + 4]
                )
                if (
                    candidate != current
                    and minimum <= left_length <= maximum
                    and minimum <= right_length <= maximum
                    and identity in identities
                    and identity != identities[index]
                ):
                    replacement = (index, candidate)
                    break
            if replacement:
                break
        self.assertIsNotNone(replacement, "frozen target lacks a duplicate-class probe")
        index, candidate = replacement
        cuts[index] = candidate
        starts = (0,) + tuple(cuts)
        ends = tuple(cut + 4 for cut in cuts) + (len(target),)
        duplicate = {
            "enzyme": submission["enzyme"],
            "fragments": [target[start:end] for start, end in zip(starts, ends)],
            "overhangs": [target[cut : cut + 4] for cut in cuts],
        }
        value, error = EVALUATOR._validate(problem, duplicate)
        self.assertIsNone(value)
        self.assertIn("classes must be unique", error)

    def test_baseline_reference_and_headroom_are_deterministic(self):
        baseline = EVALUATOR.evaluate(SOLUTION.design_assembly)
        reference = EVALUATOR.evaluate(REFERENCE.design_assembly)
        def ensemble_headroom(problem):
            witness = REFERENCE.design_assembly(problem)
            wider = EVALUATOR.search_design(
                problem, beam_width=128, refinement_passes=8
            )
            witness_value, _ = EVALUATOR._validate(problem, witness)
            wider_value, _ = EVALUATOR._validate(problem, wider)
            if (
                wider_value is not None
                and witness_value is not None
                and wider_value > witness_value
            ):
                return wider
            return witness

        red_team = EVALUATOR.evaluate(ensemble_headroom)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertGreater(reference["combined_score"], 0.3)
        self.assertLess(reference["combined_score"], 0.8)
        self.assertGreater(reference["robustness_score"], 0.3)
        self.assertLess(reference["robustness_score"], 0.8)
        self.assertGreater(red_team["combined_score"], reference["combined_score"])
        repeated = EVALUATOR.evaluate(SOLUTION.design_assembly)
        self.assertEqual(baseline, repeated)


if __name__ == "__main__":
    unittest.main()
