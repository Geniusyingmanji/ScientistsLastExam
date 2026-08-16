"""Evidence the ledger never opens counts as zero, and zero looks like a campaign that never ran.

The maturity ledger selected experiment reports by filename prefix. A prefix list is a whitelist,
and a whitelist fails silently: a campaign whose report is named something new is not reported as
unrecognised, it is simply absent, and every count derived from it reads zero. Fifty GPT-5.6 runs
over fifty tasks sat outside the list for exactly that reason, and nothing anywhere said so.

Two things keep it from happening again, and both are pinned here. A report that declares itself
`MODEL_PERFORMANCE` is read on that declaration rather than on its name, so a new campaign is
visible without editing a list. And anything still unselected that holds trusted runs is reported
as an issue, so the next gap in the mechanism arrives as a number rather than as a silence.

The counterpart matters too: a document that says it is not performance evidence must not be
counted just because the selection widened. Protocol smokes hold runs and are not measurements.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "task_maturity_for_visibility", ROOT / "scripts" / "audit_task_maturity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvidenceVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _module()
        cls.selected = cls.module._tracked_json_paths_names()

    def test_no_trusted_run_evidence_is_invisible(self):
        invisible = self.module.unmatched_run_evidence()
        self.assertEqual(
            invisible, [],
            "these reports hold trusted runs that no selection rule reaches, so their runs count "
            "as zero rather than as evidence: %s" % invisible)

    def test_a_report_declaring_model_performance_is_selected_on_that_declaration(self):
        """Not on its filename - that is the whitelist trap this replaced."""
        declared = []
        for name in self.selected:
            document = self.module._load_json(ROOT / name)
            if isinstance(document, dict) and document.get("evidence_scope") == "MODEL_PERFORMANCE":
                declared.append(name)
        self.assertTrue(declared, "expected at least one report selected by declared scope")
        for name in declared:
            self.assertIn(name, self.selected)

    def test_a_protocol_smoke_is_not_counted_as_a_model_measurement(self):
        """It holds runs and says it is not performance evidence. The document is believed."""
        self.assertIn("PROTOCOL_SMOKE_ONLY", self.module.NON_PERFORMANCE_EVIDENCE_SCOPES)
        smokes = [name for name in
                  self.module._git(["ls-files", "experiments/*.json"], check=True).splitlines()
                  if "smoke" in name]
        self.assertTrue(smokes, "expected some smoke reports to check against")
        counted = []
        for name in smokes:
            document = self.module._load_json(ROOT / name)
            if not isinstance(document, dict):
                continue
            if document.get("evidence_scope") in self.module.NON_PERFORMANCE_EVIDENCE_SCOPES:
                records = self.module._model_run_records(
                    {name: document}, {"Optics/DiffractionGratingDesign"}, "HEAD", [])
                if records:
                    counted.append(name)
        self.assertEqual(counted, [], "a report scoped as a smoke was counted as a measurement")

    def test_the_gpt56_campaign_is_now_visible(self):
        """The concrete case: fifty runs the ledger had never opened."""
        census = [name for name in self.selected if "gpt56" in name]
        self.assertTrue(
            census,
            "the GPT-5.6 campaign is unselected again - it was invisible once for want of a "
            "filename pattern, and its runs read as zero")
        # Not every file in the campaign holds runs - a preregistration and an analysis carry the
        # same prefix - so the claim is that the runs are reachable, not that each file has them.
        with_runs = [name for name in census
                     if isinstance(json.loads((ROOT / name).read_text(encoding="utf-8"))
                                   .get("runs"), list)]
        self.assertTrue(with_runs, "the GPT-5.6 campaign is selected but none of it holds runs")


if __name__ == "__main__":
    unittest.main()
