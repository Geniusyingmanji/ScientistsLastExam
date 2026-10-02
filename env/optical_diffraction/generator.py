"""Private fixed-menu generator; no outcome-based screening or rejection."""
import hashlib
import random

from .kernel import Parameters
from .protocol import integer

STRUCTURES = ("regular_single_label", "regular_binary", "irregular_binary")


def random_generator(seed, domain):
    seed = integer(seed)
    if not isinstance(domain, str):
        raise ValueError("RNG domain must be text")
    payload = f"optical-diffraction-v0.1|{seed}|{domain}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(payload).digest(), "big"))


def generate(seed, structure=None):
    seed = integer(seed)
    if structure is None:
        structure = random_generator(seed, "family").choice(STRUCTURES)
    if structure not in STRUCTURES:
        raise ValueError("invalid operator structure")
    geometry = random_generator(seed, "geometry-" + structure)
    weight_rng = random_generator(seed, "weights-" + structure)
    label_rng = random_generator(seed, "tags-" + structure)
    n = geometry.choice([4, 5, 6, 7] if structure == "irregular_binary" else [3, 4, 5, 6, 7])
    shift = geometry.uniform(-.5, .5)
    if structure == "irregular_binary":
        raw = [0.]
        for _ in range(n-1):
            raw.append(raw[-1] + geometry.uniform(.08, .70))
        positions = [x - raw[-1]/2 + shift for x in raw]
        raw_weights = [weight_rng.uniform(.7, 1.3) for _ in range(n)]
        weights = [w/sum(raw_weights) for w in raw_weights]
        indices = list(range(n))
        label_rng.shuffle(indices)
        marked = set(indices[:label_rng.randrange(1, n)])
        tags = ["B" if i in marked else "A" for i in range(n)]
    else:
        gap = geometry.uniform(.25, .60)
        positions = [(i-(n-1)/2)*gap+shift for i in range(n)]
        weights = [1/n] * n
        parity = label_rng.randrange(2)
        tags = ["B" if (i+parity) % 2 else "A" for i in range(n)] if structure == "regular_binary" else ["A"] * n
    return Parameters(positions, weights, tags)
