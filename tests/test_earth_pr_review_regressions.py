"""Regression contracts for ActiveFullWaveformInversion."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
ROOT = Path(__file__).resolve().parents[1]

def load(task, relative='verification/evaluator.py'):
    path = ROOT / 'benchmarks' / 'EarthScience' / task / relative
    spec = importlib.util.spec_from_file_location(task + relative.replace('/', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('task,task_id', [('ActiveFullWaveformInversion', 'WavePropagation/ActiveFullWaveformInversion')])
def test_external_entrypoints_delegate_without_importing_candidate(task, task_id, tmp_path, monkeypatch):
    runner = load(task, 'frontier_eval/run_eval.py')
    candidate = tmp_path / 'candidate.py'
    marker = tmp_path / 'unsandboxed-import'
    candidate.write_text('from pathlib import Path\nPath(%r).touch()\n' % str(marker))
    output = tmp_path / 'metrics.json'
    calls = []

    def trusted_eval(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({'combined_score': 0.4, 'valid': 1.0}), stderr='')
    monkeypatch.setattr(runner.subprocess, 'run', trusted_eval)
    monkeypatch.setattr(runner.sys, 'argv', ['run_eval.py', '--candidate', str(candidate), '--metrics-out', str(output)])
    assert runner.main() == 0
    assert not marker.exists()
    (command, kwargs) = calls[0]
    assert command[1:4] == ['-m', 'sle', 'eval']
    assert command[command.index('--task') + 1] == task_id
    assert command[command.index('--candidate') + 1] == str(candidate.resolve())
    assert '--allow-uncertified' in command
    assert Path(kwargs['cwd']) == ROOT
    assert json.loads(output.read_text())['combined_score'] == 0.4

@pytest.mark.parametrize('task', ['ActiveFullWaveformInversion'])
def test_invalid_artifacts_do_not_count_as_discoveries(task):
    result = load(task).evaluate(lambda *args: {})
    assert result['valid'] == 0.0
    assert result['discovery_attempt_count'] == 0
    assert result['development_discovery_coverage'] == 0.0
    assert result['heldout_discovery_coverage'] == 0.0

@pytest.mark.parametrize('task', ['ActiveFullWaveformInversion'])
def test_confidence_tracks_recovered_mechanism_not_only_world_support(task, monkeypatch):
    oracle = load(task)
    monkeypatch.setattr(oracle, '_supported_scores', lambda *args: (0.0, 0.0, 0.0))
    spec = oracle.DEVELOPMENT_SPECS[0]
    candidate = lambda *args: {'velocity_m_s': oracle._background(), 'confidence': 1.0, 'abstain': False}
    row = oracle._evaluate_world(candidate, spec, 'development', 0)
    assert row['valid']
    assert row['confidence_score'] == 0.0

def test_fwi_zero_baseline_makes_claims_while_full_refusal_is_separate():
    oracle = load('ActiveFullWaveformInversion')
    baseline = load('ActiveFullWaveformInversion', 'solution.py')
    for level in (1, 2, 3):
        oracle.DIFFICULTY = level
        result = oracle.evaluate(baseline.invert_velocity_model)
        assert result['valid'] == 1.0
        assert result['combined_score'] == 0.0
        assert result['robustness_score'] == 0.0
        assert result['development_discovery_coverage'] == 1.0
        assert result['development_false_discovery_rate'] == 1.0
    refusal = oracle.evaluate(lambda *args: {'velocity_m_s': [], 'confidence': 0.0, 'abstain': True})
    assert refusal['valid'] == 1.0
    assert refusal['combined_score'] == 0.0
    assert refusal['discovery_attempt_count'] == 0

def test_fwi_structure_requires_improvement_over_background():
    oracle = load('ActiveFullWaveformInversion')
    world = oracle._world(oracle.DEVELOPMENT_SPECS[0])
    (truth, background) = (world['velocity'], oracle._background())
    values = []
    for fraction in (0.0, 0.001, 0.5, 1.0):
        model = background + fraction * (truth - background)
        (structure, _, mechanism) = oracle._supported_scores(world, model)
        values.append(structure)
        if fraction == 0:
            assert structure == 0.0
            assert mechanism == 0.0
    assert values == sorted(values)
    assert values[1] < 0.001
    assert values[-1] == pytest.approx(1.0)
    worse = background - 0.1 * (truth - background)
    assert oracle._supported_scores(world, worse)[0] == 0.0

def test_fwi_structured_attenuation_is_present_in_both_splits():
    oracle = load('ActiveFullWaveformInversion')
    for specs in (oracle.DEVELOPMENT_SPECS, oracle.HELDOUT_SPECS):
        cases = [spec for spec in specs if spec[1] == 'structured_attenuation']
        assert cases
        for spec in cases:
            world = oracle._world(spec)
            assert not np.array_equal(world['velocity'], oracle._background())
            source = int(oracle.SOURCE_INDICES[2])
            row = oracle._Acquisition(world).acquire(source)
            acoustic = oracle.simulate_waveforms(world['velocity'], source)
            discrepancy = np.sqrt(np.mean((acoustic - row['pressure']) ** 2))
            assert discrepancy > 20 * row['noise_std']

def test_fwi_structured_case_is_not_rejected_by_old_global_energy_gate():
    oracle = load('ActiveFullWaveformInversion')
    spec = next((s for s in oracle.DEVELOPMENT_SPECS if s[1] == 'structured_attenuation'))
    acquisition = oracle._Acquisition(oracle._world(spec))
    sources = oracle.SOURCE_INDICES[[0, 2, 4]]
    observed = np.asarray([acquisition.acquire(int(s))['pressure'] for s in sources])
    background = np.asarray([oracle.simulate_waveforms(oracle._background(), int(s)) for s in sources])
    ratio = np.linalg.norm(observed) / np.linalg.norm(background)
    relative = np.linalg.norm(observed - background) / np.linalg.norm(background)
    assert ratio > 0.95
    assert relative > 0.006
