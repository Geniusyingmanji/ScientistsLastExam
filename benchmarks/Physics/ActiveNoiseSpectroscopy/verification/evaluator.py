"""Trusted oracle for active non-Gaussian qubit noise spectroscopy.

The task deliberately pairs two noises with the same autocovariance and Lorentzian
power spectrum: Gaussian Ornstein--Uhlenbeck noise and a stationary two-state
fluctuator.  A PSD-only fit cannot separate them.  The oracle propagates the
two-state Feynman--Kac system exactly through the submitted pulse switching
function, so the complex coherence retains higher-cumulant information.
"""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np
from scipy.linalg import expm
from scipy.optimize import least_squares


SHOT_BUDGET = 24_000
MIN_SHOTS_PER_QUADRATURE = 100
MAX_SHOTS_PER_QUADRATURE = 6_000
RATE_BOUNDS = (0.2, 2.5)
VARIANCE_BOUNDS = (0.002, 0.5)
HIGH_STATE_PROBABILITY_BOUNDS = (0.10, 0.50)

CONTROL_CATALOG = (
    {"sequence_id": "ramsey_0p5", "duration_us": 0.5, "pulse_times_us": ()},
    {"sequence_id": "ramsey_1p0", "duration_us": 1.0, "pulse_times_us": ()},
    {"sequence_id": "ramsey_2p0", "duration_us": 2.0, "pulse_times_us": ()},
    {"sequence_id": "ramsey_3p5", "duration_us": 3.5, "pulse_times_us": ()},
    {"sequence_id": "echo_1p4", "duration_us": 1.4, "pulse_times_us": (0.7,)},
    {"sequence_id": "echo_3p0", "duration_us": 3.0, "pulse_times_us": (1.5,)},
    {"sequence_id": "offset_echo", "duration_us": 2.4, "pulse_times_us": (0.4,)},
    {"sequence_id": "cpmg_2", "duration_us": 3.2, "pulse_times_us": (0.8, 2.4)},
)

HELDOUT_CONTROLS = (
    {"sequence_id": "heldout_ramsey", "duration_us": 2.7, "pulse_times_us": ()},
    {"sequence_id": "heldout_offset", "duration_us": 3.1, "pulse_times_us": (0.55,)},
    {"sequence_id": "heldout_cpmg3", "duration_us": 3.0,
     "pulse_times_us": (0.5, 1.5, 2.5)},
)

PUBLIC_PROBLEM = {
    "control_catalog": [
        {
            "sequence_id": row["sequence_id"],
            "duration_us": row["duration_us"],
            "pulse_times_us": list(row["pulse_times_us"]),
        }
        for row in CONTROL_CATALOG
    ],
    "shot_budget": SHOT_BUDGET,
    "min_shots_per_quadrature": MIN_SHOTS_PER_QUADRATURE,
    "max_shots_per_quadrature": MAX_SHOTS_PER_QUADRATURE,
    "parameter_bounds": {
        "switching_rate_per_us": list(RATE_BOUNDS),
        "noise_variance_rad2_per_us2": list(VARIANCE_BOUNDS),
        "high_state_probability": list(HIGH_STATE_PROBABILITY_BOUNDS),
    },
    "switching_function": (
        "y(t) starts at +1 and flips sign at every instantaneous pi-pulse time"
    ),
    "measurement_model": (
        "measure(sequence_id, shots_per_quadrature) returns independent X and Y "
        "binomial counts with p_X+=(1+Re W)/2 and p_Y+=(1+Im W)/2; each call "
        "costs twice shots_per_quadrature"
    ),
    "supported_model": (
        "one stationary classical two-state fluctuator with centered levels, "
        "non-negative third cumulant (including the symmetric zero case), exponential "
        "correlation and a Lorentzian PSD"
    ),
    "abstain_when": (
        "the data support Gaussian noise, multiple fluctuators, or cannot distinguish "
        "the supported model from its PSD-matched Gaussian alternative within the shot budget"
    ),
}


def _intervals(control):
    duration = float(control["duration_us"])
    pulses = tuple(float(value) for value in control["pulse_times_us"])
    boundaries = (0.0,) + pulses + (duration,)
    return tuple(
        (boundaries[index + 1] - boundaries[index], 1.0 if index % 2 == 0 else -1.0)
        for index in range(len(boundaries) - 1)
    )


def filter_function(control, omega_per_us):
    """Return F(omega)=integral y(t) exp(i omega t) dt exactly by segments."""

    omega = float(omega_per_us)
    start = 0.0
    total = 0.0j
    for duration, sign in _intervals(control):
        stop = start + duration
        if abs(omega) < 1e-14:
            total += sign * duration
        else:
            total += sign * (
                np.exp(1j * omega * stop) - np.exp(1j * omega * start)
            ) / (1j * omega)
        start = stop
    return complex(total)


def gaussian_coherence(control, switching_rate_per_us,
                       noise_variance_rad2_per_us2):
    """Exact OU coherence, equivalent to integrating PSD times |F| squared."""

    rate = float(switching_rate_per_us)
    variance = float(noise_variance_rad2_per_us2)
    memory = 0.0
    chi = 0.0
    for duration, sign in _intervals(control):
        decay = math.exp(-rate * duration)
        chi += variance * (
            sign * memory * (1.0 - decay) / rate
            + duration / rate
            - (1.0 - decay) / (rate * rate)
        )
        memory = memory * decay + sign * (1.0 - decay) / rate
    return complex(math.exp(-max(0.0, chi)), 0.0)


def telegraph_coherence(control, switching_rate_per_us,
                        noise_variance_rad2_per_us2,
                        high_state_probability):
    """Exact coherence of one stationary, centered, two-state Markov fluctuator."""

    rate = float(switching_rate_per_us)
    variance = float(noise_variance_rad2_per_us2)
    high_probability = float(high_state_probability)
    low_probability = 1.0 - high_probability
    level_gap = math.sqrt(variance / (low_probability * high_probability))
    levels = np.asarray(
        [-high_probability * level_gap, low_probability * level_gap], dtype=float
    )
    # Column-vector master equation.  k_low_to_high=rate*p_high and
    # k_high_to_low=rate*p_low give the requested stationary probabilities.
    generator_transpose = np.asarray([
        [-rate * high_probability, rate * low_probability],
        [rate * high_probability, -rate * low_probability],
    ])
    conditional = np.asarray([low_probability, high_probability], dtype=complex)
    for duration, sign in _intervals(control):
        tilted = generator_transpose - 1j * sign * np.diag(levels)
        conditional = expm(tilted * duration).dot(conditional)
    return complex(np.sum(conditional))


def _true_coherence(spec, control):
    if spec["kind"] == "gaussian":
        return gaussian_coherence(control, spec["rate"], spec["variance"])
    if spec["kind"] in {"single", "ambiguous_single"}:
        return telegraph_coherence(
            control, spec["rate"], spec["variance"], spec["high_probability"]
        )
    result = 1.0 + 0.0j
    for component in spec["components"]:
        result *= telegraph_coherence(
            control,
            component["rate"],
            component["variance"],
            component["high_probability"],
        )
    return result


def _bernoulli_kl(left, right):
    left = min(1.0 - 1e-12, max(1e-12, float(left)))
    right = min(1.0 - 1e-12, max(1e-12, float(right)))
    return (
        left * math.log(left / right)
        + (1.0 - left) * math.log((1.0 - left) / (1.0 - right))
    )


def _family_separation_kl(spec):
    """Maximum full-budget RTN-vs-Gaussian KL over the complete control pool."""

    shots = SHOT_BUDGET // 2
    best_per_shot_pair = 0.0
    for control in CONTROL_CATALOG:
        telegraph = telegraph_coherence(
            control, spec["rate"], spec["variance"], spec["high_probability"]
        )
        gaussian = gaussian_coherence(control, spec["rate"], spec["variance"])
        divergence = 0.0
        for left, right in (
            (telegraph.real, gaussian.real),
            (telegraph.imag, gaussian.imag),
        ):
            p_left = 0.5 * (1.0 + left)
            p_right = 0.5 * (1.0 + right)
            divergence += _bernoulli_kl(p_left, p_right)
        best_per_shot_pair = max(best_per_shot_pair, divergence)
    # KL adds across independent shots. Because every legal query observes both
    # quadratures at equal shot count and the pool is finite, allocating the
    # entire budget to the largest per-pair divergence is the exact maximum.
    return shots * best_per_shot_pair


def _parameter_jacobian_rank(spec):
    """Local rank of complex control responses for the three physical parameters."""

    controls = tuple(
        row for row in CONTROL_CATALOG
        if row["sequence_id"] in {
            "ramsey_1p0", "ramsey_2p0", "ramsey_3p5", "echo_3p0", "offset_echo"
        }
    )
    center = np.asarray([
        spec["rate"], spec["variance"], spec["high_probability"]
    ], dtype=float)

    def response(parameters):
        values = [telegraph_coherence(control, *parameters) for control in controls]
        return np.asarray([
            component for value in values for component in (value.real, value.imag)
        ])

    columns = []
    for index in range(3):
        step = max(abs(center[index]) * 1e-4, 1e-6)
        lower = center.copy()
        upper = center.copy()
        lower[index] -= step
        upper[index] += step
        if index == 2 and upper[index] > HIGH_STATE_PROBABILITY_BOUNDS[1]:
            upper[index] = center[index]
            lower[index] = center[index] - step
        columns.append((response(upper) - response(lower)) / (upper[index] - lower[index]))
    singular = np.linalg.svd(np.column_stack(columns), compute_uv=False)
    rank = int(np.sum(singular > singular[0] * 1e-7))
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else math.inf
    return rank, condition


def _profiled_gaussian_rmse(spec):
    """Best free-rate/free-variance Gaussian fit over the complete control pool."""

    target = [_true_coherence(spec, control) for control in CONTROL_CATALOG]

    def residual(parameters):
        predicted = [
            gaussian_coherence(control, parameters[0], parameters[1])
            for control in CONTROL_CATALOG
        ]
        return np.asarray([
            component
            for estimate, truth in zip(predicted, target)
            for component in (
                estimate.real - truth.real,
                estimate.imag - truth.imag,
            )
        ])

    fits = [
        least_squares(
            residual,
            start,
            bounds=(
                [RATE_BOUNDS[0], VARIANCE_BOUNDS[0]],
                [RATE_BOUNDS[1], VARIANCE_BOUNDS[1]],
            ),
            max_nfev=400,
        )
        for start in ([0.4, 0.1], [1.0, 0.25], [2.0, 0.4])
    ]
    best = min(fits, key=lambda fit: float(np.dot(fit.fun, fit.fun)))
    return math.sqrt(float(np.mean(best.fun ** 2)))


DEVELOPMENT_WORLDS = (
    {"kind": "single", "seed": 71001, "rate": 1.00, "variance": 0.22,
     "high_probability": 0.22},
    {"kind": "single", "seed": 71002, "rate": 0.65, "variance": 0.28,
     "high_probability": 0.18},
    {"kind": "single", "seed": 71003, "rate": 1.45, "variance": 0.24,
     "high_probability": 0.20},
    {"kind": "single", "seed": 71004, "rate": 0.40, "variance": 0.45,
     "high_probability": 0.50},
    {"kind": "gaussian", "seed": 72001, "rate": 1.00, "variance": 0.22},
    {"kind": "gaussian", "seed": 72002, "rate": 0.60, "variance": 0.28},
    {"kind": "mixture", "seed": 73001, "components": (
        {"rate": 2.00, "variance": 0.14, "high_probability": 0.15},
        {"rate": 0.25, "variance": 0.14, "high_probability": 0.75},
    )},
    {"kind": "ambiguous_single", "seed": 74001, "rate": 1.00,
     "variance": 0.005, "high_probability": 0.20},
)

HELDOUT_WORLDS = (
    {"kind": "single", "seed": 81001, "rate": 0.82, "variance": 0.25,
     "high_probability": 0.16},
    {"kind": "single", "seed": 81002, "rate": 1.25, "variance": 0.30,
     "high_probability": 0.24},
    {"kind": "single", "seed": 81003, "rate": 0.55, "variance": 0.42,
     "high_probability": 0.50},
    {"kind": "gaussian", "seed": 82001, "rate": 0.80, "variance": 0.25},
    {"kind": "gaussian", "seed": 82002, "rate": 1.40, "variance": 0.18},
    {"kind": "mixture", "seed": 83001, "components": (
        {"rate": 2.50, "variance": 0.18, "high_probability": 0.12},
        {"rate": 0.30, "variance": 0.18, "high_probability": 0.80},
    )},
    {"kind": "ambiguous_single", "seed": 84001, "rate": 0.70,
     "variance": 0.004, "high_probability": 0.24},
)


class _ShotLab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.calls = 0
        self.violated = False
        self._rngs = {}

    def _protocol_error(self, message):
        self.violated = True
        raise ValueError(message)

    def _rng(self, sequence_id, quadrature):
        key = (sequence_id, quadrature)
        if key not in self._rngs:
            identity = json.dumps(
                [int(self.spec["seed"]), sequence_id, quadrature],
                separators=(",", ":"),
            ).encode("utf-8")
            digest = hashlib.sha256(identity).digest()
            words = np.frombuffer(digest[:16], dtype=np.uint32)
            self._rngs[key] = np.random.default_rng(
                np.random.SeedSequence(words.tolist())
            )
        return self._rngs[key]

    def measure(self, sequence_id, shots_per_quadrature):
        if not isinstance(sequence_id, str):
            self._protocol_error("sequence_id must be a string")
        matches = [row for row in CONTROL_CATALOG if row["sequence_id"] == sequence_id]
        if len(matches) != 1:
            self._protocol_error("sequence_id is not in the public control pool")
        if isinstance(shots_per_quadrature, (bool, np.bool_)) or not isinstance(
            shots_per_quadrature, (int, np.integer)
        ):
            self._protocol_error("shots_per_quadrature must be an integer")
        shots = int(shots_per_quadrature)
        if not (
            MIN_SHOTS_PER_QUADRATURE <= shots <= MAX_SHOTS_PER_QUADRATURE
        ):
            self._protocol_error("shots_per_quadrature lies outside the public bounds")
        cost = 2 * shots
        if self.used + cost > SHOT_BUDGET:
            self.violated = True
            raise RuntimeError("shot budget exhausted")
        self.used += cost
        self.calls += 1
        control = matches[0]
        coherence = _true_coherence(self.spec, control)
        probability_x = float(np.clip(0.5 * (1.0 + coherence.real), 0.0, 1.0))
        probability_y = float(np.clip(0.5 * (1.0 + coherence.imag), 0.0, 1.0))
        return {
            "sequence_id": sequence_id,
            "shots_per_quadrature": shots,
            "x_plus_counts": int(np.count_nonzero(
                self._rng(sequence_id, "x").random(shots) < probability_x
            )),
            "y_plus_counts": int(np.count_nonzero(
                self._rng(sequence_id, "y").random(shots) < probability_y
            )),
            "shot_cost": cost,
        }


def _problem():
    return {
        **PUBLIC_PROBLEM,
        "control_catalog": [dict(row) for row in PUBLIC_PROBLEM["control_catalog"]],
        "parameter_bounds": {
            key: list(value) for key, value in PUBLIC_PROBLEM["parameter_bounds"].items()
        },
    }


def _submission(raw):
    if not isinstance(raw, dict):
        raise ValueError("submission must be a mapping")
    abstain = raw.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be boolean")
    confidence = raw.get("confidence", 0.0)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be numeric")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0,1]")
    if abstain:
        return {"abstain": True, "confidence": confidence}
    if raw.get("noise_model") != "single_telegraph":
        raise ValueError("noise_model must be single_telegraph or the submission must abstain")
    names_and_bounds = (
        ("switching_rate_per_us", RATE_BOUNDS),
        ("noise_variance_rad2_per_us2", VARIANCE_BOUNDS),
        ("high_state_probability", HIGH_STATE_PROBABILITY_BOUNDS),
    )
    parsed = {"abstain": False, "confidence": confidence,
              "noise_model": "single_telegraph"}
    for name, bounds in names_and_bounds:
        value = raw.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(name + " must be numeric")
        value = float(value)
        if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
            raise ValueError(name + " lies outside the public bounds")
        parsed[name] = value
    return parsed


def _parameter_score(guess, truth, log_scale):
    return math.exp(-abs(math.log(float(guess) / float(truth))) / log_scale)


def _single_metrics(spec, parsed):
    rate_score = _parameter_score(
        parsed["switching_rate_per_us"], spec["rate"], 0.45
    )
    variance_score = _parameter_score(
        parsed["noise_variance_rad2_per_us2"], spec["variance"], 0.45
    )
    probability_score = math.exp(
        -abs(parsed["high_state_probability"] - spec["high_probability"]) / 0.10
    )
    mechanism = (rate_score * variance_score * probability_score) ** (1.0 / 3.0)
    errors = []
    for control in HELDOUT_CONTROLS:
        predicted = telegraph_coherence(
            control,
            parsed["switching_rate_per_us"],
            parsed["noise_variance_rad2_per_us2"],
            parsed["high_state_probability"],
        )
        actual = _true_coherence(spec, control)
        errors.append(abs(predicted - actual) ** 2)
    rms = math.sqrt(sum(errors) / len(errors))
    return {
        "mechanism_score": mechanism,
        "rate_recovery_score": rate_score,
        "variance_recovery_score": variance_score,
        "skew_recovery_score": probability_score,
        "heldout_prediction_score": math.exp(-rms / 0.08),
        "heldout_complex_coherence_rmse": rms,
    }


ROW_DEFAULTS = {
    "valid": False,
    "supported": False,
    "abstained": True,
    "mechanism_score": 0.0,
    "rate_recovery_score": 0.0,
    "variance_recovery_score": 0.0,
    "skew_recovery_score": 0.0,
    "heldout_prediction_score": 0.0,
    "heldout_complex_coherence_rmse": 1.0,
    "false_discovery": False,
    "correct_refusal": False,
    "attempted_discovery": False,
    "confidence": 0.0,
    "confidence_calibration_score": 0.0,
    "shot_units": 0,
    "query_count": 0,
}


def _evaluate_world(candidate, spec, split, index):
    lab = _ShotLab(spec)
    row = dict(ROW_DEFAULTS)
    row.update({"split": split, "world_index": index, "world_kind": spec["kind"]})
    supported = (
        spec["kind"] == "single"
        and _family_separation_kl(spec) >= 4.5
        and _parameter_jacobian_rank(spec)[0] == 3
        and _profiled_gaussian_rmse(spec) >= 0.02
    )
    row["supported"] = supported
    try:
        parsed = _submission(candidate(_problem(), lab.measure))
        if lab.violated:
            raise RuntimeError("shot budget exceeded")
        row.update({
            "valid": True,
            "abstained": parsed["abstain"],
            "confidence": parsed["confidence"],
            "shot_units": lab.used,
            "query_count": lab.calls,
        })
        if supported and not parsed["abstain"]:
            row.update(_single_metrics(spec, parsed))
            row["attempted_discovery"] = True
        elif not supported and parsed["abstain"]:
            row.update({
                "mechanism_score": 1.0,
                "correct_refusal": True,
            })
        elif not supported:
            row["false_discovery"] = True
        target = row["mechanism_score"]
        row["confidence_calibration_score"] = 1.0 - (
            row["confidence"] - target
        ) ** 2
    except Exception as exc:  # noqa: BLE001 - candidate faults fail closed
        row["reason"] = "%s: %s" % (type(exc).__name__, exc)
        row["shot_units"] = lab.used
        row["query_count"] = lab.calls
    return row


def _score_split(candidate, worlds, split, reset_before_first=False):
    rows = []
    for index, spec in enumerate(worlds):
        if (index or reset_before_first) and hasattr(candidate, "reset_session"):
            candidate.reset_session()
        rows.append(_evaluate_world(candidate, spec, split, index))
    supported = [row for row in rows if row["supported"]]
    unsupported = [row for row in rows if not row["supported"]]
    raw = float(np.mean([row["mechanism_score"] for row in rows]))
    false_claim_count = sum(row["false_discovery"] for row in unsupported)
    claimed_mechanism_count = sum(not row["abstained"] for row in rows)
    precision_weighted_numerator = (
        sum(row["mechanism_score"] for row in supported) - false_claim_count
    )
    normalized = max(
        0.0,
        min(1.0, precision_weighted_numerator / float(len(supported))),
    )
    return {
        "rows": rows,
        "normalized": normalized,
        "raw": raw,
        "valid_count": sum(row["valid"] for row in rows),
        "world_count": len(rows),
        "supported_count": len(supported),
        "unsupported_count": len(unsupported),
        "false_claim_count": false_claim_count,
        "claimed_mechanism_count": claimed_mechanism_count,
        "precision_weighted_numerator": precision_weighted_numerator,
        "mechanism_recovery": float(np.mean(
            [row["mechanism_score"] for row in supported]
        )),
        "heldout_prediction": float(np.mean(
            [row["heldout_prediction_score"] for row in supported]
        )),
        "false_discovery_rate": (
            false_claim_count / float(claimed_mechanism_count)
            if claimed_mechanism_count else 0.0
        ),
        "unsupported_false_positive_rate": (
            false_claim_count / float(len(unsupported))
        ),
        "correct_refusal_rate": float(np.mean(
            [row["correct_refusal"] for row in unsupported]
        )),
        "attempted_discovery_rate": float(np.mean(
            [row["attempted_discovery"] for row in supported]
        )),
        "unwarranted_refusal_rate": float(np.mean(
            [row["abstained"] for row in supported]
        )),
        "confidence_calibration": float(np.mean(
            [row["confidence_calibration_score"] for row in rows]
        )),
        "mean_shot_units": float(np.mean([row["shot_units"] for row in rows])),
    }


def evaluate(discover_noise):
    development = _score_split(discover_noise, DEVELOPMENT_WORLDS, "development")
    heldout = _score_split(
        discover_noise, HELDOUT_WORLDS, "heldout", reset_before_first=True
    )
    development_valid = development["valid_count"] == development["world_count"]
    heldout_complete = heldout["valid_count"] == heldout["world_count"]

    def heldout_science(value):
        # Heldout validity never changes the public development selection score.
        # It only gates claims made from the heldout split itself.
        return value if heldout_complete else 0.0

    return {
        "combined_score": development["normalized"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": development["valid_count"] / development["world_count"],
        "raw_score": development["normalized"] if development_valid else 0.0,
        "development_raw_mechanism": development["raw"],
        "development_supported_world_count": development["supported_count"],
        "development_unsupported_world_count": development["unsupported_count"],
        "development_false_claim_count": development["false_claim_count"],
        "development_claimed_mechanism_count": development[
            "claimed_mechanism_count"
        ],
        "development_precision_weighted_numerator": development[
            "precision_weighted_numerator"
        ],
        "development_mechanism_recovery": development["mechanism_recovery"],
        "development_heldout_prediction_score": development["heldout_prediction"],
        "development_false_discovery_rate": development["false_discovery_rate"],
        "development_unsupported_false_positive_rate": development[
            "unsupported_false_positive_rate"
        ],
        "development_correct_refusal_rate": development["correct_refusal_rate"],
        "development_attempted_discovery_rate": development["attempted_discovery_rate"],
        "development_discovery_coverage": development["attempted_discovery_rate"],
        "development_unwarranted_refusal_rate": development["unwarranted_refusal_rate"],
        "development_confidence_calibration": development["confidence_calibration"],
        "development_mean_shot_units": development["mean_shot_units"],
        "heldout_science_complete": heldout_complete,
        "heldout_science_estimates_suppressed": not heldout_complete,
        "heldout_valid_count": heldout["valid_count"],
        "heldout_world_count": heldout["world_count"],
        "heldout_invalid_count": heldout["world_count"] - heldout["valid_count"],
        "heldout_feasibility_rate": heldout["valid_count"] / heldout["world_count"],
        "heldout_mechanism_score": heldout_science(heldout["normalized"]),
        "heldout_supported_world_count": heldout["supported_count"],
        "heldout_unsupported_world_count": heldout["unsupported_count"],
        "heldout_false_claim_count": heldout["false_claim_count"],
        "heldout_claimed_mechanism_count": heldout["claimed_mechanism_count"],
        "heldout_mechanism_recovery": heldout_science(heldout["mechanism_recovery"]),
        "heldout_prediction_score": heldout_science(heldout["heldout_prediction"]),
        "heldout_false_discovery_rate": heldout_science(heldout["false_discovery_rate"]),
        "heldout_unsupported_false_positive_rate": heldout_science(
            heldout["unsupported_false_positive_rate"]
        ),
        "heldout_correct_refusal_rate": heldout_science(heldout["correct_refusal_rate"]),
        "heldout_attempted_discovery_rate": heldout_science(
            heldout["attempted_discovery_rate"]
        ),
        "heldout_discovery_coverage": heldout_science(
            heldout["attempted_discovery_rate"]
        ),
        "heldout_unwarranted_refusal_rate": heldout_science(
            heldout["unwarranted_refusal_rate"]
        ),
        "per_instance": development["rows"] + heldout["rows"],
        "frontier_records": [],
    }
