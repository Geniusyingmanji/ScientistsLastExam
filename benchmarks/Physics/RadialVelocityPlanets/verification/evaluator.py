"""Find the planets in a radial-velocity time series, and only the planets.

The science. A star hosting planets wobbles, and the wobble shows up as a periodic Doppler shift.
Extracting which periods are real is the founding problem of radial-velocity exoplanet detection,
and its characteristic failure is not missing planets but claiming ones that are not there. The
literature carries retracted detections traced to stellar rotation, to activity cycles, and to
aliases of the observing cadence rather than to companions - which is why this task scores false
discovery as a first-class axis rather than folding it into an accuracy number.

The oracle is astropy's Lomb-Scargle periodogram, the standard tool for unevenly sampled
astronomical time series, so both the reference detector and its false-alarm probabilities come
from the community implementation rather than a reimplementation.

Three axes, reported separately and never averaged:

    mechanism   fraction of injected planets recovered, period within tolerance
    fdr         claimed signals corresponding to no planet, over all claims. Every system carries
                a stellar activity signal that is not a planet, and some carry no planet at all.
    refusal     in some systems the planet's period is aliased against the nightly cadence, so a
                second period fits the data equally well. Nothing in the series separates them and
                the honest answer is to decline.
"""

from __future__ import annotations

import math
import random

DIFFICULTY = 1

# Difficulty is how strong the planets are against the activity signal and the noise, and how
# many nights of data there are. A 10 m/s planet in 1 m/s noise is a peak you cannot miss; a
# 2 m/s planet under a 4 m/s activity signal is where real detections are argued about.
_LADDER = {
    1: {"nights": 120, "noise": 1.2, "planet_k": (4.0, 9.0), "activity_k": (1.5, 3.0),
        "count": 5, "seed": 20260812},
    2: {"nights": 90, "noise": 1.6, "planet_k": (2.5, 6.0), "activity_k": (2.5, 4.5),
        "count": 5, "seed": 20260813},
    3: {"nights": 70, "noise": 2.0, "planet_k": (1.8, 4.0), "activity_k": (3.0, 5.5),
        "count": 5, "seed": 20260814},
}

_SEALED_LADDER = {
    1: {"nights": 110, "noise": 1.3, "planet_k": (4.0, 9.0), "activity_k": (1.5, 3.0),
        "count": 3, "seed": 992101},
    2: {"nights": 85, "noise": 1.7, "planet_k": (2.5, 6.0), "activity_k": (2.5, 4.5),
        "count": 3, "seed": 992102},
    3: {"nights": 65, "noise": 2.1, "planet_k": (1.8, 4.0), "activity_k": (3.0, 5.5),
        "count": 3, "seed": 992103},
}

# A recovered period counts as the same planet if it lands within this fractional distance. Wider
# than instrument precision, narrower than the spacing between injected periods.
PERIOD_TOLERANCE = 0.05
PLANET_PERIODS = (7.3, 12.9, 23.7, 41.2, 68.5)
ROTATION_PERIODS = (15.4, 26.8, 34.1)

_CACHE: dict = {}


def _profile(ladder, level):
    level = int(level)
    if level not in ladder:
        raise ValueError(
            "difficulty %d has no entry; measure its anchor before adding one" % level
        )
    return ladder[level]


def _sample_times(rng, nights):
    """Nightly visits with gaps, which is what produces the one-day alias structure."""
    times = []
    day = 0.0
    for _ in range(nights):
        day += 1.0 + (2.0 if rng.random() < 0.25 else 0.0)  # weather and scheduling gaps
        times.append(day + rng.uniform(-0.12, 0.12))
    return times


def _alias_period(period):
    """The one-day alias of a period: 1/(1/P - 1) in days, the classic cadence confusion."""
    inverse = 1.0 / period - 1.0
    if abs(inverse) < 1e-6:
        return None
    return abs(1.0 / inverse)


def _draw_world(rng, profile, aliased: bool):
    n_planets = rng.choice([0, 1, 1, 2])
    periods = list(rng.sample(list(PLANET_PERIODS), max(n_planets, 1)))[:n_planets]
    planets = [{"period": p,
                "amplitude": rng.uniform(*profile["planet_k"]),
                "phase": rng.uniform(0, 2 * math.pi)} for p in periods]
    activity = {"period": rng.choice(ROTATION_PERIODS),
                "amplitude": rng.uniform(*profile["activity_k"]),
                "phase": rng.uniform(0, 2 * math.pi)}
    return {"planets": planets, "activity": activity, "aliased": aliased}


def _series(rng, world, profile):
    times = _sample_times(rng, profile["nights"])
    values, errors = [], []
    for t in times:
        v = 0.0
        for planet in world["planets"]:
            v += planet["amplitude"] * math.sin(2 * math.pi * t / planet["period"]
                                                + planet["phase"])
        a = world["activity"]
        v += a["amplitude"] * math.sin(2 * math.pi * t / a["period"] + a["phase"])
        sigma = profile["noise"]
        values.append(v + rng.gauss(0.0, sigma))
        errors.append(sigma)
    return times, values, errors


def _generate(profile, tag):
    key = "worlds::%s::%s" % (tag, sorted(profile.items()))
    if key in _CACHE:
        return _CACHE[key]
    rng = random.Random(profile["seed"])
    worlds = []
    for index in range(profile["count"]):
        # Every third system is made unidentifiable: its single planet sits at a period whose
        # one-day alias is also inside the searchable range, so two periods fit equally well.
        aliased = index % 3 == 2
        world = _draw_world(rng, profile, aliased)
        if aliased:
            # Force exactly one planet at a period with a live alias.
            period = 1.0 / (1.0 + 1.0 / 29.0)  # ~0.9667 d, alias at 29 d
            world["planets"] = [{"period": period,
                                 "amplitude": rng.uniform(*profile["planet_k"]),
                                 "phase": rng.uniform(0, 2 * math.pi)}]
        times, values, errors = _series(rng, world, profile)
        world.update({
            "key": "s%d_p%d%s" % (index, len(world["planets"]), "_alias" if aliased else ""),
            "times": times, "values": values, "errors": errors,
        })
        worlds.append(world)
    _CACHE[key] = tuple(worlds)
    return _CACHE[key]


def development_worlds():
    return _generate(_profile(_LADDER, DIFFICULTY), "dev")


def sealed_worlds():
    return _generate(_profile(_SEALED_LADDER, DIFFICULTY), "sealed")


def _observation(world):
    return {
        "times": list(world["times"]),
        "velocities": list(world["values"]),
        "uncertainties": list(world["errors"]),
        "period_tolerance": PERIOD_TOLERANCE,
        "note": ("the star has a rotation signal that is not a planet; the cadence is nightly, "
                 "so one-day aliases are present"),
    }


def _parse(submission):
    if not isinstance(submission, dict):
        return None, "expected a dict, got %s" % type(submission).__name__
    if submission.get("abstain"):
        return {"abstain": True}, ""
    planets = submission.get("planets")
    if planets is None:
        return None, "missing 'planets' (or set 'abstain': True)"
    out = []
    try:
        for item in planets:
            period = float(item["period"] if isinstance(item, dict) else item[0])
            if not math.isfinite(period) or period <= 0:
                return None, "planet period must be positive and finite, got %r" % period
            out.append(period)
    except (TypeError, ValueError, KeyError, IndexError):
        return None, "planets must be an iterable of {'period': ...} or (period, ...) items"
    if len(out) > 6:
        return None, "claimed %d planets; the search range holds at most 6" % len(out)
    return {"abstain": False, "periods": out}, ""


def _match(claimed, truth):
    """Greedy one-to-one match within the fractional tolerance."""
    remaining = list(truth)
    hits = []
    for period in claimed:
        best, best_err = None, None
        for candidate in remaining:
            err = abs(period - candidate) / candidate
            if err <= PERIOD_TOLERANCE and (best_err is None or err < best_err):
                best, best_err = candidate, err
        if best is not None:
            remaining.remove(best)
            hits.append(period)
    return hits, remaining


def _score_world(world, parsed):
    truth = [p["period"] for p in world["planets"]]
    hits, missed = _match(parsed["periods"], truth)
    false_claims = len(parsed["periods"]) - len(hits)
    recovery = len(hits) / len(truth) if truth else 1.0
    return {
        "mechanism": recovery,
        "recovered": len(hits),
        "injected": len(truth),
        "claimed": len(parsed["periods"]),
        "false_claims": false_claims,
        # Classic false-discovery rate: of everything claimed, how much was not there. Undefined
        # when nothing was claimed, which is reported rather than scored as zero.
        "false_discovery_rate": (false_claims / len(parsed["periods"])
                                 if parsed["periods"] else None),
        "missed": len(missed),
    }


def _score_split(detect, worlds):
    rows = []
    for world in worlds:
        try:
            raw = detect(_observation(world))
        except Exception as exc:  # noqa: BLE001 - candidate faults are scored, not raised
            rows.append({"key": world["key"], "valid": False,
                         "reason": "raised: %s" % type(exc).__name__})
            continue
        parsed, why = _parse(raw)
        if parsed is None:
            rows.append({"key": world["key"], "valid": False, "reason": why})
            continue
        determined = not world["aliased"]
        if parsed["abstain"]:
            rows.append({"key": world["key"], "valid": True, "abstained": True,
                         "determined": determined, "mechanism": 0.0,
                         "correct_refusal": not determined})
            continue
        metrics = _score_world(world, parsed)
        metrics.update({"key": world["key"], "valid": True, "abstained": False,
                        "determined": determined, "correct_refusal": False})
        rows.append(metrics)

    valid = [r for r in rows if r["valid"]]
    determined = [r for r in valid if r["determined"]]
    undetermined = [r for r in valid if not r["determined"]]
    fdrs = [r["false_discovery_rate"] for r in valid
            if not r.get("abstained") and r.get("false_discovery_rate") is not None]
    return {
        "rows": rows,
        "valid_count": len(valid),
        "world_count": len(worlds),
        "mechanism": (sum(r["mechanism"] for r in determined) / len(determined)
                      if determined else 0.0),
        "false_discovery_rate": (sum(fdrs) / len(fdrs)) if fdrs else None,
        "correct_refusal_rate": ((sum(1 for r in undetermined if r["correct_refusal"])
                                  / len(undetermined)) if undetermined else None),
        "unwarranted_refusal_rate": (
            sum(1 for r in determined if r.get("abstained")) / len(determined)
            if determined else 0.0),
    }


def evaluate(detect_planets) -> dict:
    development = _score_split(detect_planets, development_worlds())
    valid = development["valid_count"] == development["world_count"]
    result = {
        "combined_score": float(development["mechanism"]) if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "development_mechanism_score": development["mechanism"],
        "development_false_discovery_rate": development["false_discovery_rate"],
        "development_correct_refusal_rate": development["correct_refusal_rate"],
        "development_unwarranted_refusal_rate": development["unwarranted_refusal_rate"],
        "per_instance": development["rows"],
        "difficulty": DIFFICULTY,
    }
    if valid:
        sealed = _score_split(detect_planets, sealed_worlds())
        result.update({
            "robustness_score": float(sealed["mechanism"]),
            "heldout_mechanism_score": sealed["mechanism"],
            "heldout_false_discovery_rate": sealed["false_discovery_rate"],
            "heldout_correct_refusal_rate": sealed["correct_refusal_rate"],
            "sealed_per_instance": sealed["rows"],
        })
    else:
        result["robustness_score"] = 0.0
    return result
