"""Rejected candidates must leave something to look at.

A task that rejects every proposal is the case most in need of diagnosis and the one that leaves
the least behind: the ledger stores candidates by hash only, the trajectory stores a label-blind
failure kind, and `best_program.py` is still the baseline because nothing was ever accepted.
`CalorimeterDesign` rejected 36 of 36 proposals with `candidate_runtime_error` and there was no
way to see what they had done.

The guarantee this must not break is the other direction: nothing retained here may reach the
searcher. These tests pin both halves.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sle.algorithms.evolve import RETAINED_REJECTIONS, _retain_rejected

REJECTED = {"candidate_failure_kind": "candidate_runtime_error",
            "error_message": "candidate invalid: candidate_runtime_error",
            "valid": 0.0, "combined_score": -1e18}


class RetainedRejectionTests(unittest.TestCase):
    def test_a_rejected_candidate_is_kept(self):
        with TemporaryDirectory() as tmp:
            _retain_rejected(Path(tmp), 3, "raise RuntimeError()", REJECTED, valid=False)
            kept = sorted((Path(tmp) / "rejected").glob("*.py"))
            self.assertEqual([p.name for p in kept], ["step_003.py"])
            self.assertEqual(kept[0].read_text(encoding="utf-8"), "raise RuntimeError()")

    def test_the_failure_kind_is_kept_beside_it(self):
        with TemporaryDirectory() as tmp:
            _retain_rejected(Path(tmp), 3, "x = 1", REJECTED, valid=False)
            record = json.loads((Path(tmp) / "rejected" / "step_003.json")
                                .read_text(encoding="utf-8"))
            self.assertEqual(record["candidate_failure_kind"], "candidate_runtime_error")

    def test_an_accepted_candidate_is_not_kept(self):
        with TemporaryDirectory() as tmp:
            _retain_rejected(Path(tmp), 3, "x = 1", {"valid": 1.0}, valid=True)
            self.assertFalse((Path(tmp) / "rejected").exists())

    def test_retention_is_bounded(self):
        """This is a diagnostic, not an archive of the run."""
        with TemporaryDirectory() as tmp:
            for step in range(RETAINED_REJECTIONS + 4):
                _retain_rejected(Path(tmp), step, "x = %d" % step, REJECTED, valid=False)
            kept = list((Path(tmp) / "rejected").glob("*.py"))
            self.assertEqual(len(kept), RETAINED_REJECTIONS)

    def test_a_write_failure_does_not_propagate(self):
        """Diagnostics must never be able to fail a run."""
        with TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "wd"
            blocked.write_text("not a directory", encoding="utf-8")
            _retain_rejected(blocked, 1, "x = 1", REJECTED, valid=False)


if __name__ == "__main__":
    unittest.main()
