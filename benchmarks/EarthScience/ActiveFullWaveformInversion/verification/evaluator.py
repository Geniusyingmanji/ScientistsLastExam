"""Deterministic reduced-order 2-D acoustic full-waveform discovery oracle."""

from __future__ import annotations

import math

import numpy as np

GRID_SHAPE = (20, 32)
SPACING_M = 50.0
DT_S = 0.003
N_TIME = 210
BACKGROUND_MIN = 2100.0
BACKGROUND_MAX = 3000.0
VELOCITY_BOUNDS = (1500.0, 4200.0)
SOURCE_INDICES = np.asarray((3, 9, 15, 21, 28), dtype=int)
RECEIVER_INDICES = np.arange(2, GRID_SHAPE[1] - 2, 2, dtype=int)
RECEIVER_X_M = RECEIVER_INDICES.astype(float) * SPACING_M
BUDGET_UNITS = 3

DEVELOPMENT_SPECS = (
    (41011, "supported", 0),
    (41017, "supported", 1),
    (41023, "supported", 2),
    (41039, "supported", 3),
    (41047, "null", 0),
    (41051, "misspecified", 1),
)
HELDOUT_SPECS = (
    (51001, "supported", 4),
    (51007, "supported", 5),
    (51019, "supported", 6),
    (51031, "null", 0),
    (51043, "misspecified", 2),
)


def _background():
    z = np.linspace(0.0, 1.0, GRID_SHAPE[0])[:, None]
    return np.broadcast_to(BACKGROUND_MIN + (BACKGROUND_MAX - BACKGROUND_MIN) * z,
                           GRID_SHAPE).copy()


def _velocity(seed, variant, kind):
    base = _background()
    if kind != "supported":
        return base
    rng = np.random.default_rng(int(seed))
    zz, xx = np.mgrid[0:GRID_SHAPE[0], 0:GRID_SHAPE[1]]
    count = 1 + int(variant % 3)
    for index in range(count):
        cx = rng.uniform(6.0, GRID_SHAPE[1] - 6.0)
        cz = rng.uniform(4.5, GRID_SHAPE[0] - 6.0)
        sx = rng.uniform(3.2, 6.0)
        sz = rng.uniform(2.4, 4.4)
        sign = -1.0 if (variant + index) % 2 else 1.0
        amplitude = sign * rng.uniform(520.0, 900.0)
        base += amplitude * np.exp(-0.5 * (((xx - cx) / sx) ** 2 + ((zz - cz) / sz) ** 2))
    return np.clip(base, *VELOCITY_BOUNDS)


def _ricker(time_s, frequency_hz):
    delay = 1.5 / frequency_hz
    arg = np.pi * frequency_hz * (time_s - delay)
    return (1.0 - 2.0 * arg * arg) * np.exp(-arg * arg)


def simulate_waveforms(velocity_m_s, source_index, frequency_hz=12.0, attenuation=0.0):
    """Run a small constant-density acoustic finite-difference model."""
    velocity = np.asarray(velocity_m_s, dtype=float)
    if velocity.shape != GRID_SHAPE:
        raise ValueError("velocity grid has the wrong shape")
    previous = np.zeros(GRID_SHAPE, dtype=float)
    current = np.zeros(GRID_SHAPE, dtype=float)
    traces = np.zeros((N_TIME, len(RECEIVER_INDICES)), dtype=float)
    damping = np.ones(GRID_SHAPE, dtype=float)
    damping[[0, -1], :] = 0.86
    damping[:, [0, -1]] = 0.86
    damping[[1, -2], :] = 0.94
    damping[:, [1, -2]] = 0.94
    coefficient = (velocity * DT_S / SPACING_M) ** 2
    wavelet = _ricker(np.arange(N_TIME) * DT_S, float(frequency_hz))
    for step in range(N_TIME):
        lap = np.zeros_like(current)
        lap[1:-1, 1:-1] = (
            current[1:-1, 2:] + current[1:-1, :-2]
            + current[2:, 1:-1] + current[:-2, 1:-1]
            - 4.0 * current[1:-1, 1:-1]
        )
        following = (2.0 * current - previous + coefficient * lap) * damping
        following[2, int(source_index)] += wavelet[step]
        if attenuation:
            following *= math.exp(-float(attenuation) * DT_S)
        traces[step] = following[2, RECEIVER_INDICES]
        previous, current = current, following
    return traces


def _world(spec):
    seed, kind, variant = spec
    velocity = _velocity(seed, variant, kind)
    return {"seed": int(seed), "kind": kind, "variant": int(variant), "velocity": velocity,
            "noise": 0.0025 + 0.0005 * (variant % 3)}


class _Acquisition:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = []
        self.violated = False

    def acquire(self, source_index):
        try:
            source = int(source_index)
        except Exception as exc:
            self.violated = True
            raise ValueError("source_index must be an integer") from exc
        if source not in set(int(value) for value in SOURCE_INDICES):
            self.violated = True
            raise ValueError("source_index is not in source_indices")
        if self.used + 1 > BUDGET_UNITS:
            self.violated = True
            raise RuntimeError("shot budget exceeded")
        self.used += 1
        self.calls.append(source)
        attenuation = 1.8 if self.world["kind"] == "misspecified" else 0.0
        clean = simulate_waveforms(self.world["velocity"], source, 12.0, attenuation)
        scale = max(float(np.std(clean)), 1e-8)
        sigma = self.world["noise"] * scale
        rng = np.random.default_rng(self.world["seed"] * 101 + source * 17 + self.used)
        pressure = clean + rng.normal(0.0, sigma, clean.shape)
        return {
            "source_index": source,
            "receiver_x_m": RECEIVER_X_M.copy(),
            "time_s": np.arange(N_TIME, dtype=float) * DT_S,
            "pressure": pressure,
            "noise_std": float(sigma),
            "budget_cost": 1,
        }


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    abstain = bool(submission["abstain"])
    velocity = np.asarray(submission.get("velocity_m_s"), dtype=float)
    if abstain:
        if velocity.size:
            raise ValueError("abstention requires an empty velocity grid")
        return None, confidence, True
    if velocity.shape != GRID_SHAPE or np.any(~np.isfinite(velocity)):
        raise ValueError("velocity_m_s must be a finite grid with grid_shape")
    if np.any(velocity < VELOCITY_BOUNDS[0]) or np.any(velocity > VELOCITY_BOUNDS[1]):
        raise ValueError("velocity lies outside velocity_bounds_m_s")
    return velocity.copy(), confidence, False


def _supported_scores(world, predicted):
    truth = world["velocity"]
    weight = np.linspace(0.7, 1.3, GRID_SHAPE[0])[:, None]
    rel = np.sqrt(np.sum(weight * (predicted - truth) ** 2) /
                  max(np.sum(weight * (truth - _background()) ** 2), 1.0))
    model_score = float(math.exp(-1.5 * rel))
    errors = []
    for frequency, source in ((8.0, 6), (15.0, 25)):
        observed = simulate_waveforms(truth, source, frequency)
        proposed = simulate_waveforms(predicted, source, frequency)
        errors.append(float(np.linalg.norm(proposed - observed) /
                            max(np.linalg.norm(observed), 1e-12)))
    waveform_error = float(np.mean(errors))
    waveform_score = float(math.exp(-3.0 * waveform_error))
    return model_score, waveform_score, float(math.sqrt(model_score * waveform_score))


def _empty_row(split, index):
    return {
        "split": split, "world_index": index, "valid": False, "abstained": False,
        "mechanism_score": 0.0, "model_score": 0.0, "waveform_score": 0.0,
        "waveform_relative_l2": 1e6, "confidence_score": 0.0,
        "false_discovery": False, "correct_refusal": False, "shot_calls": 0,
    }


def _evaluate_world(candidate, spec, split, index):
    row = _empty_row(split, index)
    world = _world(spec)
    acquisition = _Acquisition(world)
    try:
        submission = candidate(
            GRID_SHAPE, SPACING_M, _background(), VELOCITY_BOUNDS,
            SOURCE_INDICES.copy(), RECEIVER_X_M.copy(),
            np.arange(N_TIME, dtype=float) * DT_S, acquisition.acquire, BUDGET_UNITS,
        )
        velocity, confidence, abstain = _validate(submission)
        if acquisition.violated:
            raise ValueError("acquisition contract was violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            model_score, waveform_score, mechanism = _supported_scores(world, velocity)
            relative = -math.log(max(waveform_score, 1e-12)) / 3.0
        elif supported:
            model_score = waveform_score = mechanism = 0.0
            relative = 1e6
        else:
            correct = bool(abstain)
            model_score = waveform_score = mechanism = 1.0 if correct else 0.0
            relative = 0.0 if correct else 1e6
        target_confidence = 1.0 if (supported and not abstain) else 0.0
        row.update({
            "valid": True, "abstained": abstain, "mechanism_score": mechanism,
            "model_score": model_score, "waveform_score": waveform_score,
            "waveform_relative_l2": relative,
            "confidence_score": 1.0 - (confidence - target_confidence) ** 2,
            "false_discovery": bool(not supported and not abstain),
            "correct_refusal": bool(not supported and abstain),
            "shot_calls": len(acquisition.calls),
        })
    except Exception:
        pass
    return row


def _summary(rows, specs):
    supported = [row for row, spec in zip(rows, specs) if spec[1] == "supported"]
    unsupported = [row for row, spec in zip(rows, specs) if spec[1] != "supported"]
    raw = float(np.mean([row["mechanism_score"] for row in rows]))
    always_abstain = len(unsupported) / len(rows)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized": normalized, "raw": raw,
        "valid_count": sum(row["valid"] for row in rows),
        "model": float(np.mean([row["model_score"] for row in supported])),
        "waveform": float(np.mean([row["waveform_score"] for row in supported])),
        "confidence": float(np.mean([row["confidence_score"] for row in rows])),
        "false_discovery_count": sum(row["false_discovery"] for row in unsupported),
        "correct_refusal_count": sum(row["correct_refusal"] for row in unsupported),
        "attempt_count": sum(not row["abstained"] for row in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(invert_velocity_model):
    development = [_evaluate_world(invert_velocity_model, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(invert_velocity_model, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_SPECS)]
    dev = _summary(development, DEVELOPMENT_SPECS)
    hold = _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_model_score": dev["model"],
        "development_waveform_score": dev["waveform"],
        "development_confidence_calibration_score": dev["confidence"],
        "development_false_discovery_rate": dev["false_discovery_count"] / dev["unsupported_count"],
        "development_correct_refusal_rate": dev["correct_refusal_count"] / dev["unsupported_count"],
        "development_discovery_coverage": dev["attempt_count"] / dev["supported_count"],
        "supported_world_count": dev["supported_count"],
        "unsupported_world_count": dev["unsupported_count"],
        "discovery_attempt_count": dev["attempt_count"],
        "false_discovery_count": dev["false_discovery_count"],
        "correct_refusal_count": dev["correct_refusal_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_model_score": hold["model"],
        "heldout_waveform_score": hold["waveform"],
        "heldout_false_discovery_rate": hold["false_discovery_count"] / hold["unsupported_count"],
        "heldout_correct_refusal_rate": hold["correct_refusal_count"] / hold["unsupported_count"],
        "heldout_discovery_coverage": hold["attempt_count"] / hold["supported_count"],
        "per_world": development + heldout,
    }
