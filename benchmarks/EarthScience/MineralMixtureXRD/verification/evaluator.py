"""Deterministic powder-diffraction mixture oracle.

A synthetic rock reports its powder pattern: a coarse scan is free, and slow scans
of narrow windows cost budget. The library of twelve minerals is public; the hidden
world holds two to four of them with weight fractions, sometimes an amorphous hump
that must not trigger refusal, and sometimes an unknown crystalline phase outside
the library whose sharp peaks no library fit can absorb — that world must be refused
rather than named as the nearest library minerals.
"""

from __future__ import annotations

import math

import numpy as np

DIFFICULTY = 1

TWO_THETA_GRID = np.arange(10.0, 80.01, 0.05)
SCAN_COST = 1
BUDGET_UNITS = 4
MAX_PHASES = 4

MINERAL_LIBRARY = {
    # mineral: list of (two_theta, relative_intensity)
    "quartz": [(20.85, 100.0), (26.64, 80.0), (36.54, 40.0), (39.47, 30.0),
               (40.30, 25.0), (50.13, 30.0)],
    "calcite": [(23.02, 35.0), (29.40, 100.0), (35.96, 55.0), (39.40, 45.0),
                (43.15, 40.0), (47.50, 30.0)],
    "dolomite": [(30.98, 100.0), (33.52, 40.0), (37.38, 35.0), (41.12, 30.0),
                 (45.02, 25.0)],
    "feldspar": [(13.70, 25.0), (21.05, 45.0), (22.45, 100.0), (24.30, 30.0),
                 (27.50, 55.0), (36.60, 20.0)],
    "mica": [(12.60, 100.0), (17.70, 45.0), (26.85, 60.0), (35.10, 25.0)],
    "halite": [(27.35, 30.0), (31.70, 100.0), (45.45, 55.0), (53.80, 20.0)],
    "gypsum": [(12.95, 100.0), (20.75, 50.0), (23.40, 30.0), (29.10, 60.0),
               (31.10, 40.0)],
    "hematite": [(24.15, 35.0), (33.15, 100.0), (35.65, 80.0), (40.90, 45.0),
                 (49.48, 35.0)],
    "rutile": [(27.45, 100.0), (36.09, 60.0), (39.19, 40.0), (41.23, 30.0),
               (54.32, 25.0)],
    "zircon": [(20.05, 60.0), (26.95, 100.0), (33.60, 30.0), (36.85, 35.0)],
    "amphibole": [(11.35, 70.0), (18.20, 30.0), (28.60, 100.0), (30.40, 45.0),
                  (32.85, 40.0)],
    "pyroxene": [(14.20, 30.0), (25.30, 40.0), (27.85, 30.0), (29.85, 100.0),
                 (31.05, 45.0), (35.65, 30.0)],
}
UNKNOWN_PHASE_PEAKS = [(19.35, 90.0), (37.90, 70.0), (44.95, 55.0), (58.60, 35.0),
                       (64.10, 30.0)]
PEAK_WIDTH = 0.08

_BASE_DEVELOPMENT_SPECS = (
    (36011, "supported", False), (36017, "supported", False),
    (36023, "supported", False), (36029, "supported", True),
    (36031, "supported", True), (36037, "supported", False),
    (36041, "unknown_phase", False), (36047, "unknown_phase", True),
)
HELDOUT_SPECS = (
    (37007, "supported", False), (37013, "supported", True),
    (37019, "supported", False), (37023, "unknown_phase", False),
)


def _world(spec):
    seed, kind, amorphous = spec
    rng = np.random.default_rng(int(seed))
    count = int(rng.integers(2, MAX_PHASES + 1))
    names = sorted(rng.choice(sorted(MINERAL_LIBRARY), size=count, replace=False))
    weights = rng.dirichlet(np.full(count, 1.5))
    return {"seed": int(seed), "kind": kind, "amorphous": amorphous,
            "phases": {name: float(weight) for name, weight in zip(names, weights)},
            "amorphous_fraction": (float(rng.uniform(0.2, 0.35))
                                   if amorphous else 0.0)}


def _peak(profile, center, intensity, width):
    return intensity * np.exp(-0.5 * ((TWO_THETA_GRID - center) / width) ** 2)


def _crystalline_pattern(world):
    pattern = np.zeros_like(TWO_THETA_GRID)
    for name, weight in world["phases"].items():
        scale = weight * (1.0 - world["amorphous_fraction"])
        for center, intensity in MINERAL_LIBRARY[name]:
            pattern += _peak(pattern, center, scale * intensity,
                            PEAK_WIDTH * (1.0 + 0.05 * (hash(center) % 3)))
    if world["kind"] == "unknown_phase":
        for center, intensity in UNKNOWN_PHASE_PEAKS:
            pattern += _peak(pattern, center,
                             0.6 * (1.0 - world["amorphous_fraction"]) * intensity,
                             PEAK_WIDTH)
    return pattern


def _amorphous_pattern(world):
    if world["amorphous_fraction"] <= 0:
        return np.zeros_like(TWO_THETA_GRID)
    return 30.0 * world["amorphous_fraction"] * np.exp(
        -0.5 * ((TWO_THETA_GRID - 24.0) / 9.0) ** 2)


def problem_statement(world):
    del world
    return {
        "mineral_library": {name: [list(peak) for peak in peaks]
                            for name, peaks in MINERAL_LIBRARY.items()},
        "two_theta_range_deg": [10.0, 80.0],
        "grid_step_deg": 0.05,
        "peak_shape": "Gaussian, width about 0.08 degrees with per-peak jitter",
        "coarse_noise": 0.08,
        "slow_noise": 0.025,
        "slow_window_deg": 15.0,
        "scan_cost": SCAN_COST,
        "budget_units": BUDGET_UNITS,
        "convention": (
            "claimed weight fractions are relative to the crystalline portion; an "
            "amorphous hump is a distractor and must NOT trigger refusal, while a "
            "sharp unknown crystalline phase must"
        ),
    }


class _Diffractometer:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        truth = _crystalline_pattern(world) + _amorphous_pattern(world)
        rng = np.random.default_rng(world["seed"] + 41)
        self._slow_noise = rng.normal(0.0, 0.025, TWO_THETA_GRID.shape)
        self._coarse_seed = world["seed"] + 97

    def _noisy(self, rng, scale):
        clean = _crystalline_pattern(self.world) + _amorphous_pattern(self.world)
        sigma = scale * float(clean.max()) + 0.01
        return np.maximum(clean + rng.normal(0.0, sigma, clean.shape), 0.0)

    def coarse_scan(self):
        rng = np.random.default_rng(self._coarse_seed)
        return {"two_theta_deg": TWO_THETA_GRID.copy(),
                "intensity": self._noisy(rng, 0.08), "budget_cost": 0}

    def slow_scan(self, center_deg, width_deg=15.0):
        try:
            center = float(center_deg)
            width = float(width_deg)
            if not 10.0 <= center <= 80.0 or width <= 0 or width > 15.0 + 1e-9:
                self.violated = True
                raise ValueError("slow-scan window outside allowed bounds")
            if self.used + SCAN_COST > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("scan budget exceeded")
            self.used += SCAN_COST
            self.calls += 1
            mask = np.abs(TWO_THETA_GRID - center) <= width / 2.0
            rng = np.random.default_rng(self.world["seed"] + 313 * int(center * 10)
                                        + self.calls)
            pattern = self._noisy(rng, 0.025)
            return {"two_theta_deg": TWO_THETA_GRID[mask],
                    "intensity": pattern[mask], "budget_cost": SCAN_COST}
        except Exception:
            self.violated = True
            raise


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain")
    if not isinstance(abstain, (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    if bool(abstain):
        if submission.get("minerals") or submission.get("fractions"):
            raise ValueError("abstention requires an empty composition claim")
        return [], {}, confidence, True
    minerals = submission.get("minerals")
    if not isinstance(minerals, (list, tuple)) or \
            any(m not in MINERAL_LIBRARY for m in minerals):
        raise ValueError("minerals must name library species")
    if len(set(minerals)) != len(minerals) or not minerals:
        raise ValueError("minerals must be a nonempty unique list")
    fractions = submission.get("fractions")
    if not isinstance(fractions, dict) or set(fractions) != set(minerals):
        raise ValueError("fractions must cover exactly the claimed minerals")
    values = np.asarray([float(fractions[m]) for m in minerals])
    if np.any(~np.isfinite(values)) or np.any(values < 0) or \
            not np.isclose(values.sum(), 1.0, atol=1e-6):
        raise ValueError("fractions must be nonnegative and sum to one")
    return list(minerals), {m: float(v) for m, v in zip(minerals, values)}, confidence, False


def _mechanism_score(minerals, fractions, world):
    truth = world["phases"]
    claimed = set(minerals)
    true = set(truth)
    intersection = len(claimed & true)
    precision = intersection / len(claimed) if claimed else 0.0
    recall = intersection / len(true) if true else 0.0
    f1 = 2 * precision * recall / (precision + recall) if intersection else 0.0
    log_errors = [abs(math.log(max(fractions.get(m, 1e-6), 1e-6) / max(w, 1e-6)))
                  for m, w in truth.items()]
    abundance = math.exp(-2.5 * float(np.mean(log_errors)))
    return float(0.7 * f1 + 0.3 * abundance)


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "false_discovery": False,
            "correct_refusal": False, "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    instrument = _Diffractometer(world)
    try:
        submission = candidate(problem_statement(world), instrument.coarse_scan,
                               instrument.slow_scan, BUDGET_UNITS)
        minerals, fractions, confidence, abstain = _validate(submission)
        if instrument.violated:
            raise ValueError("diffractometer contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            mechanism = _mechanism_score(minerals, fractions, world)
        elif supported:
            mechanism = 0.0
        else:
            mechanism = 1.0 if abstain else 0.0
        target = 1.0 if (supported != abstain or (not supported and abstain)) else 0.0
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": mechanism,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target) ** 2,
                    "budget_used": instrument.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "supported"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "supported"]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {
        "normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
        "raw": raw,
        "valid_count": sum(r["valid"] for r in rows),
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(identify_minerals):
    development = [_evaluate_world(identify_minerals, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(identify_minerals, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "per_world": development + heldout,
    }
