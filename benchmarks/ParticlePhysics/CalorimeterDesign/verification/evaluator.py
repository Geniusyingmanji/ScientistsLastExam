"""Reduced-order longitudinal sampling-calorimeter design oracle, version 2.

The candidate returns three Pb/scintillator longitudinal designs, one for each
public areal-cost cap.  A normalized gamma shower profile supplies containment
and active-layer signal.  Resolution combines a sampling term, photoelectron
statistics, electronics noise, a constant term and leakage fluctuations.

This transparent parameterization is an optimization benchmark.  It is not a
GEANT4 detector simulation, a test-beam calibration or an engineering design.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping

import numpy as np
from scipy.special import gammainc, gammaln


CALORIMETER_V2 = True
ARCHIVE_SIZE = 3
X0_PB_MM = 5.612
X0_SCINTILLATOR_MM = 424.0
PB_DENSITY_KG_M3 = 11340.0
CRITICAL_ENERGY_GEV = 0.00743
SHOWER_B = 0.5
SAMPLING_SCALE = 0.018
LEAKAGE_FLUCTUATION_SCALE = 0.18
DUPLICATE_TOLERANCE_MM = 1.0e-4
GEOMETRY_TOLERANCE = 1.0e-9
DESIGN_FIELDS = (
    "passive_thicknesses_mm",
    "active_thicknesses_mm",
)


# Interleaving prevents a policy with persistent process state from learning the
# development/held-out boundary.  Reference parameters are reproducible family
# witnesses filled by the fixed-seed calibration, not global-optimality claims.
INSTANCE_SPECS = (
    {
        "name": "dev_general_purpose_32",
        "split": "development",
        "n_layers": 32,
        "energies_gev": (2.0, 5.0, 10.0, 30.0, 80.0),
        "calibration_energy_gev": 10.0,
        "light_yield_pe_per_active_gev": 12500.0,
        "electronics_noise_active_gev": 0.00045,
        "constant_term": 0.0040,
        "minimum_absorber_depth_x0": 19.5,
        "maximum_absorber_depth_x0": 27.0,
        "maximum_total_length_mm": 320.0,
        "baseline_absorber_depth_x0": 21.0,
        "baseline_active_means_mm": (1.50, 3.00, 5.00),
        "lead_cost_per_kg": 2.0,
        "active_cost_per_liter": 14.0,
        "readout_areal_cost_per_layer": 20.0,
        "nominal_reference_parameters": (
            (19.81096082232441, 0.32177307171276126, 0.882581459388294,
             0.998, 0.7243048090224606, 0.10031051840588863,
             -1.0334545848475678),
            (20.08023429251501, 0.3026196632179386, 0.9694572750873705,
             0.9943119198338319, 0.7969543192192146,
             0.3819735089686235, -0.5432300047844904),
            (21.89222630369619, 0.3385901107298446, 0.6738111134203479,
             0.998, 0.7324285468229834, 0.1262721933991813,
             -0.9313828860287446),
        ),
        "robust_reference_parameters": (
            (19.512922208361683, 0.14588537969755155,
             0.6330221470230897, 0.9055466349644425,
             0.3902267675367115, 0.40967203956013054,
             0.2879421710040865),
            (19.893150824261312, 0.14456087466639225,
             0.6530937461234066, 0.9367930527754819,
             0.6879116355469828, 0.37103976411805073,
             -0.5562637617616786),
            (21.25013991551597, 0.27772787847806535,
             0.2507772205052039, 0.9547269051201083,
             0.6002449441050093, 0.48457102744838304,
             0.025521370132149016),
        ),
    },
    {
        "name": "heldout_compact_low_signal_28",
        "split": "heldout",
        "n_layers": 28,
        "energies_gev": (1.0, 3.0, 12.0, 50.0),
        "calibration_energy_gev": 12.0,
        "light_yield_pe_per_active_gev": 9000.0,
        "electronics_noise_active_gev": 0.00065,
        "constant_term": 0.0045,
        "minimum_absorber_depth_x0": 19.0,
        "maximum_absorber_depth_x0": 26.5,
        "maximum_total_length_mm": 292.0,
        "baseline_absorber_depth_x0": 20.5,
        "baseline_active_means_mm": (1.45, 2.80, 4.70),
        "lead_cost_per_kg": 2.2,
        "active_cost_per_liter": 15.5,
        "readout_areal_cost_per_layer": 23.0,
        "nominal_reference_parameters": (
            (19.0, 0.43741263720948953, 1.0, 0.998,
             0.4817945175962318, 0.15155683334933429,
             -0.16764927525722337),
            (19.0, 0.39788066647197956, 1.0, 0.998,
             0.6820459820913323, 0.1, -1.0343301887139267),
            (19.09217374462555, 0.26080706783888635,
             0.9440292590106986, 0.998, 0.7060313385164586,
             0.13186548116983363, -0.9724148933812882),
        ),
        "robust_reference_parameters": (
            (19.058927125946507, 0.1456303859691995,
             0.496532292947083, 0.896271263754641,
             0.7336973765765332, 0.29569390474245877,
             -1.1366142317410985),
            (19.056225738340054, 0.16215364490681033,
             0.4677403158362523, 0.9333785710678434,
             0.48338827478800406, 0.2362047928410676,
             -0.3730289675419611),
            (19.032144972852166, 0.28051315437883423,
             0.29594185764619624, 0.9498400308911653,
             0.5738971745872441, 0.3852843244978343,
             -0.07891838536142268),
        ),
    },
    {
        "name": "dev_high_energy_36",
        "split": "development",
        "n_layers": 36,
        "energies_gev": (5.0, 15.0, 50.0, 150.0),
        "calibration_energy_gev": 15.0,
        "light_yield_pe_per_active_gev": 15000.0,
        "electronics_noise_active_gev": 0.00040,
        "constant_term": 0.0035,
        "minimum_absorber_depth_x0": 20.0,
        "maximum_absorber_depth_x0": 28.0,
        "maximum_total_length_mm": 352.0,
        "baseline_absorber_depth_x0": 22.0,
        "baseline_active_means_mm": (1.40, 2.90, 4.90),
        "lead_cost_per_kg": 1.9,
        "active_cost_per_liter": 13.5,
        "readout_areal_cost_per_layer": 19.0,
        "nominal_reference_parameters": (
            (21.058194409143482, 0.2517516037720387,
             0.7742123641186079, 0.998, 0.7505764663866443,
             0.2670205077945325, -0.8510180264098823),
            (22.551094929493075, 0.25240529512302345,
             0.870759944688091, 0.998, 0.7203932468210917,
             0.48441533146041976, -0.26032822175115194),
            (23.320741998889027, 0.33228204959373364,
             0.7237378348442293, 0.998, 0.5759041345884244,
             0.55, 0.11777808072977419),
        ),
        "robust_reference_parameters": (
            (20.570893561184384, 0.10341600684100606,
             0.8477889520027067, 0.901448172584861,
             0.5298543948934532, 0.41512248132126844,
             -0.04545970412852606),
            (22.419396828616453, 0.19832903452753414,
             0.5385367119147358, 0.9293884067459294,
             0.38341505062917164, 0.3803118631803938,
             0.36245455641229246),
            (22.700272190715168, 0.19939471134949247,
             0.5027785840411362, 0.9488770612413909,
             0.48502077281907285, 0.5293547162313036,
             0.10953931976351294),
        ),
    },
    {
        "name": "dev_low_energy_noise_limited_30",
        "split": "development",
        "n_layers": 30,
        "energies_gev": (0.8, 2.0, 6.0, 20.0),
        "calibration_energy_gev": 6.0,
        "light_yield_pe_per_active_gev": 10500.0,
        "electronics_noise_active_gev": 0.00080,
        "constant_term": 0.0040,
        "minimum_absorber_depth_x0": 18.5,
        "maximum_absorber_depth_x0": 26.0,
        "maximum_total_length_mm": 286.0,
        "baseline_absorber_depth_x0": 20.0,
        "baseline_active_means_mm": (1.55, 3.10, 5.10),
        "lead_cost_per_kg": 2.1,
        "active_cost_per_liter": 16.0,
        "readout_areal_cost_per_layer": 21.0,
        "nominal_reference_parameters": (
            (18.5, 0.4361366496212936, 1.0, 0.998,
             0.4553186655454147, 0.11321199835495836,
             -0.13299533325385726),
            (18.5, 0.4218200222936388, 1.0, 0.998,
             0.5239333461406469, 0.14363726006909797,
             -0.6285221677432902),
            (18.51098168882024, 0.305157337929543, 1.0, 0.998,
             0.6044866005737936, 0.15030745547928012,
             -1.0380707520762666),
        ),
        "robust_reference_parameters": (
            (18.57587134277584, 0.1776089907197254,
             0.5674287224634564, 0.9015239793370486,
             0.35212185404284335, 0.1640301561209714,
             0.3241112606954879),
            (18.554951744872163, 0.24548394732692877,
             0.48918275081797513, 0.9288422342499845,
             0.41012873308243475, 0.21029453304729556,
             0.026528407229030024),
            (18.55682254296795, 0.2025960575292714,
             0.5906213207180135, 0.9574102731592498,
             0.4255110203861133, 0.3369957147289602,
             0.022100118823102467),
        ),
    },
    {
        "name": "heldout_ultra_high_energy_40",
        "split": "heldout",
        "n_layers": 40,
        "energies_gev": (3.0, 10.0, 40.0, 120.0, 250.0),
        "calibration_energy_gev": 40.0,
        "light_yield_pe_per_active_gev": 14000.0,
        "electronics_noise_active_gev": 0.00038,
        "constant_term": 0.0038,
        "minimum_absorber_depth_x0": 20.5,
        "maximum_absorber_depth_x0": 29.0,
        "maximum_total_length_mm": 390.0,
        "baseline_absorber_depth_x0": 22.5,
        "baseline_active_means_mm": (1.35, 2.75, 4.60),
        "lead_cost_per_kg": 1.8,
        "active_cost_per_liter": 13.0,
        "readout_areal_cost_per_layer": 18.0,
        "nominal_reference_parameters": (
            (21.06398108754716, 0.36490534564110155,
             -0.061010874388833125, 0.998, 0.8, 0.55,
             0.06605236888926412),
            (22.237086486162166, 0.42271967654999887,
             -0.33198492620378595, 0.998, 0.8, 0.55,
             0.07773183231095883),
            (23.944264834091353, 0.3790200445663919,
             0.7244891832319464, 0.998, 0.7542529753009436,
             0.1105543290452373, -0.9080591116208565),
        ),
        "robust_reference_parameters": (
            (21.380481352810836, 0.35283568477613525,
             0.22888285538074027, 0.8919610473040628,
             0.30111919198513815, 0.5288068245760432,
             0.6894714057953987),
            (22.161161326221084, 0.4436519502165919,
             -0.011996948810575114, 0.9325551637791676,
             0.44239938472738705, 0.5361707206036745,
             0.5458597398593575),
            (23.26362746781877, 0.28858646907168245,
             -0.25400270815008114, 0.9477923549893376,
             0.7824113451768036, 0.3916038405731125,
             -0.4607446539950514),
        ),
    },
    {
        "name": "dev_precision_linearity_34",
        "split": "development",
        "n_layers": 34,
        "energies_gev": (1.5, 4.0, 15.0, 60.0),
        "calibration_energy_gev": 15.0,
        "light_yield_pe_per_active_gev": 18000.0,
        "electronics_noise_active_gev": 0.00030,
        "constant_term": 0.0030,
        "minimum_absorber_depth_x0": 19.5,
        "maximum_absorber_depth_x0": 27.5,
        "maximum_total_length_mm": 334.0,
        "baseline_absorber_depth_x0": 21.0,
        "baseline_active_means_mm": (1.45, 2.95, 4.85),
        "lead_cost_per_kg": 2.0,
        "active_cost_per_liter": 14.5,
        "readout_areal_cost_per_layer": 20.0,
        "nominal_reference_parameters": (
            (19.5, 0.38549347562810027, 1.0, 0.998,
             0.7282128114233307, 0.1, -0.9980586570425632),
            (19.875731407088495, 0.3907500393442468,
             0.9597687872038116, 0.998, 0.7493148948446338,
             0.1, -0.9466851337034082),
            (20.832587905124978, 0.2723863882647761,
             0.7151069169864751, 0.998, 0.7614636618012837,
             0.1402031228329485, -1.0815794162325998),
        ),
        "robust_reference_parameters": (
            (19.554325757952967, 0.24667938211864635,
             0.6247521693632527, 0.89379962342458,
             0.7543052506317856, 0.2988945840862047,
             -0.8842044503436116),
            (19.669970138617682, 0.22033763962138656,
             0.6365468824808058, 0.9364730998910902,
             0.28770884678100206, 0.4024176297278086,
             0.5350075831925053),
            (19.521402893274846, 0.21290990019615638,
             0.35941502695052385, 0.9404302604225502,
             0.48373154810760904, 0.4373912892673718,
             0.12505694542029316),
        ),
    },
)


SHIFT_SPECS = (
    {
        "name": "passive_and_active_overbuild",
        "passive_scale": 1.020,
        "active_scale": 1.025,
        "passive_pattern_mm": 0.0,
        "active_pattern_mm": 0.0,
        "gain_gradient": 0.0,
        "gain_wave": 0.0,
        "dead_material_x0_per_layer": 0.0,
        "light_yield_scale": 1.0,
        "electronics_noise_scale": 1.0,
    },
    {
        "name": "anticorrelated_layer_tolerances",
        "passive_scale": 1.0,
        "active_scale": 1.0,
        "passive_pattern_mm": 0.075,
        "active_pattern_mm": -0.090,
        "gain_gradient": 0.0,
        "gain_wave": 0.0,
        "dead_material_x0_per_layer": 0.0,
        "light_yield_scale": 1.0,
        "electronics_noise_scale": 1.0,
    },
    {
        "name": "longitudinal_calibration_nonuniformity",
        "passive_scale": 1.0,
        "active_scale": 1.0,
        "passive_pattern_mm": 0.0,
        "active_pattern_mm": 0.0,
        "gain_gradient": 0.055,
        "gain_wave": 0.025,
        "dead_material_x0_per_layer": 0.0,
        "light_yield_scale": 1.0,
        "electronics_noise_scale": 1.0,
    },
    {
        "name": "dead_support_and_light_loss",
        "passive_scale": 1.0,
        "active_scale": 1.0,
        "passive_pattern_mm": 0.0,
        "active_pattern_mm": 0.0,
        "gain_gradient": 0.0,
        "gain_wave": 0.0,
        "dead_material_x0_per_layer": 0.018,
        "light_yield_scale": 0.90,
        "electronics_noise_scale": 1.10,
    },
    {
        "name": "combined_fabrication_and_calibration_shift",
        "passive_scale": 1.012,
        "active_scale": 1.018,
        "passive_pattern_mm": 0.050,
        "active_pattern_mm": -0.060,
        "gain_gradient": -0.045,
        "gain_wave": 0.020,
        "dead_material_x0_per_layer": 0.012,
        "light_yield_scale": 0.88,
        "electronics_noise_scale": 1.15,
    },
)


def _lead_mass_kg_m2(passive_mm, density_kg_m3=PB_DENSITY_KG_M3):
    """Lead areal mass; one millimetre over one square metre is 0.001 m3."""
    return float(np.sum(passive_mm) * 1.0e-3 * float(density_kg_m3))


def _areal_cost(passive_mm, active_mm, problem):
    return float(
        float(problem["lead_cost_per_kg"])
        * _lead_mass_kg_m2(
            passive_mm, problem["lead_density_kg_m3"]
        )
        + float(problem["active_cost_per_liter"])
        * float(np.sum(active_mm))
        + float(problem["readout_areal_cost_per_layer"])
        * int(problem["n_layers"])
    )


def _cost_cap(spec, active_mean_mm):
    n_layers = int(spec["n_layers"])
    passive = np.full(
        n_layers,
        float(spec["baseline_absorber_depth_x0"]) * X0_PB_MM / n_layers,
    )
    active = np.full(n_layers, float(active_mean_mm))
    provisional = {
        "lead_density_kg_m3": PB_DENSITY_KG_M3,
        "lead_cost_per_kg": spec["lead_cost_per_kg"],
        "active_cost_per_liter": spec["active_cost_per_liter"],
        "readout_areal_cost_per_layer": (
            spec["readout_areal_cost_per_layer"]
        ),
        "n_layers": n_layers,
    }
    return _areal_cost(passive, active, provisional) / 0.90


def _public_problem(spec):
    passive_bounds = (0.80, 6.00)
    active_bounds = (1.00, 8.00)
    cost_caps = tuple(
        _cost_cap(spec, value)
        for value in spec["baseline_active_means_mm"]
    )
    maximum_lead_mass = (
        float(spec["maximum_absorber_depth_x0"])
        * X0_PB_MM * 1.0e-3 * PB_DENSITY_KG_M3
    )
    return {
        "n_layers": int(spec["n_layers"]),
        "archive_size": ARCHIVE_SIZE,
        "energies_gev": tuple(float(v) for v in spec["energies_gev"]),
        "calibration_energy_gev": float(spec["calibration_energy_gev"]),
        "light_yield_pe_per_active_gev": float(
            spec["light_yield_pe_per_active_gev"]
        ),
        "electronics_noise_active_gev": float(
            spec["electronics_noise_active_gev"]
        ),
        "constant_term": float(spec["constant_term"]),
        "passive_thickness_bounds_mm": passive_bounds,
        "active_thickness_bounds_mm": active_bounds,
        "minimum_absorber_depth_x0": float(
            spec["minimum_absorber_depth_x0"]
        ),
        "maximum_lead_mass_kg_m2": float(maximum_lead_mass),
        "maximum_total_length_mm": float(spec["maximum_total_length_mm"]),
        "option_cost_caps": cost_caps,
        "lead_density_kg_m3": PB_DENSITY_KG_M3,
        "lead_cost_per_kg": float(spec["lead_cost_per_kg"]),
        "active_cost_per_liter": float(spec["active_cost_per_liter"]),
        "readout_areal_cost_per_layer": float(
            spec["readout_areal_cost_per_layer"]
        ),
        "baseline_cost_fraction": 0.90,
        "baseline_absorber_depth_x0": float(
            spec["baseline_absorber_depth_x0"]
        ),
        "radiation_length_pb_mm": X0_PB_MM,
        "radiation_length_scintillator_mm": X0_SCINTILLATOR_MM,
        "critical_energy_gev": CRITICAL_ENERGY_GEV,
        "shower_profile_b": SHOWER_B,
        "sampling_scale": SAMPLING_SCALE,
        "leakage_fluctuation_scale": LEAKAGE_FLUCTUATION_SCALE,
        "design_fields": DESIGN_FIELDS,
        "model": "transparent_longitudinal_gamma_sampling_calorimeter_v2",
    }


def _shower_shape(energy_gev):
    energy = float(energy_gev)
    if not math.isfinite(energy) or energy <= CRITICAL_ENERGY_GEV:
        raise ValueError("energy must exceed the critical energy")
    return 1.0 + SHOWER_B * (
        math.log(energy / CRITICAL_ENERGY_GEV) - 0.5
    )


def _shower_maximum_x0(energy_gev):
    return (_shower_shape(energy_gev) - 1.0) / SHOWER_B


def _shower_density(depth_x0, energy_gev):
    depth = np.asarray(depth_x0, dtype=float)
    shape = _shower_shape(energy_gev)
    safe = np.maximum(depth, np.finfo(float).tiny)
    log_density = (
        shape * math.log(SHOWER_B)
        + (shape - 1.0) * np.log(safe)
        - SHOWER_B * safe
        - gammaln(shape)
    )
    density = np.exp(log_density)
    return np.where(depth > 0.0, density, 0.0)


def _shower_cdf(depth_x0, energy_gev):
    depth = np.asarray(depth_x0, dtype=float)
    if np.any(depth < 0.0) or not np.all(np.isfinite(depth)):
        raise ValueError("depth must be finite and nonnegative")
    return gammainc(_shower_shape(energy_gev), SHOWER_B * depth)


def _layer_phase(n_layers):
    index = np.arange(int(n_layers), dtype=float)
    return 2.0 * np.pi * (index + 0.37) / float(n_layers)


def _realize_shift(passive_mm, active_mm, shift):
    passive = np.asarray(passive_mm, dtype=float)
    active = np.asarray(active_mm, dtype=float)
    phase = _layer_phase(len(passive))
    realized_passive = (
        passive * float(shift["passive_scale"])
        + float(shift["passive_pattern_mm"]) * np.sin(phase)
    )
    realized_active = (
        active * float(shift["active_scale"])
        + float(shift["active_pattern_mm"]) * np.cos(phase + 0.4)
    )
    coordinate = np.linspace(-1.0, 1.0, len(passive))
    gain = (
        1.0
        + float(shift["gain_gradient"]) * coordinate
        + float(shift["gain_wave"]) * np.sin(2.0 * phase + 0.2)
    )
    return realized_passive, realized_active, gain


def _material_intervals(passive_mm, active_mm, dead_x0_per_layer=0.0):
    passive = np.asarray(passive_mm, dtype=float)
    active = np.asarray(active_mm, dtype=float)
    starts = np.empty(len(passive), dtype=float)
    ends = np.empty(len(passive), dtype=float)
    depth = 0.0
    dead = float(dead_x0_per_layer)
    for index in range(len(passive)):
        depth += passive[index] / X0_PB_MM
        starts[index] = depth
        depth += active[index] / X0_SCINTILLATOR_MM
        ends[index] = depth
        depth += dead
    return starts, ends, float(depth)


def _signal_fraction(
    passive_mm, active_mm, energy_gev, layer_gain=None,
    dead_x0_per_layer=0.0,
):
    starts, ends, total_depth = _material_intervals(
        passive_mm, active_mm, dead_x0_per_layer
    )
    deposits = (
        _shower_cdf(ends, energy_gev)
        - _shower_cdf(starts, energy_gev)
    )
    gain = (
        np.ones(len(deposits), dtype=float)
        if layer_gain is None else np.asarray(layer_gain, dtype=float)
    )
    if gain.shape != deposits.shape or not np.all(np.isfinite(gain)):
        raise ValueError("invalid layer gain")
    signal = float(np.sum(gain * deposits))
    return signal, deposits, total_depth


def _energy_metrics(
    passive_mm, active_mm, energy_gev, problem, calibration_signal,
    layer_gain=None, dead_x0_per_layer=0.0, light_yield_scale=1.0,
    electronics_noise_scale=1.0,
):
    signal, deposits, total_depth = _signal_fraction(
        passive_mm,
        active_mm,
        energy_gev,
        layer_gain=layer_gain,
        dead_x0_per_layer=dead_x0_per_layer,
    )
    if signal <= 1.0e-12 or calibration_signal <= 1.0e-12:
        raise ValueError("active signal fraction is nonpositive")
    containment = float(_shower_cdf(total_depth, energy_gev))
    sampling_weights = np.maximum(deposits, 0.0)
    weight_sum = float(np.sum(sampling_weights))
    if weight_sum <= 1.0e-14:
        raise ValueError("shower does not reach active material")
    effective_passive_x0 = float(np.sum(
        sampling_weights * np.asarray(passive_mm, dtype=float) / X0_PB_MM
    ) / weight_sum)
    stochastic_coefficient = SAMPLING_SCALE * math.sqrt(
        effective_passive_x0 / signal
    )
    sampling_resolution = stochastic_coefficient / math.sqrt(float(energy_gev))
    photoelectrons = (
        float(energy_gev)
        * signal
        * float(problem["light_yield_pe_per_active_gev"])
        * float(light_yield_scale)
    )
    if photoelectrons <= 0.0:
        raise ValueError("nonpositive photoelectron yield")
    photostatistics_resolution = 1.0 / math.sqrt(photoelectrons)
    electronics_resolution = (
        float(problem["electronics_noise_active_gev"])
        * float(electronics_noise_scale)
        / (float(energy_gev) * signal)
    )
    constant_resolution = float(problem["constant_term"])
    leakage_resolution = LEAKAGE_FLUCTUATION_SCALE * (1.0 - containment)
    resolution = math.sqrt(
        sampling_resolution**2
        + photostatistics_resolution**2
        + electronics_resolution**2
        + constant_resolution**2
        + leakage_resolution**2
    )
    response_ratio = signal / float(calibration_signal)
    return {
        "energy_gev": float(energy_gev),
        "signal_fraction": signal,
        "containment": containment,
        "effective_passive_thickness_x0": effective_passive_x0,
        "stochastic_coefficient": stochastic_coefficient,
        "sampling_resolution": sampling_resolution,
        "photostatistics_resolution": photostatistics_resolution,
        "electronics_resolution": electronics_resolution,
        "constant_resolution": constant_resolution,
        "leakage_resolution": leakage_resolution,
        "resolution": resolution,
        "response_ratio": response_ratio,
        "photoelectrons": photoelectrons,
    }


def _metrics_for_design(passive_mm, active_mm, problem, shift=None):
    passive = np.asarray(passive_mm, dtype=float)
    active = np.asarray(active_mm, dtype=float)
    if shift is None:
        layer_gain = np.ones(len(passive), dtype=float)
        dead = 0.0
        light_scale = 1.0
        noise_scale = 1.0
    else:
        passive, active, layer_gain = _realize_shift(passive, active, shift)
        dead = float(shift["dead_material_x0_per_layer"])
        light_scale = float(shift["light_yield_scale"])
        noise_scale = float(shift["electronics_noise_scale"])
    calibration_signal, _, _ = _signal_fraction(
        passive,
        active,
        float(problem["calibration_energy_gev"]),
        layer_gain=layer_gain,
        dead_x0_per_layer=dead,
    )
    rows = tuple(
        _energy_metrics(
            passive,
            active,
            energy,
            problem,
            calibration_signal,
            layer_gain=layer_gain,
            dead_x0_per_layer=dead,
            light_yield_scale=light_scale,
            electronics_noise_scale=noise_scale,
        )
        for energy in problem["energies_gev"]
    )
    resolutions = np.asarray([row["resolution"] for row in rows])
    response_error = np.asarray([row["response_ratio"] - 1.0 for row in rows])
    containments = np.asarray([row["containment"] for row in rows])
    mean_resolution = float(np.sqrt(np.mean(resolutions**2)))
    linearity_rms = float(np.sqrt(np.mean(response_error**2)))
    maximum_nonlinearity = float(np.max(np.abs(response_error)))
    minimum_containment = float(np.min(containments))
    loss = (
        0.62 * mean_resolution / 0.08
        + 0.18 * linearity_rms / 0.08
        + 0.08 * maximum_nonlinearity / 0.15
        + 0.12 * (1.0 - minimum_containment) / 0.08
    )
    utility = math.exp(-loss)
    return {
        "utility": float(utility),
        "loss": float(loss),
        "mean_resolution": mean_resolution,
        "linearity_rms": linearity_rms,
        "maximum_nonlinearity": maximum_nonlinearity,
        "minimum_containment": minimum_containment,
        "mean_signal_fraction": float(np.mean([
            row["signal_fraction"] for row in rows
        ])),
        "total_depth_x0": float(_material_intervals(
            passive, active, dead
        )[2]),
        "energy_metrics": rows,
    }


def _geometry_metrics(passive_mm, active_mm, problem, option_index):
    passive = np.asarray(passive_mm, dtype=float)
    active = np.asarray(active_mm, dtype=float)
    absorber_depth = float(np.sum(passive) / X0_PB_MM)
    lead_mass = _lead_mass_kg_m2(passive)
    total_length = float(np.sum(passive) + np.sum(active))
    cost = _areal_cost(passive, active, problem)
    cap = float(problem["option_cost_caps"][option_index])
    passive_low, passive_high = map(
        float, problem["passive_thickness_bounds_mm"]
    )
    active_low, active_high = map(
        float, problem["active_thickness_bounds_mm"]
    )
    feasible = bool(
        np.all(np.isfinite(passive))
        and np.all(np.isfinite(active))
        and np.all(passive >= passive_low - GEOMETRY_TOLERANCE)
        and np.all(passive <= passive_high + GEOMETRY_TOLERANCE)
        and np.all(active >= active_low - GEOMETRY_TOLERANCE)
        and np.all(active <= active_high + GEOMETRY_TOLERANCE)
        and absorber_depth
        >= float(problem["minimum_absorber_depth_x0"])
        - GEOMETRY_TOLERANCE
        and lead_mass
        <= float(problem["maximum_lead_mass_kg_m2"])
        + GEOMETRY_TOLERANCE
        and total_length
        <= float(problem["maximum_total_length_mm"])
        + GEOMETRY_TOLERANCE
        and cost <= cap + GEOMETRY_TOLERANCE
    )
    return {
        "feasible": feasible,
        "absorber_depth_x0": absorber_depth,
        "lead_mass_kg_m2": lead_mass,
        "total_length_mm": total_length,
        "areal_cost": cost,
        "cost_cap": cap,
        "cost_utilization": cost / cap,
    }


def _bounded_allocation(weights, total, lower, upper):
    weights = np.asarray(weights, dtype=float)
    count = len(weights)
    total = float(total)
    lower = float(lower)
    upper = float(upper)
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
        raise ValueError("allocation weights must be positive and finite")
    if total < count * lower - 1e-10 or total > count * upper + 1e-10:
        raise ValueError("allocation total outside bounded simplex")
    lo = 0.0
    hi = max(1.0, upper / float(np.min(weights)))
    while float(np.sum(np.clip(hi * weights, lower, upper))) < total:
        hi *= 2.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if float(np.sum(np.clip(mid * weights, lower, upper))) < total:
            lo = mid
        else:
            hi = mid
    allocation = np.clip(0.5 * (lo + hi) * weights, lower, upper)
    residual = total - float(np.sum(allocation))
    free = (allocation > lower + 1e-10) & (allocation < upper - 1e-10)
    if np.any(free):
        allocation[free] += residual / int(np.sum(free))
    elif abs(residual) > 1e-8:
        index = int(np.argmax(upper - allocation) if residual > 0 else np.argmax(allocation - lower))
        allocation[index] += residual
    return allocation


def _family_parameter_bounds(problem, option_index):
    n_layers = int(problem["n_layers"])
    passive_low, passive_high = map(
        float, problem["passive_thickness_bounds_mm"]
    )
    active_low, _ = map(float, problem["active_thickness_bounds_mm"])
    fixed_and_min_active = (
        float(problem["readout_areal_cost_per_layer"]) * n_layers
        + float(problem["active_cost_per_liter"])
        * active_low * n_layers
    )
    cost_limited_passive_mm = (
        float(problem["option_cost_caps"][option_index])
        - fixed_and_min_active
    ) / (
        float(problem["lead_cost_per_kg"])
        * float(problem["lead_density_kg_m3"]) * 1.0e-3
    )
    maximum_depth = min(
        float(problem["maximum_lead_mass_kg_m2"])
        / (
            float(problem["lead_density_kg_m3"])
            * 1.0e-3 * X0_PB_MM
        ),
        n_layers * passive_high / X0_PB_MM,
        cost_limited_passive_mm / X0_PB_MM,
    )
    minimum_depth = max(
        float(problem["minimum_absorber_depth_x0"]),
        n_layers * passive_low / X0_PB_MM,
    )
    return (
        (minimum_depth, maximum_depth),
        (-1.4, 1.4),
        (-1.0, 1.0),
        (0.58, 0.998),
        (0.20, 0.80),
        (0.10, 0.55),
        (-1.2, 1.2),
    )


def _family_design(problem, option_index, parameters):
    if len(parameters) != 7:
        raise ValueError("reference family needs seven parameters")
    (
        absorber_depth_x0,
        passive_slope,
        passive_curve,
        active_fraction,
        active_center,
        active_width,
        active_slope,
    ) = map(float, parameters)
    n_layers = int(problem["n_layers"])
    coordinate = (np.arange(n_layers, dtype=float) + 0.5) / n_layers
    centered = 2.0 * coordinate - 1.0
    passive_weights = np.exp(
        passive_slope * centered
        + passive_curve * (centered**2 - 1.0 / 3.0)
    )
    passive = _bounded_allocation(
        passive_weights,
        absorber_depth_x0 * X0_PB_MM,
        *problem["passive_thickness_bounds_mm"],
    )
    cap = float(problem["option_cost_caps"][option_index])
    fixed = float(problem["readout_areal_cost_per_layer"]) * n_layers
    passive_cost = (
        float(problem["lead_cost_per_kg"])
        * _lead_mass_kg_m2(passive, problem["lead_density_kg_m3"])
    )
    active_low, active_high = map(
        float, problem["active_thickness_bounds_mm"]
    )
    maximum_active_total = min(
        n_layers * active_high,
        float(problem["maximum_total_length_mm"]) - float(np.sum(passive)),
        (cap - fixed - passive_cost)
        / float(problem["active_cost_per_liter"]),
    )
    minimum_active_total = n_layers * active_low
    if maximum_active_total < minimum_active_total - 1e-9:
        raise ValueError("reference family has no active-material budget")
    active_total = (
        minimum_active_total
        + active_fraction * (maximum_active_total - minimum_active_total)
    )
    gaussian = np.exp(
        -0.5 * ((coordinate - active_center) / active_width) ** 2
    )
    active_weights = np.exp(active_slope * centered) * (0.18 + gaussian)
    active = _bounded_allocation(
        active_weights, active_total, active_low, active_high
    )
    return passive, active


def _weak_baseline_design(problem):
    n_layers = int(problem["n_layers"])
    passive = np.full(
        (ARCHIVE_SIZE, n_layers),
        float(problem["baseline_absorber_depth_x0"])
        * X0_PB_MM / n_layers,
        dtype=float,
    )
    active = np.empty_like(passive)
    passive_cost = (
        float(problem["lead_cost_per_kg"])
        * _lead_mass_kg_m2(
            passive[0], problem["lead_density_kg_m3"]
        )
    )
    fixed = float(problem["readout_areal_cost_per_layer"]) * n_layers
    for option, cap in enumerate(problem["option_cost_caps"]):
        active_total = (
            float(problem["baseline_cost_fraction"]) * float(cap)
            - passive_cost - fixed
        ) / float(problem["active_cost_per_liter"])
        active[option] = active_total / n_layers
    return {
        "passive_thicknesses_mm": passive,
        "active_thicknesses_mm": active,
    }


def _validate_archive(returned, problem):
    if not isinstance(returned, Mapping):
        raise TypeError("design must be a mapping")
    if set(returned) != set(DESIGN_FIELDS):
        raise ValueError(
            "design fields must be exactly %s" % (DESIGN_FIELDS,)
        )
    arrays = []
    expected_shape = (ARCHIVE_SIZE, int(problem["n_layers"]))
    for field in DESIGN_FIELDS:
        raw = np.asarray(returned[field])
        if raw.dtype.kind not in "fiu" or np.iscomplexobj(raw):
            raise TypeError("%s must be a real numeric array" % field)
        value = np.asarray(raw, dtype=float)
        if value.shape != expected_shape:
            raise ValueError(
                "%s must have shape %s" % (field, expected_shape)
            )
        if not np.all(np.isfinite(value)):
            raise ValueError("%s must be finite" % field)
        arrays.append(value)
    passive, active = arrays
    for first in range(ARCHIVE_SIZE):
        for second in range(first + 1, ARCHIVE_SIZE):
            separation = max(
                float(np.max(np.abs(passive[first] - passive[second]))),
                float(np.max(np.abs(active[first] - active[second]))),
            )
            if separation <= DUPLICATE_TOLERANCE_MM:
                raise ValueError("archive contains duplicate designs")
    for option in range(ARCHIVE_SIZE):
        geometry = _geometry_metrics(
            passive[option], active[option], problem, option
        )
        if not geometry["feasible"]:
            raise ValueError(
                "archive option %d violates public geometry or cost constraints"
                % option
            )
    return passive, active


def _normalized_score(baseline, reference, observed):
    denominator = float(reference) - float(baseline)
    if not math.isfinite(denominator) or denominator <= 1.0e-10:
        raise RuntimeError("invalid calibration anchors")
    return float(np.clip(
        (float(observed) - float(baseline)) / denominator,
        0.0,
        1.0,
    ))


def _shifted_option_metrics(passive, active, problem, option, shift):
    realized_passive, realized_active, _ = _realize_shift(
        passive, active, shift
    )
    geometry = _geometry_metrics(
        realized_passive, realized_active, problem, option
    )
    if not geometry["feasible"]:
        return {
            "name": shift["name"],
            "geometry_feasible": False,
            "utility": 0.0,
            "mean_resolution": 1.0,
            "linearity_rms": 1.0,
            "maximum_nonlinearity": 1.0,
            "minimum_containment": 0.0,
            "geometry": geometry,
        }
    metrics = _metrics_for_design(
        passive, active, problem, shift=shift
    )
    return {
        "name": shift["name"],
        "geometry_feasible": True,
        **metrics,
        "geometry": geometry,
    }


def _build_instances():
    instances = []
    for spec in INSTANCE_SPECS:
        problem = _public_problem(spec)
        baseline_design = _weak_baseline_design(problem)
        baseline_options = []
        for option in range(ARCHIVE_SIZE):
            passive = baseline_design["passive_thicknesses_mm"][option]
            active = baseline_design["active_thicknesses_mm"][option]
            nominal = _metrics_for_design(passive, active, problem)
            shifted = tuple(
                _shifted_option_metrics(
                    passive, active, problem, option, shift
                )
                for shift in SHIFT_SPECS
            )
            baseline_options.append({
                "nominal": nominal,
                "robust_utility": min(
                    nominal["utility"],
                    *(row["utility"] for row in shifted),
                ),
            })
        instance = {
            "name": spec["name"],
            "split": spec["split"],
            "problem": problem,
            "baseline_design": baseline_design,
            "baseline_options": tuple(baseline_options),
            "nominal_reference_parameters": tuple(
                tuple(row) for row in spec["nominal_reference_parameters"]
            ),
            "robust_reference_parameters": tuple(
                tuple(row) for row in spec["robust_reference_parameters"]
            ),
        }
        if len(instance["nominal_reference_parameters"]) == ARCHIVE_SIZE:
            nominal_designs = tuple(
                _family_design(problem, option, parameters)
                for option, parameters in enumerate(
                    instance["nominal_reference_parameters"]
                )
            )
            robust_designs = tuple(
                _family_design(problem, option, parameters)
                for option, parameters in enumerate(
                    instance["robust_reference_parameters"]
                )
            )
            nominal_reference = []
            robust_reference = []
            for option in range(ARCHIVE_SIZE):
                nominal = _metrics_for_design(
                    *nominal_designs[option], problem
                )
                robust_shifts = tuple(
                    _shifted_option_metrics(
                        *robust_designs[option], problem, option, shift
                    )
                    for shift in SHIFT_SPECS
                )
                robust_nominal = _metrics_for_design(
                    *robust_designs[option], problem
                )
                nominal_reference.append(nominal)
                robust_reference.append({
                    "nominal": robust_nominal,
                    "robust_utility": min(
                        robust_nominal["utility"],
                        *(row["utility"] for row in robust_shifts),
                    ),
                })
            instance["nominal_reference_designs"] = nominal_designs
            instance["robust_reference_designs"] = robust_designs
            instance["nominal_reference"] = tuple(nominal_reference)
            instance["robust_reference"] = tuple(robust_reference)
        instances.append(instance)
    return tuple(instances)


INSTANCES = _build_instances()
DEVELOPMENT_INSTANCES = tuple(
    row for row in INSTANCES if row["split"] == "development"
)
HELDOUT_INSTANCES = tuple(
    row for row in INSTANCES if row["split"] == "heldout"
)


def _score_instance(design_calorimeter, instance):
    try:
        if "nominal_reference" not in instance:
            raise RuntimeError("calorimeter references have not been calibrated")
        returned = design_calorimeter(copy.deepcopy(instance["problem"]))
        passive_archive, active_archive = _validate_archive(
            returned, instance["problem"]
        )
        options = []
        for option in range(ARCHIVE_SIZE):
            passive = passive_archive[option]
            active = active_archive[option]
            nominal = _metrics_for_design(
                passive, active, instance["problem"]
            )
            geometry = _geometry_metrics(
                passive, active, instance["problem"], option
            )
            shifted = tuple(
                _shifted_option_metrics(
                    passive,
                    active,
                    instance["problem"],
                    option,
                    shift,
                )
                for shift in SHIFT_SPECS
            )
            robust_utility = min(
                nominal["utility"],
                *(row["utility"] for row in shifted),
            )
            baseline = instance["baseline_options"][option]
            options.append({
                "option_index": option,
                "valid": True,
                "score": _normalized_score(
                    baseline["nominal"]["utility"],
                    instance["nominal_reference"][option]["utility"],
                    nominal["utility"],
                ),
                "robustness_score": _normalized_score(
                    baseline["robust_utility"],
                    instance["robust_reference"][option]["robust_utility"],
                    robust_utility,
                ),
                "nominal_utility": nominal["utility"],
                "robust_utility": robust_utility,
                "mean_resolution": nominal["mean_resolution"],
                "linearity_rms": nominal["linearity_rms"],
                "maximum_nonlinearity": nominal["maximum_nonlinearity"],
                "minimum_containment": nominal["minimum_containment"],
                "mean_signal_fraction": nominal["mean_signal_fraction"],
                "shift_geometry_feasibility_rate": float(np.mean([
                    row["geometry_feasible"] for row in shifted
                ])),
                "geometry": geometry,
                "nominal": nominal,
                "shifted": shifted,
                "passive_thicknesses_mm": passive.tolist(),
                "active_thicknesses_mm": active.tolist(),
            })
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "score": float(np.mean([row["score"] for row in options])),
            "robustness_score": float(np.mean([
                row["robustness_score"] for row in options
            ])),
            "mean_resolution": float(np.mean([
                row["mean_resolution"] for row in options
            ])),
            "linearity_rms": float(np.mean([
                row["linearity_rms"] for row in options
            ])),
            "maximum_nonlinearity": float(np.max([
                row["maximum_nonlinearity"] for row in options
            ])),
            "minimum_containment": float(np.min([
                row["minimum_containment"] for row in options
            ])),
            "mean_cost_utilization": float(np.mean([
                row["geometry"]["cost_utilization"] for row in options
            ])),
            "shift_geometry_feasibility_rate": float(np.mean([
                row["shift_geometry_feasibility_rate"] for row in options
            ])),
            "options": options,
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "robustness_score": 0.0,
            "mean_resolution": 1.0,
            "linearity_rms": 1.0,
            "maximum_nonlinearity": 1.0,
            "minimum_containment": 0.0,
            "mean_cost_utilization": 0.0,
            "shift_geometry_feasibility_rate": 0.0,
        }


def _reset_candidate_session(design_calorimeter):
    reset = getattr(design_calorimeter, "reset_session", None)
    if callable(reset):
        reset()


def evaluate(design_calorimeter):
    records = []
    for index, instance in enumerate(INSTANCES):
        if index:
            _reset_candidate_session(design_calorimeter)
        records.append(_score_instance(design_calorimeter, instance))
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    development_score = float(np.mean([row["score"] for row in development]))
    heldout_score = float(np.mean([row["score"] for row in heldout]))
    result = {
        "combined_score": development_score if (
            development_valid == len(development)
        ) else 0.0,
        "valid": 1.0 if development_valid == len(development) else 0.0,
        "feasibility_rate": development_valid / len(development),
        "raw_score": development_score if (
            development_valid == len(development)
        ) else 0.0,
        "robustness_score": float(np.mean([
            row["robustness_score"] for row in development
        ])),
        "development_validation_gap": development_score - float(np.mean([
            row["robustness_score"] for row in development
        ])),
        "heldout_policy_score": heldout_score if (
            heldout_valid == len(heldout)
        ) else 0.0,
        "heldout_robustness_score": float(np.mean([
            row["robustness_score"] for row in heldout
        ])),
        "heldout_feasibility_rate": heldout_valid / len(heldout),
        "development_mean_resolution": float(np.mean([
            row["mean_resolution"] for row in development
        ])),
        "heldout_mean_resolution": float(np.mean([
            row["mean_resolution"] for row in heldout
        ])),
        "development_linearity_rms": float(np.mean([
            row["linearity_rms"] for row in development
        ])),
        "heldout_linearity_rms": float(np.mean([
            row["linearity_rms"] for row in heldout
        ])),
        "development_minimum_containment": float(np.min([
            row["minimum_containment"] for row in development
        ])),
        "heldout_minimum_containment": float(np.min([
            row["minimum_containment"] for row in heldout
        ])),
        "development_mean_cost_utilization": float(np.mean([
            row["mean_cost_utilization"] for row in development
        ])),
        "heldout_mean_cost_utilization": float(np.mean([
            row["mean_cost_utilization"] for row in heldout
        ])),
        "development_shift_geometry_feasibility_rate": float(np.mean([
            row["shift_geometry_feasibility_rate"] for row in development
        ])),
        "heldout_shift_geometry_feasibility_rate": float(np.mean([
            row["shift_geometry_feasibility_rate"] for row in heldout
        ])),
        "candidate_instance_call_count": len(records),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in records
        ])),
        "per_instance": records,
    }
    if development_valid != len(development):
        result["error_message"] = (
            "candidate invalid on a development calorimeter instance"
        )
    return result


def reference_policy(problem, robust=False):
    matches = [row for row in INSTANCES if row["problem"] == problem]
    if len(matches) != 1:
        raise ValueError("unknown calorimeter problem")
    instance = matches[0]
    key = (
        "robust_reference_designs" if robust
        else "nominal_reference_designs"
    )
    if key not in instance:
        raise RuntimeError("calorimeter references have not been calibrated")
    designs = instance[key]
    return {
        "passive_thicknesses_mm": np.vstack([
            row[0] for row in designs
        ]),
        "active_thicknesses_mm": np.vstack([
            row[1] for row in designs
        ]),
    }
