"""Finite-size empirical scaling with nuisance corrections and identifiable refusal.

Ambiguous worlds have a certified small pairwise KL bound over every affordable
query, rather than a label assigned solely from a noise threshold.
"""

from __future__ import annotations

import math
from numbers import Real

import numpy as np

DIFFICULTY = 1

CLASSES = ("constant", "logarithmic", "linear", "linearithmic", "quadratic",
           "exponential")
SIZE_BOUNDS = (8, 384)
COST_TIERS = ((64, 1), (192, 2), (384, 3))
BUDGET_UNITS = 18

# Budget is a hard observation constraint, not an artificial score discount.
MAX_EVIDENCE_COST_PENALTY = 0.0
NOISE_SIGMA = 0.16
SEALED_SIZE = 700

# Replicated families prevent a single lucky three-point fit from dominating a
# tiny class-per-seed split. Seeds are frozen and independent across splits.
_BASE_DEVELOPMENT_SPECS = tuple(
    (30011 + 101*r + 17*j, "supported", name)
    for r in range(4) for j,name in enumerate(CLASSES)
) + tuple((34001+103*r, "supported_narrow", "exponential") for r in range(4)) + tuple(
    (35011+107*r, kind, "linear" if r%2 == 0 else "linearithmic")
    for r in range(8) for kind in ("ambiguous", "misspecified"))
HELDOUT_SPECS = tuple(
    (40009 + 109*r + 19*j, "supported", name)
    for r in range(3) for j,name in enumerate(CLASSES)
) + tuple((44017+113*r, "supported_narrow", "exponential") for r in range(3)) + tuple(
    (45007+127*r, kind, "linear" if r%2 == 0 else "linearithmic")
    for r in range(6) for kind in ("ambiguous", "misspecified"))


def class_shape(name, size):
    log_size = math.log2(max(size, 2))
    if name == "constant":
        return 1.0
    if name == "logarithmic":
        return log_size
    if name == "linear":
        return float(size)
    if name == "linearithmic":
        return size * log_size
    if name == "quadratic":
        return float(size) ** 2
    if name == "exponential":
        return 2.0 ** (size / 8.0)
    raise ValueError("unknown class")


def _sample_scale(rng, family):
    reference = class_shape(family, 64)
    return float(10.0 ** rng.uniform(1.0, 3.5)) / reference


def _world(spec):
    seed, kind, family = spec
    rng = np.random.default_rng(int(seed))
    scale = _sample_scale(rng, family)
    narrow = kind in ("ambiguous", "supported_narrow")
    correction = float(rng.uniform(-2., 2.))
    if kind == "supported_narrow":
        # Same public domain AND noise as the ambiguous pair. A genuinely steep
        # observed exponential slope, rather than precision metadata, distinguishes it.
        correction = -1.5 + .25 * correction
    return {"seed": int(seed), "kind": kind, "family": family, "scale": scale,
            "correction": correction,
            "bounds": (64, 72) if narrow else SIZE_BOUNDS,
            "noise": .12 if narrow else NOISE_SIGMA}


def problem_statement(world):
    return {
        "classes": list(CLASSES),
        "class_shapes": {
            "constant": "c", "logarithmic": "c*log2(m)", "linear": "c*m",
            "linearithmic": "c*m*log2(m)", "quadratic": "c*m^2",
            "exponential": "c*2^(m/8)",
        },
        "size_bounds": list(world["bounds"]),
        "cost_tiers": [[bound, cost] for bound, cost in COST_TIERS],
        "budget_units": BUDGET_UNITS,
        "log_noise_std": world["noise"],
        "nuisance_model": "log runtime = log(c*f(m)) + a*64/m; -2 <= a <= 2",
        "noise_note": "independent Gaussian log timing error with stated standard deviation",
        "refusal_note": "refuse model inadequacy or classes observationally indistinguishable within the query domain and budget",
    }


def _true_runtime(world, size):
    log_value = math.log(world["scale"] * class_shape(world["family"], size))
    log_value += world["correction"] * 64. / size
    if world["kind"] == "misspecified":
        log_value += 1.4 * math.sin(3. * math.log(size))
    return math.exp(min(log_value, 690.))


def ambiguity_information_bound(world):
    """KL upper bound for ANY adaptive policy, and equal-prior binary accuracy.

    Match a linear and a linearithmic world at the geometric midpoint of their
    log-ratio range. Keep their nuisance coefficients and Gaussian noise equal.
    The chain rule bounds adaptive transcript KL by budget times max KL/cost;
    Pinsker then bounds the best possible classification accuracy.
    """
    sizes = np.arange(world["bounds"][0], world["bounds"][1]+1)
    ratios = np.log(np.log2(sizes))
    delta = ratios - .5*(min(ratios)+max(ratios))
    kl = BUDGET_UNITS * max(d*d/(2*world["noise"]**2*_call_cost(int(n)))
                            for n,d in zip(sizes,delta))
    return float(kl), float(min(1., .5 + math.sqrt(kl/2.)/2.))


def _call_cost(size):
    for bound, cost in COST_TIERS:
        if size <= bound:
            return cost
    return 3


class _Profiler:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def time_run(self, size):
        try:
            if isinstance(size, (bool, np.bool_)) or not isinstance(size, Real) or not math.isfinite(size) or float(size) != int(size):
                raise ValueError("size must be an integer")
            value = int(size)
            if not self.world["bounds"][0] <= value <= self.world["bounds"][1]:
                self.violated = True
                raise ValueError("size outside allowed bounds")
            cost = _call_cost(value)
            if self.used + cost > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("profiling budget exceeded")
            self.used += cost
            self.calls += 1
            rng = np.random.default_rng(self.world["seed"] + 7919 * value
                                        + 17 * self.calls)
            clean = _true_runtime(self.world, value)
            observed = clean * math.exp(rng.normal(0.0, self.world["noise"]))
            return {"size": value, "runtime_ms": float(observed),
                    "budget_cost": cost}
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
    probabilities = submission.get("class_probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(CLASSES):
        raise ValueError("class_probabilities must cover exactly the six classes")
    probs = np.asarray([probabilities[name] for name in CLASSES], dtype=float)
    if probs.shape != (len(CLASSES),) or np.any(~np.isfinite(probs)) or \
            np.any(probs < 0.0) or np.any(probs > 1.0) or \
            not np.isclose(probs.sum(), 1.0, atol=1e-6, rtol=0.0):
        raise ValueError("class probabilities must be nonnegative and sum to one")
    if bool(abstain):
        if submission.get("scale") is not None:
            raise ValueError("abstention requires an empty scale")
        return probs, None, confidence, True
    scale = float(submission.get("scale"))
    if not math.isfinite(scale) or not 1e-12 <= scale <= 1e12:
        raise ValueError("scale must be a positive finite constant")
    return probs, scale, confidence, False


def _scale_score(proposed, truth):
    return float(math.exp(-2.0 * abs(math.log(max(proposed, 1e-12)
                                               / max(truth, 1e-12)))))


def _extrapolation_score(world, scale, family):
    truth = world["scale"] * class_shape(world["family"], SEALED_SIZE)
    predicted = scale * class_shape(family, SEALED_SIZE)
    return float(math.exp(-2.0 * abs(math.log(max(predicted, 1e-300)
                                               / max(truth, 1e-300)))))


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "intrinsic_mechanism_score": 0.0,
            "evidence_efficiency_score": 0.0, "class_probability": 0.0, "scale_score": 0.0,
            "extrapolation_score": 0.0, "false_discovery": False,
            "correct_refusal": False, "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    profiler = _Profiler(world)
    try:
        # Scientific worlds are independent experiments, including across splits.
        reset = getattr(candidate, "reset_session", None)
        if callable(reset):
            reset()
        submission = candidate(problem_statement(world), profiler.time_run,
                               BUDGET_UNITS)
        probs, scale, confidence, abstain = _validate(submission)
        if profiler.violated:
            raise ValueError("profiler contract violated")
        supported = world["kind"].startswith("supported")
        if supported and not abstain:
            class_probability = float(probs[CLASSES.index(world["family"])])
            scale_score = _scale_score(scale, world["scale"])
            extrapolation = sum(float(prob) * _extrapolation_score(world, scale, name)
                                for prob, name in zip(probs, CLASSES))
            mechanism = float((max(class_probability, 1e-9) * max(scale_score, 1e-9)
                               * max(extrapolation, 1e-9)) ** (1.0 / 3.0))
        elif supported:
            class_probability = scale_score = extrapolation = mechanism = 0.0
        else:
            correct = bool(abstain)
            class_probability = scale_score = extrapolation = mechanism = \
                1.0 if correct else 0.0
        # Confidence predicts the intrinsic quality of the submitted response,
        # including correct refusal; a wrong supported claim is not rewarded.
        target = mechanism
        evidence_efficiency = 1.0 - MAX_EVIDENCE_COST_PENALTY * (
            profiler.used / BUDGET_UNITS)
        # Efficiency adjusts supported discovery only. Refusal quality remains a
        # separate axis so evidence-backed refusal is not penalized relative to
        # the always-abstain normalization baseline.
        scored_mechanism = mechanism * evidence_efficiency if supported else mechanism
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": scored_mechanism,
                    "intrinsic_mechanism_score": mechanism,
                    "evidence_efficiency_score": evidence_efficiency,
                    "class_probability": class_probability,
                    "scale_score": scale_score,
                    "extrapolation_score": extrapolation,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target) ** 2,
                    "budget_used": profiler.used})
    except BaseException:
        pass
    return row


def _summary(rows, specs):
    supported = [r for r, s in zip(rows, specs) if s[1].startswith("supported")]
    unsupported = [r for r, s in zip(rows, specs) if not s[1].startswith("supported")]
    raw = float(np.mean([r["mechanism_score"] for r in rows]))
    abstain_base = len(unsupported) / len(rows)
    return {
        "normalized": float(np.clip((raw - abstain_base) / (1.0 - abstain_base), 0.0, 1.0)),
        "raw": raw,
        "confidence": float(np.mean([r["confidence_score"] for r in rows])),
        "valid_count": sum(r["valid"] for r in rows),
        "evidence_efficiency": float(np.mean([r["evidence_efficiency_score"] for r in rows])),
        "class_probability": float(np.mean([r["class_probability"] for r in supported])) if supported else 0.0,
        "scale_score": float(np.mean([r["scale_score"] for r in supported])) if supported else 0.0,
        "extrapolation_score": float(np.mean([r["extrapolation_score"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(r["valid"] and not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(identify_scaling_law):
    development = [_evaluate_world(identify_scaling_law, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(identify_scaling_law, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] > 0
    hold_valid = hold["valid_count"] > 0
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "heldout_mechanism_score": hold["raw"],
        "development_confidence_score": dev["confidence"],
        "development_discovery_attempt_count": dev["attempt_count"],
        "development_evidence_efficiency_score": dev["evidence_efficiency"],
        "development_class_probability": dev["class_probability"],
        "development_scale_score": dev["scale_score"],
        "development_extrapolation_score": dev["extrapolation_score"],
        "development_false_discovery_rate": dev["false_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "false_discovery_count": dev["false_count"],
        "correct_refusal_count": dev["refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_evidence_efficiency_score": hold["evidence_efficiency"],
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
