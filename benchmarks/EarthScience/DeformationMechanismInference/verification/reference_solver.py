"""Truth-blind coarse source-family grid-search witness."""

import numpy as np


def _forward(name, p, stations):
    x0, y0, depth, strength, scale = p
    dx, dy = stations[:, 0] - x0, stations[:, 1] - y0
    radius = np.sqrt(dx * dx + dy * dy) + 1e-12
    if name == "mogi":
        den = (dx * dx + dy * dy + depth * depth) ** 1.5
        return strength * np.column_stack((dx, dy, np.full(len(stations), depth))) / den[:, None]
    amp = strength / 1e9
    if name == "sill":
        uz = amp * np.exp(-0.5 * (radius / scale) ** 2) * (1500.0 / depth)
        ur = 0.25 * uz * radius / scale
        return np.column_stack((ur * dx / radius, ur * dy / radius, uz))
    along = (dx + 0.35 * dy) / np.sqrt(1.0 + 0.35 ** 2)
    across = (dy - 0.35 * dx) / np.sqrt(1.0 + 0.35 ** 2)
    horizontal = amp * np.exp(-0.5 * (across / scale) ** 2) * np.tanh(along / scale)
    return np.column_stack((0.94 * horizontal, 0.34 * horizontal, 0.55 * np.abs(horizontal)))


def infer_deformation_source(survey_bounds_m, model_library, measure, budget_units):
    del budget_units
    lo, hi = survey_bounds_m
    axis = np.linspace(lo, hi, 5)
    stations = np.asarray([(x, y) for x in axis for y in axis if not (x == 0 and y == 0)])[:20]
    measurement = measure(stations, "gnss")
    observed = np.asarray(measurement["displacement_m"])
    noise = float(measurement["noise_std_m"])
    # Eliminate linear reference-frame nuisance parameters by variable projection.
    design = np.zeros((len(stations),3,5))
    design[:,:,:3] = np.eye(3)
    design[:,2,3:] = stations / 5000.
    basis, _ = np.linalg.qr(design.reshape(-1,5))
    def project(field):
        vector = np.asarray(field).ravel()
        return (vector-basis@(basis.T@vector)).reshape(-1,3)
    observed = project(observed)
    bounds = np.asarray(model_library["parameter_bounds"], dtype=float)
    candidates = []
    for name in model_library["mechanisms"]:
        for x0 in (-1800.0, 0.0, 1800.0):
            for y0 in (-1800.0, 0.0, 1800.0):
                for depth in (1200.0, 2600.0, 4200.0):
                    for scale in (900.0, 1800.0, 2800.0):
                        unit = project(_forward(name, [x0, y0, depth, 1e9, scale], stations))
                        strength = 1e9 * np.sum(unit * observed) / max(np.sum(unit * unit), 1e-15)
                        strength = np.clip(strength, bounds[3, 0], bounds[3, 1])
                        p = np.asarray([x0, y0, depth, strength, scale])
                        error = float(np.mean((project(_forward(name, p, stations)) - observed) ** 2))
                        candidates.append((error, name, p))
    from scipy.optimize import least_squares
    lower, upper = bounds[:, 0], bounds[:, 1]
    refined = []
    for name in model_library["mechanisms"]:
        seeds = sorted((row for row in candidates if row[1] == name), key=lambda row: row[0])[:2]
        for _, _, initial in seeds:
            def residual(unit):
                parameters = lower + unit * (upper - lower)
                return (project(_forward(name, parameters, stations)) - observed).ravel()
            result = least_squares(residual, np.clip((initial-lower)/(upper-lower),1e-8,1-1e-8),
                                   bounds=(0.,1.), max_nfev=120, ftol=1e-9, xtol=1e-9, gtol=1e-9)
            parameters = lower + result.x * (upper-lower)
            refined.append((float(np.mean(result.fun**2)),name,parameters))
    candidates = refined
    candidates.sort(key=lambda row: row[0])
    best = candidates[0]
    signal_rms = float(np.sqrt(np.mean(observed ** 2)))
    best_rms = float(np.sqrt(best[0]))
    # Noise scale came from the charged survey, not a separate redundant call.
    if signal_rms < 2.0 * noise or best_rms > 3.0 * noise:
        return {"mechanism_probabilities": {name: 1.0 / 3.0 for name in model_library["mechanisms"]},
                "parameters": [], "confidence": 0.1, "abstain": True}
    probabilities = {name: 0.05 for name in model_library["mechanisms"]}
    probabilities[best[1]] = 0.90
    return {"mechanism_probabilities": probabilities, "parameters": best[2],
            "confidence": 0.75, "abstain": False}
