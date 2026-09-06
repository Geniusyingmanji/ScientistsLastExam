"""What actually changed, and whether the affordable measurements can tell.

The renewed growth of atmospheric methane after 2007 came with d13C trending lighter, and the field
has not settled what drove it: isotopic evidence has been read as a largely microbial source, and
that reading has been challenged on the grounds of spatial variability in source signatures and open
questions in the sinks. Both objections are modelled here rather than described.

  * `attributable` - one source changed, and a tracer the budget can afford pins which. Ethane is
    co-emitted by fossil methane and not by microbial methane; radiocarbon separates fossil (which
    is 14C-dead) from everything modern.
  * `sink_confounded` - part of the change is in the OH sink. Burden and d13C alone cannot separate
    a weaker sink from a lighter source, and in this world the sink proxy is uninformative, which is
    the actual state of the methyl-chloroform record after its emissions ceased. Abstention is
    correct.
  * `microbial_overlap` - two microbial sources moved, and their published d13C ranges overlap by
    more than the change. Ethane and radiocarbon both say "not fossil" and neither says which
    microbial source. Naming one is a claim the data cannot support.
"""
from __future__ import annotations

import numpy as np

from box import MICROBIAL, SOURCES, SOURCE_ORDER, integrate

WINDOW_YEARS = 20
CHANGE_YEAR = 10


def _nominal():
    return np.array([SOURCES[name]["nominal"] for name in SOURCE_ORDER], dtype=float)


def build(seed, count):
    rng = np.random.default_rng(seed)
    cases = []
    for index in range(count):
        regime = ("attributable", "sink_confounded", "microbial_overlap")[index % 3]
        emissions = np.tile(_nominal(), (WINDOW_YEARS, 1))
        oh_scale = np.ones(WINDOW_YEARS)
        changed = set()
        if regime == "attributable":
            name = str(rng.choice(["fossil", "biomass_burning", "wetlands"]))
            step = float(rng.uniform(18.0, 35.0))
            emissions[CHANGE_YEAR:, SOURCE_ORDER.index(name)] += step
            changed.add(name)
        elif regime == "sink_confounded":
            # The whole change is in the sink and *no source moved*. Measured: a pure source change
            # reproduces this trajectory to within observational noise, reduced misfit 0.00, so the
            # burden and d13C records alone say nothing against it. Naming any source here is a
            # false discovery, and a searcher can only know that by noticing it has no constraint
            # on the sink - not by looking at the fit.
            oh_scale[CHANGE_YEAR:] = float(rng.uniform(0.955, 0.980))
        else:
            pair = list(rng.choice(sorted(MICROBIAL), size=2, replace=False))
            for name in pair:
                emissions[CHANGE_YEAR:, SOURCE_ORDER.index(str(name))] += float(
                    rng.uniform(10.0, 20.0))
                changed.add(str(name))
        burden, delta = integrate(emissions, oh_scale, WINDOW_YEARS)
        cases.append({
            "case_id": "era%03d" % index,
            "regime": regime,
            "emissions": emissions,
            "oh_scale": oh_scale,
            "changed": frozenset(changed),
            "burden": burden,
            "delta": delta,
            "seed": int(rng.integers(0, 2 ** 31 - 1)),
        })
    return cases


def answerable(case):
    return case["regime"] == "attributable"
