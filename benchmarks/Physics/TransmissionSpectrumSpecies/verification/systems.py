"""The frozen system set: what is in each atmosphere, and which of them can be resolved at all."""
from __future__ import annotations

import numpy as np

from world import CONFUSABLE, SPECIES_ORDER

# Four regimes. The names are the scientific claim being made about each system, and the evaluator
# scores different things on different regimes - identification on the ones that are identifiable,
# refusal on the ones that are not.
#
#   clear       enough signal, no confusable species: the set is recoverable and must be reported
#   confusable  exactly one of the DMS/C2H4 pair is present, and their bands overlap at 0.98
#               correlation, so no allocation of the budget separates them: abstention is correct
#   muted       a grey cloud deck sits above the features and mutes all of them at once: nothing is
#               identifiable and abstention is correct
#   sparse      the species are separable in principle but the budget cannot reach the required
#               depth on enough bands at once; abstention is correct


def build(seed, count):
    """Deterministic draw of `count` systems."""
    rng = np.random.default_rng(seed)
    plain = [name for name in SPECIES_ORDER if name not in CONFUSABLE]
    systems = []
    for index in range(count):
        regime = ("clear", "confusable", "muted", "sparse")[index % 4]
        abundances = np.zeros(len(SPECIES_ORDER))
        chosen = rng.choice(plain, size=int(rng.integers(1, 4)), replace=False)
        for name in chosen:
            abundances[SPECIES_ORDER.index(name)] = float(rng.uniform(0.5, 3.0))
        present = set(chosen)
        if regime == "confusable":
            partner = str(rng.choice(sorted(CONFUSABLE)))
            abundances[SPECIES_ORDER.index(partner)] = float(rng.uniform(0.8, 2.5))
            present.add(partner)
        # Calibrated against the budget rather than chosen by eye. With BUDGET transits spread over
        # twelve bands, the best achievable signal-to-noise on the species signal is
        # max|D - D_flat| / (noise / sqrt(budget * points_per_band)); the four regimes are placed at
        # roughly 30, 30, 0.2 and 0.8 by that measure, so "unidentifiable" means the whole budget
        # spent on the best band still does not reach unit signal-to-noise.
        grey = {"clear": 0.02, "confusable": 0.02, "muted": 500.0, "sparse": 0.02}[regime]
        noise = {"clear": 1.0e-3, "confusable": 1.0e-3, "muted": 1.0e-3, "sparse": 6.5e-2}[regime]
        systems.append({
            "system_id": "sys%03d" % index,
            "regime": regime,
            "present": frozenset(present),
            "abundances": abundances,
            "grey": grey,
            "rayleigh": float(rng.uniform(0.0, 0.02)),
            "depth": float(rng.uniform(0.004, 0.012)),
            "scale": float(rng.uniform(2.0e-4, 5.0e-4)),
            "noise_per_transit": noise,
            # Fixed at construction so the noise realisation is a property of the frozen system set
            # rather than of the process that evaluates it.
            "noise_seed": int(rng.integers(0, 2 ** 31 - 1)),
        })
    return systems


def identifiable(system):
    """Is the species set recoverable from any allocation of the budget?"""
    return system["regime"] == "clear"


def scorable_species(system):
    """Which species a report is graded on. The confusable pair is never graded as present or
    absent, because the world does not determine it: grading it would reward a coin flip."""
    return tuple(name for name in SPECIES_ORDER if name not in CONFUSABLE)
