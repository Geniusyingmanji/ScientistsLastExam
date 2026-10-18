"""Separate opt-in restricted-grid episode. Old default remains unrestricted."""
import json
from .matrix_episode import MatrixEpisode
from .acquisition_domain import AcquisitionDomain


class RestrictedEpisode(MatrixEpisode):
    def __init__(self, seed, root, frequencies, circuits, amplitude, reserved,
                 budget=280, max_attempts=16):
        self.domain=AcquisitionDomain(frequencies,circuits,amplitude)
        reservation=self.domain.verify_reserved(reserved)
        super().__init__(seed,root,budget,max_attempts)
        # Operator-only freeze; describe reveals allowed domain, never queries.
        with (self.root/'restricted-domain.json').open('x') as f:
            json.dump({'domain':self.domain.describe(),'reserved':reserved,
                       'verification':reservation},f,allow_nan=False)

    def validate_acquisition(self,spec):
        return self.domain.validate(spec)

    def call(self,tool,**args):
        result=super().call(tool,**args)
        if tool=='describe':
            result['acquisition_domain']=self.domain.describe()
            result['task_scope']='Restricted-grid episode; not comparable to unrestricted exploration.'
        return result
