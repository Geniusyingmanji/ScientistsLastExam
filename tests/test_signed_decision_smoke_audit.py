from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_signed_decision_smoke.py"
ROOT = SCRIPT.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.repo_paths import (  # noqa: E402
    resolve_run_workdir,
    run_workdir_is_present,
)

SPEC = importlib.util.spec_from_file_location("signed_decision_smoke_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SignedDecisionSmokeAuditTests(unittest.TestCase):
    def test_real_gpt55_protocol_smoke_replays(self):
        raw = json.loads(MODULE.DEFAULT_RAW.read_text(encoding="utf-8"))
        recorded = raw["runs"][0]["workdir"]
        resolve_run_workdir(recorded, ROOT).relative_to(ROOT)
        if not run_workdir_is_present(recorded, ROOT):
            self.skipTest("the signed-decision run this audit reads is not in this checkout")
        report = MODULE.build_report(MODULE.DEFAULT_RAW)
        self.assertEqual(report["issues"], [])
        self.assertTrue(report["execution_passed"])
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["observed"]["signed_action"], "commit")
        self.assertGreater(
            report["observed"]["best_score"], report["observed"]["baseline_score"]
        )
        self.assertEqual(
            report["observed"]["input_tokens"]
            + report["observed"]["output_tokens"],
            report["observed"]["total_tokens"],
        )

    def test_zero_runs_fails_closed(self):
        raw = json.loads(MODULE.DEFAULT_RAW.read_text(encoding="utf-8"))
        raw["runs"] = []
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "zero-runs.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = MODULE.build_report(path)
        self.assertFalse(report["execution_passed"])
        self.assertIn(
            "signed-decision smoke must contain exactly one run",
            report["issues"],
        )

    def test_missing_or_invalid_workdir_fails_closed(self):
        raw = json.loads(MODULE.DEFAULT_RAW.read_text(encoding="utf-8"))
        for recorded in (None, "/tmp/not-a-recorded-run"):
            changed = json.loads(json.dumps(raw))
            if recorded is None:
                changed["runs"][0].pop("workdir")
            else:
                changed["runs"][0]["workdir"] = recorded
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "malformed.json"
                path.write_text(json.dumps(changed), encoding="utf-8")
                report = MODULE.build_report(path)
            self.assertFalse(report["execution_passed"])
            self.assertTrue(any(
                "workdir resolution failed" in issue for issue in report["issues"]
            ), report["issues"])


if __name__ == "__main__":
    unittest.main()
