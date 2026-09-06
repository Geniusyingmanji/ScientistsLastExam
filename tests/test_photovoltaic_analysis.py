from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_photovoltaic_tandem_calibrations.py"


def _analysis():
    spec = importlib.util.spec_from_file_location(
        "photovoltaic_tandem_calibration_test", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PhotovoltaicRuntimeIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _analysis()
        try:
            cls.report = cls.module.analyze()
        except FileNotFoundError as missing:
            raise unittest.SkipTest(
                "the runs this analysis reads are not in this checkout: %s" % missing
            )

    def test_trusted_runtime_mismatch_fails_closed(self):
        records = copy.deepcopy(self.report["records"])
        records["normal_budget_three"]["trusted_evaluator_runtime_sha256"] = "f" * 64
        altered = self.module._analyze_records(
            self.report["task_calibration"], records,
        )
        self.assertFalse(altered["execution_passed"])
        self.assertFalse(altered["input_trusted_evaluator_runtime_equivalent"])


if __name__ == "__main__":
    unittest.main()
