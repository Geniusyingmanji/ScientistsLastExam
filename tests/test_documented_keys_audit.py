"""Tests for the audit that finds inputs a task never names in its prompt.

This audit is why `CalorimeterDesign` went from rejecting 36 of 36 proposals to 74% valid and a
score of 1.0000: it passed 27 keys and named 15 of them, and a proposal that guessed
`light_yield_per_gev` for `light_yield_pe_per_active_gev` raised at runtime. What the audit must
not do is the opposite - claim a key is undocumented when it is not, which would send someone
editing a prompt that was already right.
"""
from __future__ import annotations

import unittest

from scripts.audit_documented_keys import (evaluator_problem_keys, submission_keys,
                                           subscript_keys)


class SubscriptKeyTests(unittest.TestCase):
    def test_a_subscript_read_is_found(self):
        self.assertEqual(subscript_keys('x = problem["n_layers"]'), {"n_layers"})

    def test_a_get_is_found(self):
        self.assertEqual(subscript_keys('x = problem.get("n_layers")'), {"n_layers"})

    def test_the_other_names_the_input_goes_by_are_found(self):
        source = 'a = instance["p"]\nb = spec["q"]\nc = inputs["r"]'
        self.assertEqual(subscript_keys(source), {"p", "q", "r"})

    def test_a_subscript_on_something_else_is_not_an_input(self):
        """`results["score"]` is an output, and reporting it would send someone to fix a prompt
        that never needed the key."""
        self.assertEqual(subscript_keys('results["score"] = 1'), set())

    def test_a_computed_key_is_not_guessed_at(self):
        self.assertEqual(subscript_keys('x = problem[name]'), set())

    def test_unparseable_source_yields_nothing_rather_than_raising(self):
        self.assertEqual(subscript_keys("def broken("), set())


class EvaluatorKeyTests(unittest.TestCase):
    def test_keys_returned_by_a_problem_constructor_are_found(self):
        source = (
            "def _public_problem(spec):\n"
            "    return {'a': 1, 'b': 2}\n"
        )
        self.assertEqual(evaluator_problem_keys(source), {"a", "b"})

    def test_a_helper_that_is_not_about_the_problem_is_ignored(self):
        """Otherwise any internal mapping in the evaluator is mistaken for the candidate's input."""
        source = (
            "def _score_instance(row):\n"
            "    return {'mechanism_score': 1.0}\n"
        )
        self.assertEqual(evaluator_problem_keys(source), set())

    def test_both_sources_together_exceed_either_alone(self):
        """The baseline is a lower bound: a key it does not read is invisible in it."""
        evaluator = (
            "def _public_problem(spec):\n"
            "    return {'used': 1, 'unused': 2}\n"
        )
        baseline = 'x = problem["used"]'
        self.assertEqual(subscript_keys(baseline), {"used"})
        self.assertEqual(evaluator_problem_keys(evaluator) - subscript_keys(baseline),
                         {"unused"})


class InventoryScanTests(unittest.TestCase):
    """Finding nothing has to be distinguishable from finding nothing wrong.

    Before `_subscript_index` handled the pre-3.9 grammar, this audit found zero input keys on the
    evaluation host and therefore reported zero undocumented ones - a vacuous pass indistinguishable
    from a real one, on the machine where it actually runs. A count is asserted so that a scanner
    which stops seeing anything fails loudly instead of congratulating the repository.
    """

    def test_the_scan_finds_input_keys_across_the_inventory(self):
        from sle.registry import list_tasks

        total = 0
        for spec in list_tasks(None):
            evaluator = spec.task_dir / "verification" / "evaluator.py"
            if evaluator.is_file():
                total += len(subscript_keys(evaluator.read_text(encoding="utf-8")))
        self.assertGreater(
            total, 20,
            "the input-key scan found almost nothing across the whole inventory, which is what a "
            "broken scanner looks like - not what a well-documented benchmark looks like")


if __name__ == "__main__":
    unittest.main()


class SubmissionKeyTests(unittest.TestCase):
    """The other half of the interface: names the candidate must return under.

    These are stricter than the input side, because a submission with the wrong key set is
    rejected before it is scored - the candidate loses everything, not one field. That makes a
    false positive here costly in the other direction: it sends someone to document a field that
    is not part of the contract at all.
    """

    def test_a_key_read_off_the_submission_is_found(self):
        self.assertIn("mass", submission_keys('x = submission["mass"]'))

    def test_a_declared_contract_constant_is_found(self):
        source = 'CALIBRATION_KEYS = {"start_offset_counts", "end_offset_counts"}'
        self.assertEqual(submission_keys(source),
                         {"start_offset_counts", "end_offset_counts"})

    def test_the_evaluators_own_metrics_dict_is_not_the_submission(self):
        """`result["error_message"]` is something the evaluator writes, not something asked for."""
        self.assertEqual(submission_keys('result["error_message"] = "x"'), set())

    def test_a_constant_that_merely_ends_in_keys_is_not_the_contract(self):
        self.assertEqual(submission_keys('WORLD_KEYS = {"seed", "kind"}'), set())

    def test_a_name_that_means_the_hidden_truth_elsewhere_is_excluded(self):
        """One task uses `fitted` for the candidate result and another for the world's truth."""
        self.assertEqual(submission_keys('x = fitted["log10_a"]'), set())
