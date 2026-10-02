"""Private pre-observation parameter generation without rejection selection."""

import hashlib

import numpy as np

from .kernel import Parameters
from .protocol import integer

STRUCTURES = ("neutral_drift", "constant_selection", "frequency_dependence", "symmetric_mutation")


def random_generator(seed, stream):
    seed = integer(seed, "seed")
    if not isinstance(stream, str):
        raise ValueError("RNG stream must be text")
    data = f"population_drift-0.1|{seed}|{stream}".encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(data).digest()[:16], "big"))


def generate(seed, structure):
    if structure not in STRUCTURES:
        raise ValueError("invalid operator structure")
    rng = random_generator(seed, "parameters-"+structure)
    if structure == "neutral_drift":
        return Parameters(0., 0., 0.)
    if structure == "constant_selection":
        return Parameters(float(rng.choice([-1, 1])*rng.uniform(.15, .55)), 0., 0.)
    if structure == "frequency_dependence":
        return Parameters(0., float(rng.choice([-1, 1])*rng.uniform(.45, 1.0)), 0.)
    return Parameters(0., 0., float(rng.uniform(.003, .02)))
