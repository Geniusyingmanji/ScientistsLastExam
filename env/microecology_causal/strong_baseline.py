"""Author-informed reference: known equations, three structures and parameter box.

This is NOT autonomous discovery or the registered candidate baseline. Fitting
accepts public records only; no World/seed/private instance/holdout is accepted.
Kernel reuse is explicit model-family information, not a truth-parameter oracle.
"""

from dataclasses import fields
import itertools
import math
import time

import numpy as np
from scipy.optimize import least_squares
from scipy.special import ndtr

from .kernel import A, B, C, S, X, Y, Z, Kernel, Parameters, STRUCTURES
from .protocol import CHANNELS, NOISE_STD, validate_spec


PROTOCOL = "microecology-causal-author-reference-0.1"
PARAMETER_NAMES = tuple(field.name for field in fields(Parameters))
NOMINAL = {name: float(getattr(Parameters(), name)) for name in PARAMETER_NAMES}
ROLES = {"X": X, "Y": Y, "Z": Z}
DEFAULT_LIMITS = {"cpu_seconds": 60.0, "wall_seconds": 90.0,
                  "residual_attempts": 234, "attempts_per_local_fit": 72,
                  "local_fits": 3}


class _BudgetStop(RuntimeError):
    pass


def _limits(changes):
    if changes is not None and (not isinstance(changes, dict) or set(changes) - set(DEFAULT_LIMITS)):
        raise ValueError("unknown reference fit limit")
    value = dict(DEFAULT_LIMITS, **(changes or {}))
    for key, maximum in DEFAULT_LIMITS.items():
        item = value[key]
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("fit limits must be finite positive numbers")
        try:
            finite = math.isfinite(item)
        except OverflowError:
            finite = False
        if not finite or not 0 < item <= maximum or (type(maximum) is int and type(item) is not int):
            raise ValueError("fit limits may only reduce the declared finite ceiling")
    return value


def _model(value):
    if not isinstance(value, dict) or set(value) != {"structure", "peak_roles", "parameters"}:
        raise ValueError("model requires explicit structure, peak_roles and parameters")
    if value["structure"] not in STRUCTURES:
        raise ValueError("unknown reference structure")
    roles = value["peak_roles"]
    if not isinstance(roles, list) or len(roles) != 3 or any(not isinstance(role, str) for role in roles) or set(roles) != set(ROLES):
        raise ValueError("peak_roles must be a permutation of X,Y,Z")
    parameters = value["parameters"]
    if not isinstance(parameters, dict) or set(parameters) != set(PARAMETER_NAMES):
        raise ValueError("model parameters must specify the known eleven-dimensional box")
    checked = {}
    for name, nominal in NOMINAL.items():
        item = parameters[name]
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("invalid reference parameter")
        try:
            item = float(item)
        except (ValueError, OverflowError):
            raise ValueError("invalid reference parameter") from None
        if not math.isfinite(item) or not .88 * nominal <= item <= 1.12 * nominal:
            raise ValueError("reference parameter outside known box")
        checked[name] = item
    return {"structure": value["structure"], "peak_roles": list(roles), "parameters": checked}


def _simulate(model, spec, check=lambda: None):
    """Apply public event semantics to explicit candidate parameters only."""
    kernel = Kernel(Parameters(**model["parameters"]), model["structure"])
    indices = [A, B, C, S] + [ROLES[role] for role in model["peak_roles"]]
    state = np.zeros(8)
    state[:4] = [spec["initial"][key] for key in ("nutrient", "A", "B", "C")]
    times = np.asarray(spec["times_h"])
    result = np.empty((len(times), 8))
    current, temperature, event_index = 0.0, spec["temperature_c"], 0
    boundaries = sorted(set([0.0, times[-1]] + [event["time_h"] for event in spec["events"]]))
    for boundary in boundaries:
        check()
        selected = (times > current) & (times <= boundary)
        sampled, state = kernel.advance(state, boundary - current, temperature, times[selected] - current)
        result[selected] = sampled
        current = boundary
        while event_index < len(spec["events"]) and spec["events"][event_index]["time_h"] == boundary:
            event = spec["events"][event_index]
            if "feed" in event:
                state[S] += event["feed"]
            elif "deplete" in event:
                channel = CHANNELS.index(event["deplete"]["channel"])
                state[indices[channel]] *= 1 - event["deplete"]["fraction"]
            else:
                temperature = event["temperature_c"]
            event_index += 1
        result[times == boundary] = state
    check()
    return result[:, indices]


def predict(model, spec):
    """Predict latent clean concentrations from one frozen fitted JSON model."""
    return _simulate(_model(model), validate_spec(spec)).tolist()


def _records(records):
    if not isinstance(records, list) or not 1 <= len(records) <= 16:
        raise ValueError("fit needs 1..16 public records")
    checked = []
    for record in records:
        if not isinstance(record, dict) or not {"spec", "observation"} <= set(record) or set(record) - {"id", "spec", "observation", "cost"}:
            raise ValueError("only public record fields are accepted")
        if "id" in record and (not isinstance(record["id"], str) or not 1 <= len(record["id"]) <= 100):
            raise ValueError("invalid public record id")
        if "cost" in record and (type(record["cost"]) is not int or not 1 <= record["cost"] <= 54):
            raise ValueError("invalid public record cost")
        spec = validate_spec(record["spec"])
        observation = record["observation"]
        if not isinstance(observation, dict) or set(observation) != {"axis", "channels", "values"}:
            raise ValueError("observation must contain public axis/channels/values only")
        axis = observation["axis"]
        if (observation["channels"] != list(CHANNELS) or not isinstance(axis, list) or
                any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in axis) or axis != spec["times_h"]):
            raise ValueError("public observation channels/axis mismatch")
        values = observation["values"]
        if not isinstance(values, list) or len(values) != len(spec["times_h"]) or any(not isinstance(row, list) or len(row) != 7 for row in values):
            raise ValueError("observation has invalid shape")
        for row in values:
            for item in row:
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    raise ValueError("observations must be finite public numbers")
                try:
                    finite = math.isfinite(item)
                except OverflowError:
                    finite = False
                if not finite or not 0 <= item <= 1e6:
                    raise ValueError("observations must be finite nonnegative concentrations")
        checked.append((spec, np.asarray(values, dtype=float)))
    return checked


def fit(records, *, limits=None):
    """Fit using ONLY public records and reducible computation ceilings.

    Results and fitted class/mapping are operator-private. CPU deadlines are
    cooperative, checked before each bounded ODE segment; one solve can finish
    after the threshold. Attempts include finite-difference Jacobian calls.
    """
    start_cpu, start_wall = time.process_time(), time.perf_counter()
    limits = _limits(limits)
    data = _records(records)
    attempts, completed, trajectories = 0, 0, 0
    best, screening, local = None, [], []
    stop_reason = None

    def check():
        if time.process_time() - start_cpu >= limits["cpu_seconds"]:
            raise _BudgetStop("cpu_limit")
        if time.perf_counter() - start_wall >= limits["wall_seconds"]:
            raise _BudgetStop("wall_limit")

    def evaluate(model, local_check=lambda: None):
        nonlocal attempts, completed, trajectories, best
        check()
        local_check()
        if attempts >= limits["residual_attempts"]:
            raise _BudgetStop("residual_attempt_limit")
        attempts += 1
        residual = []
        def guard():
            check()
            local_check()
        for spec, observed in data:
            guard()
            trajectories += 1
            clean = _simulate(model, spec, guard)
            sigma = np.asarray(NOISE_STD)
            z = clean / sigma
            mean = clean * ndtr(z) + sigma * np.exp(-.5*z*z) / math.sqrt(2*math.pi)
            residual.append(((mean - observed) / sigma).ravel())
        values = np.concatenate(residual)
        loss = float(np.mean(values*values))
        completed += 1
        if best is None or loss < best["training_noise_weighted_mse"]:
            best = {"model": _model(model), "training_noise_weighted_mse": loss}
        return values, loss

    try:
        for structure in STRUCTURES:
            for roles in itertools.permutations(ROLES):
                model = {"structure": structure, "peak_roles": list(roles), "parameters": dict(NOMINAL)}
                _, loss = evaluate(model)
                screening.append({"structure": structure, "peak_roles": list(roles), "training_noise_weighted_mse": loss})
        candidates = [min((row for row in screening if row["structure"] == structure), key=lambda row: row["training_noise_weighted_mse"]) for structure in STRUCTURES]
        for ordinal, candidate in enumerate(candidates[:limits["local_fits"]]):
            check()
            structure = candidate["structure"]
            active = [name for name in PARAMETER_NAMES if name != "inhibition_consumer" or structure == "inhibitory_feedback"]
            local_start, local_wall, initial_attempts = time.process_time(), time.perf_counter(), attempts
            remaining = limits["local_fits"] - ordinal
            cpu_share = max(0., limits["cpu_seconds"] - (local_start - start_cpu)) / remaining
            wall_share = max(0., limits["wall_seconds"] - (local_wall - start_wall)) / remaining
            entry = {"structure": structure, "peak_roles": candidate["peak_roles"], "active_dimensions": len(active),
                     "converged": False, "status": "started", "solver_status": None, "jacobian_rank": None,
                     "best_training_noise_weighted_mse": candidate["training_noise_weighted_mse"],
                     "best_parameters": dict(NOMINAL)}

            def local_check():
                if time.process_time() - local_start >= cpu_share or time.perf_counter() - local_wall >= wall_share:
                    raise _BudgetStop("local_time_share")

            def residual(multipliers):
                if attempts - initial_attempts >= limits["attempts_per_local_fit"]:
                    raise _BudgetStop("local_attempt_limit")
                model = {"structure": structure, "peak_roles": candidate["peak_roles"], "parameters": dict(NOMINAL)}
                for name, multiplier in zip(active, multipliers):
                    model["parameters"][name] = float(NOMINAL[name] * multiplier)
                values, loss = evaluate(model, local_check)
                if loss < entry["best_training_noise_weighted_mse"]:
                    entry["best_training_noise_weighted_mse"] = loss
                    entry["best_parameters"] = dict(model["parameters"])
                return values

            try:
                result = least_squares(residual, np.ones(len(active)), bounds=(.88,1.12),
                                       max_nfev=12, ftol=1e-6, xtol=1e-6, gtol=1e-6)
                entry.update(converged=bool(result.success), status="converged" if result.success else "optimizer_iteration_limit",
                             solver_status=int(result.status), jacobian_rank=int(np.linalg.matrix_rank(result.jac)))
            except _BudgetStop as error:
                entry["status"] = str(error)
                if str(error) in ("cpu_limit", "wall_limit", "residual_attempt_limit"):
                    stop_reason = str(error)
            except (RuntimeError, ValueError, FloatingPointError, OverflowError) as error:
                entry["status"] = "numerical_failure"
                entry["error_type"] = type(error).__name__
            entry.update(residual_attempts=attempts-initial_attempts, cpu_seconds=time.process_time()-local_start)
            local.append(entry)
            if stop_reason:
                break
    except _BudgetStop as error:
        stop_reason = str(error)
    except (RuntimeError, ValueError, FloatingPointError, OverflowError) as error:
        stop_reason = "screening_numerical_failure:" + type(error).__name__
    converged = bool(best and any(row["structure"] == best["model"]["structure"] and
                                  row["peak_roles"] == best["model"]["peak_roles"] and row["converged"] for row in local))
    return {"protocol": PROTOCOL, "author_informed": True, "autonomous_discovery": False,
            "limits": limits, "record_count": len(data), "model": best["model"] if best else None,
            "training_noise_weighted_mse": best["training_noise_weighted_mse"] if best else None,
            "converged": converged, "status": "no_model" if best is None else "converged" if converged else "best_available_unconverged",
            "stop_reason": stop_reason or ("local_fits_finished" if len(local) == limits["local_fits"] else "screening_only"),
            "screening": screening, "local_fits": local,
            "usage": {"residual_attempts": attempts, "completed_residuals": completed, "trajectory_attempts": trajectories,
                      "cpu_seconds": time.process_time()-start_cpu, "wall_seconds": time.perf_counter()-start_wall},
            "limitations": "Knows structure menu, exact equation family/yields/temperature law and parameter box. Fits only one screen-selected peak mapping per structure; local optimization can miss a better mapping or optimum. Inactive parameters and restricted observational equivalences remain unidentifiable. Training fit/convergence is not mechanism certification."}
