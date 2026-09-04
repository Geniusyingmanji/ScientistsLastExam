"""Every external record this benchmark divides by must carry a date, and the date must be recent.

An uncapped task normalises against a published record. When the record moves and the ledger does
not, the task silently mis-scores: a candidate that merely matches the new record reads as having
beaten the old one. The cells this repository normalises against are live research - AlphaEvolve
raised the eleven-dimensional kissing number in 2025, FunSearch the dimension-eight cap set - so
"the anchor was right when we wrote it" is not a property that keeps.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPEC = importlib.util.spec_from_file_location(
    "check_anchor_freshness", ROOT / "scripts/check_anchor_freshness.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AnchorFreshnessTests(unittest.TestCase):
    def test_every_anchor_has_a_date_and_a_source(self):
        report = MODULE.collect()
        self.assertEqual(report["issues"], [], "anchors missing a retrieved_on date or a source_url")
        self.assertGreater(report["anchor_count"], 0)

    def test_no_anchor_is_past_its_staleness_window(self):
        report = MODULE.collect()
        stale = ["%s/%s (%s days)" % (a["task_id"], a["name"], a["age_days"])
                 for a in report["anchors"] if a["stale"]]
        self.assertEqual(stale, [], "re-derive these from source and update retrieved_on")

    def test_actively_researched_cells_get_the_tighter_window(self):
        """Cap sets, kissing numbers and matrix-multiplication ranks are being moved by AlphaEvolve
        and FunSearch right now. They must not sit under the same window as a proven optimum."""
        report = MODULE.collect()
        live = [a for a in report["anchors"] if a["actively_researched"]]
        self.assertGreater(len(live), 0, "the live-research hints no longer match any anchor")
        for anchor in live:
            self.assertEqual(anchor["window_days"], report["max_age_days"] // 2, anchor["name"])

    def test_a_stale_anchor_is_actually_reported(self):
        """Positive control: without it, this file passes because the checker found nothing."""
        from datetime import timedelta
        future = date.today() + timedelta(days=400)
        report = MODULE.collect(today=future)
        self.assertGreater(report["stale_count"], 0)
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
