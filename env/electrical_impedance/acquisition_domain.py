"""Public acquisition domain for a separately frozen restricted-design task.

This is not a secret blacklist: candidates see the allowed frequency and circuit
sets. It changes the task and must not be applied to existing frozen runs.
"""
from .protocol import validate_spec


class AcquisitionDomain:
    def __init__(self, frequencies, circuits, amplitude):
        if not frequencies or not circuits:
            raise ValueError('nonempty domain required')
        self.specs=tuple(validate_spec(dict(frequencies_hz=list(frequencies),
            source_ohm=s,load_ohm=l,amplitude_v=amplitude)) for s,l in circuits)
        self.frequencies=frozenset(self.specs[0]['frequencies_hz'])
        self.circuits=frozenset((s['source_ohm'],s['load_ohm']) for s in self.specs)
        self.amplitude=self.specs[0]['amplitude_v']

    def describe(self):
        return {'frequencies_hz':sorted(self.frequencies),
                'source_load_pairs':sorted(self.circuits),'amplitude_v':self.amplitude,
                'scope':'Restricted acquisition grid; arbitrary-grid results are not comparable.'}

    def validate(self, value):
        s=validate_spec(value)
        if not set(s['frequencies_hz'])<=self.frequencies or (s['source_ohm'],s['load_ohm']) not in self.circuits or s['amplitude_v']!=self.amplitude:
            raise ValueError('outside public acquisition domain')
        return s

    def verify_reserved(self, queries):
        if not queries:raise ValueError('nonempty reserved queries required')
        rows=0
        for q in queries:
            s=validate_spec(q)
            for f in s['frequencies_hz']:
                if f in self.frequencies and (s['source_ohm'],s['load_ohm']) in self.circuits and s['amplitude_v']==self.amplitude:
                    raise ValueError('reserved row is acquirable')
                rows+=1
        return {'reserved_rows':rows,'exact_disjoint':True,
                'scope':'Exact tuple disjointness only; nearby interpolation may remain easy.'}
