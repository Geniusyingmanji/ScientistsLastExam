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

from box import SOURCE_ORDER
from instruments import BUDGET, COSTS, Network
from worlds import CHANGE_YEAR, WINDOW_YEARS, answerable, build

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
