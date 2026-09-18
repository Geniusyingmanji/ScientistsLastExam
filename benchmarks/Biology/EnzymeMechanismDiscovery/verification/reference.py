"""Truth-blind numerical witness and ablations.

Only public problem fields, public model.py and execute(tool, arguments) are
used. This is a candidate construction witness, not difficulty calibration.
"""
from __future__ import annotations

import copy
import numpy as np
from scipy.optimize import least_squares

from benchmarks.Biology.EnzymeMechanismDiscovery.model import (
    CHANNELS, MODULES, MODULE_PARAMETER, rate, simulate,
)


def _design(substrate, product=0.0, enzyme=1.0, pulse=None):
    return {"initial": {"substrate": substrate, "product": product, "enzyme": enzyme},
            "times": [0.2, 0.6, 1.2, 2.3, 4.2, 7.8],
            "channels": ["substrate", "product"], "pulse": pulse}


def _from_coefficients(coefficients):
    kcat, km, k2, feedback, inhibition, decay = coefficients
    return {"kcat": float(kcat), "km": float(km), "k2": float(k2),
            "ki": 1.0 / feedback if feedback > 1e-12 else None,
            "ks": 1.0 / inhibition if inhibition > 1e-12 else None,
            "kd": float(decay) if decay > 1e-12 else None}


def _predictions(parameters, record):
    args = record["arguments"]
    if record["tool"] == "initial_rate":
        initial = args["initial"]
        return np.array([rate(parameters, initial["substrate"], initial["product"], initial["enzyme"])])
    trajectory = simulate(parameters, args, rtol=1e-5, atol=1e-7)
    indices = [CHANNELS.index(channel) for channel in args["channels"]]
    return trajectory[:, indices].reshape(-1)


def _observed(record):
    if record["tool"] == "initial_rate":
        return np.array([record["rate"]])
    return np.array([row[channel] for row in record["observations"]
                     for channel in record["arguments"]["channels"]])


def _fit(problem, records, initial=None, selected=None):
    ranges = problem["active_parameter_ranges"]
    lower = [ranges[key][0] for key in ("kcat", "km", "k2")] + [0.0, 0.0, 0.0]
    upper = [ranges[key][1] for key in ("kcat", "km", "k2")] + [1.0 / ranges["ki"][0], 1.0 / ranges["ks"][0], ranges["kd"][1]]
    initial = np.array(initial if initial is not None else [(a + b) / 2 for a, b in zip(lower, upper)])
    free = list(range(6))
    if selected is not None:
        free = [0, 1, 2]
        initial[3:] = 0.0
        for offset, module in enumerate(MODULES, 3):
            if module in selected:
                free.append(offset)
                key = MODULE_PARAMETER[module]
                lower[offset] = ranges[key][0] if key == "kd" else 1.0 / ranges[key][1]
                initial[offset] = (lower[offset] + upper[offset]) / 2
    observations = [_observed(record) for record in records]

    def expand(values):
        coefficients = initial.copy()
        coefficients[free] = values
        return coefficients

    def residual(values):
        parameters = _from_coefficients(expand(values))
        return np.concatenate([(_predictions(parameters, record) - observed) / record["sigma"]
                               for record, observed in zip(records, observations)])

    lo, hi = np.array(lower)[free], np.array(upper)[free]
    start = np.clip(initial[free], lo + 1e-9, hi - 1e-9)
    solved = least_squares(residual, start, bounds=(lo, hi), max_nfev=100,
                           ftol=2e-7, xtol=2e-7, gtol=2e-7)
    return expand(solved.x)


def _selected(problem, coefficients):
    ranges = problem["active_parameter_ranges"]
    thresholds = [0.5 / ranges["ki"][1], 0.5 / ranges["ks"][1], 0.5 * ranges["kd"][0]]
    return [module for module, value, threshold in zip(MODULES, coefficients[3:], thresholds) if value > threshold]


def _claim(problem, records, coefficients):
    selected = _selected(problem, coefficients)
    final = _fit(problem, records, initial=coefficients, selected=selected)
    parameters = _from_coefficients(final)
    # Protect against negligible optimizer boundary roundoff when validating.
    for key, value in parameters.items():
        if value is not None:
            lo, hi = problem["active_parameter_ranges"][key]
            parameters[key] = min(hi, max(lo, value))
    return {"decision": "discover", "mechanism": selected, "parameters": parameters,
            "evidence_ids": [record["evidence_id"] for record in records]}


def discover(problem, execute, adaptive=True, comparison_budget=104):
    """Sequential perturbations plus continuous compositional model fitting."""
    if isinstance(comparison_budget, bool) or not isinstance(comparison_budget, int) or comparison_budget < 52:
        raise ValueError("comparison budget must allow two initial and one pulse assay")
    initial_designs = [
        _design(0.35, enzyme=0.65), _design(4.5),
        _design(1.2, product=2.5), _design(2.0, enzyme=0.4),
    ]
    if comparison_budget < 104:
        initial_designs = initial_designs[:2]
    records = [execute("time_course", design) for design in initial_designs]
    coefficients = _fit(problem, records)
    pool = [
        _design(2.2, pulse={"time": 2.8, "species": "enzyme", "amount": 1.0}),
        _design(0.8, pulse={"time": 2.8, "species": "substrate", "amount": 2.2}),
        _design(2.8, pulse={"time": 2.8, "species": "product", "amount": 2.0}),
        _design(5.8, product=1.2, enzyme=1.5,
                pulse={"time": 2.8, "species": "enzyme", "amount": 0.7}),
        _design(1.2, product=3.8, enzyme=1.2,
                pulse={"time": 2.8, "species": "substrate", "amount": 1.5}),
    ]
    if adaptive:
        # Choose the two assays with the greatest disagreement among fitted
        # model and single-module counterfactuals per charged measurement.
        fitted = _from_coefficients(coefficients)
        alternatives = []
        selected = _selected(problem, coefficients)
        for module in MODULES:
            alternate = copy.deepcopy(fitted)
            key = MODULE_PARAMETER[module]
            alternate[key] = None if module in selected else sum(problem["active_parameter_ranges"][key]) / 2
            alternatives.append(alternate)

        def discrimination(design):
            predicted = simulate(fitted, design)
            indices = [CHANNELS.index(channel) for channel in design["channels"]]
            return sum(float(((simulate(alt, design)[:, indices] - predicted[:, indices]) ** 2).sum())
                       for alt in alternatives) / (4 + len(design["times"]) * len(indices) + (4 if design["pulse"] else 0))

        pool = sorted(pool, key=discrimination, reverse=True)
    additional = min(2, (comparison_budget - 16 * len(initial_designs)) // 20)
    records.extend(execute("time_course", design) for design in pool[:additional])
    coefficients = _fit(problem, records, initial=coefficients)
    return _claim(problem, records, coefficients)


def solve(problem, experiment):
    """Generic callback adapter used by the trusted episode smoke runner."""
    return discover(problem, experiment)


def fixed_design_control(problem, execute):
    """Same inference, first two predetermined pulses; no claimed superiority."""
    return discover(problem, execute, adaptive=False)


def initial_rate_control(problem, execute):
    """Old static-rate design: cannot observe k2 or the decay module."""
    # Same 104-unit comparison cap as the dynamic controls. A 3-unit assay
    # permits 34 measurements (102 units); replication cannot resolve the
    # structural non-identifiability of k2 and decay in initial rates.
    points = [(s, p) for p in (0.0, 2.5) for s in (0.2, 0.7, 2.0, 5.5)]
    records = [execute("initial_rate", {"initial": {"substrate": points[i % 8][0],
               "product": points[i % 8][1], "enzyme": 1.0}}) for i in range(34)]
    coefficients = _fit(problem, records)
    # The rate likelihood is exactly constant in these coordinates. Report a
    # fixed guess rather than implying that an arbitrary optimizer value was
    # evidence for intermediate turnover or decay.
    coefficients[2] = sum(problem["active_parameter_ranges"]["k2"]) / 2
    coefficients[5] = 0.0
    return _claim(problem, records, coefficients)


def no_query_control(problem, execute=None):
    parameters = {key: sum(problem["active_parameter_ranges"][key]) / 2 for key in ("kcat", "km", "k2")}
    parameters.update(ki=None, ks=None, kd=None)
    return {"decision": "discover", "mechanism": [], "parameters": parameters, "evidence_ids": []}


def abstain_control(problem, execute=None):
    return {"decision": "abstain", "mechanism": [], "parameters": {}, "evidence_ids": []}


POLICIES = {
    "reference": solve,
    "fixed": fixed_design_control,
    "static": initial_rate_control,
    "no_query": no_query_control,
    "abstain": abstain_control,
}
