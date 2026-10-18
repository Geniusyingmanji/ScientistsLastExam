"""Sampling uncertainty for replicated four-arm observable contrasts.

Rows are independent replicate blocks; columns are fixed matched arms in
low/low, high/low, low/high, high/high order. Pairing within a block is allowed.
This estimates repeat-readout uncertainty, not model bias, identifiability,
parameter uncertainty or a calibrated discovery score. No confidence label is
assigned automatically (especially under clipping or small samples).
"""
import numpy as np


def summarize(replicates):
    x = np.asarray(replicates, dtype=float)
    if x.ndim != 2 or x.shape[1] != 4 or x.shape[0] < 2 or not np.isfinite(x).all():
        raise ValueError('at least two finite four-arm replicate blocks required')
    weights = {'A_at_B_low': [-1,1,0,0], 'A_at_B_high': [0,0,-1,1],
               'B_at_A_low': [-1,0,1,0], 'B_at_A_high': [0,-1,0,1],
               'AB_interaction': [1,-1,-1,1]}
    effects = {}
    for name, w in weights.items():
        values = x @ np.asarray(w)
        effects[name] = {'replicate_effects': values.tolist(),
                         'mean': float(values.mean()),
                         'standard_error': float(values.std(ddof=1)/np.sqrt(len(values)))}
    return {'replicate_blocks': len(x), 'effects': effects,
            'scope': 'Independent repeat blocks assumed; no automatic significance or discovery score.',
            'discovery_score': None}
