"""A heat-equation baseline fitted exclusively to public experimental records.

This standalone module imports no world, simulator, instance seed or hidden
parameter source. Equations, coefficient bounds, controls and noise below are
from the public heat-transport description. Its independently chosen 64-interval
spatial approximation is part of the baseline, not an operator-grid dependency.

``baseline(records, spec)`` has the shared baseline interface. For reuse outside
that interface, ``fit_public_records`` returns a JSON-safe frozen fit, including
timing and local identifiability diagnostics; ``predict_fitted`` predicts from
that fit and a public experiment. No query outcome participates in fitting.
"""
import functools
import json
import math
import numbers
import time

import numpy as np
from scipy.linalg import eigh_tridiagonal, solve_banded
from scipy.optimize import least_squares


VERSION = "heat-public-pde-baseline-0.1.0"
CHANNELS = ("probe_1_temperature", "probe_2_temperature", "probe_3_temperature")
NOISE_STD = 0.04
MAX_RECORDS = 256
MAX_FIT_RECORDS = 16
GRID_INTERVALS = 64
MAX_NFEV = 60
_FIELDS = {"times", "probes", "initial_temperature", "boundary_temperatures",
           "ambient_temperature", "heaters", "flow", "cooling"}
_NAMES = ("diffusivity_left", "diffusivity_right", "interface_position", "flow_gain", "loss")
_LOWER = np.array([0.006, 0.006, 0.3, 0.02, 0.01])
_UPPER = np.array([0.06, 0.06, 0.7, 0.10, 0.08])
_PRIOR = (_LOWER + _UPPER) / 2
_X = np.linspace(0.0, 1.0, GRID_INTERVALS + 1)
_DX = 1.0 / GRID_INTERVALS


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(name + " must be a finite real number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(name + " must be a finite real number") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(name + " outside the public range")
    return value


def _array(value, name, minimum, maximum, low, high, ordered=False):
    if not isinstance(value, (list, tuple)) or not minimum <= len(value) <= maximum:
        raise ValueError(name + " has invalid array length")
    result = [_number(item, name, low, high) for item in value]
    if ordered and any(right <= left for left, right in zip(result, result[1:])):
        raise ValueError(name + " must strictly increase")
    return result


def _spec(spec):
    """Duplicate only the public experiment schema, with bounded numeric work."""
    if not isinstance(spec, dict) or set(spec) != _FIELDS:
        raise ValueError("experiment fields do not match the public heat schema")
    result = {
        "times": _array(spec["times"], "times", 1, 25, 0, 30, True),
        "probes": _array(spec["probes"], "probes", 3, 3, .05, .95, True),
        "initial_temperature": _number(spec["initial_temperature"], "initial_temperature", 0, 80),
        "boundary_temperatures": _array(spec["boundary_temperatures"], "boundary_temperatures", 2, 2, 0, 80),
        "ambient_temperature": _number(spec["ambient_temperature"], "ambient_temperature", 0, 40),
        "flow": _number(spec["flow"], "flow", -1, 1),
        "cooling": _number(spec["cooling"], "cooling", 0, 3),
        "heaters": [],
    }
    if not isinstance(spec["heaters"], (list, tuple)) or len(spec["heaters"]) > 3:
        raise ValueError("heaters must contain zero to three entries")
    for heater in spec["heaters"]:
        if not isinstance(heater, dict) or set(heater) != {"position", "power", "width"}:
            raise ValueError("heater requires position, power, width")
        result["heaters"].append({"position": _number(heater["position"], "heater position", .05, .95),
                                   "power": _number(heater["power"], "heater power", 0, 8),
                                   "width": _number(heater["width"], "heater width", .04, .2)})
    if sum(heater["power"] for heater in result["heaters"]) > 12:
        raise ValueError("sum of heater powers must not exceed 12 K/s")
    return result


def _prepare(spec):
    source = np.zeros(GRID_INTERVALS - 1)
    for heater in spec["heaters"]:
        source += heater["power"] * np.exp(-.5 * ((_X[1:-1] - heater["position"]) / heater["width"])**2)
    return spec, source


def _trajectory(parameters, prepared):
    """Finite-volume resistance and centered advection for the public PDE."""
    left_d, right_d, interface, gain, loss_rate = parameters
    spec, source = prepared
    left_fraction = np.clip((interface - _X[:-1]) / _DX, 0, 1)
    face = 1.0 / (left_fraction / left_d + (1 - left_fraction) / right_d) / _DX**2
    advection = spec["flow"] * gain / (2 * _DX)
    loss = spec["cooling"] * loss_rate
    diagonal = face[:-1] + face[1:] + loss
    lower, upper = -face[1:-1] - advection, -face[1:-1] + advection
    forcing = source + loss * spec["ambient_temperature"]
    forcing[0] += (face[0] + advection) * spec["boundary_temperatures"][0]
    forcing[-1] += (face[-1] - advection) * spec["boundary_temperatures"][1]
    band = np.zeros((3, GRID_INTERVALS - 1))
    band[0, 1:], band[1], band[2, :-1] = upper, diagonal, lower
    equilibrium = solve_banded((1, 1), band, forcing, check_finite=False)
    transform = np.r_[1.0, np.exp(.5 * np.cumsum(np.log(lower / upper)))]
    rates, vectors = eigh_tridiagonal(diagonal, -np.sqrt(lower * upper), check_finite=False)
    amplitudes = vectors.T.dot((spec["initial_temperature"] - equilibrium) / transform)
    interior = equilibrium + (np.exp(-np.outer(spec["times"], rates)) * amplitudes).dot(vectors.T) * transform
    if spec["times"][0] == 0:
        interior[0] = spec["initial_temperature"]
    predicted = np.array([np.interp(spec["probes"], _X[1:-1], row) for row in interior])
    if not np.isfinite(predicted).all():
        raise ValueError("public heat approximation returned nonfinite values")
    return predicted


def _canonical_records(records):
    if not isinstance(records, (list, tuple)) or len(records) > MAX_RECORDS:
        raise ValueError("records must be an array with at most 256 entries")
    usable = []
    for record in records:
        try:
            # Only public spec and observation content is inspected. Extra
            # metadata, IDs and any operator-only fields never enter the fit.
            spec = _spec(record["spec"])
            observation = record["observation"]
            raw = observation["values"]
            if (observation["channels"] != list(CHANNELS) or
                    not isinstance(raw, (list, tuple)) or len(raw) != len(spec["times"]) or
                    any(not isinstance(row, (list, tuple)) or len(row) != 3 for row in raw)):
                continue
            values = np.asarray(raw, dtype=float)
            axis = np.asarray(observation["axis"], dtype=float)
            if (axis.shape != (len(spec["times"]),) or not np.array_equal(axis, spec["times"]) or
                    not np.isfinite(values).all() or np.max(np.abs(values)) > 1e6 or
                    not any(time > 0 for time in spec["times"])):
                continue
            usable.append({"spec": spec, "values": values.tolist()})
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if len(usable) > MAX_FIT_RECORDS:
        usable = [usable[int(index)] for index in np.linspace(0, len(usable) - 1, MAX_FIT_RECORDS)]
    return json.dumps(usable, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _parameters(values):
    return {name: float(value) for name, value in zip(_NAMES, values)}


def _identifiability(solution, parameter_names, public_widths, observations):
    jacobian = np.asarray(solution.jac)
    scaled = jacobian * np.asarray(public_widths)
    singular = np.linalg.svd(scaled, compute_uv=False)
    largest = singular[0] if len(singular) else 0
    rank = int(sum(singular > max(largest * 1e-6, 1e-8)))
    full_rank = rank == len(parameter_names)
    condition = float(singular[0] / singular[-1]) if full_rank and singular[-1] > 0 else None
    uncertainty = None
    if full_rank and observations > len(parameter_names):
        variance_factor = max(1.0, float(np.sum(solution.fun**2)) / (observations - len(parameter_names)))
        covariance = np.linalg.pinv(jacobian.T.dot(jacobian), rcond=1e-12) * variance_factor
        uncertainty = {name: float(1.96 * math.sqrt(max(0.0, variance)))
                       for name, variance in zip(parameter_names, np.diag(covariance))}
    return {"local_scaled_jacobian_rank": rank, "parameter_count": len(parameter_names),
            "local_scaled_condition_number": condition, "scaled_singular_values": singular.tolist(),
            "approximate_95_percent_halfwidth": uncertainty,
            "limitation": "Local linearized diagnostics under the fitted public family; not global identifiability, calibrated confidence, or mechanism certification. Uniform/weak material contrast cannot localize an interface; unvaried flow or cooling controls cannot identify their gains."}


@functools.lru_cache(maxsize=8)
def _fit_cached(serialized):
    start = time.perf_counter()
    records = json.loads(serialized)
    base = {"version": VERSION, "public_bounds": {name: [float(low), float(high)] for name, low, high in zip(_NAMES, _LOWER, _UPPER)},
            "numerical_intervals": GRID_INTERVALS, "measurement_noise_std": NOISE_STD,
            "records_used": len(records), "fit_record_limit": MAX_FIT_RECORDS,
            "optimizer_max_nfev_per_start": MAX_NFEV}
    if not records:
        base.update(model="public_prior", parameters=_parameters(_PRIOR), training_rmse=None,
                    fitting_seconds=time.perf_counter() - start, candidates=[],
                    identifiability={"limitation": "No informative public records; midpoint coefficients are a prediction prior, not inferred parameters."})
        return json.dumps(base, allow_nan=False)
    prepared = [_prepare(record["spec"]) for record in records]
    masks = [np.asarray(record["spec"]["times"]) > 0 for record in records]
    observed = [np.asarray(record["values"])[mask] for record, mask in zip(records, masks)]
    observation_count = sum(value.size for value in observed)

    def residual(parameters):
        return np.concatenate([((_trajectory(parameters, setup)[mask] - values) / NOISE_STD).ravel()
                               for setup, mask, values in zip(prepared, masks, observed)])

    def uniform_residual(parameters):
        diffusivity, gain, loss = parameters
        return residual([diffusivity, diffusivity, .5, gain, loss])

    settings = {"max_nfev": MAX_NFEV, "ftol": 1e-7, "xtol": 1e-7, "gtol": 1e-7}
    uniform = least_squares(uniform_residual, _PRIOR[[0, 3, 4]],
                            bounds=(_LOWER[[0, 3, 4]], _UPPER[[0, 3, 4]]),
                            x_scale=[.03, .06, .04], **settings)
    uniform_parameters = np.array([uniform.x[0], uniform.x[0], .5, uniform.x[1], uniform.x[2]])
    candidates = [("uniform", uniform, uniform_parameters, 3)]
    for interface in (.4, .6):  # Evenly spaced interior starts of the public [.3,.7] interval.
        initial = uniform_parameters.copy()
        initial[2] = interface
        fitted = least_squares(residual, initial, bounds=(_LOWER, _UPPER),
                               x_scale=[.03, .03, .4, .06, .04], **settings)
        candidates.append(("two_region", fitted, fitted.x, 5))
    scores = [float(np.sum(item[1].fun**2)) + item[3] * math.log(max(2, observation_count)) for item in candidates]
    selected_index = int(np.argmin(scores))
    model, solution, parameters, parameter_count = candidates[selected_index]
    names = ("diffusivity", "flow_gain", "loss") if model == "uniform" else _NAMES
    widths = (_UPPER - _LOWER)[[0, 3, 4]] if model == "uniform" else _UPPER - _LOWER
    base.update(model=model, parameters=_parameters(parameters),
                training_rmse=float(np.sqrt(np.mean(solution.fun**2)) * NOISE_STD),
                training_scalar_observations=observation_count,
                fitting_seconds=time.perf_counter() - start,
                selection="Minimum of squared residual/noise plus k*log(n); two interface starts. Penalized fit compares only the publicly declared uniform/two-region families.",
                candidates=[{"model": item[0], "penalized_residual": score,
                             "training_rmse": float(np.sqrt(np.mean(item[1].fun**2)) * NOISE_STD),
                             "nfev": int(item[1].nfev), "optimizer_success": bool(item[1].success)}
                            for item, score in zip(candidates, scores)],
                identifiability=_identifiability(solution, names, widths, observation_count))
    if model == "uniform":
        base["identifiability"]["interface_position"] = "Not identified or used by the selected uniform model; stored 0.5 is a conventional placeholder."
    return json.dumps(base, allow_nan=False)


def fit_public_records(records):
    """Return a detached frozen fit; identical public data reuse an eight-entry cache.

    At most 256 input records are accepted. Malformed records are ignored; at
    most 16 valid records, evenly spread across the supplied history, are used.
    This bounds three nonlinear optimization starts to 60 evaluations each.
    """
    return json.loads(_fit_cached(_canonical_records(records)))


def predict_fitted(fit, spec):
    """Predict from frozen fitted constants and public controls only."""
    canonical = _spec(spec)
    if not isinstance(fit, dict) or not isinstance(fit.get("parameters"), dict):
        raise ValueError("fit requires a parameters object")
    parameters = [_number(fit["parameters"].get(name), name, low, high)
                  for name, low, high in zip(_NAMES, _LOWER, _UPPER)]
    return _trajectory(parameters, _prepare(canonical)).tolist()


def baseline(records, spec):
    """Drop-in strong baseline; never fits on a query or accesses its outcome."""
    canonical = _spec(spec)
    return predict_fitted(fit_public_records(records), canonical)


def clear_fit_cache():
    """Clear the public-data cache when benchmarking cold fitting runtime."""
    _fit_cached.cache_clear()
