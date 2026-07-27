from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_signed_decision_smoke.py"
SPEC = importlib.util.spec_from_file_location("signed_decision_smoke_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SignedDecisionSmokeAuditTests(unittest.TestCase):
    def test_real_gpt55_protocol_smoke_replays(self):
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


if __name__ == "__main__":
    unittest.main()
