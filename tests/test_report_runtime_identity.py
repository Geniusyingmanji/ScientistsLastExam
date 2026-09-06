"""Scientific reports must never pool or select across evaluator runtimes."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from sle.algorithms.common import atomic_write_text
from sle.evaluation_ledger import EvaluationLedger
from sle.protocol import TrajectoryEvent, append_event, load_trajectory, sha256_text, summarize_trajectory
from sle.runtime_identity import current_runtime_descriptor


ROOT = Path(__file__).resolve().parents[1]

ANALYZERS = (
    "analyze_alloy_hardness_calibrations.py",
    "analyze_calorimeter_v2_calibrations.py",
    "analyze_catalyst_deactivation_lab_calibrations.py",
    "analyze_demographic_sfs_v2_calibrations.py",
    "analyze_diffraction_grating_calibrations.py",
    "analyze_electrolyte_conductivity_design_calibrations.py",
    "analyze_force_field_hypothesis_calibrations.py",
    "analyze_photovoltaic_tandem_calibrations.py",
    "analyze_prospective_meta_analysis_calibrations.py",
    "analyze_qcm_raw_pipeline_calibrations.py",
)


def load_report(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location("runtime_identity_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_verified_run(root: Path, *, budget: int = 10) -> None:
    """Write a canonical receipt-bound run whose manifest config is deliberately misleading."""
    runtime = current_runtime_descriptor(())
    manifest = {
        "schema_version": 1,
        "algorithm": "greedy_rewrite",
        "task_id": "T/X",
        "task_contract_sha256": "a" * 64,
        "task_package_sha256": "b" * 64,
        "runtime_source_sha256": "c" * 64,
        "trusted_evaluator_runtime": runtime,
        "seed": 0,
        "feedback_mode": "normal",
        "llm_condition": {"model": "hy3"},
        "llm_condition_sha256": "d" * 64,
        "config": {"budget": 999},
    }
    atomic_write_text(root / "run_manifest.json", json.dumps(manifest) + "\n")
    ledger = EvaluationLedger(root)
    identity = {
        key: manifest[key] for key in (
            "task_id", "algorithm", "feedback_mode", "seed",
            "llm_condition_sha256", "llm_condition", "task_contract_sha256",
            "task_package_sha256", "runtime_source_sha256",
        )
    }
    identity["proposal_budget"] = budget
    runtime_hash = runtime["fingerprint_sha256"]
    cumulative = 0.0
    incumbent = "VALUE = 0\n"
    baseline_hash = sha256_text(incumbent)
    receipt = ledger.evaluate_once({
        "kind": "baseline",
        **identity,
        "trusted_evaluator_runtime_sha256": runtime_hash,
        "step": 0,
        "candidate_sha256": baseline_hash,
    }, lambda: {"combined_score": 0.0, "valid": 1.0})
    cumulative += receipt["evaluation_wall_seconds"]
    append_event(root / "trajectory.jsonl", TrajectoryEvent(
        step=0, oracle_calls=1, score=0.0, best_score=0.0,
        valid=True, accepted=True,
        wall_seconds=receipt["evaluation_wall_seconds"],
        cumulative_wall_seconds=cumulative,
        candidate_sha256=baseline_hash, parent_sha256=None, budget_units=1,
        metrics=receipt["metrics"],
        algorithm_metadata={"evaluation_request_id": receipt["request_id"]},
    ))
    for step in range(1, budget + 1):
        candidate = "VALUE = %d\n" % step
        candidate_hash = sha256_text(candidate)
        prompt_hash = "%064x" % step
        prompt_metrics = {
            "combined_score": (step - 1) / 100.0,
            "valid": 1.0,
        }
        prompt_metrics_rendered = json.dumps(prompt_metrics, indent=2)
        receipt = ledger.evaluate_once({
            "kind": "proposal",
            **identity,
            "trusted_evaluator_runtime_sha256": runtime_hash,
            "step": step,
            "candidate_sha256": candidate_hash,
            "parent_sha256": sha256_text(incumbent),
            "prompt_sha256": prompt_hash,
        }, lambda step=step: {"combined_score": step / 100.0, "valid": 1.0})
        cumulative += receipt["evaluation_wall_seconds"]
        append_event(root / "trajectory.jsonl", TrajectoryEvent(
            step=step, oracle_calls=step + 1, score=step / 100.0,
            best_score=step / 100.0, valid=True, accepted=True,
            wall_seconds=receipt["evaluation_wall_seconds"],
            cumulative_wall_seconds=cumulative,
            candidate_sha256=candidate_hash,
            parent_sha256=sha256_text(incumbent), budget_units=step + 1,
            metrics=receipt["metrics"],
            algorithm_metadata={
                "evaluation_request_id": receipt["request_id"],
                "selection_policy": "online_incumbent",
                "accepted_semantics": "online_incumbent_update",
                "proposal_slot": step,
                "prompt_source_step": step - 1,
                "feedback_released_through_step": step - 1,
                "prompt_sha256": prompt_hash,
                "prompt_metrics_sha256": sha256_text(prompt_metrics_rendered),
                "prompt_metrics_utf8_bytes": len(
                    prompt_metrics_rendered.encode("utf-8")
                ),
                "prompt_metric_keys": "combined_score,valid",
                "completed_after_active_wall_horizon": False,
            },
        ))
        incumbent = candidate
    events = load_trajectory(root / "trajectory.jsonl")
    summary = summarize_trajectory(events, budget=budget + 1)
    summary.update({
        "algorithm": "greedy_rewrite",
        "task_id": manifest["task_id"],
        "seed": manifest["seed"],
        "feedback_mode": manifest["feedback_mode"],
        "selection_policy": "online_incumbent",
        "budget": budget,
        "baseline_score": 0.0,
        "evaluation_ledger_snapshot": ledger.snapshot(),
    })
    atomic_write_text(root / "summary.json", json.dumps(summary) + "\n")
    atomic_write_text(root / "best_program.py", incumbent)


class CalibrationRuntimeIdentityTests(unittest.TestCase):
    def test_each_calibration_analyzer_binds_and_singletons_the_trusted_runtime(self):
        for name in ANALYZERS:
            with self.subTest(analyzer=name):
                source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
                self.assertIn('manifest.get("trusted_evaluator_runtime")', source)
                self.assertIn("verification = verify_run(workdir)", source)
                self.assertIn('record["trusted_evaluator_runtime_sha256"]', source)
                self.assertIn("trusted_runtimes =", source)
                self.assertIn('"input_trusted_evaluator_runtime_equivalent"', source)
                self.assertIn("len(trusted_runtimes) == 1", source)
                self.assertIn("None not in trusted_runtimes", source)


class CandidateSelectorTests(unittest.TestCase):
    def _exercise(self, script: str):
        module = load_report(script)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, package, score in (
                ("old-package", "old", 0.99),
                ("unverified", "current", 0.90),
                ("verified-current", "current", 0.50),
            ):
                run = root / name
                run.mkdir()
                (run / "run_manifest.json").write_text(json.dumps({
                    "task_id": "T/X",
                    "task_package_sha256": package,
                    "runtime_source_sha256": "source",
                    "trusted_evaluator_runtime": {
                        "fingerprint_sha256": "trusted",
                    },
                }), encoding="utf-8")
                (run / "summary.json").write_text(json.dumps({
                    "best_score": score,
                }), encoding="utf-8")
                (run / "best_program.py").write_text("PASS = True\n", encoding="utf-8")

            spec = SimpleNamespace(task_dir=root / "task")

            def verify(path, **_kwargs):
                if Path(path).name == "unverified":
                    raise ValueError("tampered")
                return {"verified": True}

            with patch.object(module, "find_task", return_value=spec), \
                    patch.object(module, "task_package_sha256", return_value="current"), \
                    patch.object(module, "runtime_source_sha256", return_value="source"), \
                    patch.object(module, "resolve_trusted_runtime", return_value=SimpleNamespace(
                        fingerprint_sha256="trusted"
                    )), patch.object(module, "verify_run", side_effect=verify):
                selected = module._best_candidate("T/X", root)
            self.assertEqual(selected, root / "verified-current" / "best_program.py")

    def test_difficulty_ladder_uses_only_current_verified_runs(self):
        self._exercise("report_difficulty_ladder.py")

    def test_hidden_axis_report_uses_only_current_verified_runs(self):
        self._exercise("report_saturation_hidden_axes.py")


class CanonicalBudgetIntegrationTests(unittest.TestCase):
    def test_cross_model_reads_budget_only_from_verified_summary(self):
        module = load_report("report_cross_model.py")
        with TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            run.mkdir()
            write_verified_run(run, budget=10)
            rows = module.read_runs(Path(temporary))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["trusted_evidence"])
        self.assertEqual(rows[0]["proposal_budget"], 10)

    def test_contract_burden_uses_verified_budget_and_current_package(self):
        module = load_report("report_contract_burden.py")
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "runs/run"
            run.mkdir(parents=True)
            write_verified_run(run, budget=10)
            task_dir = root / "task"
            (task_dir / "verification").mkdir(parents=True)
            (task_dir / "verification/evaluator.py").write_text(
                "# evaluator\n", encoding="utf-8"
            )
            initial = task_dir / "initial.py"
            initial.write_text("# initial\n", encoding="utf-8")
            spec = SimpleNamespace(
                task_id="T/X", task_dir=task_dir, initial_program_path=initial,
            )
            output = root / "burden.json"
            with patch.object(module, "list_tasks", return_value=[spec]), \
                    patch.object(module, "task_package_sha256", return_value="b" * 64):
                module.main([
                    "--runs", str(root / "runs"), "--output", str(output),
                ])
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["trusted_input_run_count"], 1)
        self.assertEqual(report["rows"][0]["proposal_budget"], 10)


if __name__ == "__main__":
    unittest.main()
