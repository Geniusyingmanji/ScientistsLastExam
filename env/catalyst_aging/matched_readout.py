"""Unregistered diagnostic: same-index counterfactual coupon/control readouts.

These are four separate reset experiments, never simultaneous measurements.
The fixed instrument state depends on event index, so matched prefixes align it.
No difficulty or unique mechanism claim follows from the algebraic cancellation.
"""
import math
from copy import deepcopy
from .protocol import validate_spec, STANDARD_RESPONSE


def quartet(prefix, reaction_event, fresh_coupon):
    if not isinstance(prefix, list) or not prefix:
        raise ValueError('nonempty shared preparation required')
    if reaction_event.get('kind') != 'reaction':
        raise ValueError('terminal reaction required')
    used = reaction_event['coupon_id']
    prepared = {e.get('coupon_id') for e in prefix if e.get('kind') == 'reaction'}
    if used not in prepared or fresh_coupon in prepared or fresh_coupon == used:
        raise ValueError('used coupon must be prepared; comparison coupon must be fresh')
    fresh = dict(reaction_event, coupon_id=fresh_coupon)
    out = {}
    for name, event in [('used', reaction_event), ('fresh', fresh),
                        ('blank', {'kind':'blank'}), ('standard', {'kind':'standard'})]:
        events = deepcopy(prefix) + [deepcopy(event)]
        out[name] = validate_spec({'events':events,'event_indices':[len(events)]})
    return out


def calibrated_contrast(values, minimum_standard_span=.15):
    """Gain-corrected used-minus-fresh product; noisy ratio is diagnostic only.

Reject weak calibration rather than manufacturing a large normalized effect.
The minimum span is public/fixed, not tuned to a hidden realization.
"""
    if set(values) != {'used','fresh','blank','standard'}:
        raise ValueError('four matched observations required')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values.values()):
        raise ValueError('finite scalar observations required')
    if not math.isfinite(minimum_standard_span) or minimum_standard_span <= 0:
        raise ValueError('positive finite calibration threshold required')
    span = values['standard'] - values['blank']
    if span < minimum_standard_span:
        raise ValueError('calibration too weak or reversed')
    return STANDARD_RESPONSE * (values['used']-values['fresh']) / span
