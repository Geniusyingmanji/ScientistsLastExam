"""Active convection--diffusion identification and robust heat-source design.

The candidate receives a visible desired temperature field, may perform charged calibration
experiments on an unknown physical world, and returns both a homogeneous PDE mechanism and a
four-source design.  Null and spatially varying worlds require refusal.  Nominal design,
mechanism recovery, prediction, physical-shift robustness and held-out transfer remain separate.
"""

from __future__ import annotations

import hashlib
import math
from functools import lru_cache

import numpy as np
from scipy.sparse import csc_matrix, lil_matrix
from scipy.sparse.linalg import factorized


CONVECTION_DIFFUSION_V2 = True
GRID_N = 25
GRID_SHAPE = (GRID_N, GRID_N)
PARAMETER_NAMES = ("kappa_x", "kappa_y", "velocity_x", "velocity_y", "loss")
PARAMETER_BOUNDS = np.asarray((
    (0.008, 0.038),
    (0.008, 0.038),
    (-0.60, 0.60),
    (-0.60, 0.60),
    (0.05, 0.60),
), dtype=float)
# Mechanism scoring scales.  These are deliberately tighter than the broad public bounds: a
# calibration that only locates the right qualitative transport regime should not saturate the
# mechanism axis.  Separate, looser admission tolerances below express whether the fitted
# parameters remain practically usable; scoring and task identifiability are not the same gate.
PARAMETER_TOLERANCES = np.asarray((0.00032, 0.00032, 0.0060, 0.0060, 0.0060))
PARAMETER_ADMISSION_TOLERANCES = np.asarray(
    (0.0040, 0.0040, 0.075, 0.075, 0.075)
)

N_DESIGN_SOURCES = 4
SOURCE_WIDTH = 0.055
SOURCE_MARGIN = 0.07
MINIMUM_SOURCE_SEPARATION = 0.09
SOURCE_STRENGTH_BOUNDS = (0.05, 3.00)
TOTAL_SOURCE_STRENGTH_LIMIT = 8.00

MIN_CALIBRATION_SOURCES = 1
MAX_CALIBRATION_SOURCES = 3
MIN_SENSORS = 4
MAX_SENSORS = 24
EXPERIMENT_BUDGET_UNITS = 12

BASE_PARAMETERS = (
    (0.014, 0.024, 0.38, 0.12, 0.18),
    (0.028, 0.012, -0.32, 0.25, 0.32),
    (0.018, 0.030, 0.18, -0.36, 0.12),
    (0.032, 0.021, -0.18, -0.28, 0.45),
    (0.011, 0.017, 0.48, -0.12, 0.28),
    (0.025, 0.033, -0.42, -0.20, 0.20),
)

# The desired field is generated in a fixed public nominal apparatus.  The hidden world controls
# the actual device response, so recovering the generating source coordinates alone is not a
# solution; the candidate must identify transport and redesign the heaters.
TARGET_PARAMETERS = np.asarray((0.022, 0.022, 0.0, 0.0, 0.25), dtype=float)

REFERENCE_DESIGNS = (
    (((0.20, 0.24), (0.70, 0.20), (0.30, 0.70), (0.76, 0.73)),
     (1.25, 1.70, 1.10, 1.45)),
    (((0.18, 0.68), (0.43, 0.24), (0.72, 0.43), (0.78, 0.78)),
     (1.60, 1.05, 1.70, 1.20)),
    (((0.22, 0.20), (0.24, 0.76), (0.61, 0.32), (0.79, 0.66)),
     (1.10, 1.55, 1.80, 1.25)),
    (((0.19, 0.43), (0.47, 0.19), (0.58, 0.72), (0.82, 0.42)),
     (1.65, 1.25, 1.45, 1.20)),
    (((0.16, 0.18), (0.46, 0.48), (0.77, 0.20), (0.72, 0.79)),
     (1.15, 1.65, 1.35, 1.55)),
    (((0.18, 0.78), (0.37, 0.31), (0.68, 0.66), (0.82, 0.27)),
     (1.50, 1.20, 1.60, 1.35)),
)

# Fixed-seed public-input L-BFGS-B witnesses for the seven supported worlds, in the order in
# DEVELOPMENT_SPECS + HELDOUT_SPECS after excluding null/misspecified cases.  They optimize the
# visible target under the hidden world's homogeneous parameters and the public source limits.
OPTIMIZED_DESIGNS = {
    73009: (
        ((0.2118246675, 0.6714696969), (0.6746444692, 0.7101051052),
         (0.1411328837, 0.2324780750), (0.6199285727, 0.1532517809)),
        (1.8536350174, 0.7511178498, 2.4144075047, 2.0285581482),
    ),
    73013: (
        ((0.1909104816, 0.6246683827), (0.5328784300, 0.1694566982),
         (0.7873534242, 0.3656996015), (0.8619659733, 0.7007129441)),
        (1.1267402332, 2.1583533812, 3.0000000000, 1.6999073198),
    ),
    73019: (
        ((0.2132067512, 0.8094209810), (0.1621746333, 0.2561067540),
         (0.7136583106, 0.7607177270), (0.5310410194, 0.4283987422)),
        (2.9586096789, 1.5341942798, 1.8392063308, 1.4063635334),
    ),
    73037: (
        ((0.7465840942, 0.7188683900), (0.2632877428, 0.4717899114),
         (0.5942544133, 0.7795446114), (0.7967919195, 0.4471275493)),
        (1.0528711972, 1.8316551622, 2.8932740157, 2.2072029081),
    ),
    83003: (
        ((0.1220171805, 0.2586923820), (0.5774583849, 0.8189462548),
         (0.3195557621, 0.4843219894), (0.2383437759, 0.6990921706)),
        (2.0274463729, 1.7067808956, 2.8214873518, 1.4292879885),
    ),
    83009: (
        ((0.8628461393, 0.3214322493), (0.7295574962, 0.7198740687),
         (0.2609778280, 0.8346646536), (0.8207847950, 0.6005900786)),
        (2.4370332614, 2.7047191728, 1.6113321693, 1.2319178392),
    ),
    83023: (
        ((0.7029490988, 0.3214790371), (0.8468704832, 0.5938721928),
         (0.2746581544, 0.1258449059), (0.6515456631, 0.1638483574)),
        (2.5437605009, 2.1500728262, 1.4707742448, 1.6807933072),
    ),
}

# (seed, parameter template, design template, sensor noise, world kind)
DEVELOPMENT_SPECS = (
    (73009, 0, 0, 0.00065, "in_library"),
    (73013, 1, 1, 0.00070, "in_library"),
    (73019, 2, 2, 0.00075, "in_library"),
    (73037, 3, 3, 0.00080, "in_library"),
    (73039, 0, 4, 0.00065, "null"),
    (73043, 2, 5, 0.00080, "misspecified"),
)
HELDOUT_SPECS = (
    (83003, 4, 4, 0.00110, "in_library"),
    (83009, 5, 5, 0.00120, "in_library"),
    (83023, 1, 2, 0.00130, "in_library"),
    (83047, 3, 0, 0.00110, "null"),
    (83059, 5, 1, 0.00130, "misspecified"),
)

SHIFT_SPECS = (
    "transport",
    "source_position",
    "source_calibration",
    "combined",
)


def _make_parameters(seed, template):
    rng = np.random.default_rng(int(seed))
    base = np.asarray(BASE_PARAMETERS[int(template)], dtype=float)
    scale = np.asarray((0.08, 0.08, 0.08, 0.08, 0.10))
    parameters = base * (1.0 + rng.uniform(-scale, scale))
    parameters[2:4] += rng.uniform(-0.025, 0.025, size=2)
    return np.clip(parameters, PARAMETER_BOUNDS[:, 0], PARAMETER_BOUNDS[:, 1])


def _make_reference_design(seed, template):
    rng = np.random.default_rng(int(seed) + 991)
    positions, strengths = REFERENCE_DESIGNS[int(template)]
    positions = np.asarray(positions, dtype=float)
    positions += rng.uniform(-0.012, 0.012, size=positions.shape)
    strengths = np.asarray(strengths, dtype=float)
    strengths *= rng.uniform(0.94, 1.06, size=len(strengths))
    return positions, strengths


def _world(spec):
    seed, parameter_template, design_template, noise, kind = spec
    positions, strengths = _make_reference_design(seed, design_template)
    return {
        "seed": int(seed),
        "parameters": _make_parameters(seed, parameter_template),
        "noise": float(noise),
        "kind": str(kind),
        "reference_positions": positions,
        "reference_strengths": strengths,
    }


def _grid(grid_n=GRID_N):
    coordinates = np.linspace(0.0, 1.0, int(grid_n))
    return coordinates, np.meshgrid(coordinates, coordinates, indexing="ij")


def _coefficient_fields(parameters, grid_n, kind):
    parameters = np.asarray(parameters, dtype=float)
    coordinates, (xx, yy) = _grid(grid_n)
    del coordinates
    kappa_x, kappa_y, velocity_x, velocity_y, loss = parameters
    if kind != "misspecified":
        return (
            np.full_like(xx, kappa_x), np.full_like(xx, kappa_y),
            np.full_like(xx, velocity_x), np.full_like(xx, velocity_y),
            np.full_like(xx, loss),
        )
    # Smooth, positive heterogeneous transport plus an unresolved recirculating component.
    kx = kappa_x * (
        1.0 + 0.42 * np.sin(2.0 * np.pi * xx) * np.sin(np.pi * yy)
    )
    ky = kappa_y * (
        1.0 - 0.36 * np.sin(np.pi * xx) * np.sin(2.0 * np.pi * yy)
    )
    vx = velocity_x + 0.48 * (yy - 0.5)
    vy = velocity_y - 0.48 * (xx - 0.5)
    reaction = loss * (1.0 + 0.30 * np.cos(2.0 * np.pi * xx) * np.cos(np.pi * yy))
    return kx, ky, vx, vy, reaction


@lru_cache(maxsize=256)
def _operator_solver(parameter_key, grid_n, kind):
    parameters = np.asarray(parameter_key, dtype=float)
    n = int(grid_n)
    spacing = 1.0 / (n - 1)
    kx, ky, vx, vy, loss = _coefficient_fields(parameters, n, kind)
    matrix = lil_matrix((n * n, n * n), dtype=float)
    for i in range(n):
        for j in range(n):
            row = i * n + j
            if i in (0, n - 1) or j in (0, n - 1):
                matrix[row, row] = 1.0
                continue
            east = 0.5 * (kx[i, j] + kx[i + 1, j])
            west = 0.5 * (kx[i, j] + kx[i - 1, j])
            north = 0.5 * (ky[i, j] + ky[i, j + 1])
            south = 0.5 * (ky[i, j] + ky[i, j - 1])
            ux = float(vx[i, j])
            uy = float(vy[i, j])
            matrix[row, row] = (
                (east + west + north + south) / spacing**2
                + abs(ux) / spacing + abs(uy) / spacing + loss[i, j]
            )
            matrix[row, (i - 1) * n + j] = (
                -west / spacing**2 - max(ux, 0.0) / spacing
            )
            matrix[row, (i + 1) * n + j] = (
                -east / spacing**2 + min(ux, 0.0) / spacing
            )
            matrix[row, i * n + j - 1] = (
                -south / spacing**2 - max(uy, 0.0) / spacing
            )
            matrix[row, i * n + j + 1] = (
                -north / spacing**2 + min(uy, 0.0) / spacing
            )
    return factorized(csc_matrix(matrix))


def source_field(source_positions, source_strengths, grid_n=GRID_N):
    """Return the public Gaussian heat-source field on the unit square."""
    positions = np.asarray(source_positions, dtype=float)
    strengths = np.asarray(source_strengths, dtype=float)
    _, (xx, yy) = _grid(grid_n)
    field = np.zeros((int(grid_n), int(grid_n)), dtype=float)
    for position, strength in zip(positions, strengths):
        field += float(strength) * np.exp(
            -0.5 * ((xx - position[0]) ** 2 + (yy - position[1]) ** 2)
            / SOURCE_WIDTH**2
        )
    field[[0, -1], :] = 0.0
    field[:, [0, -1]] = 0.0
    return field


def solve_public(parameters, source_positions, source_strengths, grid_n=GRID_N):
    """Solve the printed homogeneous convection--diffusion--loss equation."""
    parameter_array = np.asarray(parameters, dtype=float)
    if parameter_array.shape != (len(PARAMETER_NAMES),):
        raise ValueError("parameters must contain five values")
    solver = _operator_solver(tuple(map(float, parameter_array)), int(grid_n), "in_library")
    rhs = source_field(source_positions, source_strengths, grid_n).ravel()
    result = np.asarray(solver(rhs), dtype=float).reshape((int(grid_n), int(grid_n)))
    if np.any(~np.isfinite(result)):
        raise RuntimeError("non-finite public PDE solution")
    return result


def _solve_world(world, source_positions, source_strengths, grid_n=GRID_N,
                 kind=None, parameters=None):
    actual_kind = world["kind"] if kind is None else str(kind)
    actual_parameters = (
        world["parameters"] if parameters is None else np.asarray(parameters, dtype=float)
    )
    if actual_kind == "null":
        return np.zeros((int(grid_n), int(grid_n)), dtype=float)
    solver = _operator_solver(
        tuple(map(float, actual_parameters)), int(grid_n), actual_kind
    )
    rhs = source_field(source_positions, source_strengths, grid_n).ravel()
    return np.asarray(solver(rhs), dtype=float).reshape((int(grid_n), int(grid_n)))


def _target_field(world):
    # A null apparatus still receives a nonzero desired field; its zero response must be detected.
    return solve_public(
        TARGET_PARAMETERS, world["reference_positions"], world["reference_strengths"]
    )


def _bilinear_sample(field, sensor_positions):
    values = np.asarray(field, dtype=float)
    sensors = np.asarray(sensor_positions, dtype=float)
    n = values.shape[0]
    scaled = sensors * (n - 1)
    lower = np.floor(scaled).astype(int)
    lower = np.clip(lower, 0, n - 2)
    fraction = scaled - lower
    i, j = lower[:, 0], lower[:, 1]
    fx, fy = fraction[:, 0], fraction[:, 1]
    return (
        (1.0 - fx) * (1.0 - fy) * values[i, j]
        + fx * (1.0 - fy) * values[i + 1, j]
        + (1.0 - fx) * fy * values[i, j + 1]
        + fx * fy * values[i + 1, j + 1]
    )


def _query_seed(world_seed, call_index, positions, strengths, sensors):
    payload = np.concatenate((
        np.asarray(positions, dtype="<f8").ravel(),
        np.asarray(strengths, dtype="<f8").ravel(),
        np.asarray(sensors, dtype="<f8").ravel(),
    )).tobytes()
    digest = hashlib.sha256(payload).digest()
    words = np.frombuffer(digest[:16], dtype="<u4").astype(np.uint32)
    sequence = np.random.SeedSequence([
        int(world_seed), int(call_index), *[int(value) for value in words]
    ])
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


class _ThermalLaboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.violated = False
        self.failure_reason = None

    def _reject(self, message, exception_type=ValueError):
        self.violated = True
        if self.failure_reason is None:
            self.failure_reason = str(message)
        raise exception_type(message)

    def observe(self, source_positions, source_strengths, sensor_positions):
        try:
            positions = np.asarray(source_positions, dtype=float)
            strengths = np.asarray(source_strengths, dtype=float)
            sensors = np.asarray(sensor_positions, dtype=float)
        except (TypeError, ValueError, OverflowError):
            self._reject("experiment arrays must be numeric")
        if positions.ndim != 2 or positions.shape[1:] != (2,) or not (
            MIN_CALIBRATION_SOURCES <= len(positions) <= MAX_CALIBRATION_SOURCES
        ):
            self._reject("calibration source_positions must have shape (1-3,2)")
        if strengths.shape != (len(positions),):
            self._reject("calibration strengths must match source count")
        if sensors.ndim != 2 or sensors.shape[1:] != (2,) or not (
            MIN_SENSORS <= len(sensors) <= MAX_SENSORS
        ):
            self._reject("sensor_positions must have shape (4-24,2)")
        if any(np.any(~np.isfinite(value)) for value in (positions, strengths, sensors)):
            self._reject("experiment values must be finite")
        if np.any(positions < SOURCE_MARGIN) or np.any(positions > 1.0 - SOURCE_MARGIN):
            self._reject("calibration sources outside the public interior")
        if np.any(sensors < 0.04) or np.any(sensors > 0.96):
            self._reject("sensors outside the public interior")
        if np.any(strengths < 0.10) or np.any(strengths > SOURCE_STRENGTH_BOUNDS[1]):
            self._reject("calibration strengths outside public bounds")
        if float(np.sum(strengths)) > 4.75:
            self._reject("calibration total strength exceeds 4.75")
        cost = 1 + len(positions) + int(math.ceil(len(sensors) / 8.0))
        if self.used + cost > EXPERIMENT_BUDGET_UNITS:
            self._reject("thermal experiment budget exceeded", RuntimeError)
        self.used += int(cost)
        self.calls += 1
        clean_field = _solve_world(self.world, positions, strengths)
        clean = _bilinear_sample(clean_field, sensors)
        rng = np.random.default_rng(_query_seed(
            self.world["seed"], self.calls, positions, strengths, sensors
        ))
        observed = clean + rng.normal(0.0, self.world["noise"], size=len(clean))
        return {
            "source_positions": positions.copy(),
            "source_strengths": strengths.copy(),
            "sensor_positions": sensors.copy(),
            "temperature": observed,
            "temperature_noise_std": float(self.world["noise"]),
            "budget_cost": int(cost),
            "budget_used": int(self.used),
        }


def _design_specification(world):
    coordinates = np.linspace(0.0, 1.0, GRID_N)
    return {
        "grid_coordinates": coordinates,
        "target_temperature": _target_field(world),
        "n_sources": N_DESIGN_SOURCES,
        "source_width": SOURCE_WIDTH,
        "source_margin": SOURCE_MARGIN,
        "minimum_source_separation": MINIMUM_SOURCE_SEPARATION,
        "source_strength_bounds": SOURCE_STRENGTH_BOUNDS,
        "total_source_strength_limit": TOTAL_SOURCE_STRENGTH_LIMIT,
        "robustness_envelope": {
            "transport_relative": 0.10,
            "velocity_absolute": 0.055,
            "source_position_absolute": 0.014,
            "source_strength_relative": 0.07,
        },
    }


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a dictionary")
    if not isinstance(submission.get("abstain"), (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be finite and in [0,1]")
    parameters = np.asarray(submission.get("parameters"), dtype=float)
    positions = np.asarray(submission.get("source_positions"), dtype=float)
    strengths = np.asarray(submission.get("source_strengths"), dtype=float)
    if parameters.shape != (len(PARAMETER_NAMES),) or np.any(~np.isfinite(parameters)):
        raise ValueError("parameters must be a finite length-five array")
    if positions.shape != (N_DESIGN_SOURCES, 2) or np.any(~np.isfinite(positions)):
        raise ValueError("source_positions must be a finite (4,2) array")
    if strengths.shape != (N_DESIGN_SOURCES,) or np.any(~np.isfinite(strengths)):
        raise ValueError("source_strengths must be a finite length-four array")
    abstain = bool(submission["abstain"])
    if abstain:
        if np.max(np.abs(parameters)) > 1.0e6 or np.max(np.abs(positions)) > 1.0e6 or np.max(np.abs(strengths)) > 1.0e6:
            raise ValueError("abstention artifact exceeds finite safety bounds")
        return (
            np.zeros(len(PARAMETER_NAMES)), np.zeros((N_DESIGN_SOURCES, 2)),
            np.zeros(N_DESIGN_SOURCES), confidence, True,
        )
    if np.any(parameters < PARAMETER_BOUNDS[:, 0]) or np.any(
        parameters > PARAMETER_BOUNDS[:, 1]
    ):
        raise ValueError("claimed parameters outside public bounds")
    if np.any(positions < SOURCE_MARGIN) or np.any(positions > 1.0 - SOURCE_MARGIN):
        raise ValueError("design sources outside the public interior")
    if np.any(strengths < SOURCE_STRENGTH_BOUNDS[0]) or np.any(
        strengths > SOURCE_STRENGTH_BOUNDS[1]
    ):
        raise ValueError("design source strengths outside public bounds")
    if float(np.sum(strengths)) > TOTAL_SOURCE_STRENGTH_LIMIT:
        raise ValueError("design total source strength exceeds public limit")
    distances = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=2)
    distances += np.eye(N_DESIGN_SOURCES)
    if float(np.min(distances)) < MINIMUM_SOURCE_SEPARATION:
        raise ValueError("design sources violate minimum separation")
    return parameters, positions, strengths, confidence, False


def _temperature_quality(predicted, target, fraction=0.25):
    target = np.asarray(target, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    scale = max(0.015, fraction * math.sqrt(float(np.mean(target * target))))
    rmse = math.sqrt(float(np.mean((predicted - target) ** 2)))
    return float(math.exp(-0.5 * (rmse / scale) ** 2)), rmse


def _weak_design():
    return (
        np.asarray(((0.20, 0.20), (0.20, 0.80), (0.80, 0.20), (0.80, 0.80))),
        np.ones(N_DESIGN_SOURCES),
    )


def _normalized_design_score(world, positions, strengths, shift=None):
    """Normalize RMSE between a weak layout and a replayable feasible witness."""
    target = _target_field(world)
    weak_positions, weak_strengths = _weak_design()
    reference_positions, reference_strengths = OPTIMIZED_DESIGNS[world["seed"]]
    reference_positions = np.asarray(reference_positions, dtype=float)
    reference_strengths = np.asarray(reference_strengths, dtype=float)
    candidate_positions = np.asarray(positions, dtype=float)
    candidate_strengths = np.asarray(strengths, dtype=float)
    actual_world = world
    if shift is not None:
        actual_world, candidate_positions, candidate_strengths = (
            _shifted_world_and_design(
                world, candidate_positions, candidate_strengths, shift
            )
        )
        _ignored, weak_positions, weak_strengths = _shifted_world_and_design(
            world, weak_positions, weak_strengths, shift
        )
        _ignored, reference_positions, reference_strengths = (
            _shifted_world_and_design(
                world, reference_positions, reference_strengths, shift
            )
        )
    candidate_field = _solve_world(
        actual_world, candidate_positions, candidate_strengths, kind="in_library"
    )
    weak_field = _solve_world(
        actual_world, weak_positions, weak_strengths, kind="in_library"
    )
    reference_field = _solve_world(
        actual_world, reference_positions, reference_strengths, kind="in_library"
    )
    utility, candidate_error = _temperature_quality(candidate_field, target)
    _weak_utility, weak_error = _temperature_quality(weak_field, target)
    _reference_utility, reference_error = _temperature_quality(reference_field, target)
    denominator = weak_error - reference_error
    if denominator <= 1.0e-10:
        raise RuntimeError("invalid design normalization anchors")
    normalized = float(np.clip(
        (weak_error - candidate_error) / denominator, 0.0, 1.0
    ))
    return normalized, utility, candidate_error, weak_error, reference_error


def _mechanism_quality(parameters, truth):
    scaled = (np.asarray(parameters) - np.asarray(truth)) / PARAMETER_TOLERANCES
    return float(math.exp(-0.5 * float(np.mean(scaled * scaled))))


def _diagnostic_prediction_quality(world, parameters):
    diagnostic_positions = np.asarray(((0.23, 0.34), (0.71, 0.63)))
    diagnostic_strengths = np.asarray((1.55, 1.25))
    actual = _solve_world(world, diagnostic_positions, diagnostic_strengths)
    predicted = solve_public(parameters, diagnostic_positions, diagnostic_strengths)
    return _temperature_quality(predicted, actual, fraction=0.15)[0]


def _shifted_world_and_design(world, positions, strengths, shift):
    parameters = np.asarray(world["parameters"], dtype=float).copy()
    shifted_positions = np.asarray(positions, dtype=float).copy()
    shifted_strengths = np.asarray(strengths, dtype=float).copy()
    if shift in {"transport", "combined"}:
        parameters[:2] *= np.asarray((1.10, 0.92))
        parameters[2:4] += np.asarray((0.055, -0.045))
        parameters[4] *= 1.10
        parameters = np.clip(parameters, PARAMETER_BOUNDS[:, 0], PARAMETER_BOUNDS[:, 1])
    if shift in {"source_position", "combined"}:
        shifted_positions += np.asarray((
            (0.014, -0.010), (-0.012, 0.014), (0.010, 0.012), (-0.014, -0.010)
        ))
    if shift in {"source_calibration", "combined"}:
        shifted_strengths *= np.asarray((1.07, 0.94, 1.05, 0.93))
    shifted = dict(world)
    shifted["parameters"] = parameters
    return shifted, shifted_positions, shifted_strengths


def _joint_quality(mechanism, prediction, design):
    if min(mechanism, prediction, design) <= 0.0:
        return 0.0
    return float(mechanism**0.25 * prediction**0.15 * design**0.60)


def _public_failure_kind(stage, laboratory):
    if laboratory.violated:
        return "invalid_experiment_request"
    if stage == "submission_validation":
        return "invalid_return_artifact"
    if stage == "candidate_execution":
        return "candidate_runtime_or_callback_processing_error"
    return "trusted_evaluator_internal_error"


def _invalid_record(split, index, kind, failure_kind, laboratory):
    return {
        "split": split,
        "world_index": int(index),
        "kind": str(kind),
        "valid": False,
        "reason": str(failure_kind),
        "failure_kind": str(failure_kind),
        "abstain": False,
        "confidence": 0.0,
        "mechanism_quality": 0.0,
        "prediction_quality": 0.0,
        "design_quality": 0.0,
        "robust_design_quality": 0.0,
        "joint_quality": 0.0,
        "robust_joint_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "experiment_calls": int(laboratory.calls),
        "experiment_budget_units": int(laboratory.used),
    }


def _evaluate_world(design_thermal_policy, spec, split, index):
    world = _world(spec)
    laboratory = _ThermalLaboratory(world)
    stage = "candidate_execution"
    try:
        submission = design_thermal_policy(
            GRID_SHAPE, PARAMETER_NAMES, PARAMETER_BOUNDS.copy(),
            _design_specification(world), laboratory.observe,
            EXPERIMENT_BUDGET_UNITS,
        )
        stage = "submission_validation"
        parameters, positions, strengths, confidence, abstain = _validate_submission(submission)
        if laboratory.violated:
            raise RuntimeError(laboratory.failure_reason or "invalid thermal experiment")
    except Exception:
        return _invalid_record(
            split, index, world["kind"], _public_failure_kind(stage, laboratory), laboratory
        )

    if world["kind"] != "in_library":
        correct = bool(abstain)
        return {
            "split": split,
            "world_index": int(index),
            "kind": world["kind"],
            "valid": True,
            "abstain": abstain,
            "confidence": float(confidence),
            "mechanism_quality": 1.0 if correct else 0.0,
            "prediction_quality": 1.0 if correct else 0.0,
            "design_quality": 1.0 if correct else 0.0,
            "robust_design_quality": 1.0 if correct else 0.0,
            "joint_quality": 1.0 if correct else 0.0,
            "robust_joint_quality": 1.0 if correct else 0.0,
            "confidence_calibration_score": float(1.0 - (confidence - float(correct)) ** 2),
            "correct_refusal": correct,
            "false_discovery": not correct,
            "experiment_calls": int(laboratory.calls),
            "experiment_budget_units": int(laboratory.used),
        }

    if abstain:
        mechanism = prediction = design = robust_design = joint = robust_joint = 0.0
        nominal_rmse = None
    else:
        mechanism = _mechanism_quality(parameters, world["parameters"])
        prediction = _diagnostic_prediction_quality(world, parameters)
        design, design_utility, nominal_rmse, weak_rmse, reference_rmse = (
            _normalized_design_score(world, positions, strengths)
        )
        shifted_qualities = []
        shifted_utilities = []
        for shift in SHIFT_SPECS:
            shifted = _normalized_design_score(
                world, positions, strengths, shift
            )
            shifted_qualities.append(shifted[0])
            shifted_utilities.append(shifted[1])
        robust_design = float(np.mean(shifted_qualities))
        robust_design_utility = float(np.mean(shifted_utilities))
        joint = _joint_quality(mechanism, prediction, design)
        robust_joint = _joint_quality(mechanism, prediction, robust_design)
    return {
        "split": split,
        "world_index": int(index),
        "kind": world["kind"],
        "valid": True,
        "abstain": abstain,
        "confidence": float(confidence),
        "mechanism_quality": float(mechanism),
        "prediction_quality": float(prediction),
        "design_quality": float(design),
        "robust_design_quality": float(robust_design),
        "design_utility": float(design_utility) if not abstain else 0.0,
        "robust_design_utility": (
            float(robust_design_utility) if not abstain else 0.0
        ),
        "joint_quality": float(joint),
        "robust_joint_quality": float(robust_joint),
        "confidence_calibration_score": float(1.0 - (confidence - joint) ** 2),
        "correct_refusal": False,
        "false_discovery": False,
        "nominal_temperature_rmse": nominal_rmse,
        "weak_design_temperature_rmse": weak_rmse if not abstain else None,
        "reference_design_temperature_rmse": (
            reference_rmse if not abstain else None
        ),
        "experiment_calls": int(laboratory.calls),
        "experiment_budget_units": int(laboratory.used),
    }


def _normalized_joint(records, field):
    unsupported = sum(row["kind"] != "in_library" for row in records)
    baseline = unsupported / len(records)
    raw = float(np.mean([row[field] for row in records]))
    return float(np.clip((raw - baseline) / (1.0 - baseline), 0.0, 1.0))


def _split_summary(records):
    supported = [row for row in records if row["kind"] == "in_library"]
    unsupported = [row for row in records if row["kind"] != "in_library"]
    valid_count = sum(bool(row["valid"]) for row in records)
    return {
        "joint": _normalized_joint(records, "joint_quality"),
        "robust_joint": _normalized_joint(records, "robust_joint_quality"),
        "mechanism": float(np.mean([row["mechanism_quality"] for row in supported])),
        "prediction": float(np.mean([row["prediction_quality"] for row in supported])),
        "design": float(np.mean([row["design_quality"] for row in supported])),
        "robust_design": float(np.mean([row["robust_design_quality"] for row in supported])),
        "design_utility": float(np.mean([
            row.get("design_utility", 0.0) for row in supported
        ])),
        "robust_design_utility": float(np.mean([
            row.get("robust_design_utility", 0.0) for row in supported
        ])),
        "supported_claim_coverage": float(np.mean([not row["abstain"] for row in supported])),
        "false_discovery_rate": float(np.mean([row["false_discovery"] for row in unsupported])),
        "correct_refusal_rate": float(np.mean([row["correct_refusal"] for row in unsupported])),
        "confidence_calibration": float(np.mean([
            row.get("confidence_calibration_score", 0.0) for row in records
        ])),
        "valid_count": valid_count,
        "mean_calls": float(np.mean([row["experiment_calls"] for row in records])),
        "mean_budget": float(np.mean([row["experiment_budget_units"] for row in records])),
    }


def evaluate(design_thermal_policy):
    development = []
    heldout = []
    all_specs = [
        ("development", index, spec) for index, spec in enumerate(DEVELOPMENT_SPECS)
    ] + [("heldout", index, spec) for index, spec in enumerate(HELDOUT_SPECS)]
    for call_index, (split, index, spec) in enumerate(all_specs):
        if call_index and hasattr(design_thermal_policy, "reset_session"):
            design_thermal_policy.reset_session()
        record = _evaluate_world(design_thermal_policy, spec, split, index)
        (development if split == "development" else heldout).append(record)
    dev = _split_summary(development)
    hold = _split_summary(heldout)
    development_valid = dev["valid_count"] == len(development)
    heldout_valid = hold["valid_count"] == len(heldout)
    result = {
        "combined_score": dev["joint"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "raw_score": dev["joint"] if development_valid else 0.0,
        "mechanism_score": dev["mechanism"],
        "development_prediction_score": dev["prediction"],
        "development_design_score": dev["design"],
        "development_robust_design_score": dev["robust_design"],
        "development_design_utility": dev["design_utility"],
        "development_robust_design_utility": dev["robust_design_utility"],
        "robustness_score": dev["robust_joint"] if development_valid else 0.0,
        "development_validation_gap": dev["joint"] - dev["robust_joint"],
        "heldout_policy_score": hold["joint"] if heldout_valid else 0.0,
        "heldout_mechanism_score": hold["mechanism"],
        "heldout_prediction_score": hold["prediction"],
        "heldout_design_score": hold["design"],
        "heldout_robust_design_score": hold["robust_design"],
        "heldout_design_utility": hold["design_utility"],
        "heldout_robust_design_utility": hold["robust_design_utility"],
        "heldout_robustness_score": hold["robust_joint"] if heldout_valid else 0.0,
        "development_supported_claim_coverage": dev["supported_claim_coverage"],
        "heldout_supported_claim_coverage": hold["supported_claim_coverage"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": hold["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "heldout_correct_refusal_rate": hold["correct_refusal_rate"],
        "development_confidence_calibration_score": dev["confidence_calibration"],
        "heldout_confidence_calibration_score": hold["confidence_calibration"],
        "development_mean_experiment_calls": dev["mean_calls"],
        "heldout_mean_experiment_calls": hold["mean_calls"],
        "development_mean_budget_units": dev["mean_budget"],
        "heldout_mean_budget_units": hold["mean_budget"],
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "candidate_world_call_count": len(all_specs),
        "candidate_world_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
        "per_world": development + heldout,
    }
    if not development_valid:
        failure_kinds = sorted({
            row["failure_kind"] for row in development if not row["valid"]
        })
        result["error_message"] = "candidate invalid: " + ", ".join(failure_kinds)
    return result


def _reference_submission(world):
    if world["kind"] != "in_library":
        return {
            "parameters": np.zeros(len(PARAMETER_NAMES)),
            "source_positions": np.zeros((N_DESIGN_SOURCES, 2)),
            "source_strengths": np.zeros(N_DESIGN_SOURCES),
            "confidence": 1.0,
            "abstain": True,
        }
    return {
        "parameters": world["parameters"].copy(),
        "source_positions": np.asarray(OPTIMIZED_DESIGNS[world["seed"]][0]),
        "source_strengths": np.asarray(OPTIMIZED_DESIGNS[world["seed"]][1]),
        "confidence": 1.0,
        "abstain": False,
    }
