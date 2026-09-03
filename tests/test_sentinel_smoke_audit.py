from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_sentinel_smoke.py"
ROOT = SCRIPT.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.repo_paths import (  # noqa: E402
    resolve_run_workdir,
    run_workdir_is_present,
)

SPEC = importlib.util.spec_from_file_location("sentinel_smoke_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SentinelSmokeAuditTests(unittest.TestCase):
    def test_tracked_negative_smoke_passes_derived_audit(self):
        raw = json.loads(MODULE.DEFAULT_RAW.read_text(encoding="utf-8"))
        for run in raw["runs"]:
            resolved = resolve_run_workdir(run["workdir"], ROOT)
            resolved.relative_to(ROOT)
        if not all(
            run_workdir_is_present(run["workdir"], ROOT) for run in raw["runs"]
        ):
            self.skipTest("the sentinel runs this audit reads are not in this checkout")
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
                report = MODULE.build_report(path, MODULE.DEFAULT_COHORT)
            self.assertFalse(report["execution_passed"])
            self.assertTrue(any(
                "workdir resolution failed" in issue for issue in report["issues"]
            ), report["issues"])


if __name__ == "__main__":
    unittest.main()
