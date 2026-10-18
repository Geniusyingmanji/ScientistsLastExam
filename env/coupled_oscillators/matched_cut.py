"""Public paired-intervention design, not an edge-discovery score.

A nonzero matched effect can support an active connection under the documented
cut semantics. A null effect alone cannot certify absence: the connection may
not have been sufficiently excited or observed. No hidden graph is consulted.
"""
from copy import deepcopy
from .world import _validate


def build(base, edge):
    baseline = _validate(base)
    altered = deepcopy(baseline)
    altered['cut_edges'] = baseline['cut_edges'] + [edge]
    altered = _validate(altered)
    added = [p for p in altered['cut_edges'] if p not in baseline['cut_edges']]
    if len(added) != 1:
        raise ValueError('one new edge cut required')
    if any(node in baseline['clamp'] for node in added[0]):
        raise ValueError('matched connection test requires both endpoints unclamped')
    if not any(t > 0 for t in baseline['times']):
        raise ValueError('post-preparation observations required')
    return {'baseline': baseline, 'cut': altered}


def validate_pair(pair):
    if not isinstance(pair, dict) or set(pair) != {'baseline', 'cut'}:
        raise ValueError('baseline and cut specifications required')
    a, b = _validate(pair['baseline']), _validate(pair['cut'])
    added = [p for p in b['cut_edges'] if p not in a['cut_edges']]
    if len(added) != 1 or a['cut_edges'] != [p for p in b['cut_edges'] if p not in added]:
        raise ValueError('exactly one added cut required')
    expected = build(a, added[0])
    if expected['cut'] != b:
        raise ValueError('confounded paired experiment')
    return {'edge': added[0], 'rows': len(a['times']),
            'scope': 'Matched cut effect only; null effect does not establish absent edge.',
            'discovery_score': None}
