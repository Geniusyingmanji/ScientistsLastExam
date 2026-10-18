"""Explicit common-apparatus pooling for future port-reference comparisons.

Consumes every supplied successful observation, averages repeat quadratures at
each frequency, and strips episode receipt metadata. No outcome-based selection.
Not a correction or replacement of historical failed comparator results.
"""
from .protocol import validate_spec, CHANNELS
from .port_reference import validate_record, ReferenceFailure


def pool_same_apparatus(records):
    if not isinstance(records,list) or not records:
        raise ReferenceFailure('invalid_record','nonempty public records required')
    cells={};apparatus=None
    for record in records:
        s=validate_spec(record['spec']);o=record['observation']
        normalized={'spec':s,'observation':{k:o[k] for k in ('axis','channels','values')}}
        validate_record(normalized)
        key=(s['source_ohm'],s['load_ohm'],s['amplitude_v'])
        if apparatus is None:apparatus=key
        if key!=apparatus:
            raise ReferenceFailure('mixed_apparatus','pooling requires identical circuit and amplitude')
        for f,row in zip(s['frequencies_hz'],o['values']):
            cells.setdefault(f,[]).append(row)
    frequencies=sorted(cells)
    # Preserve full frequency support. Refuse rather than drop data if the
    # resulting public source record exceeds the apparatus row limit.
    source=validate_spec(dict(frequencies_hz=frequencies,source_ohm=apparatus[0],load_ohm=apparatus[1],amplitude_v=apparatus[2]))
    values=[[sum(float(x[j]) for x in cells[f])/len(cells[f]) for j in (0,1)] for f in frequencies]
    return {'record':{'spec':source,'observation':{'axis':frequencies,'channels':list(CHANNELS),'values':values}},
            'counts':[len(cells[f]) for f in frequencies], 'input_records':len(records),
            'scope':'Mean noisy quadratures before nonlinear de-embedding; bias not removed.'}
