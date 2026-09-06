"""Reference: use the isotope sign to route, then make the bottom-up number agree or abstain.

Deliberately below the ceiling. The thresholds are round numbers, the inventory search is greedy,
and no attempt is made to fit the sink jointly. What it has that the baseline does not is two
reasons to stop:

  * **top-down and bottom-up disagree** - the isotopes imply a source increased and its own
    inventory says it did not. Something outside the source list moved, and the only candidate is
    the sink. This is the confounded regime, and it is the trap the baseline walks into.
  * **the bottom-up number cannot single anyone out** - several microbial inventories move by about
    the same marginal amount. Naming one is a coin flip.

The routing is the cheap part: d13C rising means the extra methane is *heavier* than the
emission-weighted mean, which only fossil and biomass burning are, and a single ethane measurement
separates those two. Everything else costs budget.
"""
from __future__ import annotations

import numpy as np

MEAN_SIGNATURE = -53.37
SIGNATURES = {"wetlands": -61.0, "ruminants": -65.0, "waste": -55.0,
              "fossil": -44.0, "biomass_burning": -25.0}
INVENTORY_CONFIRM_SIGMA = 2.5
INVENTORY_DENY_SIGMA = 1.0


def attribute(problem, measure):
    catalogue = list(problem["source_catalogue"])
    microbial = [name for name in problem["microbial_sources"] if name in catalogue]
    nothing = {"abstain": True, "changed_sources": {}, "confidence": 0.0}

    burden = measure("burden")["burden_change_tg"]
    delta = measure("d13c")["delta13c_change_permil"]
    if burden <= 0:
        return nothing

    if delta > 0.05:
        # Heavier than the mean: fossil or biomass burning. Ethane tells them apart, and it is the
        # cheaper of the two tracers that can.
        ethane = measure("ethane")["ethane_emission_change_tg"]
        name = "fossil" if ethane > 0.9 else "biomass_burning"
        flags = {source: (source == name) for source in catalogue}
        return {"abstain": False, "changed_sources": flags, "confidence": 0.7}

    # Lighter than the mean, or barely moved: microbial, or the sink. The isotopes cannot say which,
    # so ask the sectors themselves.
    implied = MEAN_SIGNATURE + delta * 60.0
    order = sorted(microbial, key=lambda name: abs(SIGNATURES[name] - implied))
    confirmed, marginal = [], []
    for name in order[:2]:
        reading = measure("inventory", name)
        ratio = reading["emission_change_tg"] / max(reading["uncertainty"], 1e-9)
        if ratio > INVENTORY_CONFIRM_SIGMA:
            confirmed.append(name)
        elif ratio > INVENTORY_DENY_SIGMA:
            marginal.append(name)

    if len(confirmed) == 1 and not marginal:
        flags = {source: (source == confirmed[0]) for source in catalogue}
        return {"abstain": False, "changed_sources": flags, "confidence": 0.6}
    # Either nothing confirms - the isotopes point at a source whose own inventory denies it, which
    # means something outside the source list moved - or several are equally marginal.
    return nothing
