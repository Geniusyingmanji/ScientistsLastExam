"""Regression contracts for ActiveFullWaveformInversion."""
import ast
import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT = Path(__file__).resolve().parents[1]

def load(domain, task, file='verification/evaluator.py'):
    path = ROOT / 'benchmarks' / domain / task / file
    spec = importlib.util.spec_from_file_location(task + file.replace('/', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('domain,task', [('EarthScience', 'ActiveFullWaveformInversion')])
def test_twelve_malformed_candidates_fail_closed(domain, task):
    m = load(domain, task)
    invalid = [None, {}, '', True, 12, float('nan'), float('inf'), [], [0], {'plans': []}, {'abstain': 'yes'}, {'confidence': float('nan')}]
    for value in invalid:
        result = m.evaluate(lambda *args, **kwargs: value)
        assert result['valid'] == 0, (task, value)
        assert result['combined_score'] == 0, (task, value)

def test_caught_malformed_instrument_call_still_invalidates_world():
    fwi = load('EarthScience', 'ActiveFullWaveformInversion')

    def bad_shot(*args):
        try:
            args[-2](3.5)
        except ValueError:
            pass
        return {'velocity_m_s': [], 'confidence': 0.0, 'abstain': True}
    assert fwi.evaluate(bad_shot)['valid'] == 0

def _probe_ricker(time_s, frequency_hz):
    delay = 1.5 / frequency_hz
    arg = np.pi * frequency_hz * (time_s - delay)
    return (1.0 - 2.0 * arg * arg) * np.exp(-arg * arg)

def _probe_simulate(velocity, source_index, spacing_m, time_s):
    velocity = np.asarray(velocity, dtype=float)
    time_s = np.asarray(time_s, dtype=float)
    dt = float(time_s[1] - time_s[0])
    previous = np.zeros_like(velocity)
    current = np.zeros_like(velocity)
    receiver_indices = np.arange(2, velocity.shape[1] - 2, 2, dtype=int)
    traces = np.zeros((len(time_s), len(receiver_indices)))
    damping = np.ones_like(velocity)
    damping[[0, -1], :] = 0.86
    damping[:, [0, -1]] = 0.86
    damping[[1, -2], :] = 0.94
    damping[:, [1, -2]] = 0.94
    coefficient = (velocity * dt / spacing_m) ** 2
    wavelet = _probe_ricker(time_s, 12.0)
    for step in range(len(time_s)):
        lap = np.zeros_like(current)
        lap[1:-1, 1:-1] = current[1:-1, 2:] + current[1:-1, :-2] + current[2:, 1:-1] + current[:-2, 1:-1] - 4.0 * current[1:-1, 1:-1]
        following = (2.0 * current - previous + coefficient * lap) * damping
        following[2, int(source_index)] += wavelet[step]
        traces[step] = following[2, receiver_indices]
        (previous, current) = (current, following)
    return traces

def _probe_background_supported(gather, background, spacing_m, time_s):
    """The reference solver's public stage-1 null/attenuation classification."""
    observed = np.asarray(gather['pressure'])
    base = _probe_simulate(background, int(gather['source_index']), spacing_m, np.asarray(time_s))
    relative = np.linalg.norm(observed - base) / max(np.linalg.norm(base), 1e-12)
    energy_ratio = np.linalg.norm(observed) / max(np.linalg.norm(base), 1e-12)
    return not (relative < 0.006 or energy_ratio < 0.95)

def _fwi_zero_inversion(grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s, source_indices, receiver_x_m, time_s, acquire, budget_units):
    """Probe (a): one shot, stage-1 classification, return the background grid."""
    background = np.asarray(background_velocity_m_s, dtype=float)
    gather = acquire(int(source_indices[len(source_indices) // 2]))
    if not _probe_background_supported(gather, background, spacing_m, time_s):
        return {'velocity_m_s': [], 'confidence': 0.1, 'abstain': True}
    return {'velocity_m_s': background, 'confidence': 0.8, 'abstain': False}

def _fwi_constant_lens(grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s, source_indices, receiver_x_m, time_s, acquire, budget_units):
    """Probe (b): one fixed-shape Gaussian lens, single swept amplitude."""
    background = np.asarray(background_velocity_m_s, dtype=float)
    count = min(int(budget_units), 3)
    indices = np.linspace(0, len(source_indices) - 1, count, dtype=int)
    gathers = [acquire(int(source_indices[i])) for i in indices]
    if not _probe_background_supported(gathers[0], background, spacing_m, time_s):
        return {'velocity_m_s': [], 'confidence': 0.1, 'abstain': True}
    observed = np.asarray([row['pressure'] for row in gathers])
    sources = [int(row['source_index']) for row in gathers]
    (zz, xx) = np.mgrid[0:grid_shape[0], 0:grid_shape[1]]
    (cx, cz) = ((grid_shape[1] - 1) / 2.0, (grid_shape[0] - 1) / 2.0)
    lens = np.exp(-0.5 * (((xx - cx) / 4.6) ** 2 + ((zz - cz) / 3.4) ** 2))
    (best_model, best_misfit) = (None, None)
    for amplitude in np.linspace(-900.0, 900.0, 19):
        model = np.clip(background + amplitude * lens, *velocity_bounds_m_s)
        prediction = np.asarray([_probe_simulate(model, s, spacing_m, np.asarray(time_s)) for s in sources])
        misfit = float(np.linalg.norm(prediction - observed))
        if best_misfit is None or misfit < best_misfit:
            (best_model, best_misfit) = (model, misfit)
    return {'velocity_m_s': best_model, 'confidence': 0.8, 'abstain': False}

def _fwi_travel_time_only(grid_shape, spacing_m, background_velocity_m_s, velocity_bounds_m_s, source_indices, receiver_x_m, time_s, acquire, budget_units):
    """Probe (c): straight-ray linearized slowness update from first breaks only."""
    background = np.asarray(background_velocity_m_s, dtype=float)
    time_s = np.asarray(time_s, dtype=float)
    count = min(int(budget_units), 3)
    indices = np.linspace(0, len(source_indices) - 1, count, dtype=int)
    gathers = [acquire(int(source_indices[i])) for i in indices]
    if not _probe_background_supported(gathers[0], background, spacing_m, time_s):
        return {'velocity_m_s': [], 'confidence': 0.1, 'abstain': True}
    observed = np.asarray([row['pressure'] for row in gathers])
    sources = [int(row['source_index']) for row in gathers]
    base = np.asarray([_probe_simulate(background, s, spacing_m, time_s) for s in sources])

    def first_break(trace):
        amplitude = float(np.max(np.abs(trace)))
        above = np.nonzero(np.abs(trace) > 0.05 * amplitude)[0]
        return float(above[0]) if len(above) else float(len(trace) - 1)
    deltas = []
    for shot in range(len(sources)):
        for receiver in range(observed.shape[2]):
            t_obs = first_break(observed[shot, :, receiver]) * float(time_s[1] - time_s[0])
            t_bg = first_break(base[shot, :, receiver]) * float(time_s[1] - time_s[0])
            if t_bg <= 0.0:
                continue
            receiver_index = 2 + 2 * receiver
            length_m = abs(receiver_index - sources[shot]) * spacing_m
            if length_m <= 0.0:
                continue
            deltas.append((t_obs - t_bg) / length_m)
    delta_slowness = float(np.mean(deltas))
    model = 1.0 / (1.0 / background + delta_slowness)
    return {'velocity_m_s': np.clip(model, *velocity_bounds_m_s), 'confidence': 0.8, 'abstain': False}

@pytest.mark.parametrize('probe,bound,false_discovery', [(_fwi_zero_inversion, 0.001, 1.0 / 3.0), (_fwi_constant_lens, 0.16, 1.0 / 3.0), (_fwi_travel_time_only, 0.001, 1.0 / 3.0)])
def test_fwi_shortcut_probes_stay_far_below_reference(probe, bound, false_discovery):
    fwi = load('EarthScience', 'ActiveFullWaveformInversion')
    result = fwi.evaluate(probe)
    assert result['valid'] == 1.0
    assert result['development_false_discovery_rate'] == pytest.approx(false_discovery)
    print('fwi probe', probe.__name__, 'combined=%.6f' % result['combined_score'])
    assert result['combined_score'] < bound, probe.__name__
