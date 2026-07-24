"""Reduced-order silicon nMOS electrostatics and transport model.

This is deliberately a transparent compact benchmark model, not a replacement for a
two-dimensional drift--diffusion or commercial TCAD calculation.  It combines standard MOS
threshold electrostatics, a variable screening-length solution for drain coupling, the
Caughey--Thomas doping mobility law, charge-sheet current expressions and a Poisson random-
dopant estimate.  The separation makes every intermediate quantity independently testable.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.linalg import solve_banded


ELEMENTARY_CHARGE_C = 1.602176634e-19
BOLTZMANN_J_K = 1.380649e-23
VACUUM_PERMITTIVITY_F_M = 8.8541878128e-12
SILICON_PERMITTIVITY_F_M = 11.7 * VACUUM_PERMITTIVITY_F_M
OXIDE_PERMITTIVITY_F_M = 3.9 * VACUUM_PERMITTIVITY_F_M
GRID_SIZE = 121
PROFILE_COLUMNS = (
    "log10_background_acceptor_cm3",
    "log10_source_pocket_peak_cm3",
    "log10_drain_pocket_peak_cm3",
    "source_pocket_center_fraction",
    "drain_pocket_center_fraction",
    "pocket_sigma_fraction",
)


def silicon_bandgap_ev(temperature_k):
    """Varshni silicon bandgap used only for the intrinsic-density temperature shift."""
    temperature = float(temperature_k)
    return 1.17 - 4.73e-4 * temperature**2 / (temperature + 636.0)


def intrinsic_density_cm3(temperature_k):
    """Return a documented 300 K anchored intrinsic carrier-density approximation."""
    temperature = float(temperature_k)
    thermal = BOLTZMANN_J_K * temperature / ELEMENTARY_CHARGE_C
    thermal_300 = BOLTZMANN_J_K * 300.0 / ELEMENTARY_CHARGE_C
    exponent = (
        -silicon_bandgap_ev(temperature) / (2.0 * thermal)
        + silicon_bandgap_ev(300.0) / (2.0 * thermal_300)
    )
    return float(1.0e10 * (temperature / 300.0) ** 1.5 * math.exp(exponent))


def caughey_thomas_mobility_cm2_vs(doping_cm3, temperature_k):
    """Low-field electron mobility with the original Caughey--Thomas functional form."""
    doping = np.asarray(doping_cm3, dtype=float)
    minimum = 52.2
    maximum = 1417.0
    reference = 9.68e16
    exponent = 0.68
    mobility = minimum + (maximum - minimum) / (
        1.0 + (doping / reference) ** exponent
    )
    return mobility * (300.0 / float(temperature_k)) ** 2.2


def gaussian_profile_cm3(design, normalized_x, process=None):
    """Expand one six-parameter design into an active acceptor profile in cm^-3."""
    row = np.asarray(design, dtype=float)
    x = np.asarray(normalized_x, dtype=float)
    if row.shape != (6,) or not np.all(np.isfinite(row)):
        raise ValueError("doping design must be one finite six-parameter row")
    process = dict(process or {})
    background = 10.0 ** row[0]
    source_peak = 10.0 ** row[1]
    drain_peak = 10.0 ** row[2]
    sigma = float(row[5])
    profile = (
        background
        + source_peak * np.exp(-0.5 * ((x - row[3]) / sigma) ** 2)
        + drain_peak * np.exp(-0.5 * ((x - row[4]) / sigma) ** 2)
    )

    blur_fraction = float(process.get("diffusion_blur_fraction", 0.0))
    if blur_fraction > 0.0:
        spacing = float(x[1] - x[0])
        sigma_grid = blur_fraction / spacing
        radius = max(1, int(math.ceil(4.0 * sigma_grid)))
        offsets = np.arange(-radius, radius + 1, dtype=float)
        kernel = np.exp(-0.5 * (offsets / sigma_grid) ** 2)
        kernel /= float(np.sum(kernel))
        profile = np.convolve(
            np.pad(profile, radius, mode="edge"), kernel, mode="valid"
        )
    profile *= float(process.get("activation_fraction", 1.0))
    if bool(process.get("reverse_source_drain", False)):
        profile = profile[::-1]
    return np.asarray(profile, dtype=float)


def _screened_drain_potential(channel_length_m, screening_length_m, drain_v):
    """Solve -u'' + u/lambda(x)^2 = 0 with source/drain Dirichlet values."""
    screening = np.asarray(screening_length_m, dtype=float)
    if screening.shape != (GRID_SIZE,) or np.any(screening <= 0.0):
        raise ValueError("invalid screening length")
    spacing = float(channel_length_m) / (GRID_SIZE - 1)
    interior = GRID_SIZE - 2
    banded = np.zeros((3, interior), dtype=float)
    banded[0, 1:] = -1.0 / spacing**2
    banded[1, :] = 2.0 / spacing**2 + 1.0 / screening[1:-1] ** 2
    banded[2, :-1] = -1.0 / spacing**2
    rhs = np.zeros(interior, dtype=float)
    rhs[-1] = float(drain_v) / spacing**2
    potential = np.zeros(GRID_SIZE, dtype=float)
    potential[-1] = float(drain_v)
    potential[1:-1] = solve_banded((1, 1), banded, rhs)
    return potential


def evaluate_device(design, device, process=None):
    """Evaluate one profile and return finite physical diagnostics and feasibility."""
    process = dict(process or {})
    temperature = float(device["temperature_k"]) + float(
        process.get("temperature_delta_k", 0.0)
    )
    length_m = (
        float(device["channel_length_nm"])
        * float(process.get("channel_length_scale", 1.0))
        * 1.0e-9
    )
    oxide_m = (
        float(device["oxide_eot_nm"])
        * float(process.get("oxide_eot_scale", 1.0))
        * 1.0e-9
    )
    supply_v = float(device["supply_voltage_v"])
    flatband_v = float(device["flatband_voltage_v"]) + float(
        process.get("flatband_voltage_delta_v", 0.0)
    )
    body_depth_m = float(device["body_depth_nm"]) * 1.0e-9
    width_m = float(device.get("width_um", 1.0)) * 1.0e-6
    if not (
        temperature > 0.0 and length_m > 0.0 and oxide_m > 0.0
        and supply_v > 0.0 and body_depth_m > 0.0 and width_m > 0.0
    ):
        raise ValueError("invalid device condition")

    normalized_x = np.linspace(0.0, 1.0, GRID_SIZE)
    doping_cm3 = gaussian_profile_cm3(design, normalized_x, process)
    doping_m3 = doping_cm3 * 1.0e6
    thermal_v = BOLTZMANN_J_K * temperature / ELEMENTARY_CHARGE_C
    intrinsic_cm3 = intrinsic_density_cm3(temperature)
    fermi_v = thermal_v * np.log(doping_cm3 / intrinsic_cm3)
    if np.any(fermi_v <= 0.0):
        raise ValueError("acceptor profile is not extrinsic p-type")
    oxide_capacitance = OXIDE_PERMITTIVITY_F_M / oxide_m
    depletion_m = np.minimum(
        np.sqrt(
            4.0 * SILICON_PERMITTIVITY_F_M * fermi_v
            / (ELEMENTARY_CHARGE_C * doping_m3)
        ),
        body_depth_m,
    )
    screening_m = np.sqrt(
        SILICON_PERMITTIVITY_F_M
        / OXIDE_PERMITTIVITY_F_M
        * oxide_m
        * depletion_m
    )
    local_long_threshold = (
        flatband_v
        + 2.0 * fermi_v
        + np.sqrt(
            4.0
            * ELEMENTARY_CHARGE_C
            * SILICON_PERMITTIVITY_F_M
            * doping_m3
            * fermi_v
        )
        / oxide_capacitance
    )

    core = np.flatnonzero(
        (normalized_x >= 0.04) & (normalized_x <= 0.92)
    )
    zero_drain_threshold = float(np.max(local_long_threshold[core]))
    drain_potential = _screened_drain_potential(
        length_m, screening_m, supply_v
    )
    threshold_field = local_long_threshold[core] - drain_potential[core]
    barrier_index = int(core[int(np.argmax(threshold_field))])
    threshold_v = float(threshold_field.max())
    dibl_v = float(max(0.0, zero_drain_threshold - threshold_v))

    depletion_capacitance = (
        SILICON_PERMITTIVITY_F_M / depletion_m[barrier_index]
    )
    subthreshold_factor = float(1.0 + depletion_capacitance / oxide_capacitance)
    subthreshold_swing_mv_dec = float(
        math.log(10.0) * subthreshold_factor * thermal_v * 1.0e3
    )

    mobility_cm2 = caughey_thomas_mobility_cm2_vs(doping_cm3, temperature)
    mobility_m2 = float(1.0e-4 / np.mean(1.0 / mobility_cm2))
    overdrive_v = float(max(0.0, supply_v - threshold_v))
    mobility_m2 /= 1.0 + 0.35 * overdrive_v
    saturation_velocity_m_s = 1.07e5 * (300.0 / temperature) ** 0.87
    critical_field_v_m = saturation_velocity_m_s / max(mobility_m2, 1.0e-30)
    velocity_saturation_factor = 1.0 + overdrive_v / max(
        critical_field_v_m * length_m, 1.0e-30
    )

    on_current_a_per_m = (
        mobility_m2
        * oxide_capacitance
        * overdrive_v**2
        / (2.0 * length_m * velocity_saturation_factor)
    )
    # Weak inversion charge-sheet current per unit gate width.  The compact
    # prefactor is idealized, but both this quantity and the strong-inversion
    # expression above have A/m units; the reported conversions below are
    # therefore mA/um and nA/um, respectively.
    off_current_a_per_m = (
        mobility_m2
        * oxide_capacitance
        / length_m
        * subthreshold_factor
        * thermal_v**2
        * math.exp(float(np.clip(
            -threshold_v / (subthreshold_factor * thermal_v), -100.0, 40.0
        )))
        * (1.0 - math.exp(-supply_v / thermal_v))
    )
    on_current_ma_per_um = float(on_current_a_per_m * 1.0e-3)
    off_current_na_per_um = float(off_current_a_per_m * 1.0e3)

    position_m = normalized_x * length_m
    dose_cm2 = float(np.trapz(doping_cm3, position_m * 100.0))
    expected_depleted_dopants = float(
        width_m * np.trapz(doping_m3 * depletion_m, position_m)
    )
    random_dopant_sigma_v = float(
        ELEMENTARY_CHARGE_C
        * math.sqrt(max(expected_depleted_dopants, 0.0))
        / (oxide_capacitance * width_m * length_m)
    )
    log_gradient_per_fraction = float(np.max(np.abs(np.gradient(
        np.log10(doping_cm3), normalized_x
    ))))

    constraints = device["constraints"]
    checks = {
        "threshold_window": (
            float(constraints["minimum_threshold_v"]) <= threshold_v
            <= float(constraints["maximum_threshold_v"])
        ),
        "on_current": on_current_ma_per_um >= float(
            constraints["minimum_on_current_ma_per_um"]
        ),
        "dibl": dibl_v <= float(constraints["maximum_dibl_v"]),
        "subthreshold_swing": subthreshold_swing_mv_dec <= float(
            constraints["maximum_subthreshold_swing_mv_dec"]
        ),
        "random_dopant_variation": random_dopant_sigma_v <= float(
            constraints["maximum_random_dopant_sigma_v"]
        ),
        "implant_dose": dose_cm2 <= float(constraints["maximum_dose_cm2"]),
        "active_doping": float(np.max(doping_cm3)) <= float(
            constraints["maximum_active_doping_cm3"]
        ),
        "profile_gradient": log_gradient_per_fraction <= float(
            constraints["maximum_log_gradient_per_fraction"]
        ),
    }
    finite_values = (
        threshold_v, dibl_v, subthreshold_swing_mv_dec,
        on_current_ma_per_um, off_current_na_per_um, dose_cm2,
        random_dopant_sigma_v,
        log_gradient_per_fraction,
    )
    finite = bool(np.all(np.isfinite(finite_values)))
    return {
        "process_feasible": bool(finite and all(checks.values())),
        "constraint_checks": checks,
        "threshold_voltage_v": threshold_v,
        "zero_drain_threshold_voltage_v": zero_drain_threshold,
        "dibl_v": dibl_v,
        "subthreshold_swing_mv_dec": subthreshold_swing_mv_dec,
        "on_current_ma_per_um": on_current_ma_per_um,
        "off_current_na_per_um": off_current_na_per_um,
        "log10_on_off_ratio": float(math.log10(
            max(on_current_ma_per_um * 1.0e6
                / max(off_current_na_per_um, 1.0e-300),
                1.0e-300)
        )),
        "effective_mobility_cm2_vs": mobility_m2 * 1.0e4,
        "implant_dose_cm2": dose_cm2,
        "maximum_active_doping_cm3": float(np.max(doping_cm3)),
        "random_dopant_sigma_v": random_dopant_sigma_v,
        "maximum_screening_length_nm": float(np.max(screening_m) * 1.0e9),
        "barrier_position_fraction": float(normalized_x[barrier_index]),
        "maximum_log_gradient_per_fraction": log_gradient_per_fraction,
    }
