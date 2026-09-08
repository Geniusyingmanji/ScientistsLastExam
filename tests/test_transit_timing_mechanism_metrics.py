import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "benchmarks/Physics/TransitTimingAttribution/verification/evaluator.py"


class TransitMechanismMetricsTests(unittest.TestCase):
    def test_correct_wrong_and_abstained_claims_use_all_supported_worlds(self):
        spec = importlib.util.spec_from_file_location("ttv_metrics", PATH)
        evaluator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evaluator)
        # Synthetic fixtures exercise bookkeeping without tuning to evaluator worlds.
        worlds = [{"kind": k, "query_ids": ["a", "b"], "budget": 8}
                  for k in ("planet", "activity", "clock", "planet", "activity", "unsupported")]
        claims = ["planet", "clock", None, "planet", None, None]

        def run():
            iterator = iter(claims * 2)
            def candidate(*args):
                kind = next(iterator)
                return {"abstain": True} if kind is None else {
                    "mechanism": kind, "period": 1, "next_offset_days": 0,
                    "confidence": 1, "evidence_query_ids": ["a", "b"]}
            with patch.object(evaluator, "development_worlds", return_value=worlds), \
                 patch.object(evaluator, "sealed_worlds", return_value=worlds), \
                 patch.object(evaluator, "_observation", return_value={}), \
                 patch.object(evaluator, "_score", side_effect=lambda w, s: (
                     0.25, not s["abstain"] and s["mechanism"] != w["kind"])):
                return evaluator.evaluate(candidate)

        result = run()
        self.assertEqual(result, run())
        for split in ("development", "validation"):
            self.assertEqual(result[split + "_mechanism_correct_count"], 2)
            self.assertEqual(result[split + "_mechanism_total_count"], 5)
            self.assertEqual(result[split + "_mechanism_score"], 0.4)
        self.assertEqual(result["combined_score"], 0.25)
        self.assertEqual(result["robustness_score"], 0.25)


if __name__ == "__main__":
    unittest.main()
