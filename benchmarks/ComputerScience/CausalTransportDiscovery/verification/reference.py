"""Truth-blind continuous curve fitting and matched-cost designs."""
from __future__ import annotations

import numpy as np
from scipy.optimize import lsq_linear


def _basis(dose):
    return np.array([3 * dose * (1 - dose) ** 2, 3 * dose ** 2 * (1 - dose), dose ** 3])


def _fit(problem, records, extrapolate=False):
    cells = [tuple(cell) for cell in problem["cells"]]
    available = [tuple(cell) for cell in problem["bridge_accessible_cells"]]
    rows = [[] for _ in cells]
    outcomes = [[] for _ in cells]
    for record in records:
        for row in record["records"]:
            z = record["x"] if record["site"] == "source" else row["z"]
            if z is not None:
                i = cells.index((record["x"], z))
                rows[i].append(_basis(record["dose"]))
                outcomes[i].append(row["y"] - 0.5)
    curves = []
    covariances = []
    for cell, predictors, values in zip(cells, rows, outcomes):
        x = np.array(predictors)
        if cell not in available or len(predictors) < 12 or np.linalg.matrix_rank(x) < 3:
            curves.append({"estimated": False, "coefficients": None, "intervals": [[-0.35, 0.35]] * 3, "covariance": None})
            covariances.append(None)
            continue
        y = np.array(values)
        fitted = lsq_linear(x, y, bounds=(-0.35, 0.35), tol=1e-8).x
        # Bernoulli variance is at most 1/4. A conservative covariance avoids
        # pretending selected boundary fits have zero sampling uncertainty.
        covariance = 0.25 * np.linalg.inv(x.T.dot(x))
        se = np.sqrt(np.diag(covariance))
        curves.append({"estimated": True, "coefficients": fitted.tolist(),
                       "covariance": covariance.tolist(),
                       "intervals": [[max(-0.35, float(a - 1.96 * s)), min(0.35, float(a + 1.96 * s))]
                                     for a, s in zip(fitted, se)]})
        covariances.append(covariance)
    if extrapolate:
        for i, curve in enumerate(curves):
            if not curve["estimated"]:
                original = curves[0 if cells[i][0] < 0 else 3]
                if original["estimated"]:
                    curves[i] = {"estimated": True, "coefficients": list(original["coefficients"]),
                                 "covariance": [list(row) for row in original["covariance"]],
                                 "intervals": [list(interval) for interval in original["intervals"]]}
    complete = all(curve["estimated"] for curve in curves)
    modifiers = None
    if complete and all(covariance is not None for covariance in covariances):
        coefficients = np.array([curve["coefficients"] for curve in curves])
        contrasts = np.array([[x, z, x * z] for x, z in cells]).T.dot(coefficients) / 4
        resolution = problem["response_model"]["modifier_resolution"]
        threshold = (resolution["negligible_curve_rms"] + resolution["meaningful_curve_rms"]) / 2
        grid = np.array([_basis(d) for d in np.linspace(0, 1, 101)])
        modifiers = [name for name, contrast in zip(("X", "Z", "X:Z"), contrasts)
                     if float(np.sqrt(np.mean(grid.dot(contrast) ** 2))) > threshold]
    return {"decision": "discover" if complete else "partial", "curves": curves, "modifiers": modifiers}


def _surveys(problem, experiment):
    profiles = {}
    sites = problem["sites"][1:]
    # 8 site/X profiles, each 48 samples at cost4:1536 units.
    for site in sites:
        for x in (-1, 1):
            response = experiment("survey", {"site": site, "x": x, "n": 48})
            profiles[(site, x)] = (sum(z == 1 for z in response["z_values"]) + 1) / 50
    return profiles


def _run(problem, experiment, mode):
    if problem["budget_units"] != 12000:
        raise ValueError("construction policies support exactly 12000 exploration units")
    sites = problem["sites"][1:]
    doses = (0.25, 0.65, 1.0)
    records = []
    profiles = _surveys(problem, experiment) if mode == "adaptive" else None
    if mode in ("source", "extrapolate"):
        # Spend all12000 units on source trial outcomes; source
        # Z=X is already known so redundant biomarker tests are not charged.
        remaining, i = 12000, 0
        while remaining:
            n = min(256, remaining)
            records.append(experiment("trial", {"site": "source", "x": (-1, 1)[i % 2],
                                                 "dose": doses[(i // 2) % 3], "n": n, "assay_n": 0}))
            remaining -= n
            i += 1
        return _fit(problem, records, extrapolate=mode == "extrapolate")
    random = np.random.default_rng(20491)  # Independent of private world seed.
    if mode == "factorial":
        # Strong all-bridge competitor: no pilot expense, every site at every
        # X/dose, 24 *125 *4 =12000. No hand-picked rotating-site weakness.
        for x in (-1, 1):
            for dose in doses:
                for site in sites:
                    records.append(experiment("trial", {"site": site, "x": x, "dose": dose,
                                                         "n": 125, "assay_n": 125}))
        return _fit(problem, records)
    # Use the known source support efficiently: its concordant biomarkers need
    # no assay. The bridge budget is reserved for the missing discordant curves.
    for x in (-1, 1):
        for dose in doses:
            records.append(experiment("trial", {"site": "source", "x": x, "dose": dose,
                                                 "n": 256, "assay_n": 0}))
    accessible = [tuple(cell) for cell in problem["bridge_accessible_cells"]]
    bridge_x = [x for x in (-1, 1) if (x, -x) in accessible]
    subjects = (12000 - 1536 - (1536 if mode == "adaptive" else 0)) // 4
    per_cell_dose = subjects // (3 * len(bridge_x))
    for x in bridge_x:
        for dose in doses:
            if mode == "adaptive":
                site = max(sites, key=lambda value: profiles[(value, x)] if x == -1 else 1 - profiles[(value, x)])
                remaining = per_cell_dose
                while remaining:
                    n = min(256, remaining)
                    records.append(experiment("trial", {"site": site, "x": x, "dose": dose,
                                                         "n": n, "assay_n": n}))
                    remaining -= n
            else:
                # Full factorial at every dose; fixed/random spend no units on
                # profiles they ignore, and both use exactly12000 total units.
                n = per_cell_dose // 4
                for position in range(4):
                    site = sites[position] if mode == "fixed" else sites[int(random.integers(4))]
                    records.append(experiment("trial", {"site": site, "x": x, "dose": dose,
                                                         "n": n, "assay_n": n}))
    return _fit(problem, records)


def solve(problem, experiment):
    return _run(problem, experiment, "adaptive")


def fixed(problem, experiment):
    return _run(problem, experiment, "fixed")


def random_design(problem, experiment):
    return _run(problem, experiment, "random")


def fixed_full_factorial(problem, experiment):
    return _run(problem, experiment, "factorial")


def source_only(problem, experiment):
    return _run(problem, experiment, "source")


def source_extrapolation(problem, experiment):
    return _run(problem, experiment, "extrapolate")


def bounds_only(problem, experiment):
    return {"decision": "partial", "curves": [
        {"estimated": False, "coefficients": None, "intervals": [[-0.35, 0.35]] * 3, "covariance": None}
        for _ in problem["cells"]], "modifiers": None}


def abstain(problem, experiment):
    return {"decision": "abstain", "curves": [], "modifiers": None}


def prior_zero(problem, experiment):
    claim = bounds_only(problem, experiment)
    available = [tuple(cell) for cell in problem["bridge_accessible_cells"]]
    for i, cell in enumerate(problem["cells"]):
        if tuple(cell) in available:
            claim["curves"][i] = {"estimated": True, "coefficients": [0.0] * 3,
                                    "intervals": [[-0.35, 0.35]] * 3,
                                    "covariance": (np.eye(3) * (0.35 / 1.96) ** 2).tolist()}
    if len(available) == 4:
        claim["decision"], claim["modifiers"] = "discover", []
    return claim


POLICIES = {"reference": solve, "fixed": fixed, "random": random_design,
            "fixed_full_factorial": fixed_full_factorial,
            "source_only": source_only, "source_extrapolation": source_extrapolation,
            "bounds_only": bounds_only, "abstain": abstain}
POLICIES["prior_zero"] = prior_zero
