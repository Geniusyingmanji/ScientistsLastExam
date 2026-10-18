"""Exact row-level overlap audit for future tasks, without changing old scores.

Inputs must be successful acquisition specifications from the trusted ledger.
Labels describe support geometry, not scientific novelty or guaranteed holdout.
"""
from .protocol import validate_spec


def classify_rows(acquired, query):
    specs = [validate_spec(s) for s in acquired]
    query = validate_spec(query)
    seen = set()
    for s in specs:
        for f in s['frequencies_hz']:
            seen.add((f,s['source_ohm'],s['load_ohm'],s['amplitude_v']))
    rows = []
    for f in query['frequencies_hz']:
        key = (f,query['source_ohm'],query['load_ohm'],query['amplitude_v'])
        same_amplitude = [x for x in seen if x[3] == key[3]]
        frequency_seen = any(x[0] == f for x in same_amplitude)
        circuit_seen = any(x[1:3] == key[1:3] for x in same_amplitude)
        amplitude_only = key not in seen and any(x[:3] == key[:3] for x in seen)
        if key in seen: kind = 'observed'
        elif amplitude_only: kind = 'amplitude_only'
        elif not same_amplitude: kind = 'amplitude_confounded'
        elif frequency_seen and circuit_seen: kind = 'new_combination'
        elif frequency_seen: kind = 'apparatus_only'
        elif circuit_seen: kind = 'frequency_only'
        else: kind = 'joint'
        rows.append({'frequency_hz':f,'kind':kind,'exact_overlap':key in seen,
                     'frequency_seen_at_amplitude':frequency_seen,
                     'circuit_seen_at_amplitude':circuit_seen})
    return {'rows':rows,'counts':{k:sum(r['kind']==k for r in rows) for k in sorted({r['kind'] for r in rows})},
            'all_exact_disjoint':all(not r['exact_overlap'] for r in rows),
            'scope':'Exact acquisition-ledger overlap only; no enforced holdout or discovery score.'}
