"""Private passive circuits, solved as small continuous-time linear systems."""

import hashlib
from dataclasses import dataclass

import numpy as np

from .protocol import integer, number, validate_spec

STRUCTURES = ("leaky_single_rc", "leaky_double_rc", "leaky_series_rlc")


def random_generator(seed, stream):
    seed = integer(seed, "seed")
    token = ("electrical_impedance-0.1|%d|%s" % (seed, stream)).encode("utf-8")
    return np.random.default_rng(int.from_bytes(hashlib.sha256(token).digest()[:16], "big"))


@dataclass(frozen=True)
class Branch:
    resistance: float
    capacitance: float
    inductance: float = 0.

    def __post_init__(self):
        for name, low, high in (("resistance", 50., 2500.), ("capacitance", 1e-7, 2e-5), ("inductance", 0., .3)):
            object.__setattr__(self, name, number(getattr(self, name), low, high, name))


@dataclass(frozen=True)
class Parameters:
    leakage_ohm: float
    branches: tuple

    def __post_init__(self):
        object.__setattr__(self, "leakage_ohm", number(self.leakage_ohm, 1000, 20000, "leakage resistance"))
        if not isinstance(self.branches, tuple) or len(self.branches) > 2 or any(not isinstance(b, Branch) for b in self.branches):
            raise ValueError("branches must be a tuple of at most two Branch objects")
        if any(b.inductance > 0 for b in self.branches) and len(self.branches) != 1:
            raise ValueError("an inductive branch must be the only branch")

    @classmethod
    def generate(cls, seed, structure):
        if structure not in STRUCTURES:
            raise ValueError("unknown private structure")
        rng = random_generator(seed, "parameters")
        leakage = float(rng.uniform(3000, 12000))
        if structure == "leaky_single_rc":
            branches = (Branch(float(rng.uniform(150, 650)), float(rng.uniform(.5e-6, 4e-6))),)
        elif structure == "leaky_double_rc":
            branches = (Branch(float(rng.uniform(150, 650)), float(rng.uniform(.3e-6, 1.2e-6))),
                        Branch(float(rng.uniform(450, 1800)), float(rng.uniform(3e-6, 10e-6))))
        else:
            branches = (Branch(float(rng.uniform(80, 260)), float(rng.uniform(.8e-6, 4e-6)), float(rng.uniform(.04, .18))),)
        return cls(leakage, branches)


class Kernel:
    MAX_SOLVES = 65

    def __init__(self, parameters):
        if not isinstance(parameters, Parameters):
            raise ValueError("expected Parameters")
        self.parameters = parameters

    def system(self, spec):
        """Return diagonal E,F,G,C,D for E*x'=Fx+G Vin, Vport=Cx+D Vin.

        Row scaling avoids division by a very small positive inductance.
        """
        spec = validate_spec(spec)
        params = self.parameters
        g = 1/spec["source_ohm"] + 1/spec["load_ohm"] + 1/params.leakage_ohm
        if len(params.branches) == 1 and params.branches[0].inductance > 0:
            branch = params.branches[0]
            d = 1/(spec["source_ohm"]*g)
            f = np.array([[0., 1.], [-1., -(branch.resistance+1/g)]])
            return np.array([branch.capacitance, branch.inductance]), f, np.array([0., d]), np.array([0., -1/g]), d
        conductances = np.array([1/b.resistance for b in params.branches])
        g += float(conductances.sum())
        c = conductances/g
        d = 1/(spec["source_ohm"]*g)
        f = conductances[:, None]*(np.tile(c, (len(c), 1))-np.eye(len(c)))
        return np.array([b.capacitance for b in params.branches]), f, conductances*d, c, d

    def spectrum(self, spec):
        spec = validate_spec(spec)
        mass, matrix, b, c, d = self.system(spec)
        values, solves = [], 0
        for frequency in spec["frequencies_hz"]:
            if len(b):
                if solves >= self.MAX_SOLVES:
                    raise RuntimeError("electrical spectrum solve budget exhausted")
                solves += 1
                try:
                    state = np.linalg.solve(np.diag(2j*np.pi*frequency*mass)-matrix, b)
                except np.linalg.LinAlgError as error:
                    raise RuntimeError("electrical spectrum linear solve failed") from error
                response = d + c @ state
            else:
                response = complex(d)
            voltage = spec["amplitude_v"]*response
            if not np.isfinite(voltage):
                raise RuntimeError("electrical spectrum became nonfinite")
            values.append([float(voltage.real), float(voltage.imag)])
        return np.asarray(values), {"linear_solves": solves, "state_dimension": len(b)}
