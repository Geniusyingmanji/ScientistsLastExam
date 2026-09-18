"""Trusted adapter for the candidate recovery-design scientific task."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random

import numpy as np
from scipy.optimize import least_squares

from benchmarks.Biology.EnzymeRecoveryDesign.model import (
    activity, observable, equivalence_grid, canonical_pools, order_two_certificate, RESOLUTION, RESOLUTION_TIMES,
)


TASK_ID = "SystemsBiology/EnzymeRecoveryDesign"
RANGES = {"k_loss": [0.008, 0.07], "fraction": [0.10, 0.45],
          "kon": [0.12, 2.8], "koff": [0.025, 1.4],
          "gain": [0.8, 1.2], "offset": [-0.06, 0.06],
          "carryover": [-0.35, 0.35], "tau": [0.3, 20.0]}
BOUNDS = {"dose": [0.1, 4.0], "loading": [0.2, 8.0], "washout": [0.0, 40.0], "rescue": [0.0, 0.5]}


def _rng(seed, purpose):
    return random.Random(int.from_bytes(hashlib.sha256((str(seed) + ":" + purpose).encode()).digest(), "big"))


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _number(value, bounds):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not bounds[0] <= value <= bounds[1]:
        raise ValueError("numeric value outside declared bounds")
    if not math.isfinite(value):
        raise ValueError("numeric value must be finite")


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("incorrect object keys")


def _ratio(n, d, status="zero_denominator"):
    return {"numerator": n, "denominator": d, "value": n / d if d else None,
            "status": "measured" if d else status}


def _pool_equivalences(model):
    count = len(canonical_pools(model["pools"]))
    if count == 0:
        return {0}, None
    d, l, t = equivalence_grid()
    expected = activity(model, d, l, t)
    zero_excluded = bool(np.max(np.ptp(expected.reshape(9, len(RESOLUTION_TIMES)), axis=1)) > 2 * RESOLUTION)
    if not zero_excluded:
        def zero_residual(x):
            return np.exp(-x[0] * d * l) - expected
        fit = least_squares(zero_residual, [model["k_loss"]], bounds=([0.0], [0.1]))
        error = float(np.max(np.abs(zero_residual(fit.x))))
        if error <= RESOLUTION:
            return {0}, error
        return set(), error
    if count == 1:
        return {1}, None

    def residual(x):
        equivalent = {"k_loss": model["k_loss"], "pools": [{"fraction": x[0], "kon": x[1], "koff": x[2]}]}
        return activity(equivalent, d, l, t) - expected

    candidates = []
    # The equivalent aggregate fraction can exceed an individual population's
    # generator range. Accept it as a valid effective one-pool predictor.
    for source in model["pools"]:
        start = [sum(p["fraction"] for p in model["pools"]), source["kon"], source["koff"]]
        fit = least_squares(residual, start, bounds=([0.0, 0.04, 0.005], [0.9, 5.0, 3.0]), max_nfev=120)
        candidates.append(float(np.max(np.abs(residual(fit.x)))))
    distance = min(candidates)
    if distance <= RESOLUTION:
        return {1}, distance
    if order_two_certificate(model) > 0:
        return {2}, distance
    # A failed optimizer is not a proof that order two is distinguishable.
    return set(), distance


class RecoveryEnvironment:
    task_id = TASK_ID
    budget_units = 48

    def __init__(self, seed):
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("private seed must be a nonnegative integer")
        self._seed = seed
        rng = _rng(seed, "world")
        count = rng.randrange(3)
        loss = rng.randrange(2)
        self._model = {"k_loss": rng.uniform(*RANGES["k_loss"]) if loss else 0.0, "pools": []}
        for _ in range(count):
            self._model["pools"].append({"fraction": rng.uniform(*RANGES["fraction"]),
                                         "kon": math.exp(rng.uniform(math.log(0.12), math.log(2.8))),
                                         "koff": math.exp(rng.uniform(math.log(0.025), math.log(1.4)))})
        if count == 2 and rng.random() < 0.3:
            first = self._model["pools"][0]
            self._model["pools"][1]["kon"] = min(2.8, max(0.12, first["kon"] * rng.uniform(0.95, 1.05)))
            self._model["pools"][1]["koff"] = min(1.4, max(0.025, first["koff"] * rng.uniform(0.95, 1.05)))
        self._nuisance = {key: rng.uniform(*RANGES[key]) for key in ("gain", "offset", "carryover", "tau")}
        self._allowed_counts, self._equivalence_error = _pool_equivalences(self._model)
        self._spent = 0
        self._evidence = {}
        self._claim = None
        self._confirmation = None
        self._truth = None

    def public_problem(self):
        return {
            "task_id": self.task_id, "contract_version": "recovery-candidate-v1", "budget_units": self.budget_units,
            "evaluation_role": "hardening_candidate", "frontier_eligible": False,
            "units": {"time": "minute", "dose": "relative inhibitor concentration", "activity": "fraction of fresh activity"},
            "bounds": copy.deepcopy(BOUNDS), "generator_ranges": copy.deepcopy(RANGES),
            "predictor_ranges": {"k_loss": [0.0, 0.1], "fraction": [0.0, 0.9], "kon": [0.04, 5.0], "koff": [0.005, 3.0]},
            "tools": {"assay": {"arguments": ["dose", "loading", "washout", "rescue", "control", "readout"],
                                  "controls": ["specimen", "blank", "standard"], "readouts": ["optical", "orthogonal"],
                                  "cost": "1 optical or 3 orthogonal; add 1 for nonzero rescue",
                                  "response_keys": ["evidence_id", "arguments", "value", "sigma"]}},
            "noise_sigma": {"optical": 0.012, "orthogonal": 0.015},
            "claim_schema": {"keys": ["decision", "irreversible_loss", "pool_count", "model", "evidence_ids"],
                             "decision": ["discover", "partial", "abstain"],
                             "irreversible_loss": "boolean or null for unresolved",
                             "pool_count": "minimum resolved effective order 0,1,2 or null; exact duplicate pools merge",
                             "model": "k_loss plus pools list; each pool has fraction,kon,koff; fractions sum<=0.9",
                             "evidence_ids": "distinct native assay IDs; empty allowed",
                             "abstain": "both structural fields null and model null"},
            "equivalence": {"activity_tolerance": RESOLUTION, "dose_grid": [0.2, 1.0, 4.0], "loading_grid": [0.3, 2.0, 8.0],
                            "washout_grid": list(RESOLUTION_TIMES),
                            "rule": "minimum resolved order: positive lower-order witnesses and analytic two-exponential separation certificate; otherwise order unresolved, never infer uniqueness from failed fitting"},
            "confirmation": {"experiments": 12, "readout": "orthogonal", "prediction_rmse_tolerance": 0.05,
                             "fresh_mixed_conditions": True, "claim_immutable": True},
        }

    def action_cost(self, tool, arguments):
        if tool != "assay":
            raise ValueError("unknown tool")
        _keys(arguments, ["dose", "loading", "washout", "rescue", "control", "readout"])
        for key, bounds in BOUNDS.items():
            _number(arguments[key], bounds)
        if arguments["control"] not in ("specimen", "blank", "standard") or arguments["readout"] not in ("optical", "orthogonal"):
            raise ValueError("invalid assay mode")
        if arguments["control"] != "specimen" and arguments["rescue"] != 0:
            raise ValueError("rescue applies only to specimen")
        return (1 if arguments["readout"] == "optical" else 3) + int(arguments["rescue"] > 0)

    def experiment(self, tool, arguments):
        if self._claim is not None:
            raise ValueError("exploration closed")
        cost = self.action_cost(tool, arguments)
        if self._spent + cost > self.budget_units:
            raise ValueError("experiment budget exhausted")
        arguments = copy.deepcopy(arguments)
        index = len(self._evidence) + 1
        sigma = 0.012 if arguments["readout"] == "optical" else 0.015
        value = float(observable(self._model, self._nuisance, arguments)) + _rng(self._seed, "experiment:" + str(index)).gauss(0.0, sigma)
        response = {"evidence_id": "assay-{:04d}".format(index), "arguments": arguments, "value": value, "sigma": sigma}
        self._spent += cost
        self._evidence[response["evidence_id"]] = copy.deepcopy(response)
        return response

    def validate_claim(self, claim):
        _keys(claim, ["decision", "irreversible_loss", "pool_count", "model", "evidence_ids"])
        if claim["decision"] not in ("discover", "partial", "abstain"):
            raise ValueError("invalid decision")
        evidence = claim["evidence_ids"]
        if not isinstance(evidence, list) or any(not isinstance(e, str) or e not in self._evidence for e in evidence) or len(set(evidence)) != len(evidence):
            raise ValueError("invalid evidence citations")
        loss, count = claim["irreversible_loss"], claim["pool_count"]
        if loss is not None and not isinstance(loss, bool):
            raise ValueError("loss must be boolean or null")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count not in (0, 1, 2)):
            raise ValueError("count must be 0,1,2 or null")
        if claim["decision"] == "abstain":
            if loss is not None or count is not None or claim["model"] is not None:
                raise ValueError("abstention cannot assert a mechanism")
            return
        if claim["decision"] == "discover" and (loss is None or count is None):
            raise ValueError("discovery must resolve both components")
        if claim["decision"] == "partial" and ((loss is None) == (count is None)):
            raise ValueError("partial must resolve exactly one component")
        model = claim["model"]
        _keys(model, ["k_loss", "pools"])
        _number(model["k_loss"], [0.0, 0.1])
        pools = model["pools"]
        if not isinstance(pools, list) or len(pools) > 2:
            raise ValueError("invalid pool list")
        for pool in pools:
            _keys(pool, ["fraction", "kon", "koff"])
            for key, bounds in self.public_problem()["predictor_ranges"].items():
                if key != "k_loss":
                    _number(pool[key], bounds)
        if sum(p["fraction"] for p in pools) > 0.9000000001:
            raise ValueError("pool fractions exceed enzyme population")
        if loss is not None and loss != (model["k_loss"] > 0):
            raise ValueError("model contradicts loss claim")
        if count is not None and count != len(canonical_pools(pools)):
            raise ValueError("model contradicts pool claim")

    def confirm(self, claim):
        self.validate_claim(claim)
        canonical = _json(claim)
        if self._claim is not None:
            if canonical != self._claim:
                raise ValueError("claim already committed")
            return copy.deepcopy(self._confirmation)
        rng = _rng(self._seed, "confirmation")
        rows, truth = [], []
        for _ in range(12):
            args = {"dose": math.exp(rng.uniform(math.log(0.15), math.log(4.0))),
                    "loading": math.exp(rng.uniform(math.log(0.25), math.log(8.0))),
                    "washout": math.exp(rng.uniform(math.log(0.05), math.log(40.0))),
                    "rescue": 0.25 if rng.random() < 0.3 else 0.0, "control": "specimen", "readout": "orthogonal"}
            latent = float(observable(self._model, self._nuisance, args))
            truth.append(latent)
            rows.append({"arguments": args, "value": latent + rng.gauss(0.0, 0.015), "sigma": 0.015})
        self._claim, self._truth = canonical, truth
        self._confirmation = {"protocol": "fresh-orthogonal-mixed-interventions-v1", "observations": rows}
        return copy.deepcopy(self._confirmation)

    def evaluate(self, claim, confirmation):
        self.validate_claim(claim)
        if self._claim != _json(claim) or _json(confirmation) != _json(self._confirmation):
            raise ValueError("claim or confirmation differs from committed evidence")
        loss, count = claim["irreversible_loss"], claim["pool_count"]
        declared = int(loss is not None) + int(count is not None)
        # A submitted lower-order predictor can supply a positive witness that
        # the oracle's finite nonlinear search missed. An overparameterized
        # accurate predictor never supplies a minimum-order certificate.
        equivalence_error = None
        if claim["model"] is not None:
            grid = equivalence_grid()
            equivalence_error = float(np.max(np.abs(activity(claim["model"], *grid) - activity(self._model, *grid))))
        candidate_equivalent = equivalence_error is not None and equivalence_error <= RESOLUTION
        allowed_counts = set(self._allowed_counts)
        grid_truth = activity(self._model, *equivalence_grid()).reshape(9, len(RESOLUTION_TIMES))
        zero_excluded = bool(np.max(np.ptp(grid_truth, axis=1)) > 2 * RESOLUTION)
        if count == 0 and not allowed_counts and candidate_equivalent:
            allowed_counts = {0}
        if count == 1 and not allowed_counts and candidate_equivalent and zero_excluded:
            allowed_counts = {1}
        count_correct = count is not None and count in allowed_counts
        correct = int(loss is not None and loss == (self._model["k_loss"] > 0)) + int(count_correct)
        known_declared = int(loss is not None) + int(count is not None and bool(allowed_counts))
        false_known = int(loss is not None and loss != (self._model["k_loss"] > 0)) + int(count is not None and bool(allowed_counts) and not count_correct)
        errors = []
        if claim["model"] is not None:
            for row, expected in zip(confirmation["observations"], self._truth):
                predicted = float(observable(claim["model"], {}, row["arguments"]))
                errors.append(predicted - expected)
        rmse = float(np.sqrt(np.mean(np.square(errors)))) if errors else None
        prediction = math.exp(-((rmse / 0.05) ** 2)) if rmse is not None else 0.0
        return {"valid": True,
                "mechanism_recovery": _ratio(correct, 1 + int(bool(allowed_counts))),
                "complete_effective_claims_accepted": _ratio(int(correct == 2), 1),
                "certified_component_accuracy": _ratio(correct, 1 + int(bool(allowed_counts))),
                "certified_component_fraction": _ratio(1 + int(bool(allowed_counts)), 2),
                "false_discovery_rate": _ratio(false_known, known_declared),
                "discovery_coverage": _ratio(int(declared > 0), 1), "component_coverage": _ratio(declared, 2),
                "refusal_rate": _ratio(int(declared == 0), 1),
                "correct_refusal_rate": _ratio(0, 0, "not_applicable_no_out_of_family_worlds"),
                "confirmation_rmse": rmse, "prediction_score": prediction,
                "confirmation_pass_rate": _ratio(sum(abs(e) <= 0.05 for e in errors), len(errors)),
                "experiment_budget_used": self._spent,
                "pool_count_resolution": "minimum_order_certified" if allowed_counts else "unresolved_at_declared_resolution",
                "resolved_order_coverage": _ratio(int(bool(allowed_counts) and count is not None), 1),
                "order_resolvability_rate": _ratio(int(bool(allowed_counts)), 1),
                "order_refusal_rate": _ratio(int(not allowed_counts and count is None), int(not allowed_counts)),
                "unsupported_order_claims": _ratio(int(not allowed_counts and count is not None), int(count is not None)),
                "pool_order_is_unique": None,
                "candidate_equivalence_grid_max_error": equivalence_error,
                "evidence_kind": "fresh_simulation_same_effective_family"}


def create_environment(seed):
    return RecoveryEnvironment(seed)
