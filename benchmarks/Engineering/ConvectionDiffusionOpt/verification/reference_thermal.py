"""A truth-blind reference for ConvectionDiffusionOpt.

Every recorded proposal declines every world, scoring exactly the all-abstain baseline, and the
card's claim that a defensible retrieval would do better had never been executed. This executes
it, using only what a candidate receives: the grid, the parameter bounds, the design
specification, the experiment callback and the budget. It never reads the hidden world.

    solve       the printed homogeneous equation, discretised the way the task prints it -
                conservative diffusion, upwind convection, Dirichlet zero boundary.
    calibrate   two experiments, ten of twelve budget units, each a single heater at a different
                corner of the domain with twenty-four sensors. One heater position leaves the
                velocity poorly constrained, because the plume it produces only samples the flow
                in one direction.
    fit         least squares over the five coefficients, bounded to the published ranges.
    refuse      by reduced chi-square against the noise the callback declares. A heterogeneous
                apparatus cannot be fitted down to the sensor noise by any member of the
                homogeneous family, which is exactly what the residual reports. A world with no
                heat response is caught separately, by its sensors never leaving zero.
    design      four sources placed by local search on the published objective under the fitted
                model, respecting the margin, separation and power limits.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import csc_matrix, lil_matrix
from scipy.sparse.linalg import factorized

# Reduced chi-square above which the homogeneous family is judged wrong for this apparatus. A
# correct model fitted to its own noise sits near one.
ABSTAIN_CHI_SQUARE = 4.0

# Below this the sensors never moved and there is nothing to identify.
DEAD_RESPONSE = 1e-6


def _grid(n):
    axis = np.linspace(0.0, 1.0, n)
    return axis, np.meshgrid(axis, axis, indexing="ij")


def _solve(parameters, positions, strengths, n, width):
    """The printed homogeneous model: upwind convection, conservative diffusion, T=0 on the edge."""
    kappa_x, kappa_y, velocity_x, velocity_y, loss = np.asarray(parameters, dtype=float)
    spacing = 1.0 / (n - 1)
    _axis, (xx, yy) = _grid(n)

    source = np.zeros((n, n), dtype=float)
    for position, strength in zip(np.asarray(positions, dtype=float),
                                  np.asarray(strengths, dtype=float)):
        source += float(strength) * np.exp(
            -0.5 * ((xx - position[0]) ** 2 + (yy - position[1]) ** 2) / width ** 2)
    source[[0, -1], :] = 0.0
    source[:, [0, -1]] = 0.0

    matrix = lil_matrix((n * n, n * n), dtype=float)
    for i in range(n):
        for j in range(n):
            row = i * n + j
            if i in (0, n - 1) or j in (0, n - 1):
                matrix[row, row] = 1.0
                continue
            matrix[row, row] = (
                2.0 * (kappa_x + kappa_y) / spacing ** 2
                + abs(velocity_x) / spacing + abs(velocity_y) / spacing + loss)
            matrix[row, (i - 1) * n + j] = (-kappa_x / spacing ** 2
                                            - max(velocity_x, 0.0) / spacing)
            matrix[row, (i + 1) * n + j] = (-kappa_x / spacing ** 2
                                            + min(velocity_x, 0.0) / spacing)
            matrix[row, i * n + j - 1] = (-kappa_y / spacing ** 2
                                          - max(velocity_y, 0.0) / spacing)
            matrix[row, i * n + j + 1] = (-kappa_y / spacing ** 2
                                          + min(velocity_y, 0.0) / spacing)
    right_hand = source.reshape(-1).copy()
    right_hand[np.asarray([i * n + j for i in range(n) for j in range(n)
                           if i in (0, n - 1) or j in (0, n - 1)])] = 0.0
    return factorized(csc_matrix(matrix))(right_hand).reshape(n, n)


def _sample(field, positions, axis):
    """Bilinear sampling, which is how the apparatus reads its sensors.

    Nearest-node sampling is close enough to look right and nowhere near close enough to fit: the
    declared sensor noise is 6.5e-4 against field values around 0.27, so a one per cent sampling
    error is a four-sigma residual and every world reads as misspecified. The reference abstained
    on all of them until this matched.
    """
    n = len(axis)
    spacing = axis[1] - axis[0]
    values = []
    for x, y in np.asarray(positions, dtype=float):
        fi = min(max((x - axis[0]) / spacing, 0.0), n - 1.0)
        fj = min(max((y - axis[0]) / spacing, 0.0), n - 1.0)
        i0, j0 = int(np.floor(fi)), int(np.floor(fj))
        i1, j1 = min(i0 + 1, n - 1), min(j0 + 1, n - 1)
        ti, tj = fi - i0, fj - j0
        values.append(
            field[i0, j0] * (1 - ti) * (1 - tj) + field[i1, j0] * ti * (1 - tj)
            + field[i0, j1] * (1 - ti) * tj + field[i1, j1] * ti * tj)
    return np.asarray(values, dtype=float)


def design_thermal_policy(grid_shape, parameter_names, parameter_bounds,
                          design_specification, experiment, budget_units):
    n = int(grid_shape[0])
    axis = np.asarray(design_specification["grid_coordinates"], dtype=float)
    target = np.asarray(design_specification["target_temperature"], dtype=float)
    width = float(design_specification["source_width"])
    margin = float(design_specification["source_margin"])
    separation = float(design_specification["minimum_source_separation"])
    n_sources = int(design_specification["n_sources"])
    strength_low, strength_high = design_specification["source_strength_bounds"]
    total_limit = float(design_specification["total_source_strength_limit"])
    bounds = np.asarray(parameter_bounds, dtype=float)

    # Twenty-four sensors on an interior lattice, reused for both calls so the two experiments
    # differ only in where the heat came from.
    interior = np.linspace(0.18, 0.82, 5)
    sensors = np.array([(x, y) for x in interior for y in interior])[:24]

    calibrations = []
    for heater in ((0.30, 0.30), (0.70, 0.70)):
        result = experiment([list(heater)], [3.0], sensors.tolist())
        calibrations.append((np.asarray([heater], dtype=float),
                             np.asarray([3.0], dtype=float),
                             np.asarray(result["temperature"], dtype=float),
                             float(result["temperature_noise_std"])))

    if max(float(np.max(np.abs(reading)))
           for _p, _s, reading, _n in calibrations) < DEAD_RESPONSE:
        # No heat response: there is no transport to identify.
        return {
            "parameters": np.mean(bounds, axis=1),
            "source_positions": np.full((n_sources, 2), 0.5),
            "source_strengths": np.zeros(n_sources),
            "confidence": 0.0,
            "abstain": True,
        }

    def residual_on(subset, values):
        parts = []
        for positions, strengths, reading, noise in subset:
            field = _solve(values, positions, strengths, n, width)
            parts.append((_sample(field, sensors, axis) - reading) / max(noise, 1e-12))
        return np.concatenate(parts)

    attempt = least_squares(
        lambda values: residual_on(calibrations, values),
        np.mean(bounds, axis=1),
        bounds=(bounds[:, 0], bounds[:, 1]), max_nfev=200)
    parameters = np.asarray(attempt.x, dtype=float)
    degrees = max(1, len(attempt.fun) - len(parameters))
    ratio = float(np.sum(attempt.fun ** 2) / degrees)
    if ratio > ABSTAIN_CHI_SQUARE:
        return {
            "parameters": np.mean(bounds, axis=1),
            "source_positions": np.full((n_sources, 2), 0.5),
            "source_strengths": np.zeros(n_sources),
            "confidence": float(np.clip(ABSTAIN_CHI_SQUARE / ratio, 0.0, 1.0)),
            "abstain": True,
        }

    # Place the sources by local search on the published objective under the fitted model. A
    # gradient method is not worth it here: the field is linear in the strengths, so the strengths
    # are solved exactly for any placement, and only the four positions are searched over.
    low, high = margin, 1.0 - margin
    rng = np.random.default_rng(0)
    best_positions, best_strengths, best_error = None, None, np.inf
    for _attempt in range(24):
        positions = rng.uniform(low, high, size=(n_sources, 2))
        if n_sources > 1:
            gaps = [np.linalg.norm(positions[a] - positions[b])
                    for a in range(n_sources) for b in range(a + 1, n_sources)]
            if min(gaps) < separation:
                continue
        # Linear in the strengths: build the per-source basis fields and solve the least-squares
        # problem for the strengths directly.
        basis = np.stack([
            _solve(parameters, [positions[index]], [1.0], n, width).reshape(-1)
            for index in range(n_sources)], axis=1)
        strengths, *_ = np.linalg.lstsq(basis, target.reshape(-1), rcond=None)
        strengths = np.clip(strengths, strength_low, strength_high)
        total = float(np.sum(np.abs(strengths)))
        if total > total_limit:
            strengths = strengths * (total_limit / total)
        error = float(np.mean((basis @ strengths - target.reshape(-1)) ** 2))
        if error < best_error:
            best_positions, best_strengths, best_error = positions, strengths, error

    if best_positions is None:
        best_positions = np.full((n_sources, 2), 0.5)
        best_strengths = np.zeros(n_sources)

    return {
        "parameters": parameters,
        "source_positions": best_positions,
        "source_strengths": best_strengths,
        "confidence": float(np.clip(1.0 - ratio / ABSTAIN_CHI_SQUARE, 0.0, 1.0)),
        "abstain": False,
    }
