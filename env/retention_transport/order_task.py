"""Prospective observable task on the existing world, not a new World/registry entry.

A predictor receives both legal schedules and predicts signed recovery(left-right).
No clean targets or family identities are exposed by the public contract.
"""
import math
import numpy as np

VERSION = 'retention-order-task-0.1'
CONTRAST_SCALE = 0.1


def describe():
    return {'version': VERSION,
            'question': 'Predict recovery(left) minus recovery(right) at their shared final time. Both schedules move the same total fluid volume; their rates occur in opposite order.',
            'interpretation': 'A measurable order effect refutes cumulative-volume-only predictions in that regime. A null effect does not uniquely identify internal geometry.',
            'noise': 'Each arm uses an independently prepared cartridge and independent readout noise; contrast SD is sqrt(2)*0.002 per pair.',
            'score': '100*exp(-RMSE/0.1) across signed contrasts. Report absolute recovery prediction and quantitative claims separately.',
            'status': 'unregistered prospective task; no model results yet'}


def pair(rate_a, rate_b, duration):
    vals = (rate_a, rate_b, duration)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vals):
        raise ValueError('rates and duration must be finite numbers')
    if not (0 <= rate_a <= 3 and 0 <= rate_b <= 3 and 0 < duration <= 6) or rate_a == rate_b:
        raise ValueError('different rates in [0,3], duration in (0,6] required')
    def arm(a, b):
        return {'times': [2.*duration], 'flow': [{'at': 0., 'rate': float(a)}, {'at': float(duration), 'rate': float(b)}]}
    return {'left': arm(rate_a, rate_b), 'right': arm(rate_b, rate_a)}


def observe(world, design, *, noise_key):
    """Operator measurement helper; clean targets require explicit noise_key=None."""
    if set(design) != {'left', 'right'}:
        raise ValueError('expected left and right schedules')
    specs = [world.validate(design[k]) for k in ('left', 'right')]
    a,b=specs
    if len(a['times']) != 1 or a['times'] != b['times'] or len(a['flow']) != 2 or len(b['flow']) != 2:
        raise ValueError('one common final readout and two segments required')
    expected=pair(a['flow'][0]['rate'],a['flow'][1]['rate'],a['flow'][1]['at'])
    if design != expected:
        raise ValueError('expected matched-volume reversed order pair')
    values = [world.run(s, noise_key=None if noise_key is None else f'{noise_key}:{i}')['values'][-1][0] for i,s in enumerate(specs)]
    return float(values[0]-values[1])


def score(predictions, targets):
    pred, truth = np.asarray(predictions), np.asarray(targets)
    if pred.dtype.kind not in 'fiu' or truth.dtype.kind not in 'fiu' or pred.ndim != 1 or pred.shape != truth.shape or not pred.size:
        raise ValueError('equal nonempty real vectors required')
    if not np.isfinite(pred).all() or not np.isfinite(truth).all():
        raise ValueError('finite contrasts required')
    rmse = float(np.sqrt(np.mean((pred-truth)**2)))
    return {'rmse': rmse, 'score': 100.*math.exp(-rmse/CONTRAST_SCALE)}
