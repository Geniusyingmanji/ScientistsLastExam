"""Hidden oracle for MethaneSourceAttribution.

Atmospheric methane resumed growing in 2007 and its d13C has trended lighter since. What drove it is
not settled: isotopic evidence has been read as a largely microbial source, and that reading has
been challenged on the grounds of spatial variability in source signatures and open questions in the
sinks. The field's own summary is that source signatures remain poorly constrained.

Both objections are the task.

**The sink is the first one.** OH removes the light isotopologue faster, so it raises d13C. A weaker
sink and a lighter source both push the burden up and d13C down, and measured here, a pure source
change reproduces a sink-only trajectory to within observational noise - reduced misfit 0.00 against
5 Tg on the burden and 0.02 per mil on d13C. The burden and isotope records alone say *nothing*
against attributing a sink change entirely to sources.

**Overlapping signatures are the second.** Wetlands, ruminants and waste are all microbial and their
published d13C ranges overlap. Ethane and radiocarbon separate fossil from everything else and do
not separate microbial sources from each other.

Four regimes, two answerable, and a budget that cannot buy every measurement. The two refusal
regimes fail differently: one has an unmeasured dimension, the other an unresolvable one.

The confounded regime carries a trap that the construction produced rather than received. Its burden
rises while d13C falls only slightly, and the source that explains that is one slightly lighter than
the emission-weighted mean - which is waste. A searcher that buys the isotopes and the tracers
concludes "waste increased", confidently and wrongly. The way out is to buy the waste inventory,
find no change, and treat the contradiction between the top-down inference and the bottom-up number
as the reason to abstain. That contradiction is the real methane-budget problem.

Three axes, reported separately and never averaged, with denominators, plus a coverage counter.
"""
from __future__ import annotations

import math

import numpy as np

# The box model, the world and the instrument menu are inlined rather than imported from siblings.
# The trusted driver loads this file by path, not as a package, so `from box import ...` resolves
# against the harness's sys.path and not against this directory. verification/box.py, worlds.py and
# instruments.py remain the readable statements of the same model and the task's tests check they
# agree. Names were checked against this module's own before inlining: a previous task in this
# repository had its expression evaluator silently rebound by a top-level `evaluate` this way.


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

DIFFICULTY = 1

CASE_COUNT = 32
DEV_SEED = 20260906


def _public_case(case, budget):
    return {
        "case_id": case["case_id"],
        "source_catalogue": list(SOURCE_ORDER),
        "measurement_costs": dict(COSTS),
        "observation_budget": budget,
        "window_years": WINDOW_YEARS,
        "change_year": CHANGE_YEAR,
        # Public, because hiding it would make the task about guessing which sources are microbial
        # rather than about what to do when several are.
        "microbial_sources": ["wetlands", "ruminants", "waste"],
        "note": "the sink can move too, and it is not one of the sources",
    }


def _read_report(value):
    if not isinstance(value, dict):
        raise ValueError("a report is a mapping")
    abstain = value.get("abstain")
    if not isinstance(abstain, bool):
        raise ValueError("'abstain' must be a boolean")
    confidence = value.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("'confidence' must be a number")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("'confidence' must lie in [0, 1]")
    claimed = set()
    if not abstain:
        sources = value.get("changed_sources")
        if not isinstance(sources, dict):
            raise ValueError("'changed_sources' must be a mapping when not abstaining")
        for name, flag in sources.items():
            if name not in SOURCE_ORDER:
                raise ValueError("unknown source %r" % (name,))
            if not isinstance(flag, bool):
                raise ValueError("source flags must be booleans")
            if flag:
                claimed.add(name)
    return abstain, claimed, confidence


def evaluate(attribute, seed=DEV_SEED, count=CASE_COUNT, budget=BUDGET):
    cases = build(seed, count)
    rows = []
    for case in cases:
        record = {"case_id": case["case_id"], "regime": case["regime"],
                  "answerable": answerable(case)}
        try:
            network = Network(case, budget)
            abstain, claimed, confidence = _read_report(
                attribute(_public_case(case, budget), network.measure))
            truth = set(case["changed"])
            record.update({
                "valid": True, "abstained": abstain, "confidence": confidence,
                "budget_used": budget - network.remaining,
                "claimed": sorted(claimed),
                "recovered": bool(not abstain and claimed == truth and answerable(case)),
                "false_claims": len(claimed - truth),
                "claims": len(claimed),
            })
        except Exception as exc:  # noqa: BLE001 - a bad report scores zero, it does not crash this
            record.update({
                "valid": False, "reason": "%s: %s" % (type(exc).__name__, exc),
                "abstained": False, "confidence": 0.0, "budget_used": 0, "claimed": [],
                "recovered": False, "false_claims": 0, "claims": 0,
            })
        rows.append(record)

    findable = [r for r in rows if r["answerable"]]
    unfindable = [r for r in rows if not r["answerable"]]
    recovery = (sum(1 for r in findable if r["recovered"]) / len(findable)) if findable else 0.0
    claims = sum(r["claims"] for r in rows)
    false_claims = sum(r["false_claims"] for r in rows)
    false_discovery = (false_claims / claims) if claims else 0.0
    refusal = (sum(1 for r in unfindable if r["abstained"]) / len(unfindable)) if unfindable else 0.0
    coverage = sum(1 for r in rows if not r["abstained"]) / len(rows) if rows else 0.0

    combined = recovery * (1.0 - false_discovery) * refusal
    return {
        "combined_score": float(max(0.0, combined)),
        "valid": 1.0 if any(r["valid"] for r in rows) else 0.0,
        "feasibility_rate": sum(1 for r in rows if r["valid"]) / len(rows),
        "raw_score": float(combined),
        "mechanism_score": float(recovery),
        "mechanism_score_denominator": len(findable),
        "false_discovery_rate": float(false_discovery),
        "false_discovery_denominator": claims,
        "correct_refusal_rate": float(refusal),
        "correct_refusal_denominator": len(unfindable),
        "discovery_coverage": float(coverage),
        "per_case": rows,
    }
