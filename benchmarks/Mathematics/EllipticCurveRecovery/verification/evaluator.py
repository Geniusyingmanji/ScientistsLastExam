"""Deterministic elliptic-curve coefficient oracle.

A hidden curve y^2 = x^3 + ax + b over the rationals answers point counts modulo
chosen primes: for each p the oracle returns #E(F_p) exactly. Small primes pin
(a mod p, b mod p); the Chinese remainder theorem lifts them to the bounded
integer window. Two worlds break the elliptic premise — a singular cubic and a
genus-two quartic — whose point counts no pair (a, b) can reproduce, and those
worlds must be refused rather than fitted.
"""

from __future__ import annotations

import math

import numpy as np

PRIME_LIST = (11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
              73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139,
              149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199, 211,
              223, 227, 229, 233, 239, 241, 251, 257, 263, 269, 271, 277, 281,
              283, 293, 307, 311, 313, 317, 331, 337, 347, 349, 353, 359, 367,
              373, 379, 383, 389, 397, 401, 409, 419, 421, 431, 433, 439, 443,
              449, 457, 461, 463, 467, 479, 487, 491, 499, 503, 509, 521, 523,
              541, 547, 557, 563, 569, 571, 577, 587, 593, 599, 601, 607, 613,
              617, 619, 631, 641, 643, 647, 653, 659, 661, 673, 677, 683, 691,
              701, 709, 719, 727, 733, 739, 743, 751, 757, 761, 769, 773, 787,
              797, 809, 811, 821, 823, 827, 829, 839, 853, 857, 859, 863, 877,
              881, 883, 887, 907, 911, 919, 929, 937, 941, 947, 953, 967, 971,
              977, 983, 991, 997, 1009, 1013, 1019, 1021, 1031, 1033, 1039,
              1049, 1051, 1061, 1063, 1069, 1087, 1091, 1093, 1097)
COEFFICIENT_BOUND = 40
COST_TIERS = ((200, 1), (2000, 2), (1100, 3))
BUDGET_UNITS = 8

_BASE_DEVELOPMENT_SPECS = (
    (41011, "elliptic"), (41017, "elliptic"), (41023, "elliptic"),
    (41029, "elliptic"), (41031, "elliptic"),
    (41037, "singular"), (41041, "genus_two"),
)
HELDOUT_SPECS = (
    (42007, "elliptic"), (42013, "elliptic"), (42017, "elliptic"),
    (42021, "singular"), (42023, "genus_two"),
)


def _legendre_count_cubic(prime, a, b):
    """#E(F_p) = 1 + #{x : chi(x^3+ax+b) >= 0 counted with multiplicity}.

    Each x with nonzero quadratic-residue value contributes two points (y and -y),
    each x with value zero contributes one (y = 0); the point at infinity adds one.
    """
    total = 1
    for x in range(prime):
        value = (x * x * x + a * x + b) % prime
        if value == 0:
            total += 1
        elif pow(value, (prime - 1) // 2, prime) == 1:
            total += 2
    return total


def _legendre_count_quartic(prime, coefficients):
    """Affine point count of y^2 = quartic(x) over F_p.

    A genus-two curve carries roughly twice as many points as an elliptic curve;
    the count sits far outside the Hasse interval of every elliptic pair, so no
    (a, b) can reproduce it and the world must be refused.
    """
    total = 0
    for x in range(prime):
        value = 0
        for coefficient in coefficients:
            value = (value * x + coefficient) % prime
        if value == 0:
            continue
        if pow(value, (prime - 1) // 2, prime) == 1:
            total += 2
    return total + 2  # two points at infinity on the smooth model


def _world(spec):
    seed, kind = spec
    rng = np.random.default_rng(int(seed))
    if kind == "elliptic":
        while True:
            a = int(rng.integers(-COEFFICIENT_BOUND, COEFFICIENT_BOUND + 1))
            b = int(rng.integers(-COEFFICIENT_BOUND, COEFFICIENT_BOUND + 1))
            if 4 * a ** 3 + 27 * b * b != 0:
                break
        quartic = None
    elif kind == "singular":
        # Discriminant zero: a nodal or cuspidal cubic.
        while True:
            b = int(rng.integers(-COEFFICIENT_BOUND, COEFFICIENT_BOUND + 1))
            if b != 0:
                break
        a = int(round(-(27 * b * b / 4.0) ** (1.0 / 3.0)))
        if 4 * a ** 3 + 27 * b * b != 0:
            a = -b  # 4(-b)^3 + 27b^2 = 0 only for specific b; force exact zero below
        # exact singular pair: choose t with a = -3t^2, b = 2t^3
        t = int(rng.integers(1, 3))
        a, b = -3 * t * t, 2 * t ** 3
        quartic = None
    else:
        a = b = None
        quartic = [int(v) for v in rng.integers(-8, 9, size=5)]
    return {"seed": int(seed), "kind": kind, "a": a, "b": b, "quartic": quartic}


def problem_statement(world):
    del world
    return {
        "curve_family": "y^2 = x^3 + a*x + b with |a|,|b| <= %d and nonzero discriminant"
                        % COEFFICIENT_BOUND,
        "prime_list": list(PRIME_LIST),
        "cost_tiers": [[bound, cost] for bound, cost in COST_TIERS],
        "budget_units": BUDGET_UNITS,
        "answer_semantics": "the oracle returns the exact size of the solution set mod p, computed by Legendre sums",
        "refusal_note": (
            "singular cubics and genus-two quartics produce point counts no "
            "elliptic pair can reproduce and must be refused"
        ),
    }


class _ArithmeticOracle:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def count_points(self, prime):
        try:
            value = int(prime)
            if value not in PRIME_LIST:
                self.violated = True
                raise ValueError("prime must come from the published list")
            cost = next((c for bound, c in COST_TIERS if value <= bound), 3)
            if self.used + cost > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("query budget exceeded")
            self.used += cost
            self.calls += 1
            if self.world["kind"] == "elliptic":
                count = _legendre_count_cubic(value, self.world["a"], self.world["b"])
            elif self.world["kind"] == "singular":
                count = _legendre_count_cubic(value, self.world["a"], self.world["b"])
            else:
                count = _legendre_count_quartic(value, self.world["quartic"])
            return {"prime": value, "point_count": int(count), "budget_cost": cost}
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
        if submission.get("a") is not None or submission.get("b") is not None:
            raise ValueError("abstention requires empty coefficients")
        return None, None, confidence, True
    a = int(submission.get("a"))
    b = int(submission.get("b"))
    if not (-COEFFICIENT_BOUND <= a <= COEFFICIENT_BOUND
            and -COEFFICIENT_BOUND <= b <= COEFFICIENT_BOUND):
        raise ValueError("coefficients outside public bounds")
    return a, b, confidence, False


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "false_discovery": False,
            "correct_refusal": False, "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    oracle = _ArithmeticOracle(world)
    try:
        submission = candidate(problem_statement(world), oracle.count_points,
                               BUDGET_UNITS)
        a, b, confidence, abstain = _validate(submission)
        if oracle.violated:
            raise ValueError("oracle contract violated")
        supported = world["kind"] == "elliptic"
        if supported and not abstain:
            error = (abs(a - world["a"]) + abs(b - world["b"])) / (4.0 * COEFFICIENT_BOUND)
            mechanism = float(math.exp(-6.0 * error))
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
                    "budget_used": oracle.used})
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1] == "elliptic"]
    unsupported = [r for r, s in zip(rows, specs) if s[1] != "elliptic"]
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


def evaluate(recover_curve):
    development = [_evaluate_world(recover_curve, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(recover_curve, spec, "heldout", i)
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
