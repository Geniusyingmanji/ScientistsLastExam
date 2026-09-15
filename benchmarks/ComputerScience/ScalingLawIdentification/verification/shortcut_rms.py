"""Fixed best development probe from the 2304-setting review sweep.

A five-point doubling ladder, bounded nuisance fit, hard class probability and
one RMS gate; it intentionally lacks a class-identifiability test.
"""
import math
import numpy as np


def _shape(name, size):
    log_size = math.log2(max(size, 2))
    return {"constant": 1., "logarithmic": log_size, "linear": float(size),
            "linearithmic": size*log_size, "quadratic": float(size)**2,
            "exponential": 2.**(size/8.)}[name]


def identify_scaling_law(problem, time_run, budget_units):
    lo, hi = problem['size_bounds']
    ladder = (8, 16, 32, 64, 128)
    sizes = ladder if lo <= min(ladder) and max(ladder) <= hi else np.rint(np.geomspace(lo, hi, len(ladder))).astype(int)
    logs = np.log([time_run(int(n))['runtime_ms'] for n in sizes])
    x = 64./np.asarray(sizes)
    fits = []
    for name in problem['classes']:
        y = logs - np.log([_shape(name, n) for n in sizes])
        a = np.clip(np.dot(x-x.mean(), y-y.mean())/max(np.sum((x-x.mean())**2), 1e-15), -2, 2)
        residual = y-a*x
        fits.append((float(np.std(residual)), math.exp(float(residual.mean()))))
    best = int(np.argmin([rms for rms, scale in fits]))
    abstain = fits[best][0] > .4
    return {'class_probabilities': {name: float(i == best) for i, name in enumerate(problem['classes'])},
            'scale': None if abstain else fits[best][1], 'abstain': bool(abstain), 'confidence': .8}
