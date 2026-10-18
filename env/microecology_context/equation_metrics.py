"""Operator-side equation diagnostics, not a calibrated discovery score.

Inputs are frozen scalar flux/derivative predictions at matched states. Partition
and scales must be chosen before seeing predictions. No model execution here.
"""
import math


def _vector(values):
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError('nonempty vector required')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('finite numeric vector required')
    return list(values)


def derivative_errors(predicted, target, groups, scale):
    target = _vector(target)
    if type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0:
        raise ValueError('positive fixed physical scale required')
    if len(groups) != len(target) or any(not isinstance(g,str) or not g for g in groups):
        raise ValueError('predeclared state group per row required')
    valid = True
    try:
        predicted = _vector(predicted)
        valid = len(predicted) == len(target)
    except ValueError:
        valid = False
    out = {}
    for group in sorted(set(groups)):
        ids = [i for i,g in enumerate(groups) if g == group]
        out[group] = {'count': len(ids), 'valid': valid,
            'normalized_rmse': math.sqrt(sum(((predicted[i]-target[i])/scale)**2 for i in ids)/len(ids)) if valid else None}
    return {'groups': out, 'failed_prediction': not valid, 'discovery_score': None}


def factorial_effects(values):
    """Order: A low/B low, A high/B low, A low/B high, A high/B high.

    Caller must hold all other state/control values fixed; this arithmetic
    cannot verify the design or identify a unique mechanism.
    """
    v = _vector(values)
    if len(v) != 4:
        raise ValueError('four matched arms required')
    return {'A_at_B_low': v[1]-v[0], 'A_at_B_high': v[3]-v[2],
            'B_at_A_low': v[2]-v[0], 'B_at_A_high': v[3]-v[1],
            'AB_interaction': v[3]-v[1]-v[2]+v[0]}


def effect_errors(predicted, target, scale):
    # Reuse validation; no truth-dependent normalization or threshold tuning.
    derivative_errors([0.], [0.], ['validation'], scale)
    actual = factorial_effects(target)
    try:
        fitted = factorial_effects(predicted)
    except ValueError:
        return {'failed_prediction': True, 'effects': None, 'discovery_score': None}
    return {'failed_prediction': False, 'effects': {
        k: {'predicted': fitted[k], 'target': actual[k],
            'normalized_absolute_error': abs(fitted[k]-actual[k])/scale}
        for k in actual}, 'discovery_score': None}
