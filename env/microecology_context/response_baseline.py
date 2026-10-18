"""Public-observation endpoint controls; not a mechanistic equation estimator.

Fixed temperature, endpoint, and all initial pools except A/B are required.
Unregularized least squares uses every record (including repeats); rank failure
is explicit. No private kernel, sampled parameters, or targets are accepted.
"""
import numpy as np
from .world import validate, CHANNELS


def _signature(spec):
    s = validate(spec)
    if s['events']:
        raise ValueError('event-free endpoint controls required')
    return (s['temperature'], s['times'][-1],
            tuple((k, v) for k, v in s['initial'].items() if k not in ('A', 'B')))


def _features(spec, interaction):
    s = validate(spec)
    a, b = s['initial']['A'], s['initial']['B']
    return [1., a, b] + ([a*b] if interaction else [])


def fit(records, *, interaction=False):
    if type(interaction) is not bool:
        raise ValueError('interaction must be boolean')
    if not records:
        raise ValueError('public observations required')
    signature = _signature(records[0]['spec'])
    x, y = [], []
    for record in records:
        s = validate(record['spec'])
        if _signature(s) != signature:
            raise ValueError('confounded endpoint observations')
        obs = record['observation']
        if obs['times'] != s['times'] or obs['channels'] != list(CHANNELS):
            raise ValueError('observation axis/channel mismatch')
        values = np.asarray(obs['values'], dtype=float)
        if values.shape != (len(s['times']), len(CHANNELS)) or not np.isfinite(values).all():
            raise ValueError('finite observation matrix required')
        x.append(_features(s, interaction)); y.append(values[-1])
    x, y = np.asarray(x), np.asarray(y)
    coeff, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise ValueError('rank-deficient training design')
    return {'interaction': interaction, 'signature': signature,
            'coefficients': coeff.tolist(), 'rank': int(rank),
            'singular_values': singular.tolist(), 'records': len(records),
            'training_predictions': (x @ coeff).tolist(),
            'training_rmse_by_channel': np.sqrt(np.mean((x @ coeff-y)**2,axis=0)).tolist(),
            'scope': 'Endpoint response surface only; no local flux or unique mechanism claim.'}


def predict(model, specs):
    # Canonicalize the signature so a saved JSON snapshot behaves identically.
    import json
    signature = json.dumps(model['signature'])
    for s in specs:
        if json.dumps(_signature(s)) != signature:
            raise ValueError('query changes fixed endpoint controls')
    coeff = np.asarray(model['coefficients'], dtype=float)
    if coeff.shape != (4 if model['interaction'] else 3, len(CHANNELS)) or not np.isfinite(coeff).all():
        raise ValueError('invalid fitted coefficients')
    if not specs:
        return []
    return (np.asarray([_features(s,model['interaction']) for s in specs]) @ coeff).tolist()
