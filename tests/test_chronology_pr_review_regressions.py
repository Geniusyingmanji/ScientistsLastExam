"""Security and scientific artifact regressions from the September PR re-review."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(task, relative="verification/evaluator.py"):
    path = ROOT / "benchmarks" / "EarthScience" / task / relative
    spec = importlib.util.spec_from_file_location(task + relative.replace("/", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("task,task_id", [("ChronologyAssimilation", "Paleoclimate/ChronologyAssimilation")])
def test_external_entrypoints_delegate_without_importing_candidate(task, task_id, tmp_path, monkeypatch):
    runner = load(task, "frontier_eval/run_eval.py")
    candidate = tmp_path / "candidate.py"
    marker = tmp_path / "unsandboxed-import"
    candidate.write_text("from pathlib import Path\nPath(%r).touch()\n" % str(marker))
    output = tmp_path / "metrics.json"
    calls = []

    def trusted_eval(command, **kwargs):
        calls.append((command, kwargs))
        metrics = json.dumps({"combined_score": 0.4, "valid": 1.0})
        Path(command[command.index("--metrics-out") + 1]).write_text(metrics)
        return SimpleNamespace(returncode=0, stdout=metrics, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", trusted_eval)
    monkeypatch.setattr(runner.sys, "argv", ["run_eval.py", "--candidate", str(candidate), "--metrics-out", str(output)])
    assert runner.main() == 0
    assert not marker.exists()
    command, kwargs = calls[0]
    assert Path(command[1]) == ROOT / "sle/frontier_eval_entrypoint.py"
    assert command[command.index("--task") + 1] == task_id
    assert command[command.index("--candidate") + 1] == str(candidate.resolve())
    assert Path(command[command.index("--root") + 1]) == ROOT
    assert float(command[command.index("--timeout") + 1]) == runner.EVAL_TIMEOUT_S
    assert json.loads(output.read_text())["combined_score"] == 0.4




def test_invalid_chronology_artifacts_are_not_discovery_attempts():
    oracle = load("ChronologyAssimilation")
    result = oracle.evaluate(lambda *args: {})
    assert result["valid"] == 0.0
    assert result["discovery_attempt_count"] == 0
    assert result["development_discovery_coverage"] == 0.0
    assert result["heldout_discovery_coverage"] == 0.0


@pytest.mark.parametrize("indices", [[True], [False], [0, True], [0.0], ["0"], [0.5],
                                     [], [0, 0], [-1], [36], list(range(11)), [[0]]])
def test_malformed_sample_indices_poison_dating_contract(indices):
    oracle = load("ChronologyAssimilation")
    lab = oracle._DatingLab(oracle._world(oracle.DEVELOPMENT_SPECS[0]))
    with pytest.raises((ValueError, TypeError)):
        lab.date_sample(0, indices)
    assert lab.violated
    assert lab.used == 0


def test_dating_budget_and_zero_abstention():
    oracle = load("ChronologyAssimilation")
    lab = oracle._DatingLab(oracle._world(oracle.DEVELOPMENT_SPECS[0]))
    for record in range(8):
        response = lab.date_sample(record, [1, 7, 14, 21, 28])
        assert response["budget_cost"] == 2
    assert lab.used == oracle.BUDGET_UNITS
    with pytest.raises(RuntimeError, match="budget exceeded"):
        lab.date_sample(0, [2])
    assert lab.violated
    assert lab.used == oracle.BUDGET_UNITS
    refusal = {"temperature_mean": [], "temperature_std": [], "age_offsets_years": [],
               "confidence": 0., "abstain": True}
    result = oracle.evaluate(lambda *args: dict(refusal))
    assert result["valid"] == 1.0
    assert result["combined_score"] == 0.0
    assert result["discovery_attempt_count"] == 0
    assert result["development_correct_refusal_rate"] == 1.0


@pytest.mark.parametrize("field,value", [("temperature_mean", 1e308),
                                          ("temperature_std", 1e-308)])
def test_numerically_unscorable_reconstructions_fail_closed(field, value):
    oracle = load("ChronologyAssimilation")
    def candidate(grid, catalog, lab, budget):
        answer = {"temperature_mean": np.zeros_like(grid), "temperature_std": np.ones_like(grid),
                  "age_offsets_years": np.zeros(len(catalog)), "confidence": .5, "abstain": False}
        answer[field] = np.full_like(grid, value)
        return answer
    result = oracle.evaluate(candidate)
    assert result["valid"] == 0.0
    assert result["combined_score"] == 0.0
    json.dumps(result, allow_nan=False)


def test_curves_do_not_hide_malformed_optional_offsets():
    oracle = load("ChronologyAssimilation")
    world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
    answer = {"temperature_mean": np.zeros_like(oracle.TIME_GRID),
              "temperature_std": np.ones_like(oracle.TIME_GRID),
              "sample_ages_years": world["true_ages"], "age_offsets_years": [0.],
              "confidence": .5, "abstain": False}
    with pytest.raises(ValueError, match="one entry per proxy"):
        oracle._validate(answer)



def test_confident_wrong_climate_does_not_earn_perfect_calibration():
    oracle = load("ChronologyAssimilation")
    def candidate(grid, catalog, lab, budget):
        return {"temperature_mean": np.full_like(grid, 5.), "temperature_std": np.ones_like(grid),
                "age_offsets_years": np.zeros(len(catalog)), "confidence": 1., "abstain": False}
    row = oracle._evaluate_world(candidate, oracle.DEVELOPMENT_SPECS[0], "development", 0)
    assert row["valid"]
    assert row["confidence_score"] < 1e-3



def test_weak_chronology_baseline_claims_reconstructions_at_every_level():
    oracle = load("ChronologyAssimilation")
    baseline = load("ChronologyAssimilation", "solution.py")
    for level in (1, 2, 3):
        oracle.DIFFICULTY = level
        result = oracle.evaluate(baseline.reconstruct_climate)
        assert result["valid"] == 1.0
        assert result["combined_score"] == 0.0
        assert result["robustness_score"] == 0.0
        assert result["development_discovery_coverage"] == 1.0
        assert result["development_false_discovery_rate"] == 1.0
