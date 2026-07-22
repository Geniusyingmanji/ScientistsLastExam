from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _module():
    path = ROOT / "scripts/analyze_heat_exchanger_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("heat_exchanger_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, proxy, robustness, feasibility, false_promotion):
    return {
        "combined_score": score,
        "development_proxy_score": proxy,
        "heldout_exact_score": score * 1.2,
        "heldout_proxy_score": proxy * 1.1,
        "robustness_score": robustness,
        "heldout_robustness_score": robustness * 1.1,
        "feasibility_rate": feasibility,
        "heldout_feasibility_rate": 1.0,
        "development_false_promotion_rate": false_promotion,
        "heldout_false_promotion_rate": false_promotion + 0.02,
        "development_proxy_exact_rank_correlation": 0.9,
        "heldout_proxy_exact_rank_correlation": 0.95,
        "valid": 1.0,
    }


def _instances(scores):
    names = ("water", "oil", "glycol", "high_flow")
    return [
        {
            "name": name, "split": "development", "score": score,
            "proxy_score": score + 0.02, "robustness_score": score * 0.8,
            "exact_feasibility_rate": 1.0,
            "proxy_feasibility_rate": 1.0, "false_promotion_rate": 0.0,
            "proxy_exact_rank_correlation": 0.9,
            "raw_exact_hypervolume": score, "raw_proxy_hypervolume": score,
            "raw_shifted_hypervolumes": [score, score, score],
        }
        for name, score in zip(names, scores)
    ] + [
        {
            "name": "held_%d" % index, "split": "heldout", "score": 0.2,
            "proxy_score": 0.2, "robustness_score": 0.2,
            "exact_feasibility_rate": 1.0,
            "proxy_feasibility_rate": 1.0, "false_promotion_rate": 0.0,
            "proxy_exact_rank_correlation": 0.9,
            "raw_exact_hypervolume": 0.2, "raw_proxy_hypervolume": 0.2,
            "raw_shifted_hypervolumes": [0.2, 0.2, 0.2],
        }
        for index in range(2)
    ]


def _record(label, mode, budget, tokens, events, selected, scores):
    return {
        "label": label,
        "report": label + ".json",
        "report_sha256": "1" * 64,
        "trajectory_sha256": "2" * 64,
        "source_revision": "3" * 40,
        "feedback_mode": mode,
        "feedback_scope": "synthetic sealed scope",
        "selection_policy": (
            "offline_best_of_open_loop_batch"
            if mode == "selection_blind" else "online_incumbent"
        ),
        "seed": 1,
        "proposal_budget": budget,
        "server_side_seed_control": False,
        "oracle_calls": budget + 1,
        "total_tokens": tokens,
        "best_score": selected["combined_score"],
        "selected_step": (
            0 if label == "budget_one"
            else (events[-1]["step"] if mode == "normal" else 1)
        ),
        "selected_candidate_sha256": "4" * 64,
        "selected_metrics": selected,
        "selected_per_instance": _instances(scores),
        "invalid_proposals": ([{"step": 1, "reasons": ["outside bounds"]}]
                              if label == "budget_one" else []),
        "trajectory": events,
    }


def _event(step, accepted, metrics):
    return {
        "step": step, "accepted": accepted,
        "candidate_sha256": str(step) * 64,
        "parent_sha256": None if step == 0 else "0" * 64,
        **metrics,
    }


def _fixtures():
    baseline = _metrics(0.0, 0.0, 0.0, 1.0, 0.0)
    first = _metrics(0.01, 0.02, 0.005, 1.0, 0.0)
    normal = _metrics(0.13, 0.18, 0.14, 0.97, 0.04)
    blind = _metrics(0.29, 0.28, 0.24, 1.0, 0.17)
    calibration = {
        "source_revision": "5" * 40,
        "policies": {
            "proxy_only_classical_policy": {
                "metrics": _metrics(0.997, 1.0, 0.94, 0.95, 0.09),
                "per_instance": _instances([0.99, 0.99, 0.99, 0.99]),
            }
        },
    }
    records = {
        "budget_one": _record(
            "budget_one", "normal", 1, 6000,
            [_event(0, True, baseline), _event(1, False, baseline)],
            baseline, [0.0, 0.0, 0.0, 0.0],
        ),
        "normal_budget_three": _record(
            "normal_budget_three", "normal", 3, 25000,
            [_event(0, True, baseline), _event(1, False, baseline),
             _event(2, True, first), _event(3, True, normal)],
            normal, [0.0, 0.43, 0.0, 0.075],
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind", 3, 20000,
            [_event(0, True, baseline), _event(1, True, blind),
             _event(2, False, baseline), _event(3, False, first)],
            blind, [0.15, 0.45, 0.25, 0.31],
        ),
    }
    return calibration, records


class HeatExchangerAnalysisTests(unittest.TestCase):
    def test_analysis_retains_multifidelity_and_noncausal_contrasts(self):
        module = _module()
        calibration, records = _fixtures()
        report = module._analyze_records(calibration, records, source_equivalent=True)
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        self.assertLess(
            report["normal_minus_blind_selected_contrast"]["combined_score"], 0.0
        )
        self.assertLess(
            report["normal_minus_blind_selected_contrast"][
                "development_false_promotion_rate"
            ], 0.0,
        )
        self.assertLess(
            report["within_normal_accepted_step_changes"][-1]["feasibility_rate"],
            0.0,
        )
        self.assertGreaterEqual(
            report["selected_regime_concentration"]["normal_budget_three"][
                "near_zero_regime_count"
            ],
            2,
        )

    def test_source_mismatch_or_erased_classical_failures_breaks_gate(self):
        module = _module()
        calibration, records = _fixtures()
        self.assertFalse(module._analyze_records(
            calibration, records, source_equivalent=False
        )["execution_passed"])
        calibration["policies"]["proxy_only_classical_policy"]["metrics"][
            "feasibility_rate"
        ] = 1.0
        self.assertFalse(module._analyze_records(
            calibration, records, source_equivalent=True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
