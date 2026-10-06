"""Trusted operator binding for exposed fixtures; never a sealed evaluation."""
import hashlib
import json
from .development_design import design
from .metrics import summarize


def fixture_manifest():
    d = design()
    payload = json.dumps(d, sort_keys=True, separators=(',', ':'), allow_nan=False)
    entries = []
    for panel in d['panels']:
        for i, spec in enumerate(panel['specs']):
            entries.append({'id': '%s-%d' % (panel['kind'], i + 1),
                            'axis': panel['kind'], 'spec': spec})
    return {'schema': 'isotope-exposed-metric-binding-1',
            'design_sha256': hashlib.sha256(payload.encode()).hexdigest(),
            'exposure': d['exposure'], 'structural_holdout': False,
            'entries': entries}


def score_fixtures(predictions, targets, *, design_sha256):
    """Arrays keyed by fixed fixture IDs. Targets must come from trusted operator.

    Caller cannot relabel axes or supply alternate conditions. Hash binds the
    public design, not outcome provenance, execution isolation or model freezing.
    All fixtures required; incomplete runs must be reported separately.
    """
    m = fixture_manifest()
    if design_sha256 != m['design_sha256']:
        raise ValueError('development design hash mismatch')
    expected = {e['id'] for e in m['entries']}
    if not isinstance(predictions, dict) or not isinstance(targets, dict):
        raise ValueError('fixture mappings required')
    if set(predictions) != expected or set(targets) != expected:
        raise ValueError('exact complete fixture IDs required')
    records = [{'axis': e['axis'], 'spec': e['spec'],
                'prediction': predictions[e['id']], 'target': targets[e['id']]}
               for e in m['entries']]
    result = summarize(records)
    result.update({k: m[k] for k in ('schema', 'design_sha256', 'exposure', 'structural_holdout')})
    result['target_provenance'] = 'Trusted caller responsibility; not authenticated by this helper.'
    return result
