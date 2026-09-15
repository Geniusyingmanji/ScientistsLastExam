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

    def test_mechanism_on_another_split_is_not_reported_missing(self):
        axes = {
            "mechanism": {
                "value": None, "key": "mechanism_score", "split": "unsplit",
                "requested_split": "heldout", "status": "published_on_other_split",
            },
            "fdr": {"value": 0.1, "key": "development_false_discovery_rate"},
            "refusal": {"value": 1.0, "key": "correct_refusal_rate"},
        }
        row = {"task": "X/Y", "verdict": "exhausted_unpaired"}
        out = self.mod.classify_discovery_row(row, "discovery", axes)
        self.assertEqual(out["published_on_other_split"], ["mechanism"])
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
        self.assertEqual(rows[0]["axes_join"], "exact")
        self.assertEqual(rows[1]["missing_axes"], ["mechanism", "fdr", "refusal"])
        self.assertEqual(rows[1]["axes_join"], "no_match")

    def _identity(self, **extra):
        row = {
            "task": "Mathematics/SequenceLawRecovery",
            "model": "hy3-ioa",
            "llm_condition_sha256": "condition-a",
            "task_version": "task-v1",
            "runtime_source_sha256": "runtime-a",
        }
        row.update(extra)
        return row

    def test_multi_seed_triple_joins_when_admission_names_seed_and_mode(self):
        axes0 = {
            "mechanism": {"value": 0.4, "key": "heldout_mechanism_score", "split": "heldout"},
            "fdr": {"value": 0.1, "key": "heldout_false_discovery_rate", "split": "heldout"},
            "refusal": {"value": 0.8, "key": "heldout_unsupported_refusal_rate", "split": "heldout"},
        }
        axes1 = {
            "mechanism": {"value": 0.6, "key": "heldout_mechanism_score", "split": "heldout"},
            "fdr": {"value": 0.2, "key": "heldout_false_discovery_rate", "split": "heldout"},
            "refusal": {"value": 0.7, "key": "heldout_unsupported_refusal_rate", "split": "heldout"},
        }
        triple = {"schema_version": 2, "rows": [
            {**self._identity(seed=0, feedback_mode="normal", status="ok", axes=axes0)},
            {**self._identity(seed=1, feedback_mode="normal", status="ok", axes=axes1)},
        ]}
        admission = {"rows": [
            {**self._identity(seed=0, feedback_mode="normal", verdict="measures_iteration")},
            {**self._identity(seed=1, feedback_mode="normal", verdict="measures_iteration")},
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
            document = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 4)
        self.assertEqual(document["rows"][0]["axes"], axes0)
        self.assertEqual(document["rows"][1]["axes"], axes1)
        self.assertEqual(document["rows"][0]["missing_axes"], [])
        self.assertEqual(document["rows"][1]["missing_axes"], [])
        self.assertEqual(document["rows"][0]["axes_join"], "exact")
        self.assertEqual(document["axes_join"]["exact"], 2)

    def test_multi_seed_triple_does_not_claim_axes_unpublished(self):
        axes = {
            "mechanism": {"value": 0.5, "key": "heldout_mechanism_score"},
            "fdr": {"value": 0.1, "key": "heldout_false_discovery_rate"},
            "refusal": {"value": 0.8, "key": "heldout_unsupported_refusal_rate"},
        }
        triple = {"schema_version": 2, "rows": [
            {**self._identity(seed=0, feedback_mode="normal", status="ok", axes=axes)},
            {**self._identity(seed=1, feedback_mode="normal", status="ok", axes=axes)},
        ]}
        admission = {"rows": [
            {**self._identity(verdict="measures_iteration")},
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
            row = json.loads(output_path.read_text(encoding="utf-8"))["rows"][0]
        self.assertEqual(row["axes_join"], "all_coarse")
        self.assertEqual(row["missing_axes"], [])
        self.assertEqual(len(row["axes_by_run"]), 2)
        self.assertEqual(row["axes"], axes)
        self.assertNotIn("axes_join_reason", row)

    def test_pooled_admission_runs_list_joins_every_arm(self):
        axes_normal = {
            "mechanism": {"value": 0.5, "key": "heldout_mechanism_score"},
            "fdr": {"value": 0.1, "key": "heldout_false_discovery_rate"},
            "refusal": {"value": 0.8, "key": "heldout_unsupported_refusal_rate"},
        }
        axes_blind = {
            "mechanism": {"value": 0.4, "key": "heldout_mechanism_score"},
            "fdr": {"value": 0.2, "key": "heldout_false_discovery_rate"},
            "refusal": {"value": 0.7, "key": "heldout_unsupported_refusal_rate"},
        }
        triple = {"schema_version": 2, "rows": [
            {**self._identity(seed=0, feedback_mode="normal", status="ok", axes=axes_normal)},
            {**self._identity(seed=0, feedback_mode="selection_blind", status="ok", axes=axes_blind)},
        ]}
        admission = {"rows": [
            {**self._identity(
                verdict="measures_iteration",
                runs=[
                    {"seed": 0, "feedback_mode": "normal", "cohort": "paired"},
                    {"seed": 0, "feedback_mode": "selection_blind", "cohort": "paired"},
                ],
            )},
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
            document = json.loads(output_path.read_text(encoding="utf-8"))
        row = document["rows"][0]
        self.assertEqual(row["axes_join"], "pooled_runs")
        self.assertEqual(row["missing_axes"], [])
        self.assertEqual(len(row["axes_by_run"]), 2)
        self.assertEqual(row["axes"]["mechanism"]["status"], "pooled_across_runs")
        self.assertIsNone(row["axes"]["mechanism"]["value"])
        self.assertEqual(document["discovery_rows_missing_axes"], 0)
        self.assertEqual(document["axes_join"]["pooled_runs"], 1)

    def test_admission_chains_from_the_criterion_producer(self):
        import contextlib
        import io

        scripts = Path(__file__).resolve().parents[1] / "scripts"
        admission_spec = importlib.util.spec_from_file_location(
            "admission_criterion_chain", scripts / "report_admission_criterion.py")
        admission_mod = importlib.util.module_from_spec(admission_spec)
        admission_spec.loader.exec_module(admission_mod)
        triple_spec = importlib.util.spec_from_file_location(
            "discovery_triple_chain", scripts / "report_discovery_triple.py")
        triple_mod = importlib.util.module_from_spec(triple_spec)
        triple_spec.loader.exec_module(triple_mod)

        def write_run(directory: Path, seed: int, mode: str, scores: list[float]) -> None:
            directory.mkdir(parents=True)
            (directory / "run_manifest.json").write_text(json.dumps({
                "task_id": "Mathematics/SequenceLawRecovery",
                "feedback_mode": mode,
                "seed": seed,
                "llm_condition": {"model": "hy3-ioa"},
                "llm_condition_sha256": "condition-a",
                "task_package_sha256": "task-package",
                "runtime_source_sha256": "runtime-a",
            }), encoding="utf-8")
            events = [{"step": 0, "valid": True, "score": 0.0, "metrics": {
                "combined_score": 0.0,
                "heldout_mechanism_score": 0.0,
                "heldout_false_discovery_rate": 0.0,
                "heldout_unsupported_refusal_rate": 0.0,
                "heldout_discovery_coverage": 0.0,
            }}]
            for index, score in enumerate(scores, start=1):
                events.append({
                    "step": index,
                    "valid": True,
                    "score": score,
                    "metrics": {
                        "combined_score": score,
                        "heldout_mechanism_score": 0.4 + 0.05 * seed,
                        "heldout_false_discovery_rate": 0.1,
                        "heldout_unsupported_refusal_rate": 0.8,
                        "heldout_discovery_coverage": 0.7,
                    },
                })
            (directory / "trajectory.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )

        open_loop = [0.5] * 12
        feedback = [0.52, 0.54, 0.57, 0.60, 0.63, 0.66, 0.70, 0.74, 0.78, 0.82, 0.86, 0.90]
        with TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            for seed in (0, 1, 2):
                write_run(runs / "paired" / ("blind_%d" % seed), seed, "selection_blind", open_loop)
                write_run(runs / "paired" / ("normal_%d" % seed), seed, "normal", feedback)
            admission_json = Path(tmp) / "admission.json"
            triple_json = Path(tmp) / "triple.json"
            output_path = Path(tmp) / "out.json"
            with contextlib.redirect_stdout(io.StringIO()):
                admission_mod.main(["--runs", str(runs), "--output", str(admission_json)])
                triple_mod.main(["--runs", str(runs), "--output", str(triple_json)])
                self.mod.main([
                    "--admission", str(admission_json),
                    "--triple", str(triple_json),
                    "--output", str(output_path),
                ])
            admission = json.loads(admission_json.read_text(encoding="utf-8"))
            joined = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(len(admission["rows"]), 1)
        self.assertEqual(len(admission["rows"][0]["runs"]), 6)
        self.assertNotEqual(admission["rows"][0]["verdict"], "unknown")
        row = joined["rows"][0]
        self.assertEqual(row["axes_join"], "pooled_runs")
        self.assertEqual(row["missing_axes"], [])
        self.assertEqual(len(row["axes_by_run"]), 6)
        self.assertEqual(
            {(item["seed"], item["feedback_mode"]) for item in row["axes_by_run"]},
            {(seed, mode) for seed in (0, 1, 2) for mode in ("normal", "selection_blind")},
        )
        self.assertIn(
            row["axes"]["mechanism"]["status"],
            {"semantics_unrecorded", "pooled_across_runs"},
        )
        self.assertEqual(joined["discovery_rows_missing_axes"], 0)
        self.assertEqual(joined["axes_join"]["pooled_runs"], 1)

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
