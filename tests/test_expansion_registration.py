"""Finite Shannon and dephrasure resources remain explicit, isolated candidates."""
from __future__ import annotations

import importlib.util
import json
import sys
from types import SimpleNamespace

import pytest
import yaml

from sle.certification import certification_status
from sle.registry import list_tasks


EXPECTED_CANDIDATES = {
    "Mathematics/ShannonCapacityConstruction": ("Mathematics", "build_code"),
    "QuantumFoundations/DephrasureCodeDesign": ("Physics", "design_code"),
}


@pytest.mark.parametrize("task_id", EXPECTED_CANDIDATES)
def test_expansion_is_discoverable_only_as_candidate(task_id):
    inventory = {spec.task_id: spec for spec in list_tasks(None)}
    assert task_id in inventory
    spec = inventory[task_id]
    discipline, entrypoint = EXPECTED_CANDIDATES[task_id]
    assert (spec.discipline, spec.entrypoint) == (discipline, entrypoint)
    assert certification_status(task_id) == "candidate"
    assert task_id not in {spec.task_id for spec in list_tasks()}
    assert spec.metadata["scientific_role"] == "optimization"
    assert spec.metadata["score_mode"] == "uncapped"
    assert spec.metadata["gpu_required"] is False


@pytest.mark.parametrize("task_id", EXPECTED_CANDIDATES)
def test_expansion_exposes_contract_and_records_uncalibrated_lineage(task_id):
    spec = next(spec for spec in list_tasks(None) if spec.task_id == task_id)
    assert set(spec.agent_files) == {"Task.md", "solution.py", "frontier_eval/constraints.txt"}
    card = yaml.safe_load((spec.task_dir / "TASK_CARD.yaml").read_text())
    assert card["review"]["status"] == "pending_external"
    assert card["lineage"]["status"] == "unknown"
    assert card["lineage"]["builder_model_ids"] == ["unknown_inherited_codex_model"]
    assert card["lineage"]["calibration_runs"] == []
    assert card["lineage"]["calibration_evidence_status"] == "missing"
    assert card["long_horizon"]["status"] == "not_tested"
    assert (spec.task_dir / "references/known_best.md").is_file()


@pytest.mark.parametrize("task_id", EXPECTED_CANDIDATES)
@pytest.mark.parametrize("worker_success", [True, False])
def test_expansion_wrapper_delegates_and_fails_closed(task_id, worker_success, tmp_path, monkeypatch):
    """A failed trusted subprocess must not trigger any in-process candidate fallback."""
    task = next(spec for spec in list_tasks(None) if spec.task_id == task_id)
    module_spec = importlib.util.spec_from_file_location("expansion_wrapper", task.eval_dir / "run_eval.py")
    wrapper = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(wrapper)
    marker = tmp_path / "candidate-imported"
    candidate = tmp_path / "candidate.py"
    candidate.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    metrics = tmp_path / "metrics.json"
    calls = []

    def trusted_process(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0 if worker_success else 1,
            stdout=json.dumps({"combined_score": 1.25, "valid": 1.0}),
            stderr="sandbox unavailable" if not worker_success else "",
        )

    monkeypatch.setattr(wrapper.subprocess, "run", trusted_process)
    monkeypatch.setattr(sys, "argv", ["run_eval.py", "--candidate", str(candidate), "--metrics-out", str(metrics)])
    assert wrapper.main() == 0
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:7] == [sys.executable, "-m", "sle", "eval", "--task", task_id, "--allow-uncertified"]
    assert command[command.index("--candidate") + 1] == str(candidate.resolve())
    assert kwargs["cwd"] == str(wrapper.ROOT)
    assert not marker.exists()
    result = json.loads(metrics.read_text())
    assert result["combined_score"] == (1.25 if worker_success else -1e18)
    assert result["valid"] == (1.0 if worker_success else 0.0)
