"""One-dimensional Fourier-modal/RCWA diffraction-grating oracle, version 2.

Candidates return a five-layer binary dielectric relief.  The trusted oracle
solves Maxwell's equations by a truncated Fourier modal method for both TE and
TM polarization, normal and oblique incidence, multiple wavelengths and sealed
material/fabrication shifts.  Development and held-out regimes are separate.

The implementation uses an independent dense boundary solve rather than a
candidate-visible simulator.  It follows the Fourier-modal formulation of
Moharam and Gaylord (1981) with inverse-permittivity factorization for TM, as
motivated by Lalanne and Morris (1996) and Li (1996).  It is a deterministic
lossless 1D isotropic model, not fabricated-device or full-vector 2D evidence.
"""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np


RCWA_GRATING_V2 = True
LAYER_COUNT = 5
FOURIER_ORDER = 9
POLARIZATIONS = ("TE", "TM")
TARGET_ORDER = 1
MIN_FEATURE_FRACTION = 0.08
MAX_TOTAL_DEPTH_FRACTION = 0.85
ENERGY_TOLERANCE = 2.0e-7
CONDITION_LIMIT = 5.0e12


WORLD_SPECS = (
    {
        "name": "dev_visible_titania",
        "split": "development",
        "period_um": 0.82,
        "center_wavelength_um": 0.64,
        "incident_index": 1.0,
        "substrate_index": 1.46,
        "ridge_index": 2.22,
        "angles_deg": (-6.0, 0.0, 6.0),
        "wavelength_scales": (0.97, 1.0, 1.03),
        "reference_parameters": (
            (0.115, 0.122, 0.083, 0.101, 0.096),
            (0.72, 0.34, 0.29, 0.69, 0.84),
            (0.23, 0.57, 0.54, 0.37, 0.75),
        ),
        "anchors": (0.18014399889340393, 0.532133681719001,
                    0.13483237185212524, 0.44019507865384405),
    },
    {
        "name": "heldout_red_silicon_nitride",
        "split": "heldout",
        "period_um": 0.94,
        "center_wavelength_um": 0.72,
        "incident_index": 1.0,
        "substrate_index": 1.45,
        "ridge_index": 2.05,
        "angles_deg": (-8.0, 0.0, 8.0),
        "wavelength_scales": (0.965, 1.0, 1.035),
        "reference_parameters": (
            (0.140, 0.144, 0.098, 0.123, 0.116),
            (0.741, 0.332, 0.294, 0.687, 0.849),
            (0.230, 0.568, 0.544, 0.374, 0.750),
        ),
        "anchors": (0.20278483445805393, 0.4685463609260546,
                    0.1552103101728418, 0.40130215926359536),
    },
    {
        "name": "dev_near_ir_silicon_nitride",
        "split": "development",
        "period_um": 1.24,
        "center_wavelength_um": 0.94,
        "incident_index": 1.0,
        "substrate_index": 1.50,
        "ridge_index": 2.03,
        "angles_deg": (-7.0, 0.0, 7.0),
        "wavelength_scales": (0.97, 1.0, 1.03),
        "reference_parameters": (
            (0.188, 0.194, 0.132, 0.166, 0.154),
            (0.74, 0.33, 0.30, 0.68, 0.85),
            (0.23, 0.57, 0.54, 0.37, 0.75),
        ),
        "anchors": (0.19473081088858865, 0.4945997546172699,
                    0.14318642196916834, 0.4292864766132388),
    },
    {
        "name": "dev_blue_titania",
        "split": "development",
        "period_um": 0.66,
        "center_wavelength_um": 0.50,
        "incident_index": 1.0,
        "substrate_index": 1.52,
        "ridge_index": 2.35,
        "angles_deg": (-5.0, 0.0, 5.0),
        "wavelength_scales": (0.975, 1.0, 1.025),
        "reference_parameters": (
            (0.087, 0.094, 0.061, 0.078, 0.073),
            (0.73, 0.35, 0.28, 0.70, 0.83),
            (0.23, 0.57, 0.54, 0.37, 0.75),
        ),
        "anchors": (0.1192360204505921, 0.5170498868268243,
                    0.09020651541347875, 0.4775205953501223),
    },
    {
        "name": "heldout_telecom_silicon",
        "split": "heldout",
        "period_um": 1.72,
        "center_wavelength_um": 1.31,
        "incident_index": 1.0,
        "substrate_index": 1.45,
        "ridge_index": 2.06,
        "angles_deg": (-10.0, 0.0, 10.0),
        "wavelength_scales": (0.97, 1.0, 1.03),
        "reference_parameters": (
            (0.254, 0.262, 0.178, 0.224, 0.211),
            (0.741, 0.332, 0.294, 0.687, 0.849),
            (0.230, 0.568, 0.544, 0.374, 0.750),
        ),
        "anchors": (0.19275788460425558, 0.47150195943043827,
                    0.14553387064111, 0.3993352497091286),
    },
    {
        "name": "dev_green_titania",
        "split": "development",
        "period_um": 0.74,
        "center_wavelength_um": 0.56,
        "incident_index": 1.0,
        "substrate_index": 1.47,
        "ridge_index": 2.28,
        "angles_deg": (-7.0, 0.0, 7.0),
        "wavelength_scales": (0.97, 1.0, 1.03),
        "reference_parameters": (
            (0.099, 0.106, 0.070, 0.088, 0.083),
            (0.72, 0.34, 0.29, 0.69, 0.84),
            (0.23, 0.57, 0.54, 0.37, 0.75),
        ),
        "anchors": (0.12554121767053006, 0.5299481907323139,
                    0.095913600202855, 0.4684159871939997),
    },
)


SHIFT_SPECS = (
    {
        "name": "etch_shallow_overlay",
        "depth_scale": 0.94,
        "fill_offset": 0.015,
        "lateral_offset": 0.012,
        "ridge_index_scale": 1.0,
        "angle_offset_deg": 0.0,
    },
    {
        "name": "etch_deep_underlay",
        "depth_scale": 1.06,
        "fill_offset": -0.015,
        "lateral_offset": -0.012,
        "ridge_index_scale": 1.0,
        "angle_offset_deg": 0.0,
    },
    {
        "name": "material_index_low",
        "depth_scale": 1.0,
        "fill_offset": 0.0,
        "lateral_offset": 0.0,
        "ridge_index_scale": 0.985,
        "angle_offset_deg": 3.0,
    },
    {
        "name": "material_index_high",
        "depth_scale": 1.0,
        "fill_offset": 0.0,
        "lateral_offset": 0.0,
        "ridge_index_scale": 1.015,
        "angle_offset_deg": -3.0,
    },
)


def _public_problem(spec: dict[str, Any]) -> dict[str, Any]:
    period = float(spec["period_um"])
    return {
        "period_um": period,
        "center_wavelength_um": float(spec["center_wavelength_um"]),
        "incident_index": float(spec["incident_index"]),
        "substrate_index": float(spec["substrate_index"]),
        "ridge_index": float(spec["ridge_index"]),
        "target_transmission_order": TARGET_ORDER,
        "layer_count": LAYER_COUNT,
        "depth_bounds_um": (0.02 * period, 0.22 * period),
        "fill_fraction_bounds": (0.10, 0.90),
        "offset_fraction_bounds": (0.0, 1.0),
        "minimum_feature_fraction": MIN_FEATURE_FRACTION,
        "maximum_total_depth_um": MAX_TOTAL_DEPTH_FRACTION * period,
        "development_angles_deg": tuple(float(x) for x in spec["angles_deg"]),
        "development_wavelength_scales": tuple(
            float(x) for x in spec["wavelength_scales"]
        ),
        "polarizations": POLARIZATIONS,
        "design_columns": (
            "depth_um",
            "ridge_fill_fraction",
            "lateral_offset_fraction",
        ),
    }


def _validate_design(value: Any, problem: dict[str, Any]) -> np.ndarray:
    raw = np.asarray(value)
    if raw.shape != (int(problem["layer_count"]), 3):
        raise ValueError("return one depth/fill/offset row per grating layer")
    if raw.dtype.kind not in "iuf":
        raise ValueError("grating values must be real numeric scalars")
    design = np.asarray(raw, dtype=float)
    if not np.all(np.isfinite(design)):
        raise ValueError("grating values must be finite")
    depth_lo, depth_hi = map(float, problem["depth_bounds_um"])
    fill_lo, fill_hi = map(float, problem["fill_fraction_bounds"])
    offset_lo, offset_hi = map(float, problem["offset_fraction_bounds"])
    if np.any((design[:, 0] < depth_lo) | (design[:, 0] > depth_hi)):
        raise ValueError("layer depth is outside the public bound")
    if np.any((design[:, 1] < fill_lo) | (design[:, 1] > fill_hi)):
        raise ValueError("ridge fill fraction is outside the public bound")
    if np.any((design[:, 2] < offset_lo) | (design[:, 2] >= offset_hi)):
        raise ValueError("lateral offset must lie in [0, 1)")
    minimum = float(problem["minimum_feature_fraction"])
    if np.any(np.minimum(design[:, 1], 1.0 - design[:, 1]) < minimum):
        raise ValueError("ridge or trench violates the minimum feature fraction")
    if float(np.sum(design[:, 0])) > float(problem["maximum_total_depth_um"]):
        raise ValueError("total relief depth exceeds the public fabrication limit")
    return design


def _branch_sqrt(values: np.ndarray) -> np.ndarray:
    result = np.sqrt(np.asarray(values, dtype=complex))
    result = np.where(np.imag(result) < -1e-12, -result, result)
    result = np.where(
        (np.abs(np.imag(result)) <= 1e-12) & (np.real(result) < 0.0),
        -result,
        result,
    )
    return result


def _binary_convolution(
    ridge_epsilon: float,
    trench_epsilon: float,
    fill_fraction: float,
    center_fraction: float,
    orders: np.ndarray,
) -> np.ndarray:
    differences = orders[:, None] - orders[None, :]
    coefficients = (
        (float(ridge_epsilon) - float(trench_epsilon))
        * float(fill_fraction)
        * np.sinc(differences * float(fill_fraction))
        * np.exp(-2j * np.pi * differences * float(center_fraction))
    )
    return coefficients + np.eye(len(orders)) * float(trench_epsilon)


def _layer_modes(
    epsilon: np.ndarray,
    kx: np.ndarray,
    polarization: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = len(kx)
    kx_matrix = np.diag(kx)
    if polarization == "TE":
        operator = epsilon - kx_matrix @ kx_matrix
        eigenvalues, field = np.linalg.eig(operator)
        propagation = _branch_sqrt(eigenvalues)
        flux = field @ np.diag(propagation)
    elif polarization == "TM":
        epsilon_inverse = np.linalg.inv(epsilon)
        operator = epsilon @ (
            np.eye(count) - kx_matrix @ epsilon_inverse @ kx_matrix
        )
        eigenvalues, field = np.linalg.eig(operator)
        propagation = _branch_sqrt(eigenvalues)
        flux = epsilon_inverse @ field @ np.diag(propagation)
    else:
        raise ValueError("unknown polarization")
    return field, flux, propagation


def _rcwa_efficiencies(
    design: np.ndarray,
    wavelength_um: float,
    period_um: float,
    incident_index: float,
    substrate_index: float,
    ridge_index: float,
    incidence_angle_deg: float,
    polarization: str,
    fourier_order: int = FOURIER_ORDER,
) -> dict[str, Any]:
    """Solve one lossless 1D binary-stack scattering problem by dense matching."""

    orders = np.arange(-int(fourier_order), int(fourier_order) + 1)
    count = len(orders)
    normalized_kx = (
        float(incident_index) * math.sin(math.radians(incidence_angle_deg))
        + orders * float(wavelength_um) / float(period_um)
    )
    layer_data = []
    for depth, fill, center in np.asarray(design, dtype=float):
        epsilon = _binary_convolution(
            float(ridge_index) ** 2,
            1.0,
            float(fill),
            float(center),
            orders,
        )
        field, flux, propagation = _layer_modes(
            epsilon, normalized_kx, polarization
        )
        phase = np.diag(np.exp(
            1j * 2.0 * np.pi / float(wavelength_um)
            * propagation * float(depth)
        ))
        layer_data.append((field, flux, phase))

    incident_q = _branch_sqrt(
        float(incident_index) ** 2 - normalized_kx**2
    )
    substrate_q = _branch_sqrt(
        float(substrate_index) ** 2 - normalized_kx**2
    )
    if polarization == "TE":
        incident_admittance = incident_q
        substrate_admittance = substrate_q
    else:
        incident_admittance = incident_q / float(incident_index) ** 2
        substrate_admittance = substrate_q / float(substrate_index) ** 2
    incident_matrix = np.diag(incident_admittance)
    substrate_matrix = np.diag(substrate_admittance)
    zero_index = int(fourier_order)
    excitation = np.zeros(count, dtype=complex)
    excitation[zero_index] = 1.0
    incident_flux = float(np.real(incident_admittance[zero_index]))
    if incident_flux <= 0.0:
        raise ValueError("incident order is not propagating")

    layer_count = len(layer_data)
    size = 2 * count + 2 * count * layer_count
    matrix = np.zeros((size, size), dtype=complex)
    right = np.zeros(size, dtype=complex)
    reflected = slice(0, count)
    transmitted = slice(count, 2 * count)

    def forward(index: int) -> slice:
        start = 2 * count + 2 * count * index
        return slice(start, start + count)

    def backward(index: int) -> slice:
        start = 2 * count + 2 * count * index + count
        return slice(start, start + count)

    row = 0
    field, flux, phase = layer_data[0]
    matrix[row:row + count, reflected] = np.eye(count)
    matrix[row:row + count, forward(0)] = -field
    matrix[row:row + count, backward(0)] = -field @ phase
    right[row:row + count] = -excitation
    row += count
    matrix[row:row + count, reflected] = -incident_matrix
    matrix[row:row + count, forward(0)] = -flux
    matrix[row:row + count, backward(0)] = flux @ phase
    right[row:row + count] = -incident_flux * excitation
    row += count

    for index in range(layer_count - 1):
        field, flux, phase = layer_data[index]
        next_field, next_flux, next_phase = layer_data[index + 1]
        matrix[row:row + count, forward(index)] = field @ phase
        matrix[row:row + count, backward(index)] = field
        matrix[row:row + count, forward(index + 1)] = -next_field
        matrix[row:row + count, backward(index + 1)] = -next_field @ next_phase
        row += count
        matrix[row:row + count, forward(index)] = flux @ phase
        matrix[row:row + count, backward(index)] = -flux
        matrix[row:row + count, forward(index + 1)] = -next_flux
        matrix[row:row + count, backward(index + 1)] = next_flux @ next_phase
        row += count

    field, flux, phase = layer_data[-1]
    matrix[row:row + count, forward(layer_count - 1)] = field @ phase
    matrix[row:row + count, backward(layer_count - 1)] = field
    matrix[row:row + count, transmitted] = -np.eye(count)
    row += count
    matrix[row:row + count, forward(layer_count - 1)] = flux @ phase
    matrix[row:row + count, backward(layer_count - 1)] = -flux
    matrix[row:row + count, transmitted] = -substrate_matrix

    condition_number = float(np.linalg.cond(matrix))
    if not math.isfinite(condition_number) or condition_number > CONDITION_LIMIT:
        raise ValueError("RCWA boundary system is ill-conditioned")
    solution = np.linalg.solve(matrix, right)
    reflected_amplitude = solution[reflected]
    transmitted_amplitude = solution[transmitted]
    reflection = (
        np.maximum(0.0, np.real(incident_admittance))
        / incident_flux * np.abs(reflected_amplitude) ** 2
    )
    transmission = (
        np.maximum(0.0, np.real(substrate_admittance))
        / incident_flux * np.abs(transmitted_amplitude) ** 2
    )
    total = float(np.sum(reflection) + np.sum(transmission))
    if not (
        np.all(np.isfinite(reflection))
        and np.all(np.isfinite(transmission))
        and abs(total - 1.0) <= ENERGY_TOLERANCE
    ):
        raise ValueError("lossless RCWA energy conservation failed")
    target_index = np.where(orders == TARGET_ORDER)[0]
    target_efficiency = (
        float(transmission[target_index[0]]) if len(target_index) else 0.0
    )
    return {
        "orders": orders,
        "reflection": reflection,
        "transmission": transmission,
        "target_efficiency": target_efficiency,
        "energy_sum": total,
        "condition_number": condition_number,
    }


def _weak_baseline_design(problem: dict[str, Any]) -> np.ndarray:
    period = float(problem["period_um"])
    depth = min(
        float(problem["depth_bounds_um"][1]),
        0.11 * period,
    )
    design = np.zeros((LAYER_COUNT, 3), dtype=float)
    design[:, 0] = depth
    design[:, 1] = 0.5
    design[:, 2] = 0.5
    return design


def _reference_design(problem: dict[str, Any], spec: dict[str, Any]) -> np.ndarray:
    depths, fills, offsets = spec["reference_parameters"]
    design = np.column_stack((depths, fills, offsets)).astype(float)
    # Reference depths are stored in micrometres for their own wavelength family.
    return _validate_design(design, problem)


def _shifted_design(
    design: np.ndarray, problem: dict[str, Any], shift: dict[str, Any]
) -> np.ndarray:
    shifted = np.asarray(design, dtype=float).copy()
    phase = 2.0 * np.pi * (np.arange(len(shifted)) + 0.31) / len(shifted)
    shifted[:, 0] *= float(shift["depth_scale"]) * (
        1.0 + 0.012 * np.sin(phase)
    )
    shifted[:, 1] += float(shift["fill_offset"]) * np.cos(phase + 0.4)
    shifted[:, 2] = np.mod(
        shifted[:, 2]
        + float(shift["lateral_offset"]) * np.sin(phase + 0.8),
        1.0,
    )
    return shifted


def _realized_geometry_feasible(
    design: np.ndarray, problem: dict[str, Any]
) -> bool:
    minimum = float(problem["minimum_feature_fraction"])
    return bool(
        np.all(np.isfinite(design))
        and np.all(design[:, 0] > 0.0)
        and np.all(np.minimum(design[:, 1], 1.0 - design[:, 1]) >= minimum)
        and float(np.sum(design[:, 0]))
        <= float(problem["maximum_total_depth_um"]) + 1e-12
    )


def _condition_efficiencies(
    design: np.ndarray,
    problem: dict[str, Any],
    ridge_index_scale: float = 1.0,
    angle_offset_deg: float = 0.0,
    fourier_order: int = FOURIER_ORDER,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    records = []
    values = []
    for wavelength_scale in problem["development_wavelength_scales"]:
        wavelength = float(problem["center_wavelength_um"]) * float(
            wavelength_scale
        )
        for base_angle in problem["development_angles_deg"]:
            angle = float(base_angle) + float(angle_offset_deg)
            for polarization in POLARIZATIONS:
                result = _rcwa_efficiencies(
                    design,
                    wavelength,
                    float(problem["period_um"]),
                    float(problem["incident_index"]),
                    float(problem["substrate_index"]),
                    float(problem["ridge_index"]) * float(ridge_index_scale),
                    angle,
                    polarization,
                    fourier_order=fourier_order,
                )
                value = float(result["target_efficiency"])
                values.append(value)
                records.append({
                    "wavelength_um": wavelength,
                    "incidence_angle_deg": angle,
                    "polarization": polarization,
                    "target_efficiency": value,
                    "energy_sum": result["energy_sum"],
                    "condition_number": result["condition_number"],
                })
    return np.asarray(values, dtype=float), records


def _utility(efficiencies: np.ndarray) -> float:
    values = np.asarray(efficiencies, dtype=float)
    return float(
        0.55 * np.mean(values)
        + 0.25 * np.quantile(values, 0.20)
        + 0.20 * np.min(values)
    )


def _normalized_score(baseline: float, reference: float, value: float) -> float:
    denominator = float(reference) - float(baseline)
    if denominator <= 1e-9:
        raise ValueError("invalid reference normalization")
    return float(np.clip((float(value) - float(baseline)) / denominator, 0.0, 1.0))


def _make_world(spec: dict[str, Any]) -> dict[str, Any]:
    problem = _public_problem(spec)
    baseline_design = _validate_design(_weak_baseline_design(problem), problem)
    reference_design = _reference_design(problem, spec)
    anchors = tuple(float(value) for value in spec["anchors"])
    if len(anchors) != 4:
        raise ValueError("world anchors must contain four utilities")
    world = copy.deepcopy(spec)
    world.update({
        "problem": problem,
        "baseline_design": baseline_design,
        "reference_design": reference_design,
        "baseline_utility": anchors[0],
        "reference_utility": anchors[1],
        "baseline_robust_utility": anchors[2],
        "reference_robust_utility": anchors[3],
    })
    return world


WORLDS = tuple(_make_world(spec) for spec in WORLD_SPECS)
DEVELOPMENT_WORLDS = tuple(
    world for world in WORLDS if world["split"] == "development"
)
HELDOUT_WORLDS = tuple(world for world in WORLDS if world["split"] == "heldout")


def _evaluate_world(design_grating, world: dict[str, Any]) -> dict[str, Any]:
    problem = world["problem"]
    try:
        returned = design_grating(copy.deepcopy(problem))
        design = _validate_design(returned, problem)
        nominal_values, nominal_records = _condition_efficiencies(design, problem)
        nominal_utility = _utility(nominal_values)
        nominal_score = _normalized_score(
            world["baseline_utility"], world["reference_utility"], nominal_utility
        )
        shift_records = []
        shift_utilities = []
        for shift in SHIFT_SPECS:
            realized = _shifted_design(design, problem, shift)
            geometry_feasible = _realized_geometry_feasible(realized, problem)
            if geometry_feasible:
                shifted_values, _ = _condition_efficiencies(
                    realized,
                    problem,
                    ridge_index_scale=shift["ridge_index_scale"],
                    angle_offset_deg=shift["angle_offset_deg"],
                )
                shifted_utility = _utility(shifted_values)
            else:
                shifted_utility = 0.0
            shift_utilities.append(shifted_utility)
            shift_records.append({
                "name": shift["name"],
                "geometry_feasible": geometry_feasible,
                "utility": shifted_utility,
            })
        robust_utility = min(shift_utilities)
        robustness_score = _normalized_score(
            world["baseline_robust_utility"],
            world["reference_robust_utility"],
            robust_utility,
        )
        return {
            "name": world["name"],
            "split": world["split"],
            "valid": True,
            "failure_kind": None,
            "score": nominal_score,
            "robustness_score": robustness_score,
            "nominal_utility": nominal_utility,
            "robust_utility": robust_utility,
            "mean_target_efficiency": float(np.mean(nominal_values)),
            "twentieth_percentile_target_efficiency": float(
                np.quantile(nominal_values, 0.20)
            ),
            "minimum_target_efficiency": float(np.min(nominal_values)),
            "te_mean_target_efficiency": float(np.mean([
                row["target_efficiency"]
                for row in nominal_records if row["polarization"] == "TE"
            ])),
            "tm_mean_target_efficiency": float(np.mean([
                row["target_efficiency"]
                for row in nominal_records if row["polarization"] == "TM"
            ])),
            "maximum_energy_residual": float(max(
                abs(row["energy_sum"] - 1.0) for row in nominal_records
            )),
            "maximum_condition_number": float(max(
                row["condition_number"] for row in nominal_records
            )),
            "all_shift_geometries_feasible": all(
                row["geometry_feasible"] for row in shift_records
            ),
            "nominal_conditions": nominal_records,
            "shifts": shift_records,
        }
    except Exception:
        return {
            "name": world["name"],
            "split": world["split"],
            "valid": False,
            "failure_kind": "invalid_grating_submission",
            "score": 0.0,
            "robustness_score": 0.0,
            "nominal_utility": 0.0,
            "robust_utility": 0.0,
            "mean_target_efficiency": 0.0,
            "twentieth_percentile_target_efficiency": 0.0,
            "minimum_target_efficiency": 0.0,
            "te_mean_target_efficiency": 0.0,
            "tm_mean_target_efficiency": 0.0,
            "maximum_energy_residual": 0.0,
            "maximum_condition_number": 0.0,
            "all_shift_geometries_feasible": False,
            "nominal_conditions": [],
            "shifts": [],
        }


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    return float(np.mean([float(row[key]) for row in rows]))


def evaluate(design_grating) -> dict[str, Any]:
    records = []
    for index, world in enumerate(WORLDS):
        if index and hasattr(design_grating, "reset_session"):
            design_grating.reset_session()
        records.append(_evaluate_world(design_grating, world))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    valid = all(row["valid"] for row in records)
    combined = _mean(development, "score") if valid else 0.0
    result = {
        "combined_score": combined,
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": float(np.mean([row["valid"] for row in development])),
        "raw_score": combined,
        "robustness_score": _mean(development, "robustness_score"),
        "heldout_policy_score": _mean(heldout, "score"),
        "heldout_robustness_score": _mean(heldout, "robustness_score"),
        "development_mean_target_efficiency": _mean(
            development, "mean_target_efficiency"
        ),
        "heldout_mean_target_efficiency": _mean(
            heldout, "mean_target_efficiency"
        ),
        "development_minimum_target_efficiency": _mean(
            development, "minimum_target_efficiency"
        ),
        "heldout_minimum_target_efficiency": _mean(
            heldout, "minimum_target_efficiency"
        ),
        "development_te_mean_target_efficiency": _mean(
            development, "te_mean_target_efficiency"
        ),
        "heldout_te_mean_target_efficiency": _mean(
            heldout, "te_mean_target_efficiency"
        ),
        "development_tm_mean_target_efficiency": _mean(
            development, "tm_mean_target_efficiency"
        ),
        "heldout_tm_mean_target_efficiency": _mean(
            heldout, "tm_mean_target_efficiency"
        ),
        "development_maximum_energy_residual": max(
            row["maximum_energy_residual"] for row in development
        ),
        "heldout_maximum_energy_residual": max(
            row["maximum_energy_residual"] for row in heldout
        ),
        "development_shift_geometry_feasibility": float(np.mean([
            row["all_shift_geometries_feasible"] for row in development
        ])),
        "heldout_shift_geometry_feasibility": float(np.mean([
            row["all_shift_geometries_feasible"] for row in heldout
        ])),
        "heldout_feasibility_rate": float(np.mean([row["valid"] for row in heldout])),
        "candidate_instance_call_count": len(records),
        "candidate_instance_valid_rate": float(np.mean([row["valid"] for row in records])),
        "per_instance": records,
    }
    return result


def baseline_policy(problem: dict[str, Any]) -> np.ndarray:
    return _weak_baseline_design(problem)


def reference_policy(problem: dict[str, Any]) -> np.ndarray:
    matches = [
        world for world in WORLDS
        if abs(world["problem"]["period_um"] - problem["period_um"]) < 1e-12
        and abs(
            world["problem"]["center_wavelength_um"]
            - problem["center_wavelength_um"]
        ) < 1e-12
    ]
    if len(matches) != 1:
        raise ValueError("reference world is ambiguous")
    return np.asarray(matches[0]["reference_design"], dtype=float).copy()
