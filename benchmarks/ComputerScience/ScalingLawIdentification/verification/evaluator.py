"""Deterministic scaling-law oracle.

A black-box program answers timed runs: request a size, receive its runtime with
multiplicative noise. Six textbook asymptotic classes are public; the hidden world
holds one class and a scale constant — or a runtime that branches on the input size
(no single law exists), or a jitter so large the law is unrecoverable. Both must be
refused rather than forced onto the nearest class.
"""

from __future__ import annotations

import math

import numpy as np

DIFFICULTY = 1

CLASSES = ("constant", "logarithmic", "linear", "linearithmic", "quadratic",
           "exponential")
SIZE_BOUNDS = (8, 1024)
COST_TIERS = ((128, 1), (512, 2), (1024, 3))
BUDGET_UNITS = 12
NOISE_SIGMA = 0.03
JITTER_SIGMA = 0.60
SEALED_SIZE = 800

_BASE_DEVELOPMENT_SPECS = (
    (30011, "supported", "constant"), (30017, "supported", "logarithmic"),
    (30023, "supported", "linear"), (30029, "supported", "linearithmic"),
    (30031, "supported", "quadratic"), (30037, "supported", "exponential"),
    (30041, "branch", "branch"), (30047, "jitter", "linear"),
)
HELDOUT_SPECS = (
    (31007, "supported", "quadratic"), (31013, "supported", "linearithmic"),
    (31019, "supported", "logarithmic"), (31023, "branch", "branch"),
    (31029, "jitter", "quadratic"),
)


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
    scale = _sample_scale(rng, "linear" if kind in ("branch", "jitter") else family)
    return {"seed": int(seed), "kind": kind, "family": family, "scale": scale,
            "noise": JITTER_SIGMA if kind == "jitter" else NOISE_SIGMA}


def problem_statement(world):
    del world
    return {
        "classes": list(CLASSES),
        "class_shapes": {
            "constant": "c", "logarithmic": "c*log2(m)", "linear": "c*m",
            "linearithmic": "c*m*log2(m)", "quadratic": "c*m^2",
            "exponential": "c*2^(m/8)",
        },
        "size_bounds": list(SIZE_BOUNDS),
        "cost_tiers": [[bound, cost] for bound, cost in COST_TIERS],
        "budget_units": BUDGET_UNITS,
        "noise_note": "run times carry multiplicative noise; repeats draw fresh noise",
        "refusal_note": (
            "runtimes that branch on the input size follow no single class, and "
            "noise floors far above three percent make the law unrecoverable; both "
            "must be refused"
        ),
    }


def _true_runtime(world, size):
    if world["kind"] == "branch":
        value = world["scale"] * (size ** 2 if size % 3 == 1
                                  else size * math.log2(max(size, 2)))
    else:
        value = world["scale"] * class_shape(world["family"], size)
    return float(min(value, 1e300))


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
            value = int(size)
            if not SIZE_BOUNDS[0] <= value <= SIZE_BOUNDS[1]:
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
    if np.any(~np.isfinite(probs)) or np.any(probs < 0.0) or \
            not np.isclose(probs.sum(), 1.0, atol=1e-6):
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
    truth = _true_runtime(world, SEALED_SIZE)
    predicted = scale * class_shape(family, SEALED_SIZE)
    return float(math.exp(-2.0 * abs(math.log(max(predicted, 1e-300)
                                               / max(truth, 1e-300)))))


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "class_probability": 0.0, "scale_score": 0.0,
            "extrapolation_score": 0.0, "false_discovery": False,
            "correct_refusal": False, "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    profiler = _Profiler(world)
    try:
        submission = candidate(problem_statement(world), profiler.time_run,
                               BUDGET_UNITS)
        probs, scale, confidence, abstain = _validate(submission)
        if profiler.violated:
            raise ValueError("profiler contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            class_probability = float(probs[CLASSES.index(world["family"])])
            scale_score = _scale_score(scale, world["scale"])
            chosen = CLASSES[int(np.argmax(probs))]
            extrapolation = _extrapolation_score(world, scale, chosen)
            mechanism = float((max(class_probability, 1e-9) * max(scale_score, 1e-9)
                               * max(extrapolation, 1e-9)) ** (1.0 / 3.0))
        elif supported:
            class_probability = scale_score = extrapolation = mechanism = 0.0
        else:
            correct = bool(abstain)
            class_probability = scale_score = extrapolation = mechanism = \
                1.0 if correct else 0.0
        target = 1.0 if (supported != abstain or (not supported and abstain)) else 0.0
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": mechanism,
                    "class_probability": class_probability,
                    "scale_score": scale_score,
                    "extrapolation_score": extrapolation,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target) ** 2,
                    "budget_used": profiler.used})
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
        "class_probability": float(np.mean([r["class_probability"] for r in supported])) if supported else 0.0,
        "scale_score": float(np.mean([r["scale_score"] for r in supported])) if supported else 0.0,
        "extrapolation_score": float(np.mean([r["extrapolation_score"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(identify_scaling_law):
    development = [_evaluate_world(identify_scaling_law, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(identify_scaling_law, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
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
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": hold["false_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["refusal_count"] / hold["unsupported_count"],
        "per_world": development + heldout,
    }
