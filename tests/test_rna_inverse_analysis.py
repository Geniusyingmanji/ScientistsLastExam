from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/analyze_rna_inverse_design_calibrations.py"
SPEC = importlib.util.spec_from_file_location("rna_inverse_analysis", SCRIPT)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def _event(step, score, valid=True, failure=None, false_promotion=0.0):
    metrics = {field: 0.0 for field in ANALYSIS.SCIENCE_FIELDS}
    metrics.update({
        "development_exact_utility": score,
        "robustness_score": max(0.0, score - 0.01),
        "heldout_policy_score": max(0.0, score - 0.02),
        "heldout_robustness_score": max(0.0, score - 0.03),
        "development_proxy_false_promotion_rate": false_promotion,
        "heldout_proxy_false_promotion_rate": false_promotion,
    })
    return {
        "step": step,
        "valid": valid,
        "score": score,
        "best_score": score,
        "accepted": valid and score > 0.0,
        "candidate_sha256": str(step),
        "parent_sha256": None if step == 0 else "0",
        "failure_kind": failure,
        "science_metrics": metrics,
    }


def _record(label, mode, budget, events, tokens):
    return {
        "label": label,
        "source_revision": "input",
        "source_scope": ["frontier_science", "benchmarks"],
        "llm_condition_sha256": "condition",
        "feedback_mode": mode,
        "proposal_budget": budget,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "wall_seconds": 10.0,
        "best_score": max(event["score"] for event in events),
        "selected_metrics": max(events, key=lambda event: event["score"])[
            "science_metrics"
        ],
        "integrity_passed": True,
        "trajectory": [_event(0, 0.0)] + events,
    }


class RNAInverseAnalysisTests(unittest.TestCase):
    def test_analysis_retains_proxy_false_promotion_and_noncausal_scope(self):
        one = _record(
            "budget_one", "normal", 1,
            [_event(1, 0.0, valid=False, failure="invalid_sequence")], 100,
        )
        normal_events = [
            _event(1, 0.2, false_promotion=1.0),
            _event(2, 0.5, false_promotion=0.6),
            _event(3, 0.7, false_promotion=0.4),
        ]
        normal = _record(
            "normal_budget_three", "normal", 3, normal_events, 300
        )
        blind = _record(
            "blind_budget_three", "selection_blind", 3,
            [_event(1, 0.6), _event(2, 0.9), _event(3, 0.0)], 200,
        )
        report = ANALYSIS._analyze_records(
            {"source_revision": "input"},
            {
                "budget_one": one,
                "normal_budget_three": normal,
                "blind_budget_three": blind,
            },
            expected_source_revision="input",
        )
        self.assertTrue(report["execution_passed"])
        self.assertEqual(
            report["proposal_hurdle_summary"]["invalid_sequence_count"], 1
        )
        self.assertTrue(report["descriptive_findings"][
            "normal_accepts_three_monotone_improvements"
        ])
        self.assertTrue(report["descriptive_findings"][
            "normal_endpoint_retains_proxy_false_promotions"
        ])
        self.assertFalse(report["descriptive_findings"][
            "feedback_effect_identified"
        ])

    def test_failure_kind_prefers_sanitized_or_prefixed_taxonomy(self):
        self.assertEqual(
            ANALYSIS._failure_kind({
                "metrics": {
                    "candidate_failure_kind": "candidate_runtime_error",
                    "error_message": "candidate invalid: invalid_sequence",
                }
            }),
            "candidate_runtime_error",
        )
        self.assertEqual(
            ANALYSIS._failure_kind({
                "metrics": {"error_message": "candidate invalid: invalid_sequence"}
            }),
            "invalid_sequence",
        )

    def test_shortcut_scan_rejects_fixed_instance_literals(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text(
                "def design_rna(problem):\n    return 'A' * problem['length']\n",
                encoding="utf-8",
            )
            bad = Path(tmp) / "bad.py"
            bad.write_text(
                "def design_rna(problem):\n"
                "    return 'A' if problem.get('name') == 'hairpin_24' else 'C'\n",
                encoding="utf-8",
            )
            self.assertTrue(ANALYSIS._fixed_instance_shortcut_scan(clean)["passed"])
            scanned = ANALYSIS._fixed_instance_shortcut_scan(bad)
            self.assertFalse(scanned["passed"])
            self.assertEqual(
                scanned["fixed_instance_literal_hits"], ["hairpin_24"]
            )


if __name__ == "__main__":
    unittest.main()
