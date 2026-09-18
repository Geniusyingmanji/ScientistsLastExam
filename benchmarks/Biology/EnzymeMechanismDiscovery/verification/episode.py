"""Trusted episode implementation. Never expose this module to candidates."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random

from benchmarks.Biology.EnzymeMechanismDiscovery.model import (
    CHANNELS, MODULES, MODULE_PARAMETER, PARAMETERS, rate, simulate,
)


TASK_ID = "SystemsBiology/EnzymeMechanismDiscovery"
CONCENTRATION_SIGMA = 0.006
RATE_SIGMA = 0.008
PARAMETER_RANGES = {
    "kcat": [0.7, 1.8], "km": [0.35, 1.0], "k2": [0.3, 1.2],
    "ki": [0.5, 1.6], "ks": [1.8, 5.0], "kd": [0.08, 0.2],
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _rng(seed, label):
    digest = hashlib.sha256((str(seed) + ":" + label).encode("ascii")).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _number(value, lower, upper, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a finite number")
    # Compare before converting to a C double: a legal JSON integer may be
    # arbitrarily large and math.isfinite(10**1000) raises OverflowError.
    if not lower <= value <= upper or not math.isfinite(value):
        raise ValueError(name + " outside public bounds")


def _keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(name + " has incorrect keys")


def _ratio(numerator, denominator, zero_status="zero_denominator"):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None,
            "status": "measured" if denominator else zero_status}


class EnzymeEnvironment:
    task_id = TASK_ID
    budget_units = 216

    def __init__(self, seed):
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        self._seed = seed
        draw = _rng(seed, "world")
        self._parameters = {key: draw.uniform(*bounds)
                            for key, bounds in PARAMETER_RANGES.items()}
        self._mechanism = tuple(module for module in MODULES if draw.randrange(2))
        for module in MODULES:
            if module not in self._mechanism:
                self._parameters[MODULE_PARAMETER[module]] = None
        self._spent = 0
        self._evidence = {}
        self._committed = None
        self._confirmation = None
        self._confirmation_truth = None

    def public_problem(self):
        return {
            "task_id": self.task_id, "contract_version": "episode-pilot-v1",
            "budget_units": self.budget_units,
            "units": {"time": "minute", "concentration": "mM", "enzyme": "relative_activity"},
            "target": "composite effective kinetic modules and fresh trajectory predictions",
            "modules": list(MODULES), "parameters": list(PARAMETERS),
            "active_parameter_ranges": copy.deepcopy(PARAMETER_RANGES),
            "initial_bounds": {"substrate": [0.1, 6.0], "product": [0.0, 4.0], "enzyme": [0.2, 2.0]},
            "time_bounds": [0.02, 8.0], "max_samples": 12,
            "channels": list(CHANNELS),
            "pulse_bounds": {"time": [0.1, 6.0], "amount": [0.1, 3.0]},
            "pulse_species": ["substrate", "product", "enzyme"],
            "noise": {"distribution": "independent additive Gaussian", "concentration_sigma": CONCENTRATION_SIGMA,
                      "initial_rate_sigma": RATE_SIGMA, "negative_readings": "retain; do not clip"},
            "tools": {
                "initial_rate": {"arguments": ["initial"], "cost": "3",
                                 "returns": ["evidence_id", "tool", "arguments", "rate", "sigma"]},
                "time_course": {"arguments": ["initial", "times", "channels", "pulse"],
                                "cost": "4 + len(times)*len(channels) + (4 if pulse else 0)",
                                "returns": ["evidence_id", "tool", "arguments", "observations", "sigma"]},
            },
            "claim_schema": {
                "keys": ["decision", "mechanism", "parameters", "evidence_ids"],
                "decision": ["discover", "abstain"],
                "mechanism": "unique module names; absent module is an explicit negative claim",
                "parameters": "all six keys; ki/ks/kd null iff their module is absent; numeric values inside active_parameter_ranges",
                "evidence_ids": "unique native evidence_id values returned by this episode; may be empty",
                "abstain": "mechanism=[] and parameters={}",
            },
            "confirmation": {"protocol": "three new mixed-load pulse trajectories after immutable claim commitment",
                             "channels": list(CHANNELS), "noise_independent_of_exploration": True,
                             "prediction_tolerance_rmse_mM": 0.06},
            "identifiability": "all pilot worlds lie inside this model class; no calibrated-refusal opportunities are asserted",
        }

    def action_cost(self, tool, arguments):
        if tool not in ("initial_rate", "time_course"):
            raise ValueError("unknown experiment tool")
        _keys(arguments, ["initial"] if tool == "initial_rate" else
              ["initial", "times", "channels", "pulse"], "arguments")
        initial = arguments["initial"]
        _keys(initial, ["substrate", "product", "enzyme"], "initial")
        for key, bounds in self.public_problem()["initial_bounds"].items():
            _number(initial[key], bounds[0], bounds[1], key)
        if tool == "initial_rate":
            return 3
        times = arguments["times"]
        if not isinstance(times, list) or not 1 <= len(times) <= 12:
            raise ValueError("times must have 1 to 12 samples")
        for t in times:
            _number(t, 0.02, 8.0, "sample time")
        if any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError("sample times must be strictly increasing")
        channels = arguments["channels"]
        if not isinstance(channels, list) or not 1 <= len(channels) <= 3:
            raise ValueError("channels must be a nonempty list")
        if any(not isinstance(c, str) or c not in CHANNELS for c in channels) or len(set(channels)) != len(channels):
            raise ValueError("channels must be unique public species")
        pulse = arguments["pulse"]
        if pulse is not None:
            _keys(pulse, ["time", "species", "amount"], "pulse")
            _number(pulse["time"], 0.1, 6.0, "pulse time")
            _number(pulse["amount"], 0.1, 3.0, "pulse amount")
            if pulse["species"] not in ("substrate", "product", "enzyme"):
                raise ValueError("unsupported pulse species")
            if pulse["time"] >= times[-1]:
                raise ValueError("pulse must precede the final sample")
        return 4 + len(times) * len(channels) + (4 if pulse else 0)

    def experiment(self, tool, arguments):
        if self._committed is not None:
            raise ValueError("exploration is closed after confirmation commitment")
        cost = self.action_cost(tool, arguments)
        if self._spent + cost > self.budget_units:
            raise ValueError("experiment budget exhausted")
        arguments = copy.deepcopy(arguments)
        index = len(self._evidence) + 1
        noise = _rng(self._seed, "exploration:" + str(index))
        response = self._observe(tool, arguments, noise)
        response["evidence_id"] = "assay-{:04d}".format(index)
        self._spent += cost
        self._evidence[response["evidence_id"]] = copy.deepcopy(response)
        return response

    def _observe(self, tool, arguments, noise):
        response = {"tool": tool, "arguments": copy.deepcopy(arguments)}
        if tool == "initial_rate":
            initial = arguments["initial"]
            response.update(rate=rate(self._parameters, initial["substrate"], initial["product"], initial["enzyme"]) +
                            noise.gauss(0.0, RATE_SIGMA), sigma=RATE_SIGMA)
        else:
            trajectory = simulate(self._parameters, arguments)
            channels = arguments["channels"]
            response.update(observations=[
                {channel: float(row[CHANNELS.index(channel)]) + noise.gauss(0.0, CONCENTRATION_SIGMA)
                 for channel in channels} for row in trajectory
            ], sigma=CONCENTRATION_SIGMA)
        return response

    def validate_claim(self, claim):
        _keys(claim, ["decision", "mechanism", "parameters", "evidence_ids"], "claim")
        if claim["decision"] not in ("discover", "abstain"):
            raise ValueError("invalid claim decision")
        evidence = claim["evidence_ids"]
        if not isinstance(evidence, list) or len(evidence) > 72:
            raise ValueError("invalid evidence list")
        if any(not isinstance(e, str) or e not in self._evidence for e in evidence) or len(set(evidence)) != len(evidence):
            raise ValueError("claim cites unknown or duplicate evidence")
        modules = claim["mechanism"]
        if not isinstance(modules, list) or any(not isinstance(m, str) or m not in MODULES for m in modules):
            raise ValueError("invalid mechanism modules")
        if len(set(modules)) != len(modules):
            raise ValueError("duplicate mechanism module")
        if claim["decision"] == "abstain":
            if modules or claim["parameters"] != {}:
                raise ValueError("abstention must have empty mechanism and parameters")
            return
        parameters = claim["parameters"]
        _keys(parameters, PARAMETERS, "parameters")
        for key in ("kcat", "km", "k2"):
            _number(parameters[key], *PARAMETER_RANGES[key], key)
        for module, key in MODULE_PARAMETER.items():
            if module in modules:
                _number(parameters[key], *PARAMETER_RANGES[key], key)
            elif parameters[key] is not None:
                raise ValueError("absent module parameter must be null")

    def _confirmation_designs(self):
        draw = _rng(self._seed, "confirmation-designs")
        designs = []
        for species in ("enzyme", "substrate", "product"):
            designs.append({
                "initial": {"substrate": draw.uniform(1.4, 4.6), "product": draw.uniform(0.35, 1.8),
                            "enzyme": draw.uniform(0.45, 1.4)},
                "times": [0.3, 0.9, 1.8, 3.2, 4.7, 6.2, 8.0], "channels": list(CHANNELS),
                "pulse": {"time": draw.uniform(2.0, 3.0), "species": species, "amount": draw.uniform(0.35, 1.4)},
            })
        return designs

    def confirm(self, claim):
        self.validate_claim(claim)
        committed = _canonical(claim)
        if self._committed is not None:
            if committed != self._committed:
                raise ValueError("claim already committed")
            return copy.deepcopy(self._confirmation)
        noise = _rng(self._seed, "confirmation-observations")
        observations = []
        truth = []
        for design in self._confirmation_designs():
            truth.append(simulate(self._parameters, design))
            observations.append(self._observe("time_course", design, noise))
        confirmation = {"protocol": "independent-mixed-pulse-v1", "experiments": observations}
        # Commit only after the trusted solver succeeds; a solver failure is
        # infrastructure failure, not a candidate scientific zero.
        self._committed = committed
        self._confirmation = copy.deepcopy(confirmation)
        self._confirmation_truth = truth
        return confirmation

    def evaluate(self, claim, confirmation):
        self.validate_claim(claim)
        if self._committed is None or _canonical(claim) != self._committed:
            raise ValueError("evaluation requires the committed claim")
        if _canonical(confirmation) != _canonical(self._confirmation):
            raise ValueError("confirmation does not match trusted observations")
        discovered = claim["decision"] == "discover"
        claimed = set(claim["mechanism"])
        actual = set(self._mechanism)
        exact = discovered and claimed == actual
        errors = []
        if discovered:
            for observed, expected in zip(confirmation["experiments"], self._confirmation_truth):
                predicted = simulate(claim["parameters"], observed["arguments"])
                errors.append(float(((predicted - expected) ** 2).mean() ** 0.5))
        rmse = (sum(error * error for error in errors) / len(errors)) ** 0.5 if errors else None
        prediction = math.exp(-((rmse / 0.06) ** 2)) if rmse is not None else 0.0
        return {
            "valid": True, "combined_score": float(exact) * prediction,
            "mechanism_recovery": _ratio(int(exact), 1),
            "module_accuracy": _ratio(sum((m in claimed) == (m in actual) for m in MODULES) if discovered else 0, 3),
            "false_discovery_rate": _ratio(int(discovered and not exact), int(discovered)),
            "module_false_discovery_rate": _ratio(len(claimed - actual), len(claimed)),
            "refusal_rate": _ratio(int(not discovered), 1),
            "correct_refusal_rate": _ratio(0, 0, "not_applicable_all_worlds_in_family"),
            "discovery_coverage": _ratio(int(discovered), 1),
            "confirmation_pass_rate": _ratio(sum(error <= 0.06 for error in errors), 3 if discovered else 0),
            "confirmation_rmse_mM": rmse, "prediction_score": prediction,
            "evidence_citation_count": len(claim["evidence_ids"]), "experiment_budget_used": self._spent,
            "evidence_kind": "fresh_simulated_trajectories_same_effective_model_family",
        }


def create_environment(seed):
    return EnzymeEnvironment(seed)
