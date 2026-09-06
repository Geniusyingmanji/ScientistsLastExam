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
from instruments import INVENTORY_RELATIVE_SIGMA

WINDOW_YEARS = 20
CHANGE_YEAR = 10


def _nominal():
    return np.array([SOURCES[name]["nominal"] for name in SOURCE_ORDER], dtype=float)


def build(seed, count):
    rng = np.random.default_rng(seed)
    cases = []
    for index in range(count):
        regime = ("tracer_identifiable", "inventory_identifiable",
                  "sink_confounded", "microbial_overlap")[index % 4]
        emissions = np.tile(_nominal(), (WINDOW_YEARS, 1))
        oh_scale = np.ones(WINDOW_YEARS)
        changed = set()
        if regime == "tracer_identifiable":
            # Fossil and biomass burning both leave a tracer an affordable measurement can see:
            # fossil co-emits ethane and is radiocarbon-dead, biomass burning is isotopically heavy
            # and co-emits some ethane.
            name = str(rng.choice(["fossil", "biomass_burning"]))
            emissions[CHANGE_YEAR:, SOURCE_ORDER.index(name)] += float(rng.uniform(20.0, 35.0))
            changed.add(name)
        elif regime == "inventory_identifiable":
            # One microbial source, and a change large enough that its sector inventory resolves it.
            # Scaled to the sector's own inventory uncertainty, like the overlap regime, so the
            # two are separated by resolvability rather than by absolute size: 2.5 to 4 sigma here
            # against 0.8 to 1.4 there. A flat 30-45 Tg left the two touching at 2.1 against 2.2.
            name = str(rng.choice(sorted(MICROBIAL)))
            sigma = INVENTORY_RELATIVE_SIGMA * SOURCES[name]["nominal"]
            emissions[CHANGE_YEAR:, SOURCE_ORDER.index(name)] += float(
                rng.uniform(3.5, 5.0)) * sigma
            changed.add(name)
        elif regime == "sink_confounded":
            # The whole change is in the sink and *no source moved*. Measured: a pure source change
            # reproduces this trajectory to within observational noise, reduced misfit 0.00, so the
            # burden and d13C records alone say nothing against it. The sink proxy is uninformative
            # here, which is the state of the methyl chloroform constraint now that its emissions
            # have ceased.
            oh_scale[CHANGE_YEAR:] = float(rng.uniform(0.955, 0.980))
        else:
            # Two microbial sources, each moving by less than its inventory resolves, with
            # overlapping d13C ranges. The total is comparable to the single-source case.
            # Each change is scaled to the sector's own inventory uncertainty rather than set in
            # absolute terms. A flat 10-18 Tg looked small but is three sigma for waste, whose
            # nominal emission is 75 Tg - one member of the pair was resolvable and the regime was
            # not what it claimed.
            pair = list(rng.choice(sorted(MICROBIAL), size=2, replace=False))
            for name in pair:
                index_of = SOURCE_ORDER.index(str(name))
                sigma = INVENTORY_RELATIVE_SIGMA * SOURCES[str(name)]["nominal"]
                emissions[CHANGE_YEAR:, index_of] += float(rng.uniform(0.8, 1.5)) * sigma
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
    return case["regime"] in ("tracer_identifiable", "inventory_identifiable")
