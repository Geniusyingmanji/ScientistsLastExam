"""Discovery admission must not promote a public-score Δ to measures_iteration."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "report_discovery_admission.py"
    spec = importlib.util.spec_from_file_location("discovery_admission", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiscoveryAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_optimization_row_is_unchanged(self):
        row = {"task": "Chemistry/LennardJonesCluster", "verdict": "measures_iteration"}
        out = self.mod.classify_discovery_row(row, "optimization")
        self.assertEqual(out["verdict"], "measures_iteration")
        self.assertNotIn("iteration_claim", out)

    def test_discovery_measures_iteration_is_stripped(self):
        row = {"task": "Mathematics/SequenceLawRecovery", "verdict": "measures_iteration"}
        out = self.mod.classify_discovery_row(row, "discovery")
        self.assertEqual(out["public_score_verdict"], "measures_iteration")
        self.assertEqual(out["verdict"], "discovery_public_score_only")
        self.assertIn("not_from_combined_score", out["iteration_claim"])

    def test_discovery_ceiling_does_not_claim_mechanism_solved(self):
        row = {"task": "Mathematics/SequenceLawRecovery", "verdict": "solved_at_ceiling"}
        out = self.mod.classify_discovery_row(row, "discovery")
        self.assertEqual(out["verdict"], "public_score_at_ceiling")
        self.assertIn("mechanism", out["iteration_claim"])

    def test_absent_axis_input_is_explicitly_reported_missing(self):
        row = {"task": "X/Y", "verdict": "exhausted_unpaired"}
        out = self.mod.classify_discovery_row(row, "discovery")
        self.assertEqual(out["missing_axes"], ["mechanism", "fdr", "refusal"])
        self.assertEqual(out["count_without_denominator"], [])

    def test_count_without_denominator_is_surfaced_not_imputed(self):
        axes = {
            "mechanism": {"value": 0.5, "key": "mechanism_score"},
            "fdr": {"value": None, "key": "development_false_discoveries",
                    "status": "count_without_denominator"},
            "refusal": {"value": 1.0, "key": "correct_refusal_rate"},
        }
        row = {"task": "X/Y", "verdict": "exhausted_unpaired"}
        out = self.mod.classify_discovery_row(row, "discovery", axes)
        self.assertEqual(out["count_without_denominator"], ["fdr"])
        self.assertEqual(out["missing_axes"], [])

    def test_triple_axes_join_only_to_the_same_full_run_identity(self):
        axes = {
            "mechanism": {"value": 0.5, "key": "mechanism_score"},
            "fdr": {"value": 0.1, "key": "false_discovery_rate"},
            "refusal": {"value": 0.8, "key": "correct_refusal_rate"},
        }
        triple = {"rows": [{
            "task": "Mathematics/SequenceLawRecovery",
            "model": "hy3-ioa",
            "llm_condition_sha256": "condition-a",
            "task_version": "task-v1",
            "runtime_source_sha256": "runtime-a",
            "trusted_evaluator_runtime_sha256": "trusted-a",
            "algorithm": "greedy_rewrite",
            "feedback_mode": "normal",
            "proposal_budget": 1,
            "seed": 0,
            "run_manifest_sha256": "manifest-a",
            "trusted_evidence": True,
            "status": "ok",
            "axes": axes,
        }]}
        admission = {"rows": [
            {
                "task": "Mathematics/SequenceLawRecovery",
                "model": "hy3-ioa",
                "llm_condition_sha256": "condition-a",
                "task_version": "task-v1",
                "runtime_source_sha256": "runtime-a",
                "trusted_evaluator_runtime_sha256": "trusted-a",
                "algorithm": "greedy_rewrite",
                "evidence_runs": [{
                    "feedback_mode": "normal",
                    "proposal_budget": 1,
                    "seed": 0,
                    "run_manifest_sha256": "manifest-a",
                }],
                "trusted_evidence": True,
                "verdict": "measures_iteration",
            },
            {
                "task": "Mathematics/SequenceLawRecovery",
                "model": "hy3-ioa",
                "llm_condition_sha256": "condition-b",
                "task_version": "task-v2",
                "runtime_source_sha256": "runtime-b",
                "trusted_evaluator_runtime_sha256": "trusted-b",
                "algorithm": "greedy_rewrite",
                "trusted_evidence": True,
                "verdict": "measures_iteration",
            },
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            admission_path = root / "admission.json"
            triple_path = root / "triple.json"
            output_path = root / "out.json"
            admission_path.write_text(json.dumps(admission), encoding="utf-8")
            triple_path.write_text(json.dumps(triple), encoding="utf-8")
            self.mod.main([
                "--admission", str(admission_path),
                "--triple", str(triple_path),
                "--output", str(output_path),
            ])
            rows = json.loads(output_path.read_text(encoding="utf-8"))["rows"]
        self.assertEqual(rows[0]["axes"], axes)
        self.assertEqual(rows[0]["missing_axes"], [])
        self.assertEqual(rows[1]["missing_axes"], ["mechanism", "fdr", "refusal"])

    def test_multiple_run_axes_are_preserved_per_exact_arm_not_maximized(self):
        base = {
            "task": "Mathematics/SequenceLawRecovery",
            "model": "hy3-ioa",
            "llm_condition_sha256": "condition-a",
            "task_version": "task-v1",
            "runtime_source_sha256": "runtime-a",
            "trusted_evaluator_runtime_sha256": "trusted-a",
            "algorithm": "greedy_rewrite",
            "trusted_evidence": True,
        }
        triple_rows = []
        evidence_runs = []
        for mode, budget, seed, value, digest in (
            ("normal", 1, 0, 0.4, "manifest-normal"),
            ("selection_blind", 3, 1, 0.9, "manifest-blind"),
        ):
            arm = {
                "feedback_mode": mode, "proposal_budget": budget,
                "seed": seed, "run_manifest_sha256": digest,
            }
            evidence_runs.append(arm)
            triple_rows.append({
                **base, **arm, "status": "ok",
                "axes": {
                    "mechanism": {"value": value, "key": "mechanism_score"},
                    "fdr": {"value": 0.1, "key": "false_discovery_rate"},
                    "refusal": {"value": 0.8, "key": "correct_refusal_rate"},
                },
            })
        admission = {"rows": [{
            **base, "verdict": "measures_iteration", "evidence_runs": evidence_runs,
        }]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            admission_path = root / "admission.json"
            triple_path = root / "triple.json"
            output_path = root / "out.json"
            admission_path.write_text(json.dumps(admission), encoding="utf-8")
            triple_path.write_text(json.dumps({"rows": triple_rows}), encoding="utf-8")
            self.mod.main([
                "--admission", str(admission_path), "--triple", str(triple_path),
                "--output", str(output_path),
            ])
            row = json.loads(output_path.read_text(encoding="utf-8"))["rows"][0]
        self.assertEqual(len(row["axis_evidence"]), 2)
        self.assertEqual(
            {entry["proposal_budget"] for entry in row["axis_evidence"]}, {1, 3}
        )
        self.assertNotIn("axes", row)

    def test_every_expected_run_reports_joined_unusable_or_missing(self):
        base = {
            "task": "Mathematics/SequenceLawRecovery",
            "model": "hy3-ioa",
            "llm_condition_sha256": "condition-a",
            "task_version": "task-v1",
            "runtime_source_sha256": "runtime-a",
            "trusted_evaluator_runtime_sha256": "trusted-a",
            "algorithm": "greedy_rewrite",
            "trusted_evidence": True,
        }
        arms = [
            {
                "feedback_mode": "normal", "proposal_budget": 1, "seed": 0,
                "run_manifest_sha256": "manifest-joined",
            },
            {
                "feedback_mode": "selection_blind", "proposal_budget": 3,
                "seed": 1, "run_manifest_sha256": "manifest-no-valid",
            },
            {
                "feedback_mode": "normal", "proposal_budget": 3, "seed": 2,
                "run_manifest_sha256": "manifest-unmatched",
            },
        ]
        axes = {
            "mechanism": {"value": 0.5, "key": "mechanism_score"},
            "fdr": {"value": 0.1, "key": "false_discovery_rate"},
            "refusal": {"value": 0.8, "key": "correct_refusal_rate"},
        }
        triple = {"rows": [
            {**base, **arms[0], "status": "ok", "axes": axes},
            {**base, **arms[1], "status": "no valid proposal"},
        ]}
        admission = {"rows": [{
            **base, "verdict": "measures_iteration", "evidence_runs": arms,
        }]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            admission_path = root / "admission.json"
            triple_path = root / "triple.json"
            output_path = root / "out.json"
            admission_path.write_text(json.dumps(admission), encoding="utf-8")
            triple_path.write_text(json.dumps(triple), encoding="utf-8")
            self.mod.main([
                "--admission", str(admission_path), "--triple", str(triple_path),
                "--output", str(output_path),
            ])
            report = json.loads(output_path.read_text(encoding="utf-8"))
        evidence = report["rows"][0]["axis_evidence"]
        self.assertEqual(len(evidence), 3)
        self.assertEqual(
            [entry["join_status"] for entry in evidence],
            ["joined", "unusable", "missing"],
        )
        self.assertEqual(evidence[0]["missing_axes"], [])
        self.assertEqual(
            evidence[1]["missing_axes"], ["mechanism", "fdr", "refusal"]
        )
        self.assertEqual(
            evidence[2]["missing_axes"], ["mechanism", "fdr", "refusal"]
        )
        self.assertEqual(report["expected_evidence_run_count"], 3)
        self.assertEqual(
            report["axis_join_status_counts"],
            {"joined": 1, "missing": 1, "unusable": 1},
        )
        self.assertEqual(report["evidence_runs_missing_axes_count"], 2)
        self.assertEqual(report["discovery_rows_missing_axes"], 1)


if __name__ == "__main__":
    unittest.main()
