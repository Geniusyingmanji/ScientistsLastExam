"""Truth-blind fit/design witnesses; none use private seeds or world state."""
from __future__ import annotations

import math
import numpy as np
from scipy.optimize import least_squares

from benchmarks.Biology.EnzymeRecoveryDesign.model import observable, order_two_certificate


def assay(dose=1.0, loading=2.0, washout=0.0, control="specimen", readout="optical", rescue=0.0):
    return dict(dose=float(dose), loading=float(loading), washout=float(washout),
                rescue=float(rescue), control=control, readout=readout)


def _decode(x, loss, count):
    index = 0
    k_loss = float(x[index]) if loss else 0.0
    index += int(loss)
    pools = []
    if count:
        total = x[index]
        index += 1
        mix = x[index] if count == 2 else 1.0
        index += int(count == 2)
        for fraction in ([total] if count == 1 else [total * mix, total * (1 - mix)]):
            pools.append({"fraction": float(fraction), "kon": float(np.exp(x[index])), "koff": float(np.exp(x[index + 1]))})
            index += 2
    return {"k_loss": k_loss, "pools": pools}, {
        "gain": float(x[index]), "offset": float(x[index + 1]),
        "carryover": float(x[index + 2]), "tau": float(np.exp(x[index + 3]))}


def _bounds(loss, count):
    lo = [0.0001] if loss else []
    hi = [0.1] if loss else []
    start = [0.025] if loss else []
    if count:
        lo += [0.001]
        hi += [0.9]
        start += [0.45]
        if count == 2:
            lo += [0.03]
            hi += [0.97]
            start += [0.5]
        for j in range(count):
            lo += [math.log(0.04), math.log(0.005)]
            hi += [math.log(5.0), math.log(3.0)]
            start += [math.log(0.6), math.log(0.08 if j == 0 else 0.8)]
    lo += [0.8, -0.06, -0.35, math.log(0.3)]
    hi += [1.2, 0.06, 0.35, math.log(20.0)]
    start += [1.0, 0.0, 0.0, math.log(4.0)]
    return np.array(lo), np.array(hi), np.array(start)


def fit_models(records):
    grouped = []
    for readout in ("optical", "orthogonal"):
        for control in ("specimen", "blank", "standard"):
            selected = [r for r in records if r["arguments"]["readout"] == readout and r["arguments"]["control"] == control]
            if selected:
                args = {key: np.array([r["arguments"][key] for r in selected]) for key in ("dose", "loading", "washout", "rescue")}
                args.update(readout=readout, control=control)
                grouped.append((args, np.array([r["value"] for r in selected]), np.array([r["sigma"] for r in selected])))
    fits = []
    for loss in (False, True):
        for count in (0, 1, 2):
            lo, hi, start = _bounds(loss, count)

            def residual(x):
                model, nuisance = _decode(x, loss, count)
                return np.concatenate([(observable(model, nuisance, args) - observed) / sigma
                                       for args, observed, sigma in grouped])

            best = None
            for phase in (0, 1):
                initial = start.copy() if phase == 0 else lo + 0.65 * (hi - lo)
                result = least_squares(residual, initial, bounds=(lo, hi), max_nfev=120,
                                       ftol=1e-5, xtol=1e-5, gtol=1e-5)
                sse = float(np.square(result.fun).sum())
                if best is None or sse < best[0]:
                    best = (sse, result)
            sse, result = best
            model, nuisance = _decode(result.x, loss, count)
            fits.append({"model": model, "nuisance": nuisance, "loss": loss, "count": count,
                         "sse": sse, "bic": sse + len(result.x) * math.log(max(len(records), 2))})
    return sorted(fits, key=lambda row: row["bic"])


def _initial(experiment):
    settings = [assay(2.5, 4.0, 0.0, control="blank"), assay(2.5, 4.0, 8.0, control="blank"),
                assay(0.2, 0.3, 0.0, control="standard"), assay(2.5, 4.0, 0.0, control="standard")]
    settings += [assay(d, l, t) for d, l, t in ((0.2, 0.3, 0), (0.2, 6, 1), (1, 2, 0), (1, 2, 8),
                                                   (3.5, 0.5, 0), (3.5, 6, 0.3), (3.5, 6, 12), (1, 6, 35))]
    return [experiment("assay", settings_) for settings_ in settings]


def _claim(records, fits, partial=True):
    best = fits[0]
    competitive = [fit for fit in fits if fit["bic"] - best["bic"] <= 3.0]
    loss = best["loss"]
    count = best["count"]
    if partial:
        if len({fit["loss"] for fit in competitive}) > 1:
            loss = None
        if len({fit["count"] for fit in competitive}) > 1:
            count = None
        if count == 2 and order_two_certificate(best["model"]) <= 0:
            count = None
    if loss is None and count is None:
        return {"decision": "abstain", "irreversible_loss": None, "pool_count": None, "model": None,
                "evidence_ids": [r["evidence_id"] for r in records]}
    return {"decision": "discover" if loss is not None and count is not None else "partial",
            "irreversible_loss": loss, "pool_count": count, "model": best["model"],
            "evidence_ids": [r["evidence_id"] for r in records]}


def solve(problem, experiment):
    records = _initial(experiment)
    fits = fit_models(records)
    candidates = [assay(d, l, t, readout=readout) for readout in ("optical", "orthogonal")
                  for d in (0.2, 0.8, 2.0, 4.0) for l in (0.3, 2.0, 8.0) for t in (0.0, 0.3, 1.5, 6.0, 16.0, 40.0)]
    log_weights = np.array([-0.5 * (fit["bic"] - fits[0]["bic"]) for fit in fits])
    predictions = np.array([[float(observable(fit["model"], fit["nuisance"], args)) for args in candidates] for fit in fits])
    spent = len(records)
    last_fit = spent
    while spent < problem["budget_units"]:
        weights = np.exp(np.maximum(log_weights - np.max(log_weights), -40.0))
        weights /= weights.sum()
        weights = 0.9 * weights + 0.1 / len(weights)
        mean = weights @ predictions
        variance = weights @ np.square(predictions - mean)
        costs = np.array([1 if a["readout"] == "optical" else 3 for a in candidates])
        sigmas = np.array([0.012 if a["readout"] == "optical" else 0.015 for a in candidates])
        utility = variance / (costs * sigmas ** 2)
        utility[costs > problem["budget_units"] - spent] = -1
        index = int(np.argmax(utility))
        spent += int(costs[index])
        record = experiment("assay", candidates.pop(index))
        records.append(record)
        log_weights -= 0.5 * np.square((predictions[:, index] - record["value"]) / record["sigma"])
        predictions = np.delete(predictions, index, axis=1)
        # Refit after half the new assays so parameter error is not mistaken
        # for evidence against an otherwise adequate model family.
        if spent - last_fit >= 6:
            last_fit = spent
            fits = fit_models(records)
            log_weights = np.array([-0.5 * (fit["bic"] - fits[0]["bic"]) for fit in fits])
            predictions = np.array([[float(observable(fit["model"], fit["nuisance"], args)) for args in candidates] for fit in fits])
    return _claim(records, fit_models(records))


def fixed(problem, experiment):
    records = _initial(experiment)
    # Broad recovery/loading challenges; all twelve are orthogonal and hence
    # immune to the optical nuisance. Same initial calibration and same fitter.
    settings = [(0.2, 0.3, 0), (0.2, 8, 1.5), (0.2, 8, 40), (0.8, 2, 0),
                (0.8, 8, 6), (0.8, 8, 40), (2, 0.3, 0.3), (2, 2, 6),
                (2, 8, 16), (4, 0.3, 0), (4, 2, 1.5), (4, 8, 40)]
    n = (problem["budget_units"] - 12) // 3
    chosen = [settings[i] for i in np.linspace(0, len(settings) - 1, n, dtype=int)]
    records.extend(experiment("assay", assay(d, l, t, readout="orthogonal")) for d, l, t in chosen)
    for _ in range((problem["budget_units"] - 12) % 3):
        records.append(experiment("assay", assay(2.0, 4.0, 2.0)))
    return _claim(records, fit_models(records))


def random_design(problem, experiment):
    rng = np.random.default_rng(31021)  # Policy seed, never the private world seed.
    records = _initial(experiment)
    for _ in range((problem["budget_units"] - 12) // 3):
        records.append(experiment("assay", assay(np.exp(rng.uniform(np.log(0.1), np.log(4.0))),
                                                 np.exp(rng.uniform(np.log(0.2), np.log(8.0))),
                                                 np.exp(rng.uniform(np.log(0.03), np.log(40.0))), readout="orthogonal")))
    for _ in range((problem["budget_units"] - 12) % 3):
        records.append(experiment("assay", assay(2.0, 4.0, 2.0)))
    return _claim(records, fit_models(records))


def fixed_optical(problem, experiment):
    records = _initial(experiment)
    settings = [assay(d, l, t) for d in (0.2, 1.0, 4.0) for l in (0.3, 2.0, 8.0) for t in (0.0, 0.8, 6.0, 40.0)]
    chosen = [settings[i] for i in np.linspace(0, len(settings) - 1, problem["budget_units"] - 12, dtype=int)]
    records.extend(experiment("assay", args) for args in chosen)
    return _claim(records, fit_models(records))


def fixed_orthogonal(problem, experiment):
    # The expensive readout can legitimately bypass optical calibration.
    # Sixteen orthogonal assays exhaust the same 48-unit budget.
    settings = [(d, l, t) for d, l in ((0.2, 8.0), (0.8, 2.0), (2.0, 0.3), (4.0, 8.0))
                for t in (0.0, 0.8, 6.0, 40.0)]
    chosen = [settings[i] for i in np.linspace(0, len(settings) - 1, problem["budget_units"] // 3, dtype=int)]
    records = [experiment("assay", assay(d, l, t, readout="orthogonal")) for d, l, t in chosen]
    for _ in range(problem["budget_units"] % 3):
        records.append(experiment("assay", assay(2.0, 4.0, 2.0)))
    return _claim(records, fit_models(records))


def passive(problem, experiment):
    records = []
    # Full matched budget, one loading condition; numerous times/replicates.
    for t in np.concatenate([np.array([0.0]), np.geomspace(0.03, 40.0, problem["budget_units"] - 1)]):
        records.append(experiment("assay", assay(1.0, 2.0, float(t))))
    return _claim(records, fit_models(records))


def abstain(problem, experiment=None):
    return {"decision": "abstain", "irreversible_loss": None, "pool_count": None, "model": None, "evidence_ids": []}


def no_query(problem, experiment=None):
    return {"decision": "discover", "irreversible_loss": False, "pool_count": 0,
            "model": {"k_loss": 0.0, "pools": []}, "evidence_ids": []}


def no_query_max(problem, experiment=None):
    return {"decision": "discover", "irreversible_loss": True, "pool_count": 2,
            "model": {"k_loss": 0.035, "pools": [{"fraction": 0.25, "kon": 0.7, "koff": 0.08},
                                                      {"fraction": 0.25, "kon": 0.7, "koff": 0.8}]}, "evidence_ids": []}


def always_max_order_fit(problem, experiment):
    settings = [(d, l, t) for d, l in ((0.2, 8.0), (0.8, 2.0), (2.0, 0.3), (4.0, 8.0))
                for t in (0.0, 0.8, 6.0, 40.0)]
    records = [experiment("assay", assay(d, l, t, readout="orthogonal")) for d, l, t in settings]
    fits = [fit for fit in fit_models(records) if fit["count"] == 2]
    return _claim(records, fits, partial=False)


POLICIES = {"reference": solve, "fixed": fixed, "random": random_design, "fixed_optical": fixed_optical,
            "fixed_orthogonal": fixed_orthogonal, "passive": passive, "abstain": abstain,
            "no_query": no_query, "no_query_max": no_query_max, "always_max_order_fit": always_max_order_fit}
