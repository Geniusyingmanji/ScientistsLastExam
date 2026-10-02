"""Private instance generation; labels are operator strata, never answers."""

import hashlib

import numpy as np

from .kernel import Parameters
from .protocol import integer

STRUCTURES = ("static_frequency_spread", "irreversible_transverse_decay", "mixed")


def random_generator(seed, stream):
    seed = integer(seed, "seed")
    if not isinstance(stream, str):
        raise ValueError("RNG stream must be text")
    token = ("spin_echo-0.1|%d|%s" % (seed, stream)).encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(token).digest()[:16], "big"))


def generate(seed, structure):
    if structure not in STRUCTURES:
        raise ValueError("unknown operator structure")
    rng = random_generator(seed, "parameters-" + structure)
    center = float(rng.uniform(-10, 10))
    if structure == "irreversible_transverse_decay":
        return Parameters((center,), (1.0,), float(rng.uniform(5, 14)))
    count = int(rng.choice([5, 7, 9]))
    weights = rng.uniform(.5, 1.5, count)
    weights /= weights.sum()
    locations = rng.uniform(-1, 1, count)
    locations -= float(weights @ locations)
    spread = float(rng.uniform(8, 20))
    variance = float(weights @ (locations*locations))
    if variance <= 0:
        # A degenerate draw is a recorded generation error, never a redraw.
        raise RuntimeError("degenerate frequency draw")
    frequencies = center + locations*(spread / np.sqrt(variance))
    rate = 0.0 if structure == "static_frequency_spread" else float(rng.uniform(3, 12))
    return Parameters(tuple(frequencies.tolist()), tuple(weights.tolist()), rate)

