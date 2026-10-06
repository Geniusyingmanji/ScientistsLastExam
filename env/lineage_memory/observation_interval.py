"""Fixed-design observed squared-difference contrast; no hidden parameter inputs."""
import math
import numbers


def _differences(rows):
    if not isinstance(rows, list) or not 2 <= len(rows) <= 20000:
        raise ValueError('require 2..20000 observed pairs per arm')
    out = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError('each observation must contain two proportions')
        if any(isinstance(v, bool) or not isinstance(v, numbers.Real) or not math.isfinite(v) or not 0 <= v <= 1 for v in row):
            raise ValueError('observed proportions must be finite in [0,1]')
        out.append((float(row[0])-float(row[1]))**2)
    return out


def fixed_interval(control, treatment, alpha=.05):
    """Single predeclared fixed-size contrast. No optional stopping guarantee.

    Independent rows and arms required. Estimates half the reduction in expected
    within-pair squared difference. Covariance interpretation additionally needs
    identical marginal distributions across arms; this helper cannot verify it.
    """
    if isinstance(alpha, bool) or not isinstance(alpha, numbers.Real) or not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError('alpha must be finite in (0,1)')
    a, b = _differences(control), _differences(treatment)
    if len(a) != len(b):
        raise ValueError('equal predeclared arm sizes required')
    estimate = math.fsum((x-y)/2 for x,y in zip(a,b))/len(a)
    radius = math.sqrt(math.log(2/alpha)/(2*len(a)))
    return {'estimand': 'half_reduction_in_expected_squared_pair_difference',
            'estimate': estimate, 'interval': [max(-.5,estimate-radius),min(.5,estimate+radius)],
            'radius_bound': radius, 'pairs_per_arm':len(a), 'alpha':float(alpha),
            'covariance_interpretation_verified':False,
            'scope':'Fixed single contrast, independent rows/arms; not sequential or mechanism certification.'}
