"""Unregistered prospective task; the frozen capacity batch scorer is unchanged."""
import math
import numpy as np

VERSION = 'capacity-order-task-0.1'
ABSOLUTE_SCALE = 0.1
CONTRAST_SCALE = 0.05


def describe():
    return {
        'version': VERSION,
        'question': 'Predict recovered fractions for both schedules at the shared final time, and hence the signed left-minus-right difference.',
        'design': 'Same load and time; three equal-duration rates in reverse order, then an identical optional tail. Each arm starts with a fresh preparation.',
        'interpretation': 'Different endpoints refute a memoryless integral-of-flow clock in this regime. Linear hidden-state dynamics can also produce order effects; this is not a unique mechanism test.',
        'noise': 'Independent Gaussian readout SD0.002 per arm; pair difference SD sqrt(2)*0.002.',
        'score': '50% absolute recovery score + 50% signed contrast score. Each is 100*exp(-RMSE/scale), with public scales0.1 and0.05 respectively. Both components are reported. No mechanism-label or claim score.',
        'output': 'One row [left_fraction,right_fraction] per design; contrast is derived from the same predictions.',
        'status': 'prototype task; no shared registration or model results',
    }


def _real(x, lo, hi):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not lo <= x <= hi:
        raise ValueError('finite numeric control outside legal range')
    return float(x)


def pair(load, rates, duration, final_time, tail_rate=1.):
    load = _real(load, .1, 3)
    if not isinstance(rates, (list, tuple)) or len(rates) != 3:
        raise ValueError('three rates required')
    rates = [_real(q, 0, 3) for q in rates]
    duration = _real(duration, 0, 3)
    if duration == 0 or rates[0] == rates[2]:
        raise ValueError('positive duration and non-palindromic rates required')
    final_time = _real(final_time, 3*duration, 12)
    tail_rate = _real(tail_rate, 0, 3)
    def arm(qs):
        flow = [{'at': i*duration, 'rate': q} for i, q in enumerate(qs)]
        if final_time > 3*duration:
            flow.append({'at': 3*duration, 'rate': tail_rate})
        return {'load': load, 'times': [final_time], 'flow': flow}
    return {'left': arm(rates), 'right': arm(rates[::-1])}


def validate_pair(world, design):
    if not isinstance(design, dict) or set(design) != {'left', 'right'}:
        raise ValueError('left and right required')
    a, b = (world.validate(design[k]) for k in ('left', 'right'))
    if len(a['times']) != 1 or len(a['flow']) not in (3, 4):
        raise ValueError('one final time and three or four segments required')
    expected = pair(a['load'], [s['rate'] for s in a['flow'][:3]],
                    a['flow'][1]['at'], a['times'][0],
                    a['flow'][3]['rate'] if len(a['flow']) == 4 else 1.)
    if {'left': a, 'right': b} != expected:
        raise ValueError('expected matched-duration reversed schedules')
    return expected


def observe(world, design, *, noise_key):
    design = validate_pair(world, design)
    return [float(world.run(design[k], noise_key=None if noise_key is None else f'{noise_key}:{k}')['values'][0][0])
            for k in ('left', 'right')]


def score(predictions, targets):
    a, b = np.asarray(predictions), np.asarray(targets)
    if a.dtype.kind not in 'fiu' or b.dtype.kind not in 'fiu' or a.ndim != 2 or a.shape != b.shape or a.shape[1] != 2 or not a.shape[0]:
        raise ValueError('equal nonempty N-by-2 real arrays required')
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('finite predictions required')
    a, b = a.astype(float), b.astype(float)
    # Reject overflow instead of quietly accepting an invalid derived contrast.
    with np.errstate(over='ignore', invalid='ignore'):
        err = a-b
        contrast = (a[:, 0]-a[:, 1])-(b[:, 0]-b[:, 1])
    if not np.isfinite(err).all() or not np.isfinite(contrast).all():
        raise ValueError('nonfinite prediction error')
    absolute_rmse = math.hypot(*err.ravel()) / math.sqrt(err.size)
    contrast_rmse = math.hypot(*contrast) / math.sqrt(contrast.size)
    absolute = 100*math.exp(-absolute_rmse/ABSOLUTE_SCALE)
    order = 100*math.exp(-contrast_rmse/CONTRAST_SCALE)
    return {'absolute_rmse': absolute_rmse, 'contrast_rmse': contrast_rmse,
            'absolute_score': absolute, 'contrast_score': order,
            'score': .5*absolute+.5*order}
