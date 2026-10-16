"""Operator-only direct higher-order control of a carbon-conserving C flux.

Independent prototype; does not change the frozen context kernel or registry.
Concentrations are mmol C/L. This is a phenomenological direct interaction,
not a claim about a molecular implementation.
"""
import numpy as np
from .kernel import Kernel

class DirectKernel(Kernel):
    def __init__(self, seed, interaction='three_body'):
        if interaction not in ('pairwise', 'three_body'):
            raise ValueError('unknown interaction')
        super().__init__(seed, 'fixed')
        self.interaction = interaction
        self.beta, self.gamma, self.ka, self.kb = .5, 1.5, .2, .3
        self.anchor_a = .2

    def modulation(self, a, b):
        a, b = max(float(a), 0.), max(float(b), 0.)
        gate = a/(self.ka+a) if self.interaction == 'three_body' else self.anchor_a/(self.ka+self.anchor_a)
        return 1 + b/(self.kb+b)*(-self.beta+self.gamma*gate)

    def derivative(self, t, state, temp):
        z = np.maximum(state, 0.)
        out = super().derivative(t, state, temp)
        _, a, b, c, _, n, y, _, _, _ = z
        theta = 2**((temp-30)/10)
        base = theta*self.p['uc']*c*n/(self.p['kn']+n)/(1+y/self.p['ki'])
        extra = base*(self.modulation(a,b)-1)
        out[3] += .5*extra
        out[5] -= extra
        out[8] += .5*extra
        return out
