"""Discovery-contract pins for AMOCTippingRefusal.

The public score is mechanism, normalised so that declining every world is exactly zero.
Red-noise and ice-restore worlds are unsupported. A historical dip is therefore a false
discovery, and a fold that has not yet jumped is missed by the no-probe baseline.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from _sandbox_tools import skip_unless_sandbox  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TASK = ROOT / "benchmarks/EarthScience/AMOCTippingRefusal"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AMOCTippingRefusalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "amoc_oracle")
        cls.baseline = _load(TASK / "solution.py", "amoc_baseline")
        cls.reference = _load(
            TASK / "verification/reference_probe.py", "amoc_reference"
        )

    def test_full_abstention_is_valid_and_scores_zero(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _probe: {"abstain": True}
        )
        self.assertEqual(metrics["valid"], 1.0)
        self.assertEqual(metrics["combined_score"], 0.0)
        self.assertEqual(metrics["development_correct_refusal_rate"], 1.0)
        self.assertEqual(metrics["development_discovery_coverage"], 0.0)

    def test_the_historical_dip_baseline_is_valid_and_below_the_reference(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_amoc)
        reference = self.evaluator.evaluate(self.reference.interpret_amoc)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertLess(baseline["combined_score"], reference["combined_score"])
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(baseline["development_false_discovery_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertEqual(reference["development_signal_recovery_rate"], 1.0)

    def test_a_fold_has_not_jumped_in_the_public_series(self):
        baseline = self.evaluator.evaluate(self.baseline.interpret_amoc)
        folds = [row for row in baseline["per_instance"]
                 if row["kind"] == "fold" and row["split"] == "development"]
        self.assertTrue(folds)
        self.assertTrue(all(row["true_collapse_year"] > 2020 for row in folds))
        self.assertFalse(any(row["mechanism_score"] for row in folds))

    def test_explicit_no_tipping_is_not_a_correct_refusal(self):
        metrics = self.evaluator.evaluate(
            lambda _problem, _probe: {
                "has_tipping": False,
                "confidence": 0.0,
                "abstain": False,
            }
        )
        unsupported = [
            row for row in metrics["per_instance"]
            if row["kind"] in {"red_noise", "ice"}
        ]
        self.assertTrue(unsupported)
        self.assertTrue(all(row["mechanism_score"] == 0.0 for row in unsupported))
        self.assertTrue(all(not row["correct_refusal"] for row in unsupported))

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_candidate_state_cannot_encode_the_fixed_world_order(self):
        from sle.evaluate import evaluate_candidate
        from sle.registry import find_task

        source = """
            call_index = 0

            def interpret_amoc(_problem, _probe):
                global call_index
                current = call_index
                call_index += 1
                if current in {0, 1, 2, 7, 8}:
                    return {
                        "has_tipping": True,
                        "collapse_year": 2098,
                        "confidence": 1.0,
                        "abstain": False,
                    }
                return {"abstain": True, "confidence": 1.0}
        """
        spec = find_task("Oceanography/AMOCTippingRefusal", include_uncertified=True)
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            metrics = evaluate_candidate(spec, candidate, timeout_s=30)
        self.assertEqual(metrics["combined_score"], 0.0, metrics)
        self.assertEqual(metrics["development_false_discovery_rate"], 1.0, metrics)

    def test_declared_eval_command_keeps_the_oracle_out_of_candidate_imports(self):
        source = """
            import evaluator

            def interpret_amoc(_problem, _probe):
                return {"abstain": True, "confidence": 0.0}
        """
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            metrics_path = Path(tmp) / "metrics.json"
            candidate.write_text(textwrap.dedent(source), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(TASK / "frontier_eval/run_eval.py"),
                    "--candidate", str(candidate),
                    "--metrics-out", str(metrics_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(metrics["valid"], 0.0, metrics)

    def test_this_is_not_energy_balance_parameter_inversion(self):
        from sle.registry import find_task
        spec = find_task("Oceanography/AMOCTippingRefusal", include_uncertified=True)
        other = find_task("ClimateScience/EnergyBalanceModel", include_uncertified=True)
        self.assertEqual(spec.entrypoint, "interpret_amoc")
        self.assertNotEqual(spec.entrypoint, other.entrypoint)
        self.assertEqual(spec.metadata.get("scientific_role"), "discovery")
        self.assertNotEqual(spec.task_dir, other.task_dir)


if __name__ == "__main__":
    unittest.main()
