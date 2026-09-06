"""Frozen two-box model of atmospheric methane and its carbon isotope ratio.

The physics kept is the part that makes attribution hard and the part the field is arguing about.
Methane's burden and its d13C obey

    d[CH4]/dt   = sum_i E_i - k * [OH] * [CH4]
    d(d13C)/dt  = ( sum_i E_i (delta_i - d13C) ) / [CH4]  -  k * [OH] * eps

where `eps` is the kinetic isotope effect of the OH sink: the sink preferentially removes the light
isotopologue, so it *raises* d13C. That single term is why the attribution problem is open. A
decrease in the sink and an increase in a light (13C-depleted) source both push the burden up and
d13C down, and no amount of measuring [CH4] and d13C alone separates them.

Source signatures are the second difficulty. Wetlands, ruminants and waste are all microbial and
their d13C ranges overlap; fossil methane is heavier but its range overlaps biomass burning. The
published signature maps carry uncertainties large enough that "which microbial source" is often
not answerable from isotopes at all.

Both are modelled explicitly rather than as noise, because they are the two reasons a real
attribution fails.
"""
from __future__ import annotations

import numpy as np

# Tg CH4 per year, and per-mil d13C signatures. Ranges rather than points: the spread is the
# published uncertainty on the signature, and it is what makes the microbial sources confusable.
SOURCES = {
    "wetlands":        {"signature": -61.0, "spread": 6.0, "nominal": 180.0},
    "ruminants":       {"signature": -65.0, "spread": 5.0, "nominal": 110.0},
    "waste":           {"signature": -55.0, "spread": 7.0, "nominal": 75.0},
    "fossil":          {"signature": -44.0, "spread": 4.0, "nominal": 175.0},
    "biomass_burning": {"signature": -25.0, "spread": 5.0, "nominal": 40.0},
}
SOURCE_ORDER = tuple(SOURCES)

MICROBIAL = frozenset({"wetlands", "ruminants", "waste"})
# The *total* sink fractionation, not the OH one alone. OH by itself is about 3.9 per mil; the soil
# and chlorine sinks fractionate more strongly, and the number that closes the observed budget is
# larger. It is not a free parameter here - the nominal emissions above carry an emission-weighted
# signature of -53.4 per mil, and the observed atmospheric value is -47.2, so the effective
# fractionation is 6.2, which is inside the 6-7 the literature gives for the total sink. Setting it
# to the OH-only 3.9 leaves the model drifting three per mil over twenty years, which is how this
# was caught.
KIE_PERMIL = 6.2
LIFETIME_YEARS = 9.1      # total methane lifetime, years
BURDEN_PER_PPB = 2.75     # Tg CH4 per ppb


def integrate(emissions, oh_scale, years, burden0=5278.0, delta0=-47.2, steps_per_year=12):
    """Burden in Tg and d13C in per mil, month by month.

    `emissions` is a (years, n_sources) array in Tg/yr; `oh_scale` multiplies the sink.
    """
    emissions = np.asarray(emissions, dtype=float)
    oh_scale = np.asarray(oh_scale, dtype=float)
    signatures = np.array([SOURCES[name]["signature"] for name in SOURCE_ORDER])
    burden, delta = burden0, delta0
    dt = 1.0 / steps_per_year
    burdens, deltas = [], []
    for year in range(years):
        annual = emissions[year]
        sink_rate = oh_scale[year] / LIFETIME_YEARS
        for _ in range(steps_per_year):
            total_emission = float(annual.sum())
            loss = sink_rate * burden
            # The isotope budget: sources pull d13C toward their own signature, and the sink pushes
            # it up because it removes the light isotopologue faster.
            source_term = float((annual * (signatures - delta)).sum()) / max(burden, 1e-9)
            sink_term = sink_rate * KIE_PERMIL
            burden = burden + dt * (total_emission - loss)
            delta = delta + dt * (source_term + sink_term)
        burdens.append(burden)
        deltas.append(delta)
    return np.array(burdens), np.array(deltas)
