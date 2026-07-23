"""Broadband locally reacting acoustic-absorber oracle, version 2.

Candidates design one Helmholtz cell per equal panel-area partition.  The nominal
oracle combines Stinson's circular-tube dynamic density, a finite-depth rigid-backed
cavity and small-aperture radiation resistance.  A public low-frequency proxy,
interleaved held-out bands and sealed air/angle/manufacturing shifts are retained as
separate diagnostics.

This is a deterministic reduced-order acoustics benchmark.  It is not a substitute
for thermoviscous finite elements, structural coupling or impedance-tube measurements.
"""

from __future__ import annotations

import copy
import math

import numpy as np
from scipy.special import jve


ABSORBER_V2 = True
FREQUENCY_SAMPLES = 160
ABSORPTION_THRESHOLD = 0.50
AIR_DENSITY_KG_M3 = 1.204
SOUND_SPEED_M_S = 343.0
DYNAMIC_VISCOSITY_PA_S = 1.825e-5
DESIGN_COLUMNS = (
    "cavity_depth_m",
    "neck_length_m",
    "neck_radius_m",
)


# Reference parameters are fixed, replayable witnesses in the four-parameter family
# [low-frequency multiplier, high-frequency multiplier, common neck radius,
# common neck length].  They were calibrated independently for nominal and worst-shift
# utility; they are not global-optimality claims.
INSTANCE_SPECS = (
    {
        "name": "dev_low_octaves",
        "split": "development",
        "n_resonators": 8,
        "frequency_band_hz": (250.0, 1000.0),
        "maximum_total_depth_m": 0.100,
        "cell_side_m": 0.040,
        "nominal_reference_parameters": (
            1.1515347570520218, 0.788338272509079,
            0.00316949138616944, 0.002,
        ),
        "robust_reference_parameters": (
            1.150136204484, 0.785129098210, 0.003170886926,
            0.002005766199,
        ),
    },
    {
        "name": "heldout_mid_octaves",
        "split": "heldout",
        "n_resonators": 10,
        "frequency_band_hz": (400.0, 1600.0),
        "maximum_total_depth_m": 0.075,
        "cell_side_m": 0.032,
        "nominal_reference_parameters": (
            1.3962499104266386, 1.0310352154483788,
            0.005536502809408399, 0.0020096979026370046,
        ),
        "robust_reference_parameters": (
            1.3999877448130125, 0.9933024343090622,
            0.005263978004604066, 0.002,
        ),
    },
    {
        "name": "dev_bass_band",
        "split": "development",
        "n_resonators": 8,
        "frequency_band_hz": (180.0, 800.0),
        "maximum_total_depth_m": 0.120,
        "cell_side_m": 0.045,
        "nominal_reference_parameters": (
            1.191065226040, 0.794793918418, 0.002801455301,
            0.002044658502,
        ),
        "robust_reference_parameters": (
            1.1659964186156468, 0.7658142047719123,
            0.002698099966403592, 0.002,
        ),
    },
    {
        "name": "dev_high_band",
        "split": "development",
        "n_resonators": 6,
        "frequency_band_hz": (500.0, 1800.0),
        "maximum_total_depth_m": 0.065,
        "cell_side_m": 0.030,
        "nominal_reference_parameters": (
            1.398573291489, 0.947451992017, 0.005994634180,
            0.002008942264,
        ),
        "robust_reference_parameters": (
            1.3932096367157734, 0.9414675665002129,
            0.0059609611482720985, 0.0020073609448848072,
        ),
    },
    {
        "name": "heldout_wide_band",
        "split": "heldout",
        "n_resonators": 9,
        "frequency_band_hz": (300.0, 1500.0),
        "maximum_total_depth_m": 0.090,
        "cell_side_m": 0.036,
        "nominal_reference_parameters": (
            1.394602461249, 0.894786126596, 0.004813772129,
            0.002006646679,
        ),
        "robust_reference_parameters": (
            1.397497286695, 0.883941023884, 0.004707132077,
            0.002003458606,
        ),
    },
    {
        "name": "dev_mid_band",
        "split": "development",
        "n_resonators": 7,
        "frequency_band_hz": (350.0, 1250.0),
        "maximum_total_depth_m": 0.080,
        "cell_side_m": 0.034,
        "nominal_reference_parameters": (
            1.398897853777, 0.958974581481, 0.004862153186,
            0.002003986610,
        ),
        "robust_reference_parameters": (
            1.396077000938, 0.950232845429, 0.004794534238,
            0.002,
        ),
    },
)


SHIFT_SPECS = (
    {
        "name": "oblique_30deg",
        "density_scale": 1.0,
        "sound_speed_scale": 1.0,
        "viscosity_scale": 1.0,
        "incidence_angle_deg": 30.0,
        "manufacturing_sign": 0,
    },
    {
        "name": "cold_dense_air_oblique",
        "density_scale": 1.08,
        "sound_speed_scale": 0.965,
        "viscosity_scale": 0.94,
        "incidence_angle_deg": 25.0,
        "manufacturing_sign": 0,
    },
    {
        "name": "warm_light_air_oblique",
        "density_scale": 0.92,
        "sound_speed_scale": 1.035,
        "viscosity_scale": 1.06,
        "incidence_angle_deg": 35.0,
        "manufacturing_sign": 0,
    },
    {
        "name": "manufacturing_pattern_a",
        "density_scale": 1.0,
        "sound_speed_scale": 1.0,
        "viscosity_scale": 1.0,
        "incidence_angle_deg": 0.0,
        "manufacturing_sign": 1,
    },
    {
        "name": "manufacturing_pattern_b_operating_shift",
        "density_scale": 1.05,
        "sound_speed_scale": 0.98,
        "viscosity_scale": 0.97,
        "incidence_angle_deg": 30.0,
        "manufacturing_sign": -1,
    },
)


def _public_problem(spec):
    maximum_radius = min(0.007, 0.20 * float(spec["cell_side_m"]))
    return {
        "n_resonators": int(spec["n_resonators"]),
        "frequency_band_hz": tuple(spec["frequency_band_hz"]),
        "frequency_sample_count": FREQUENCY_SAMPLES,
        "maximum_total_depth_m": float(spec["maximum_total_depth_m"]),
        "cell_side_m": float(spec["cell_side_m"]),
        "cavity_depth_bounds_m": (
            0.010,
            float(spec["maximum_total_depth_m"]) - 0.004,
        ),
        "neck_length_bounds_m": (0.002, 0.018),
        "neck_radius_bounds_m": (0.002, maximum_radius),
        "air_density_kg_m3": AIR_DENSITY_KG_M3,
        "sound_speed_m_s": SOUND_SPEED_M_S,
        "dynamic_viscosity_pa_s": DYNAMIC_VISCOSITY_PA_S,
        "absorption_threshold": ABSORPTION_THRESHOLD,
        "design_columns": DESIGN_COLUMNS,
    }


def _validate_design(value, problem):
    raw = np.asarray(value)
    expected = (int(problem["n_resonators"]), len(DESIGN_COLUMNS))
    if raw.shape != expected:
        raise ValueError("return one three-column geometry row per resonator")
    if raw.dtype.kind not in "iuf":
        raise ValueError("geometry values must be real numeric scalars")
    design = np.asarray(raw, dtype=float)
    if not np.all(np.isfinite(design)):
        raise ValueError("all geometry values must be finite")
    bounds = (
        problem["cavity_depth_bounds_m"],
        problem["neck_length_bounds_m"],
        problem["neck_radius_bounds_m"],
    )
    for column, (lower, upper) in enumerate(bounds):
        if np.any(design[:, column] < float(lower)) or np.any(
            design[:, column] > float(upper)
        ):
            raise ValueError("geometry is outside a public bound")
    if np.any(
        design[:, 0] + design[:, 1]
        > float(problem["maximum_total_depth_m"]) + 1e-12
    ):
        raise ValueError("cavity depth plus neck length exceeds panel depth")
    return design


def _frequencies(problem):
    low, high = problem["frequency_band_hz"]
    return np.geomspace(float(low), float(high), int(problem["frequency_sample_count"]))


def _manufactured_design(design, sign):
    shifted = np.asarray(design, dtype=float).copy()
    if not sign:
        return shifted
    phase = 2.0 * np.pi * (np.arange(len(shifted)) + 0.37) / len(shifted)
    sign = float(sign)
    shifted[:, 0] *= 1.0 + sign * 0.035 * np.sin(phase)
    shifted[:, 1] += sign * 0.00025 * np.cos(phase + 0.4)
    shifted[:, 2] *= 1.0 + sign * 0.030 * np.sin(phase + 1.1)
    return shifted


def _shift_geometry_feasible(design, problem):
    """Check hard physical envelope constraints after manufacturing error.

    Nominal design bounds define the search/fabrication specification.  Small realized
    deviations beyond an individual lower/upper design bound remain physical, but a
    nonpositive dimension, an aperture wider than its cell or an over-thick panel does not.
    """
    design = np.asarray(design, dtype=float)
    return bool(
        np.all(np.isfinite(design))
        and np.all(design > 0.0)
        and np.all(design[:, 2] < 0.45 * float(problem["cell_side_m"]))
        and np.all(
            design[:, 0] + design[:, 1]
            <= float(problem["maximum_total_depth_m"]) + 1e-12
        )
    )


def _neck_dynamic_density(omega, radius, density, viscosity):
    argument = radius[None, :] * np.sqrt(
        -1j * omega * float(density) / float(viscosity)
    )
    bessel_zero = jve(0, argument)
    bessel_one = jve(1, argument)
    correction = 1.0 - 2.0 * bessel_one / (argument * bessel_zero)
    return float(density) / correction


def _cell_impedances(design, problem, shift=None, exact=True):
    design = np.asarray(design, dtype=float)
    density = float(problem["air_density_kg_m3"])
    sound_speed = float(problem["sound_speed_m_s"])
    viscosity = float(problem["dynamic_viscosity_pa_s"])
    angle = 0.0
    if shift is not None:
        design = _manufactured_design(design, shift["manufacturing_sign"])
        density *= float(shift["density_scale"])
        sound_speed *= float(shift["sound_speed_scale"])
        viscosity *= float(shift["viscosity_scale"])
        angle = float(shift["incidence_angle_deg"])

    depth = design[:, 0]
    neck_length = design[:, 1]
    neck_radius = design[:, 2]
    frequency = _frequencies(problem)
    omega = 2.0 * np.pi * frequency[:, None]
    wavenumber = omega / sound_speed
    opening_fraction = (
        np.pi * neck_radius**2 / float(problem["cell_side_m"]) ** 2
    )
    effective_length = neck_length + 1.70 * neck_radius

    if exact:
        dynamic_density = _neck_dynamic_density(
            omega, neck_radius, density, viscosity
        )
        neck_impedance = (
            1j * omega * dynamic_density * effective_length[None, :]
            + 0.5 * density * sound_speed
            * (wavenumber * neck_radius[None, :]) ** 2
        )
        cavity_impedance = (
            -1j * density * sound_speed
            / np.tan(wavenumber * depth[None, :])
        )
    else:
        viscous_resistance = 8.0 * viscosity * effective_length / neck_radius**2
        neck_impedance = (
            viscous_resistance[None, :]
            + 1j * omega * density * effective_length[None, :]
        )
        cavity_impedance = (
            -1j * density * sound_speed**2 / (omega * depth[None, :])
        )
    cells = neck_impedance / opening_fraction[None, :] + cavity_impedance
    if not np.all(np.isfinite(cells.real)) or not np.all(
        np.isfinite(cells.imag)
    ):
        raise ValueError("acoustic model returned non-finite cell impedance")
    return frequency, cells, density, sound_speed, angle


def _absorption_spectrum(design, problem, shift=None, exact=True):
    frequency, cells, density, sound_speed, angle = _cell_impedances(
        design, problem, shift=shift, exact=exact
    )
    panel_admittance = np.mean(1.0 / cells, axis=1)
    panel_impedance = 1.0 / panel_admittance
    if not np.all(np.isfinite(panel_impedance.real)) or not np.all(
        np.isfinite(panel_impedance.imag)
    ):
        raise ValueError("acoustic model returned non-finite panel impedance")
    resistance_tolerance = 1e-9
    if float(np.min(cells.real)) < -resistance_tolerance or float(
        np.min(panel_impedance.real)
    ) < -resistance_tolerance:
        raise ValueError("acoustic impedance violates passivity")
    characteristic_normal_impedance = (
        density * sound_speed / math.cos(math.radians(angle))
    )
    reflection = (
        (panel_impedance - characteristic_normal_impedance)
        / (panel_impedance + characteristic_normal_impedance)
    )
    raw_absorption = 1.0 - np.abs(reflection) ** 2
    if not np.all(np.isfinite(raw_absorption)):
        raise ValueError("acoustic model returned a non-finite spectrum")
    if float(np.min(raw_absorption)) < -1e-9 or float(
        np.max(raw_absorption)
    ) > 1.0 + 1e-9:
        raise ValueError("passive absorption lies outside physical bounds")
    # Passive roundoff can produce values a few ulps outside [0, 1].
    absorption = np.clip(raw_absorption.real, 0.0, 1.0)
    return frequency, absorption, panel_impedance, cells


def _spectrum_metrics(absorption):
    absorption = np.asarray(absorption, dtype=float)
    mean_absorption = float(np.mean(absorption))
    quantile_absorption = float(np.quantile(absorption, 0.20))
    coverage = float(np.mean(absorption >= ABSORPTION_THRESHOLD))
    utility = (
        0.55 * mean_absorption
        + 0.30 * quantile_absorption
        + 0.15 * coverage
    )
    return {
        "utility": float(utility),
        "mean_absorption": mean_absorption,
        "twentieth_percentile_absorption": quantile_absorption,
        "coverage_above_half": coverage,
        "minimum_absorption": float(np.min(absorption)),
    }


def _normalized_score(baseline, reference, value):
    denominator = float(reference) - float(baseline)
    if denominator <= 1e-12:
        raise ValueError("invalid reference normalization")
    return float(np.clip((float(value) - float(baseline)) / denominator, 0.0, 1.0))


def _family_design(problem, parameters):
    low_multiplier, high_multiplier, neck_radius, neck_length = map(
        float, parameters
    )
    n_resonators = int(problem["n_resonators"])
    low, high = map(float, problem["frequency_band_hz"])
    target_frequency = np.geomspace(
        low * low_multiplier, high * high_multiplier, n_resonators
    )
    radius = np.full(n_resonators, neck_radius, dtype=float)
    length = np.full(n_resonators, neck_length, dtype=float)
    opening_fraction = (
        np.pi * radius**2 / float(problem["cell_side_m"]) ** 2
    )
    effective_length = length + 1.70 * radius
    depth = (
        opening_fraction * float(problem["sound_speed_m_s"]) ** 2
        / ((2.0 * np.pi * target_frequency) ** 2 * effective_length)
    )
    depth = np.clip(
        depth,
        float(problem["cavity_depth_bounds_m"][0]),
        float(problem["maximum_total_depth_m"]) - length - 0.002,
    )
    return np.column_stack((depth, length, radius))


def _weak_baseline_design(problem):
    n_resonators = int(problem["n_resonators"])
    low, high = map(float, problem["frequency_band_hz"])
    target_frequency = math.sqrt(low * high)
    radius = np.full(n_resonators, 0.003, dtype=float)
    length = np.full(n_resonators, 0.010, dtype=float)
    opening_fraction = (
        np.pi * radius**2 / float(problem["cell_side_m"]) ** 2
    )
    effective_length = length + 1.70 * radius
    depth = (
        opening_fraction * float(problem["sound_speed_m_s"]) ** 2
        / ((2.0 * np.pi * target_frequency) ** 2 * effective_length)
    )
    depth = np.clip(
        depth,
        float(problem["cavity_depth_bounds_m"][0]),
        float(problem["maximum_total_depth_m"]) - length - 0.002,
    )
    return np.column_stack((depth, length, radius))


def _metrics_for_design(design, problem, shift=None, exact=True):
    frequency, absorption, panel_impedance, cells = _absorption_spectrum(
        design, problem, shift=shift, exact=exact
    )
    metrics = _spectrum_metrics(absorption)
    shifted_design = (
        np.asarray(design, dtype=float)
        if shift is None
        else _manufactured_design(design, shift["manufacturing_sign"])
    )
    geometry_feasible = _shift_geometry_feasible(shifted_design, problem)
    acoustic_utility = metrics["utility"]
    if not geometry_feasible:
        metrics["utility"] = 0.0
    metrics.update({
        "acoustic_utility_before_geometry_gate": acoustic_utility,
        "geometry_feasible": geometry_feasible,
        "maximum_realized_total_depth_m": float(np.max(
            shifted_design[:, 0] + shifted_design[:, 1]
        )),
        "frequency_hz": frequency.tolist(),
        "absorption": absorption.tolist(),
        "minimum_cell_resistance_pa_s_m": float(np.min(cells.real)),
        "minimum_panel_resistance_pa_s_m": float(np.min(panel_impedance.real)),
    })
    return metrics


def _make_instance(spec):
    instance = copy.deepcopy(spec)
    problem = _public_problem(spec)
    baseline = _weak_baseline_design(problem)
    nominal_reference = _family_design(
        problem, spec["nominal_reference_parameters"]
    )
    robust_reference = _family_design(
        problem, spec["robust_reference_parameters"]
    )
    _validate_design(baseline, problem)
    _validate_design(nominal_reference, problem)
    _validate_design(robust_reference, problem)
    baseline_nominal = _metrics_for_design(baseline, problem)
    reference_nominal = _metrics_for_design(nominal_reference, problem)
    baseline_shifts = tuple(
        _metrics_for_design(baseline, problem, shift=shift)
        for shift in SHIFT_SPECS
    )
    reference_shifts = tuple(
        _metrics_for_design(robust_reference, problem, shift=shift)
        for shift in SHIFT_SPECS
    )
    instance.update({
        "problem": problem,
        "baseline_design": baseline,
        "nominal_reference_design": nominal_reference,
        "robust_reference_design": robust_reference,
        "baseline_nominal": baseline_nominal,
        "nominal_reference": reference_nominal,
        "baseline_robust_utility": min(
            row["utility"] for row in baseline_shifts
        ),
        "robust_reference_utility": min(
            row["utility"] for row in reference_shifts
        ),
        "baseline_shift_metrics": baseline_shifts,
        "reference_shift_metrics": reference_shifts,
    })
    return instance


INSTANCES = tuple(_make_instance(spec) for spec in INSTANCE_SPECS)
DEVELOPMENT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "development"
)
HELDOUT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "heldout"
)


def _score_instance(design_absorber, instance):
    try:
        returned = design_absorber(copy.deepcopy(instance["problem"]))
        design = _validate_design(returned, instance["problem"])
        nominal = _metrics_for_design(design, instance["problem"])
        proxy = _metrics_for_design(
            design, instance["problem"], exact=False
        )
        shifted = tuple(
            {
                "name": shift["name"],
                **_metrics_for_design(
                    design, instance["problem"], shift=shift
                ),
            }
            for shift in SHIFT_SPECS
        )
        robust_utility = min(row["utility"] for row in shifted)
        nominal_score = _normalized_score(
            instance["baseline_nominal"]["utility"],
            instance["nominal_reference"]["utility"],
            nominal["utility"],
        )
        robustness_score = _normalized_score(
            instance["baseline_robust_utility"],
            instance["robust_reference_utility"],
            robust_utility,
        )
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "score": nominal_score,
            "robustness_score": robustness_score,
            "nominal_utility": nominal["utility"],
            "robust_utility": robust_utility,
            "proxy_utility": proxy["utility"],
            "proxy_exact_utility_gap": proxy["utility"] - nominal["utility"],
            "baseline_nominal_utility": instance["baseline_nominal"]["utility"],
            "nominal_reference_utility": instance["nominal_reference"]["utility"],
            "baseline_robust_utility": instance["baseline_robust_utility"],
            "robust_reference_utility": instance["robust_reference_utility"],
            "nominal_mean_absorption": nominal["mean_absorption"],
            "nominal_twentieth_percentile_absorption": nominal[
                "twentieth_percentile_absorption"
            ],
            "nominal_coverage_above_half": nominal["coverage_above_half"],
            "shift_geometry_feasibility_rate": float(np.mean([
                row["geometry_feasible"] for row in shifted
            ])),
            "maximum_total_depth_m": float(np.max(design[:, 0] + design[:, 1])),
            "mean_opening_fraction": float(np.mean(
                np.pi * design[:, 2] ** 2
                / float(instance["problem"]["cell_side_m"]) ** 2
            )),
            "design": design.tolist(),
            "nominal": nominal,
            "proxy": proxy,
            "shifted": shifted,
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "robustness_score": 0.0,
            "nominal_utility": 0.0,
            "robust_utility": 0.0,
            "proxy_utility": 0.0,
            "proxy_exact_utility_gap": 0.0,
            "nominal_mean_absorption": 0.0,
            "nominal_twentieth_percentile_absorption": 0.0,
            "nominal_coverage_above_half": 0.0,
            "shift_geometry_feasibility_rate": 0.0,
        }


def _reset_candidate_session(design_absorber):
    reset = getattr(design_absorber, "reset_session", None)
    if callable(reset):
        reset()


def evaluate(design_absorber):
    records = []
    for index, instance in enumerate(INSTANCES):
        if index:
            _reset_candidate_session(design_absorber)
        records.append(_score_instance(design_absorber, instance))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    development_score = float(np.mean([row["score"] for row in development]))
    development_robustness = float(np.mean([
        row["robustness_score"] for row in development
    ]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    heldout_robustness = float(np.mean([
        row["robustness_score"] for row in heldout
    ]))
    result = {
        "combined_score": development_score if (
            development_valid == len(development)
        ) else 0.0,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": development_valid / len(development),
        "raw_score": development_score if (
            development_valid == len(development)
        ) else 0.0,
        "robustness_score": development_robustness,
        "development_validation_gap": (
            development_score - development_robustness
        ),
        "heldout_policy_score": heldout_score if (
            heldout_valid == len(heldout)
        ) else 0.0,
        "heldout_robustness_score": heldout_robustness,
        "heldout_feasibility_rate": heldout_valid / len(heldout),
        "development_proxy_utility": float(np.mean([
            row["proxy_utility"] for row in development
        ])),
        "heldout_proxy_utility": float(np.mean([
            row["proxy_utility"] for row in heldout
        ])),
        "development_exact_utility": float(np.mean([
            row["nominal_utility"] for row in development
        ])),
        "heldout_exact_utility": float(np.mean([
            row["nominal_utility"] for row in heldout
        ])),
        "development_mean_absorption": float(np.mean([
            row["nominal_mean_absorption"] for row in development
        ])),
        "heldout_mean_absorption": float(np.mean([
            row["nominal_mean_absorption"] for row in heldout
        ])),
        "development_twentieth_percentile_absorption": float(np.mean([
            row["nominal_twentieth_percentile_absorption"]
            for row in development
        ])),
        "heldout_twentieth_percentile_absorption": float(np.mean([
            row["nominal_twentieth_percentile_absorption"]
            for row in heldout
        ])),
        "development_coverage_above_half": float(np.mean([
            row["nominal_coverage_above_half"] for row in development
        ])),
        "heldout_coverage_above_half": float(np.mean([
            row["nominal_coverage_above_half"] for row in heldout
        ])),
        "candidate_instance_call_count": len(records),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in records
        ])),
        "per_instance": records,
    }
    if development_valid != len(development):
        result["error_message"] = "candidate invalid on a development absorber instance"
    return result


def reference_policy(problem, robust=False):
    """Return the frozen family witness matching one public problem."""
    matches = [
        instance for instance in INSTANCES
        if instance["problem"] == problem
    ]
    if len(matches) != 1:
        raise ValueError("unknown absorber problem")
    key = "robust_reference_design" if robust else "nominal_reference_design"
    return matches[0][key].copy()
