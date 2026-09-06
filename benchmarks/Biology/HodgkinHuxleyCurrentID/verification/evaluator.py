"""Deterministic voltage-clamp channel oracle.

A three-current Hodgkin-Huxley membrane answers voltage steps with ionic current
traces. The public gating kinetics are the 1952 classic; the hidden state is eight
bounded parameters (conductances, reversal potentials, and an activation shift per
voltage-gated channel). Two worlds put an extra unmodelled current on the membrane —
a fast-inactivating A-type potassium conductance, or a rectifying leak — and a
parameter claim on those worlds is a false discovery.
"""

from __future__ import annotations

import math

import numpy as np

DIFFICULTY = 1

_DIFFICULTY_LADDER = {
    1: {"noise": 0.005, "extra_scale": 1.0},
    2: {"noise": 0.010, "extra_scale": 1.4},
    3: {"noise": 0.018, "extra_scale": 1.9},
}

PARAMETER_NAMES = ("gNa", "gK", "gL", "ENa", "EK", "EL", "sNa", "sK")
PARAMETER_BOUNDS = np.asarray([
    [60.0, 140.0], [20.0, 60.0], [0.1, 1.0], [40.0, 70.0],
    [-95.0, -70.0], [-70.0, -45.0], [-10.0, 10.0], [-10.0, 10.0],
])
STEP_BOUNDS = (-70.0, 60.0)
DURATIONS = (5.0, 10.0, 20.0, 30.0)
SAMPLE_DT = 0.25
HOLDING = -80.0
PROTOCOL_COST = 1
BUDGET_UNITS = 8

_BASE_DEVELOPMENT_SPECS = (
    (27011, "supported"), (27017, "supported"), (27023, "supported"),
    (27029, "supported"), (27031, "supported"),
    (27037, "a_type"), (27041, "rectifying"),
)
HELDOUT_SPECS = (
    (28007, "supported"), (28013, "supported"), (28017, "supported"),
    (28021, "a_type"), (28025, "rectifying"),
)


def _difficulty_profile(level=None):
    level = DIFFICULTY if level is None else int(level)
    if level not in _DIFFICULTY_LADDER:
        raise ValueError("difficulty %d has no measured profile" % level)
    return _DIFFICULTY_LADDER[level]


def _x_over_expm1(x):
    """The singular classic rate-constant shape, in numerically stable form."""
    if abs(x) < 1e-7:
        return 1.0 - 0.5 * x
    return x / math.expm1(x)


def alpha_n(v):
    return 0.1 * _x_over_expm1((10.0 - v) / 10.0)


def beta_n(v):
    return 0.125 * math.exp(-v / 80.0)


def alpha_m(v):
    return _x_over_expm1((25.0 - v) / 10.0)


def beta_m(v):
    return 4.0 * math.exp(-v / 18.0)


def alpha_h(v):
    return 0.07 * math.exp(-v / 20.0)


def beta_h(v):
    return 1.0 / (math.exp((30.0 - v) / 10.0) + 1.0)


def _gating_traces(voltage, duration, sNa=0.0, sK=0.0):
    """Classic gating kinetics at fixed voltage, in closed form.

    At a clamped voltage every gating equation is linear, dx/dt = (alpha+beta)*(x_inf
    - x), so the exact solution is x_inf - (x_inf - x_0) exp(-t/tau) from the holding
    steady state — identical to an infinitesimal-step RK4 integration and fast.
    """
    time = np.arange(1, int(round(duration / SAMPLE_DT)) + 1) * SAMPLE_DT

    def trace(alpha_fn, beta_fn, veff):
        rate_step = alpha_fn(veff) + beta_fn(veff)
        steady = alpha_fn(veff) / rate_step
        hold_veff = HOLDING - (voltage - veff)  # apply the same shift at holding
        rate_hold = alpha_fn(hold_veff) + beta_fn(hold_veff)
        start_value = alpha_fn(hold_veff) / rate_hold
        return steady + (start_value - steady) * np.exp(-rate_step * time)

    veff_na, veff_k = voltage - sNa, voltage - sK
    m = trace(alpha_m, beta_m, veff_na)
    h = trace(alpha_h, beta_h, veff_na)
    n = trace(alpha_n, beta_n, veff_k)
    return time, np.column_stack((m, h, n))


def ionic_current(parameters, voltage, gating, world_kind="supported", extra_scale=1.0):
    gNa, gK, gL, ENa, EK, EL, sNa, sK = parameters
    m, h, n = gating[:, 0], gating[:, 1], gating[:, 2]
    current = (gNa * m ** 3 * h * (voltage - ENa)
               + gK * n ** 4 * (voltage - EK)
               + gL * (voltage - EL))
    if world_kind == "a_type":
        # Fast-inactivating A-type potassium outside the public family.
        a_inf = 1.0 / (1.0 + math.exp(-(voltage + 15.0) / 8.0))
        b_inf = 1.0 / (1.0 + math.exp((voltage + 60.0) / 12.0))
        time = np.arange(1, len(m) + 1) * SAMPLE_DT
        a = a_inf * (1.0 - np.exp(-time / 1.5))
        b = b_inf * np.exp(-time / 220.0) + 0.05
        current = current + 18.0 * extra_scale * a ** 3 * b * (voltage - EK)
    elif world_kind == "rectifying":
        current = current + 3.5 * extra_scale * (voltage - EL) * np.abs(
            voltage - EL) / 40.0
    return current


def _sample_parameters(rng):
    low, high = PARAMETER_BOUNDS[:, 0], PARAMETER_BOUNDS[:, 1]
    return low + rng.uniform(size=len(PARAMETER_BOUNDS)) * (high - low)


def _world(spec):
    seed, kind = spec
    profile = _difficulty_profile()
    rng = np.random.default_rng(int(seed))
    return {"seed": int(seed), "kind": kind,
            "parameters": _sample_parameters(rng),
            "noise": profile["noise"], "extra_scale": profile["extra_scale"]}


def problem_statement(world):
    del world
    return {
        "parameters": list(PARAMETER_NAMES),
        "parameter_bounds": PARAMETER_BOUNDS.copy(),
        "gating_equations": {
            "alpha_n": "0.01*(10-V)/(exp((10-V)/10)-1)",
            "beta_n": "0.125*exp(-V/80)",
            "alpha_m": "0.1*(25-V)/(exp((25-V)/10)-1)",
            "beta_m": "4*exp(-V/18)",
            "alpha_h": "0.07*exp(-V/20)",
            "beta_h": "1/(exp((30-V)/10)+1)",
        },
        "current_equation": "I = gNa*m^3*h*(V-ENa) + gK*n^4*(V-EK) + gL*(V-EL) with V replaced by V-sNa (sK) inside the sodium (potassium) gating",
        "holding_potential_mV": HOLDING,
        "step_bounds_mV": list(STEP_BOUNDS),
        "durations_ms": list(DURATIONS),
        "sample_dt_ms": SAMPLE_DT,
        "protocol_cost": PROTOCOL_COST,
        "budget_units": BUDGET_UNITS,
        "noise_note": "Gaussian noise scales with the peak absolute current of each trace",
        "refusal_note": "membranes carrying currents outside the three-current family must be refused",
    }


def _clean_current(world, voltage, duration):
    parameters = world["parameters"]
    time, gating = _gating_traces(voltage, duration,
                                  sNa=parameters[6], sK=parameters[7])
    current = ionic_current(parameters, voltage, gating,
                            world_kind=world["kind"],
                            extra_scale=world["extra_scale"])
    return time, current


class _Amplifier:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False

    def voltage_step(self, step_potential_mV, duration_ms):
        try:
            voltage = float(step_potential_mV)
            duration = float(duration_ms)
            if not math.isfinite(voltage) or not STEP_BOUNDS[0] <= voltage <= STEP_BOUNDS[1]:
                self.violated = True
                raise ValueError("step potential outside allowed bounds")
            if duration not in DURATIONS:
                self.violated = True
                raise ValueError("duration must be one of the published values")
            if self.used + PROTOCOL_COST > BUDGET_UNITS:
                self.violated = True
                raise RuntimeError("protocol budget exceeded")
            self.used += PROTOCOL_COST
            self.calls += 1
            time, current = _clean_current(self.world, voltage, duration)
            rng = np.random.default_rng(
                self.world["seed"] + int((voltage + 200.0) * 101.0) + int(duration * 7.0)
                + 13 * self.calls)
            sigma = self.world["noise"] * float(np.abs(current).max()) + 0.02
            observed = current + rng.normal(0.0, sigma, current.shape)
            return {"step_potential_mV": voltage, "duration_ms": duration,
                    "time_ms": time, "current": observed,
                    "noise_std": sigma, "budget_cost": PROTOCOL_COST}
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
        if submission.get("parameters") is not None:
            raise ValueError("abstention requires empty parameters")
        return None, confidence, True
    parameters = np.asarray(submission.get("parameters"), dtype=float).reshape(-1)
    if parameters.shape != (8,) or np.any(~np.isfinite(parameters)):
        raise ValueError("parameters must be a finite length-8 row")
    if np.any(parameters < PARAMETER_BOUNDS[:, 0] - 1e-6) or \
            np.any(parameters > PARAMETER_BOUNDS[:, 1] + 1e-6):
        raise ValueError("parameters outside public bounds")
    return parameters, confidence, False


def _parameter_score(proposed, truth):
    span = PARAMETER_BOUNDS[:, 1] - PARAMETER_BOUNDS[:, 0]
    error = (proposed - truth) / span
    return float(math.exp(-8.0 * math.sqrt(float(np.mean(error ** 2)))))


def _prediction_score(world, parameters):
    voltage, duration = 45.0, 20.0
    _, truth = _clean_current(world, voltage, duration)
    time, gating = _gating_traces(voltage, duration,
                                  sNa=parameters[6], sK=parameters[7])
    predicted = ionic_current(parameters, voltage, gating)
    scale = float(np.abs(truth).max())
    return float(math.exp(-6.0 * float(np.abs(predicted - truth).max()) / max(scale, 1e-9)))


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "abstained": False,
            "mechanism_score": 0.0, "parameter_score": 0.0,
            "prediction_score": 0.0, "false_discovery": False,
            "correct_refusal": False, "confidence_score": 0.0, "budget_used": 0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    amplifier = _Amplifier(world)
    try:
        submission = candidate(problem_statement(world), amplifier.voltage_step,
                               BUDGET_UNITS)
        parameters, confidence, abstain = _validate(submission)
        if amplifier.violated:
            raise ValueError("amplifier contract violated")
        supported = world["kind"] == "supported"
        if supported and not abstain:
            parameter_score = _parameter_score(parameters, world["parameters"])
            prediction_score = _prediction_score(world, parameters)
            mechanism = float(math.sqrt(max(parameter_score, 1e-9)
                                        * max(prediction_score, 1e-9)))
        elif supported:
            parameter_score = prediction_score = mechanism = 0.0
        else:
            correct = bool(abstain)
            parameter_score = prediction_score = mechanism = 1.0 if correct else 0.0
        target = 1.0 if (supported != abstain or (not supported and abstain)) else 0.0
        row.update({"valid": True, "abstained": abstain,
                    "mechanism_score": mechanism,
                    "parameter_score": parameter_score,
                    "prediction_score": prediction_score,
                    "false_discovery": bool(not supported and not abstain),
                    "correct_refusal": bool(not supported and abstain),
                    "confidence_score": 1.0 - (confidence - target) ** 2,
                    "budget_used": amplifier.used})
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
        "parameter_score": float(np.mean([r["parameter_score"] for r in supported])) if supported else 0.0,
        "prediction_score": float(np.mean([r["prediction_score"] for r in supported])) if supported else 0.0,
        "false_count": sum(r["false_discovery"] for r in unsupported),
        "refusal_count": sum(r["correct_refusal"] for r in unsupported),
        "attempt_count": sum(not r["abstained"] for r in supported),
        "supported_count": len(supported), "unsupported_count": len(unsupported),
    }


def evaluate(recover_channel_parameters):
    development = [_evaluate_world(recover_channel_parameters, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(recover_channel_parameters, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development, _BASE_DEVELOPMENT_SPECS), _summary(heldout, HELDOUT_SPECS)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "development_parameter_score": dev["parameter_score"],
        "development_prediction_score": dev["prediction_score"],
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
