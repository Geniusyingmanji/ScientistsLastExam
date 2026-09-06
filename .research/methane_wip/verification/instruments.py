"""What can be measured, what it costs, and what each thing can and cannot settle.

The menu is the task. Burden and d13C are cheap and, on their own, decide nothing: a sink change is
reproduced by a source change to within the noise. Everything else is a way of buying one extra
dimension, and none of them buys the sink.

  `burden`      the methane burden trend. Cheap. Says how much extra methane, not whose.
  `d13c`        the carbon isotope trend. Cheap. Says how light the extra methane is, which is a
                weighted average over sources and is also moved by the sink.
  `ethane`      the ethane-to-methane ratio. Fossil methane is co-emitted with ethane and microbial
                methane is not, so this separates fossil from everything microbial. It does not
                separate microbial sources from each other.
  `radiocarbon` 14CH4. Fossil methane is radiocarbon-dead; everything else is modern. Same cut as
                ethane by a different route, and expensive.
  `inventory`   a noisy bottom-up estimate for one named sector. Buying it for the wrong sector
                buys nothing.
  `oh_proxy`    a sink constraint. It is on the menu, it is expensive, and in the confounded world
                it returns an uninformative answer - which is the real state of the methyl
                chloroform record now that its emissions have ceased and the constraint it provided
                has decayed with them.

The last one is the point. A searcher that spends everything on tracers and never asks what
constrains the sink will attribute a sink change to sources with high confidence, which is the
failure this task is built to catch.
"""
from __future__ import annotations

import numpy as np

from box import MICROBIAL, SOURCES, SOURCE_ORDER

COSTS = {"burden": 1, "d13c": 1, "ethane": 3, "radiocarbon": 5, "inventory": 3, "oh_proxy": 6}
BUDGET = 12

BURDEN_SIGMA = 5.0
DELTA_SIGMA = 0.02
# Tightened from 0.004 and 0.012, which left the tracers at signal-to-noise below two on the very
# cases they exist to settle. These are the precisions that make an affordable tracer decisive when
# the source it identifies has moved, which is the premise of the answerable regime.
# In Tg of the tracer species per year, matched to what the trends resolve.
ETHANE_SIGMA = 0.35
RADIOCARBON_SIGMA = 4.0
INVENTORY_RELATIVE_SIGMA = 0.08

# Ethane co-emitted per unit methane, by sector. Fossil is the only large one.
ETHANE_RATIO = {"wetlands": 0.0, "ruminants": 0.0, "waste": 0.002,
                "fossil": 0.075, "biomass_burning": 0.012}
# Fraction of the emitted carbon that is radiocarbon-modern.
MODERN_FRACTION = {"wetlands": 1.0, "ruminants": 1.0, "waste": 0.9,
                   "fossil": 0.0, "biomass_burning": 1.0}


class Network:
    """Charges each measurement against the observing budget."""

    def __init__(self, case, budget=BUDGET):
        self._case = case
        self._remaining = int(budget)
        self._calls = 0
        self._rng = np.random.default_rng(case["seed"] & 0xFFFFFFFF)

    @property
    def remaining(self):
        return self._remaining

    def measure(self, name, sector=None):
        self._calls += 1
        if self._calls > 32:
            raise ValueError("too many measurement calls")
        if name not in COSTS:
            raise ValueError("unknown measurement %r" % (name,))
        cost = COSTS[name]
        if cost > self._remaining:
            raise ValueError("measurement costs more than the remaining budget")
        self._remaining -= cost
        return {"measurement": name, "remaining_budget": self._remaining,
                **self._value(name, sector)}

    def _value(self, name, sector):
        case = self._case
        early, late = case["emissions"][0], case["emissions"][-1]
        if name == "burden":
            change = float(case["burden"][-1] - case["burden"][9])
            return {"burden_change_tg": change + float(self._rng.normal(0.0, BURDEN_SIGMA)),
                    "uncertainty": BURDEN_SIGMA}
        if name == "d13c":
            change = float(case["delta"][-1] - case["delta"][9])
            return {"delta13c_change_permil": change + float(self._rng.normal(0.0, DELTA_SIGMA)),
                    "uncertainty": DELTA_SIGMA}
        if name == "ethane":
            # The change in *ethane emission*, which is what an atmospheric ethane trend reflects.
            # The first version reported the change in the mean ethane-to-methane ratio, which
            # moves whenever any source changes because the denominator does - it responded to
            # microbial changes almost as strongly as to fossil ones and separated nothing.
            ratios = np.array([ETHANE_RATIO[s] for s in SOURCE_ORDER])
            change = float(((late - early) * ratios).sum())
            return {"ethane_emission_change_tg": change + float(
                self._rng.normal(0.0, ETHANE_SIGMA)), "uncertainty": ETHANE_SIGMA}
        if name == "radiocarbon":
            # The change in radiocarbon-dead emission. Fossil is the only dead source, so this is a
            # fossil detector and nothing else.
            dead = np.array([1.0 - MODERN_FRACTION[s] for s in SOURCE_ORDER])
            change = float(((late - early) * dead).sum())
            return {"fossil_emission_change_tg": change + float(
                self._rng.normal(0.0, RADIOCARBON_SIGMA)), "uncertainty": RADIOCARBON_SIGMA}
        if name == "inventory":
            if sector not in SOURCE_ORDER:
                raise ValueError("inventory needs a sector from the catalogue")
            index = SOURCE_ORDER.index(sector)
            true_change = float(late[index] - early[index])
            scale = INVENTORY_RELATIVE_SIGMA * max(float(early[index]), 1.0)
            return {"sector": sector,
                    "emission_change_tg": true_change + float(self._rng.normal(0.0, scale)),
                    "uncertainty": scale}
        # oh_proxy
        if case["regime"] == "sink_confounded":
            # The constraint that used to exist has decayed away with the tracer that provided it.
            return {"oh_change_fraction": None, "uncertainty": None,
                    "note": "proxy record is uninformative over this window"}
        true_change = float(case["oh_scale"][-1] - case["oh_scale"][0])
        return {"oh_change_fraction": true_change + float(self._rng.normal(0.0, 0.004)),
                "uncertainty": 0.004}
