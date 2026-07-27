from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_sentinel_smoke.py"
SPEC = importlib.util.spec_from_file_location("sentinel_smoke_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SentinelSmokeAuditTests(unittest.TestCase):
    def test_tracked_negative_smoke_passes_derived_audit(self):
        report = MODULE.build_report(MODULE.DEFAULT_RAW, MODULE.DEFAULT_COHORT)
        self.assertEqual(report["task_count"], 7)
        self.assertEqual(report["issues"], [])
        self.assertTrue(report["execution_passed"])
        self.assertTrue(all(
            all(row["checks"].values()) for row in report["task_audits"]
        ))

    def test_raw_smoke_cannot_be_relabelled_as_success(self):
        raw = json.loads(MODULE.DEFAULT_RAW.read_text(encoding="utf-8"))
        raw["execution_passed"] = True
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tampered.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = MODULE.build_report(path, MODULE.DEFAULT_COHORT)
        self.assertFalse(report["execution_passed"])
        self.assertIn("raw negative smoke unexpectedly passed", report["issues"])


if __name__ == "__main__":
    unittest.main()
