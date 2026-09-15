"""Deterministic elliptic-curve coefficient oracle.

A hidden curve y^2 = x^3 + ax + b over the rationals answers point counts modulo
chosen primes: for each p the oracle returns #E(F_p) exactly. Each count leaves
a finite set of compatible (a mod p, b mod p) pairs; the Chinese remainder
theorem combines the residue sets in the bounded integer window. Two worlds
break the elliptic premise — a singular cubic and a
smooth genus-two quintic. In the frozen window the former has singular-only
lifts and the latter no lifts after enough primes. Nonsingular Q-isomorphic twins
provide a third refusal cause: an exact coefficient pair is not identifiable.
"""

from __future__ import annotations

import math
import importlib.util
from pathlib import Path
from functools import lru_cache
from numbers import Integral

import numpy as np

_spec = importlib.util.spec_from_file_location("elliptic_evidence_arithmetic", Path(__file__).with_name("arithmetic.py"))
_arithmetic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_arithmetic)

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
COEFFICIENT_BOUND = 1200
COST_TIERS = ((100, 1), (1000, 2), (1100, 3))
BUDGET_UNITS = 5

# Frozen, disjoint procedural cohorts. Exact transcript support, rather than a
# discount for unspent budget, determines recovery credit.
_BASE_DEVELOPMENT_SPECS = tuple(
    [(61000 + 101*i, "elliptic") for i in range(24)]
    + [(61101 + 101*i, "singular") for i in range(4)]
    + [(64000 + 101*i, "genus_two") for i in range(4)]
    + [(65000 + 101*i, "isomorphic") for i in range(4)])
HELDOUT_SPECS = tuple(
    [(71000 + 101*i, "elliptic") for i in range(18)]
    + [(71101 + 101*i, "singular") for i in range(4)]
    + [(74000 + 101*i, "genus_two") for i in range(4)]
    + [(75000 + 101*i, "isomorphic") for i in range(4)])


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


def _legendre_count_quintic(prime, coefficients):
    """Exact smooth projective count for y^2=f(x), monic squarefree degree 5.

    The odd-degree hyperelliptic model has genus (5-1)/2=2 and one point at
    infinity. A root of f contributes the affine point (x, 0), not zero points.
    """
    total = 1
    for x in range(prime):
        value = 0
        for coefficient in coefficients:
            value = (value * x + coefficient) % prime
        if value == 0:
            total += 1
        elif pow(value, (prime - 1) // 2, prime) == 1:
            total += 2
    return total


def _squarefree_mod_prime(coefficients, prime):
    """Euclidean polynomial gcd(f, f') over F_p, using descending coefficients."""
    def trim(values):
        values = [int(value) % prime for value in values]
        while values and values[0] == 0:
            values.pop(0)
        return values

    a = trim(coefficients)
    degree = len(a) - 1
    b = trim([value * (degree - index) for index, value in enumerate(a[:-1])])
    while b:
        remainder = a[:]
        while len(remainder) >= len(b):
            factor = remainder[0] * pow(b[0], -1, prime) % prime
            for index, value in enumerate(b):
                remainder[index] = (remainder[index] - factor * value) % prime
            remainder = trim(remainder)
        a, b = b, remainder
    return len(a) == 1


@lru_cache(maxsize=256)
def _world(spec):
    seed, kind = spec
    rng = np.random.default_rng(int(seed))
    if kind == "elliptic":
        while True:
            a = int(rng.integers(-COEFFICIENT_BOUND, COEFFICIENT_BOUND + 1))
            b = int(rng.integers(-COEFFICIENT_BOUND, COEFFICIENT_BOUND + 1))
            # Exclude rational scaling twins from supported coefficient worlds.
            primitive = not any(a % u**4 == 0 and b % u**6 == 0 for u in range(2, 5))
            scalable = abs(16*a) <= COEFFICIENT_BOUND and abs(64*b) <= COEFFICIENT_BOUND
            if 4 * a ** 3 + 27 * b * b != 0 and primitive and not scalable:
                break
        quintic = None
    elif kind == "singular":
        # Signed disjoint square classes: the former two-valued generator
        # accidentally shipped the exact same cubic in both splits.
        t = (1, 2, 3, 5)[(seed // 101) % 4] * (1 if seed < 70000 else -1)
        a, b = -3*t*t, 2*t**3
        quintic = None
    elif kind == "isomorphic":
        a = 1 + (seed // 101) % 4
        b = (1 if seed < 70000 else -1) * (1 + (seed // 103) % 8)
        quintic = None
    else:
        a = b = None
        for _ in range(1000):
            quintic = [1] + [int(v) for v in rng.integers(-8, 9, size=5)]
            if all(_squarefree_mod_prime(quintic, prime) for prime in PRIME_LIST):
                break
        else:
            raise ValueError("could not generate a smooth genus-two world")
    return {"seed": int(seed), "kind": kind, "a": a, "b": b, "quintic": quintic}


def problem_statement(world):
    del world
    return {
        "coefficient_bound": COEFFICIENT_BOUND,
        "curve_family": "y^2 = x^3 + a*x + b with |a|,|b| <= %d and nonzero discriminant"
                        % COEFFICIENT_BOUND,
        "prime_list": list(PRIME_LIST),
        "cost_tiers": [[bound, cost] for bound, cost in COST_TIERS],
        "budget_units": BUDGET_UNITS,
        "answer_semantics": "the oracle returns the exact size of the solution set mod p, computed by Legendre sums",
        "refusal_note": (
            "refuse a singular-only or empty bounded compatibility set, and "
            "indistinguishable nonsingular coefficient pairs (including Q-isomorphic twins)"
        ),
    }


class _ArithmeticOracle:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        self.transcript = []

    def count_points(self, prime):
        try:
            if isinstance(prime, (bool, np.bool_)) or not isinstance(prime, Integral):
                raise ValueError("prime must be an integer from the published list")
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
            if self.world["kind"] in ("elliptic", "isomorphic"):
                count = _legendre_count_cubic(value, self.world["a"], self.world["b"])
            elif self.world["kind"] == "singular":
                count = _legendre_count_cubic(value, self.world["a"], self.world["b"])
            else:
                count = _legendre_count_quintic(value, self.world["quintic"])
            self.transcript.append((value, int(count)))
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
    values = [submission.get("a"), submission.get("b")]
    if any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral)
           for value in values):
        raise ValueError("coefficients must be integers")
    a, b = map(int, values)
    if not (-COEFFICIENT_BOUND <= a <= COEFFICIENT_BOUND
            and -COEFFICIENT_BOUND <= b <= COEFFICIENT_BOUND):
        raise ValueError("coefficients outside public bounds")
    return a, b, confidence, False


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "intrinsic_mechanism_score": 0.0,
            "evidence_support_score": 0.0,
            "compatible_curve_count": 0, "queried_prime_count": 0, "false_discovery": False,
            "correct_refusal": False, "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    # Main provides a fresh-worker boundary: no global/import/tmpfs call-order channel.
    reset = getattr(candidate, "reset_session", None)
    if callable(reset) and (split != "development" or index > 0):
        reset()
    world = _world(spec)
    oracle = _ArithmeticOracle(world)
    try:
        submission = candidate(problem_statement(world), oracle.count_points,
                               BUDGET_UNITS)
        a, b, confidence, abstain = _validate(submission)
        if oracle.violated:
            raise ValueError("oracle contract violated")
        supported = world["kind"] == "elliptic"
        pairs = None
        # Blind abstention remains valid and costs no computation. A coefficient
        # claim earns credit only if the measurements isolate that exact pair.
        if not abstain:
            pairs = _arithmetic.compatible_pairs(oracle.transcript, COEFFICIENT_BOUND)
            if pairs is not None:
                pairs = _arithmetic.nonsingular(pairs)
        unique = pairs is not None and len(pairs) == 1 and tuple(pairs[0]) == (a, b)
        evidence_support = float(unique)
        if supported and not abstain:
            mechanism = float((a, b) == (world["a"], world["b"])) * evidence_support
        elif supported:
            mechanism = 0.0
        else:
            mechanism = float(abstain)
        target = mechanism
        scored_mechanism = mechanism
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": scored_mechanism,
                    "intrinsic_mechanism_score": mechanism,
                    "evidence_support_score": evidence_support,
                    "compatible_curve_count": len(pairs) if pairs is not None else 0,
                    "queried_prime_count": len(dict(oracle.transcript)),
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
        "confidence": float(np.mean([r["confidence_score"] for r in rows])),
        "valid_count": sum(r["valid"] for r in rows),
        "evidence_support": float(np.mean([r["evidence_support_score"] for r in supported])),
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(r["valid"] and not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(recover_curve):
    development = [_evaluate_world(recover_curve, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(recover_curve, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] > 0
    hold_valid = hold["valid_count"] > 0
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_confidence_score": dev["confidence"],
        "development_discovery_attempt_count": dev["attempt_count"],
        "development_evidence_support_score": dev["evidence_support"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_evidence_support_score": hold["evidence_support"],
        "heldout_confidence_score": hold["confidence"],
        "heldout_supported_world_count": hold["supported_count"],
        "heldout_unsupported_world_count": hold["unsupported_count"],
        "heldout_false_discovery_count": hold["false_count"],
        "heldout_correct_refusal_count": hold["refusal_count"],
        "heldout_discovery_attempt_count": hold["attempt_count"],
        "heldout_discovery_coverage": hold["attempt_count"] / hold["supported_count"],
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "per_world": development + heldout,
    }
