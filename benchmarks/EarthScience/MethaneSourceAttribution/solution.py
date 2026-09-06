"""Baseline: read the isotopes, name the source that fits, never abstain.

Buy the burden and the d13C trend, work out what single source would produce that pair, and report
it. This is the top-down inference the post-2007 debate is about, done without any of the checks the
debate is about: it has no way to notice that the sink can produce the same signal, and no way to
notice that several microbial sources produce indistinguishable ones.

It scores zero, on the axis that matters: the refusal rate is zero by construction. It also walks
straight into the confounded regime's trap, because a sink-driven rise looks exactly like a modest
increase in waste.
"""
import numpy as np

# Emission-weighted mean signature of the nominal inventory, per mil.
MEAN_SIGNATURE = -53.37
SIGNATURES = {"wetlands": -61.0, "ruminants": -65.0, "waste": -55.0,
              "fossil": -44.0, "biomass_burning": -25.0}


def attribute(problem, measure):
    burden = measure("burden")["burden_change_tg"]
    delta = measure("d13c")["delta13c_change_permil"]
    if burden <= 0:
        return {"abstain": False, "changed_sources": {}, "confidence": 0.2}

    # A step of size `burden / lifetime` in a single source with signature s shifts d13C towards s.
    # Invert that for s, then take the catalogue entry closest to it.
    implied = MEAN_SIGNATURE + delta * 60.0
    best = min(SIGNATURES, key=lambda name: abs(SIGNATURES[name] - implied))
    flags = {name: (name == best) for name in problem["source_catalogue"]}
    return {"abstain": False, "changed_sources": flags, "confidence": 0.6}
