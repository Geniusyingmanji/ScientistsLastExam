"""A cell that failed and was retried is worth its retry, not its failure.

`batch_evolve` resumes into the same working directory, so a recovered cell appears twice in the
report: the attempt that failed and the run that fixed it. The ledger deduplicated by
`(task, workdir)` and kept whichever came first, which is the failure - so a cohort the campaign
itself reported as `recovered_runs: 1` arrived at the maturity ledger one matched replicate short,
and `matched_control_at_least_three` read 42 of 43 instead of 43.

The failure mode is quiet in the usual way: nothing errors, a count is simply one lower than the
evidence supports, and the campaign report and the ledger disagree without either of them saying so.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "maturity_for_retry_tests", ROOT / "scripts" / "audit_task_maturity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(task, mode, seed, workdir, error=None):
    return {
        "task": task, "feedback_mode": mode, "seed": seed, "workdir": workdir,
        "algorithm": "greedy_rewrite", "best": 0.5, "baseline": 0.0,
        "error": error,
        "trajectory_snapshot": {"events": [
            {"step": 0, "score": 0.0, "valid": True, "oracle_calls": 1, "budget_units": 1},
            {"step": 1, "score": 0.5, "valid": True, "oracle_calls": 2, "budget_units": 2},
        ]},
    }


class RetriedCellTests(unittest.TestCase):
    TASK = "Optics/DiffractionGratingDesign"

    def _records(self, runs):
        module = _module()
        document = {
            "trusted_evidence": True, "execution_passed": True, "passed": True,
            "evidence_scope": "MODEL_PERFORMANCE",
            "config": {"budget": 3},
            "source_provenance": {"git_revision": "HEAD"},
            "runs": runs,
        }
        # A real committed path, because the ledger hashes the report file it is told about.
        # Which file it is does not matter here - only the document handed alongside it does.
        existing = next(iter(sorted((ROOT / "experiments").glob("recontract_*.json"))))
        return module._model_run_records(
            {existing.relative_to(ROOT).as_posix(): document}, {self.TASK}, "HEAD", [])

    def test_a_retry_replaces_the_attempt_it_recovered(self):
        workdir = "runs/x/Optics__DiffractionGratingDesign/greedy_rewrite/normal/seed_0"
        records = self._records([
            _run(self.TASK, "normal", 0, workdir, error="OSError: No space left on device"),
            _run(self.TASK, "normal", 0, workdir),
        ])
        rows = records[self.TASK]
        self.assertEqual(len(rows), 1, "the retry and its failure should collapse to one cell")
        self.assertIsNone(
            rows[0]["error"],
            "the cell kept its failed attempt and discarded the run that recovered it")

    def test_a_cell_that_only_failed_is_still_a_failure(self):
        workdir = "runs/x/Optics__DiffractionGratingDesign/greedy_rewrite/normal/seed_1"
        records = self._records([
            _run(self.TASK, "normal", 1, workdir, error="EvaluatorInfrastructureError"),
        ])
        rows = records[self.TASK]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["error"], "a failure with no retry must not be reported as clean")

    def test_distinct_cells_are_not_collapsed(self):
        base = "runs/x/Optics__DiffractionGratingDesign/greedy_rewrite"
        records = self._records([
            _run(self.TASK, "normal", 0, base + "/normal/seed_0"),
            _run(self.TASK, "selection_blind", 0, base + "/selection_blind/seed_0"),
        ])
        self.assertEqual(len(records[self.TASK]), 2)


if __name__ == "__main__":
    unittest.main()
