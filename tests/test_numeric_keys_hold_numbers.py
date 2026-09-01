"""A key that promises a number must not hold a sentence.

`EnzymeKineticsLaw` shipped `noise_sigma_hint` holding "additive Gaussian, sigma between 0.008
and 0.012 in velocity units". A live Opus 5 draw wrote `float(problem["noise_sigma_hint"])` in
its setup block. Every world raised `ValueError` before the first assay call, so the
three-titration design further down its own program never ran, and nine of nine proposals across
three seeds scored zero. The same program scored 0.823 once the key held `[0.008, 0.012]`.

Nothing in the run said why. The trajectory records a label-blind `candidate_runtime_error`, and
the report would have read as a model that cannot do enzyme kinetics.

The authority is `scripts/check_numeric_keys_hold_numbers.py`. This pins that it is not blind -
a checker that finds nothing and a checker that sees nothing produce the same report - and that
the inventory is clean.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_numeric_keys_hold_numbers import offending_keys  # noqa: E402
from sle.registry import list_tasks  # noqa: E402

TRAP = '''
PUBLIC_PROBLEM = {
    "assay_budget_calls": 28,
    "velocity_units": "umol_per_min_per_mg",
    "noise_sigma_hint": "additive Gaussian, sigma between 0.008 and 0.012 in velocity units",
    "abstain_when": "the enzyme obeys no law in candidate_laws",
}
'''


class NumericKeysHoldNumbersTests(unittest.TestCase):
    def test_the_checker_finds_the_trap_it_was_written_for(self):
        found = offending_keys(TRAP)
        self.assertEqual([name for name, _value, _line in found], ["noise_sigma_hint"])

    def test_a_short_label_is_not_prose(self):
        """`"units": "seconds"` is read as a label, not floated. Flagging it would make the
        checker noisy enough to be turned off, which is how a real finding gets lost."""
        self.assertEqual(offending_keys('D = {"step_units": "seconds"}'), [])

    def test_the_inventory_holds_no_numeric_key_carrying_prose(self):
        offenders = []
        scanned = 0
        for spec in list_tasks(None):
            evaluator = spec.task_dir / "verification" / "evaluator.py"
            if not evaluator.is_file():
                continue
            scanned += 1
            for name, value, line in offending_keys(evaluator.read_text(encoding="utf-8")):
                offenders.append("%s: %s at line %d = %r" % (spec.task_id, name, line, value))
        self.assertEqual(offenders, [])
        # A clean sweep of nothing is not a clean sweep.
        self.assertGreater(scanned, 40)


if __name__ == "__main__":
    unittest.main()
