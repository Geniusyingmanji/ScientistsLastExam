from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BASELINE_HASH = "0" * 64


def _module():
    path = ROOT / "scripts/analyze_cavity_v2_calibrations.py"
    spec = importlib.util.spec_from_file_location("cavity_analysis_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(score, feasible):
    rate = 1.0 if feasible else 0.0
    return {
        "combined_score": score,
        "valid": 1.0,
        "feasibility_rate": rate,
        "raw_score": score,
        "development_score": score,
        "ungated_development_score": max(score, 0.2),
        "robustness_score": score,
        "ungated_robustness_score": max(score, 0.2),
        "development_validation_gap": 0.0,
        "heldout_policy_score": score,
        "ungated_heldout_policy_score": max(score, 0.2),
        "heldout_robustness_score": score,
        "ungated_heldout_robustness_score": max(score, 0.2),
        "heldout_artifact_valid_rate": 1.0,
        "development_physics_feasibility_rate": rate,
        "heldout_physics_feasibility_rate": rate,
        "development_grid_feasibility_rate": rate,
        "heldout_grid_feasibility_rate": rate,
        "mean_development_field_similarity": score,
        "mean_heldout_field_similarity": score,
        "mean_development_poisson_relative_residual": 0.0,
        "mean_heldout_poisson_relative_residual": 0.0,
        "mean_development_transport_relative_residual": 0.0 if feasible else 1.0,
        "mean_heldout_transport_relative_residual": 0.0 if feasible else 1.0,
        "candidate_call_count": 8,
        "candidate_call_valid_rate": 1.0,
    }


def _record(label, mode, scores, feasible, tokens):
    events = [{
        "step": 0,
        "accepted": True,
        "candidate_sha256": BASELINE_HASH,
        "parent_sha256": None,
        **_metrics(0.0, False),
    }]
    parent = BASELINE_HASH
    for index, (score, is_feasible) in enumerate(zip(scores, feasible), 1):
        accepted = score > max(event["combined_score"] for event in events)
        candidate_hash = str(index) * 64
        events.append({
            "step": index,
            "accepted": accepted,
            "candidate_sha256": candidate_hash,
            "parent_sha256": BASELINE_HASH if mode == "selection_blind" else parent,
            **_metrics(score, is_feasible),
        })
        if accepted and mode != "selection_blind":
            parent = candidate_hash
    selected = max(
        (event for event in events if event["accepted"]),
        key=lambda event: event["combined_score"],
    )
    return {
        "label": label,
        "source_revision": "a" * 40,
        "feedback_mode": mode,
        "proposal_budget": len(scores),
        "oracle_calls": len(scores) + 1,
        "server_side_seed_control": False,
        "total_tokens": tokens,
        "best_score": selected["combined_score"],
        "selected_metrics": {
            key: selected[key] for key in _metrics(0.0, False)
        },
        "trajectory": events,
    }


def _fixtures():
    calibration = {
        "source_revision": "a" * 40,
        "trusted_reference": {"combined_score": 0.99999999},
    }
    records = {
        "budget_one": _record(
            "budget_one", "normal", [0.99999999], [True], 4486
        ),
        "normal_budget_three": _record(
            "normal_budget_three", "normal",
            [0.87, 0.895, 0.898], [True, True, True], 19483,
        ),
        "blind_budget_three": _record(
            "blind_budget_three", "selection_blind",
            [0.0, 0.99999999, 0.0], [False, True, False], 14288,
        ),
    }
    similarities = {
        "budget_one": 0.99999995,
        "normal_budget_three": 0.845,
        "blind_budget_three": 0.99999995,
    }
    probes = []
    for label, similarity in similarities.items():
        for index in range(3):
            probes.append({
                "candidate_label": label,
                "candidate_sha256": "f" * 64,
                "name": "probe_%d" % index,
                "Re": 137.0 + index,
                "N": 27 + 2 * index,
                "field_similarity": similarity,
                "velocity_relative_error": 1.0 - similarity,
                "streamfunction_relative_error": 1.0 - similarity,
                "poisson_relative_residual": 1.0e-12,
                "transport_relative_residual": 0.01,
                "boundary_relative_error": 0.0,
                "physics_feasible": True,
            })
    return calibration, records, probes


class CavityCalibrationAnalysisTests(unittest.TestCase):
    def test_analysis_records_ceiling_transfer_and_noncausal_scope(self):
        module = _module()
        calibration, records, probes = _fixtures()
        report = module._analyze_records(
            calibration, records, probes, source_equivalent=True
        )
        self.assertTrue(report["execution_passed"])
        self.assertIn("NOT_CAUSAL", report["evidence_scope"])
        self.assertTrue(
            report["observed_model_proposal_pattern"]["budget_one_near_ceiling"]
        )
        self.assertTrue(
            report["observed_model_proposal_pattern"]["open_loop_near_ceiling"]
        )
        self.assertLess(
            report["normal_minus_blind_diagnostic"]["development_score"], 0.0
        )
        self.assertFalse(
            report["posthoc_procedural_probe_protocol"]["preregistered"]
        )
        self.assertIn(
            "little iterative optimization headroom",
            report["interpretation"]["benchmark_implication"],
        )

    def test_lineage_source_or_probe_failure_breaks_gate(self):
        module = _module()
        calibration, records, probes = _fixtures()
        self.assertFalse(module._analyze_records(
            calibration, records, probes, source_equivalent=False
        )["execution_passed"])

        calibration, records, probes = _fixtures()
        records["blind_budget_three"]["trajectory"][2][
            "parent_sha256"
        ] = "9" * 64
        self.assertFalse(module._analyze_records(
            calibration, records, probes, source_equivalent=True
        )["execution_passed"])

        calibration, records, probes = _fixtures()
        probes[0]["physics_feasible"] = False
        self.assertFalse(module._analyze_records(
            calibration, records, probes, source_equivalent=True
        )["execution_passed"])


if __name__ == "__main__":
    unittest.main()
