"""Author-informed, single-start continuous-family reference from public records.

The force family is supplied by the author; candidates do not receive this prior.
This module never imports a World, private kernel, seed, stratum or query target.
Its fitted point is not a class decision or a parameter-uncertainty calculation.
"""

import math
import numbers
import time

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

from .protocol import CHANNELS, NOISE_STD, RESOLUTION_RADIUS, validate_spec


PROTOCOL = "orbital-author-strong-reference-0.1"
PARAMETER_NAMES = ("mu", "p", "drag")
INITIAL = (1.0, 2.0, 0.03)
LOWER = (0.6, 1.0, 0.0)
UPPER = (1.4, 3.0, 0.15)
DEFAULT_LIMITS = {
    "cpu_seconds": 30.0, "wall_seconds": 60.0, "max_nfev": 30,
    "residual_calls": 160, "rhs_evaluations": 1200000,
    "rhs_per_trajectory": 60000,
}
PREDICTION_LIMITS = {"cpu_seconds": 10.0, "wall_seconds": 20.0,
                     "rhs_evaluations": 60000, "rhs_per_trajectory": 60000}
RTOL, ATOL, MAX_STEP = 1e-8, 1e-10, 0.05


class _BudgetStop(RuntimeError):
    pass


class _NumericalFailure(RuntimeError):
    pass


def _finite(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError("expected a finite real number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError("expected a finite real number") from None
    if not math.isfinite(result):
        raise ValueError("expected a finite real number")
    return result


def _limits(changes=None, maximum=None):
    maximum = DEFAULT_LIMITS if maximum is None else maximum
    if changes is not None and (not isinstance(changes, dict) or set(changes) - set(maximum)):
        raise ValueError("unknown reference limit")
    result = dict(maximum, **(changes or {}))
    for key, ceiling in maximum.items():
        value = _finite(result[key])
        if not 0 < value <= ceiling or (type(ceiling) is int and type(result[key]) is not int):
            raise ValueError("limits may only reduce the declared positive ceiling")
    return result


def _model(model):
    if not isinstance(model, dict) or set(model) != set(PARAMETER_NAMES):
        raise ValueError("model must contain only mu, p and drag")
    values = [_finite(model[name]) for name in PARAMETER_NAMES]
    if any(value < low or value > high for value, low, high in zip(values, LOWER, UPPER)):
        raise ValueError("model outside author-declared continuous parameter bounds")
    return dict(zip(PARAMETER_NAMES, values))


class _Budget:
    def __init__(self, limits):
        self.limits = limits
        self.cpu_start, self.wall_start = time.process_time(), time.monotonic()
        self.residual_calls = self.completed_residuals = 0
        self.trajectory_attempts = self.completed_trajectories = self.rhs_evaluations = 0

    def check(self):
        if time.process_time() - self.cpu_start >= self.limits["cpu_seconds"]:
            raise _BudgetStop("cpu_limit")
        if time.monotonic() - self.wall_start >= self.limits["wall_seconds"]:
            raise _BudgetStop("wall_limit")

    def residual(self):
        self.check()
        if self.residual_calls >= self.limits["residual_calls"]:
            raise _BudgetStop("residual_call_limit")
        self.residual_calls += 1

    def rhs(self, local_count):
        self.check()
        if local_count >= self.limits["rhs_per_trajectory"]:
            raise _BudgetStop("trajectory_rhs_limit")
        if self.rhs_evaluations >= self.limits["rhs_evaluations"]:
            raise _BudgetStop("fit_rhs_limit")
        self.rhs_evaluations += 1

    def usage(self):
        return {
            "cpu_seconds": time.process_time() - self.cpu_start,
            "wall_seconds": time.monotonic() - self.wall_start,
            "residual_calls": self.residual_calls,
            "completed_residuals": self.completed_residuals,
            "trajectory_attempts": self.trajectory_attempts,
            "completed_trajectories": self.completed_trajectories,
            "rhs_evaluations": self.rhs_evaluations,
        }


def _simulate(model, spec, budget):
    """Independent RK45 evolution; ordered impulses precede same-time readouts."""
    budget.check()
    budget.trajectory_attempts += 1
    mu, power, drag = (model[name] for name in PARAMETER_NAMES)
    times = np.asarray(spec["times"], dtype=float)
    state = np.asarray(spec["position"] + spec["velocity"], dtype=float)
    output = np.empty((len(times), 4), dtype=float)
    output[times == 0] = state
    local_rhs, current, event_index = 0, 0.0, 0

    def rhs(time_coordinate, value):
        nonlocal local_rhs
        budget.rhs(local_rhs)
        local_rhs += 1
        position, velocity = value[:2], value[2:]
        softened_radius = math.sqrt(float(position @ position) + RESOLUTION_RADIUS ** 2)
        acceleration = -mu * position / softened_radius ** (power + 1) - drag * velocity
        return np.concatenate((velocity, acceleration))

    stops = sorted(set([event["time"] for event in spec["impulses"]] + [times[-1]]))
    for stop in stops:
        budget.check()
        selected = (times > current) & (times <= stop)
        requested = times[selected]
        if stop > current:
            evaluation = requested.tolist()
            if not evaluation or evaluation[-1] != stop:
                evaluation.append(stop)
            solution = solve_ivp(rhs, (current, stop), state, method="RK45",
                                 t_eval=evaluation, rtol=RTOL, atol=ATOL, max_step=MAX_STEP)
            budget.check()
            if not solution.success or not np.isfinite(solution.y).all():
                raise _NumericalFailure("reference_integration_failed")
            output[selected] = solution.y[:, :len(requested)].T
            state = solution.y[:, -1].copy()
        current = stop
        if event_index < len(spec["impulses"]) and spec["impulses"][event_index]["time"] == stop:
            state[2:] += spec["impulses"][event_index]["delta_v"]
            event_index += 1
        output[times == stop] = state
    budget.check()
    if not np.isfinite(output).all():
        raise _NumericalFailure("nonfinite_reference_prediction")
    budget.completed_trajectories += 1
    return output


def predict_with_diagnostics(model, spec, *, limits=None):
    """Return predictions plus actual work; bounded errors propagate to evaluator."""
    limits = _limits(limits, PREDICTION_LIMITS)
    model, spec = _model(model), validate_spec(spec)
    budget = _Budget(limits)
    try:
        values = _simulate(model, spec, budget)
    except (_BudgetStop, _NumericalFailure) as error:
        error.usage, error.limits = budget.usage(), limits
        raise
    return {"values": values.tolist(), "usage": budget.usage(), "limits": limits}


def predict(model, spec, *, limits=None):
    return predict_with_diagnostics(model, spec, limits=limits)["values"]


def _dynamic_rows(spec):
    times = np.asarray(spec["times"])
    assigned = np.isin(times, [event["time"] for event in spec["impulses"]])
    return (times > 0) & ~assigned


def _records(records):
    if not isinstance(records, list) or not 1 <= len(records) <= 6:
        raise ValueError("fit requires 1..6 public records")
    checked = []
    for record in records:
        if (not isinstance(record, dict) or not {"spec", "observation"} <= set(record)
                or set(record) - {"id", "spec", "observation", "cost"}):
            raise ValueError("only public record fields are accepted")
        if "id" in record and (not isinstance(record["id"], str) or not 1 <= len(record["id"]) <= 100):
            raise ValueError("invalid public record id")
        if "cost" in record and (type(record["cost"]) is not int or not 1 <= record["cost"] <= 91):
            raise ValueError("invalid public record cost")
        spec = validate_spec(record["spec"])
        observation = record["observation"]
        if not isinstance(observation, dict) or set(observation) != {"axis", "channels", "values"}:
            raise ValueError("observation must contain only public axis, channels and values")
        axis, values = observation["axis"], observation["values"]
        if (not isinstance(axis, list) or [_finite(x) for x in axis] != spec["times"]
                or observation["channels"] != list(CHANNELS)):
            raise ValueError("public observation axis/channels mismatch")
        if (not isinstance(values, list) or len(values) != len(axis)
                or any(not isinstance(row, list) or len(row) != 4 for row in values)):
            raise ValueError("public observation matrix shape mismatch")
        values = np.asarray([[_finite(x) for x in row] for row in values])
        selected = _dynamic_rows(spec)
        if not selected.any():
            raise ValueError("each source needs a nonzero, non-impulse-boundary observation")
        checked.append((spec, values, selected))
    return checked


def fit(records, *, limits=None):
    """One optimizer call, one fixed start; preserve failure and finite last iterate.

    Only completed residual evaluations can supply an interrupted finite point.
    The last point is retained by chronology, never by choosing a lower loss.
    Finite-difference residual calls count toward the hard call ceiling as well.
    """
    limits = _limits(limits)
    checked = _records(records)
    budget = _Budget(limits)
    last = {"model": None, "loss": None}
    stop_reason, convergence, status, selected_by = "not_started", False, None, None
    reported_nfev = None

    def residual(values):
        budget.residual()
        model = _model(dict(zip(PARAMETER_NAMES, values)))
        errors = [(_simulate(model, spec, budget)[selected] - observed[selected]) / NOISE_STD
                  for spec, observed, selected in checked]
        result = np.concatenate([error.ravel() for error in errors])
        with np.errstate(over="ignore", invalid="ignore"):
            loss = float(np.mean(result ** 2))
        if not np.isfinite(result).all() or not math.isfinite(loss):
            raise _NumericalFailure("nonfinite_training_residual")
        budget.check()
        budget.completed_residuals += 1
        last.update(model=model, loss=loss)
        return result

    try:
        result = least_squares(residual, INITIAL, bounds=(LOWER, UPPER), method="trf",
                               jac="2-point", max_nfev=limits["max_nfev"])
        budget.check()
        endpoint = _model(dict(zip(PARAMETER_NAMES, result.x)))
        loss = float(np.mean(result.fun ** 2))
        if not math.isfinite(loss):
            raise _NumericalFailure("nonfinite_optimizer_endpoint")
        last.update(model=endpoint, loss=loss)
        convergence, status = bool(result.success), int(result.status)
        reported_nfev = int(result.nfev)
        stop_reason = "optimizer_converged" if convergence else "optimizer_nfev_limit"
        selected_by = "single_optimizer_endpoint"
    except _BudgetStop as error:
        stop_reason = str(error)
    except (_NumericalFailure, ValueError, RuntimeError, FloatingPointError, OverflowError) as error:
        stop_reason = "numerical_failure:" + type(error).__name__
    if selected_by is None and last["model"] is not None:
        selected_by = "last_completed_residual_chronological_not_best"
    return {
        "protocol": PROTOCOL, "author_informed": True, "autonomous_discovery": False,
        "model": last["model"], "training_noise_weighted_mse": last["loss"],
        "converged": convergence, "stop_reason": stop_reason,
        "optimizer_status": status, "optimizer_reported_nfev": reported_nfev,
        "retained_point_rule": selected_by, "optimizer_starts": 1,
        "limits": limits, "usage": budget.usage(),
        "training_rows": sum(int(selected.sum()) for _, _, selected in checked),
        "excluded_t0_and_exact_impulse_rows": sum(len(spec["times"]) - int(selected.sum())
                                                   for spec, _, selected in checked),
        "uncertainty": "single fitted point only; no parameter or model uncertainty",
    }
