"""Resource-constrained finite-absorption tandem-PV oracle, version 1.

The candidate returns one series-connected tandem design for each of three
public fabrication budgets.  The public model combines a hash-bound ASTM G173
global-tilt spectrum, Beer--Lambert-like direct-gap absorption, radiative dark
current and maximum-power-point series current matching.  Hidden perturbations
separately test spectral, temperature, band-gap and optical-depth robustness.

This is a transparent detailed-balance optimization benchmark.  It is not a
device simulator, a material recommendation or an experimental efficiency
claim.  It omits non-radiative recombination, transport, interfaces, tunnel
junctions, luminescent coupling, sheet resistance and thermal balance.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar


PHOTOVOLTAIC_TANDEM_V1 = True
ARCHIVE_SIZE = 3
MAX_JUNCTIONS = 4
BANDGAP_BOUNDS_EV = (0.60, 2.30)
OPTICAL_DEPTH_BOUNDS = (0.20, 5.00)
MINIMUM_BANDGAP_SEPARATION_EV = 0.10
JUNCTION_OVERHEAD_COST = 0.45
OPTICAL_DEPTH_COST = 1.00
DATA_SHA256 = "eeb37120e14ad2fbb5e986d63b5f7711fbf622a03ebf67edabea618df397a728"

ELEMENTARY_CHARGE_C = 1.602176634e-19
PLANCK_J_S = 6.62607015e-34
LIGHT_M_S = 299792458.0
BOLTZMANN_J_K = 1.380649e-23
HC_EV_NM = 1239.8419843320026


DATA_PATH = Path(__file__).resolve().with_name("astm_g173_v1.json")


def _load_spectrum_data():
    payload = DATA_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise ValueError("photovoltaic spectrum bundle hash mismatch")
    document = json.loads(payload.decode("utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError("unexpected photovoltaic spectrum schema")
    rows = np.asarray(document.get("rows"), dtype=float)
    if rows.shape != (2002, 4) or not np.all(np.isfinite(rows)):
        raise ValueError("invalid photovoltaic spectrum table")
    wavelength = rows[:, 0]
    if not (
        wavelength[0] == 280.0
        and wavelength[-1] == 4000.0
        and np.all(np.diff(wavelength) > 0.0)
    ):
        raise ValueError("invalid photovoltaic wavelength grid")
    return document, wavelength, rows[:, 2]


SPECTRUM_DOCUMENT, BASE_WAVELENGTH_NM, BASE_GLOBAL_IRRADIANCE = _load_spectrum_data()
BASE_GLOBAL_POWER_W_M2 = float(np.trapz(BASE_GLOBAL_IRRADIANCE, BASE_WAVELENGTH_NM))


# Interleaved public spectral families are evaluated in fresh candidate
# processes.  The parameters generate observable spectra; neither split nor
# seed is included in the candidate problem.
DEVELOPMENT_SPECS = (
    (5101, 0.000, 0.00, 1.00, 300.0, (2.0, 4.5, 9.0)),
    (5102, -0.018, 0.16, 0.82, 292.0, (2.2, 5.0, 9.8)),
    (5103, 0.024, -0.14, 0.68, 315.0, (1.9, 4.8, 10.2)),
    (5104, -0.010, 0.08, 1.12, 305.0, (2.5, 5.5, 11.0)),
    (5105, 0.032, -0.20, 0.91, 322.0, (2.1, 5.2, 12.0)),
)
HELDOUT_SPECS = (
    (6101, -0.028, 0.22, 0.74, 287.0, (2.3, 4.7, 9.4)),
    (6102, 0.017, -0.10, 1.06, 310.0, (2.0, 5.8, 10.5)),
    (6103, 0.039, -0.24, 0.59, 326.0, (2.4, 5.1, 11.5)),
)


# Filled by the deterministic calibration search.  Each row is
# (bandgaps_eV, optical_depths), one row per public budget cap.
NOMINAL_REFERENCE_DESIGNS = {
    5101: (
        ((1.1040445111782398,), (1.5500000000798295,)),
        ((1.4284516075858256, 0.911772009973386),
         (1.8371102174983434, 1.7628800541351377)),
        ((1.6847961857253282, 1.1239650394095686, 0.6883786230945826),
         (3.053989122285674, 2.38672998410791, 2.205633179987866)),
    ),
    5102: (
        ((1.131242686556054,), (1.7499999996198736,)),
        ((1.5440223159704014, 0.9364460936681895),
         (2.180405912946621, 1.9195704893268832)),
        ((1.8929362365797124, 1.4321934742273021, 1.0130579354455607,
          0.6812944210462352),
         (2.301228453251592, 2.2016899012316085, 1.726854980409161,
          1.7702261073430703)),
    ),
    5103: (
        ((0.9266382544720758,), (1.4499999998905528,)),
        ((1.356543976592504, 0.8888093319694201),
         (1.9521124013352513, 1.9478833996456157)),
        ((1.5986553575625346, 1.0853863791915561, 0.6746669506415524),
         (3.427479898101356, 2.9111938683919867, 2.5071622164969085)),
    ),
    5104: (
        ((1.1240634500553721,), (2.049999999887226,)),
        ((1.5212886806073658, 0.9294208385673216),
         (2.414899076510877, 2.185022272501918)),
        ((1.7635158332403151, 1.188996972984619, 0.6917407431836164),
         (3.7206044413150323, 3.1121376757992194, 2.8161877340795507)),
    ),
    5105: (
        ((0.9170428883804344,), (1.6500000000394497,)),
        ((1.341823733082429, 0.881874327513126),
         (2.1400120228995476, 2.159979043574188)),
        ((1.687720359982885, 1.23122361171325, 0.9199291939580462,
          0.6673869412236475),
         (3.0334054549348872, 2.3790787797246096, 2.073958712561201,
          2.7135570366906787)),
    ),
    6101: (
        ((1.1480018373905052,), (1.8500000000280918,)),
        ((1.5635253003294214, 0.9473221214956766),
         (2.015298828467134, 1.7846258496388852)),
        ((1.9047130215111978, 1.3651500657289148, 0.9401807354860823),
         (2.88233189662268, 2.572106361204709, 2.5952217098908115)),
    ),
    6102: (
        ((0.9435631540815322,), (1.549999999990148,)),
        ((1.4950258628361908, 1.0771099311740457, 0.6724805719987996),
         (1.6670438262381846, 1.5494177772208713, 1.2329343548270926)),
        ((1.6166372903620578, 1.104357877866702, 0.6756835751291767),
         (3.4565825806632007, 2.979042963780418, 2.707985740872053)),
    ),
    6103: (
        ((0.9225014766451468,), (1.9500000000683295,)),
        ((1.3274581062508655, 0.8768420505062289),
         (2.1254540685914725, 2.074518507443825)),
        ((1.598187253464604, 1.251786925286246, 0.9026041374620913,
          0.654926497608002),
         (2.4196762267993592, 2.8825867656265505, 2.031475874818879,
          2.366259005105535)),
    ),
}

ROBUST_REFERENCE_DESIGNS = {
    5101: (
        ((1.1112517226881824,), (1.5499999996674432,)),
        ((1.406606934389088, 0.8544591302808561),
         (1.843805068980746, 1.7561948395596274)),
        ((1.6839600506224133, 1.0930928212442157, 0.6276829746150706),
         (3.097987263473634, 2.6170834240029217, 1.9333797466455418)),
    ),
    5102: (
        ((1.139044510188345,), (1.7499999999268439,)),
        ((1.523428786800914, 0.8800403250130217),
         (2.200286082813492, 1.8997014827156722)),
        ((1.7996439215090247, 1.1305229278573394, 0.6641431591236252),
         (3.4702944610951794, 2.572551866411261, 2.394750063789248)),
    ),
    5103: (
        ((0.9439750621398025,), (1.4500000000917588,)),
        ((1.3498038462455348, 0.8346207281027186),
         (1.9933324397210535, 1.906660964090562)),
        ((1.595941067372935, 1.0256225403209687, 0.6256476706970463),
         (3.600687049936369, 2.8573712155344455, 2.388240348366714)),
    ),
    5104: (
        ((1.1302667710206542,), (2.0500000000147294,)),
        ((1.4970966934591885, 0.872046901490704),
         (2.4179279669101983, 2.1820252458066274)),
        ((1.8319112434383393, 1.2779996248774192, 0.7332805341505606),
         (3.8359041902773368, 3.6442687982488535, 2.108706017382347)),
    ),
    5105: (
        ((0.9321360239929777,), (1.6500000000707273,)),
        ((1.3360276394896777, 0.8260139871270297),
         (2.191050639192, 2.108927460557985)),
        ((1.5926799016087783, 1.0206194130234731, 0.6238021185175998),
         (4.498505244238541, 3.2332205531798093, 2.9043120110108664)),
    ),
    6101: (
        ((1.1550017928281688,), (1.8499999999392478,)),
        ((1.5360252518973465, 0.888235460852461),
         (2.023135932044145, 1.7768425012548374)),
        ((1.892575163635695, 1.3200295329399774, 0.9071987445613593),
         (2.9428529403163814, 2.589566348091831, 2.512122080085444)),
    ),
    6102: (
        ((0.972853241079727,), (1.5499999998130933,)),
        ((1.3959821276454016, 0.8425241910947137),
         (2.486261763671638, 2.4137323831081634)),
        ((1.6125087572377532, 1.0510887206452335, 0.6211520896833695),
         (3.604037842429043, 2.9492373873306614, 2.596378038707518)),
    ),
    6103: (
        ((1.0664825164896832,), (1.9499999996242834,)),
        ((1.3171795691078445, 0.8218822027321204),
         (2.1492431674708627, 2.0507124345163916)),
        ((1.541755240045582, 1.016857656137586, 0.6296075879636164),
         (3.9301295443756175, 3.3609631851255566, 2.8367163003990816)),
    ),
}


SHIFT_NAMES = (
    "hot_cell",
    "bandgap_process",
    "thin_absorbers",
    "blue_spectrum",
    "red_spectrum",
    "combined",
)


def _spectrum_from_spec(spec):
    seed, warp, tilt, irradiance_scale, _, _ = spec
    wavelength = BASE_WAVELENGTH_NM
    source_wavelength = wavelength / (1.0 + float(warp))
    irradiance = np.interp(
        source_wavelength,
        wavelength,
        BASE_GLOBAL_IRRADIANCE,
        left=0.0,
        right=0.0,
    ) / (1.0 + float(warp))
    photon_energy = HC_EV_NM / wavelength
    tilt_weight = np.exp(float(tilt) * (photon_energy - 1.35))
    rng = np.random.default_rng(int(seed))
    for _ in range(2):
        center = rng.uniform(650.0, 1900.0)
        width = rng.uniform(35.0, 135.0)
        depth = rng.uniform(0.025, 0.12)
        tilt_weight *= 1.0 - depth * np.exp(
            -0.5 * ((wavelength - center) / width) ** 2
        )
    irradiance = np.maximum(0.0, irradiance * tilt_weight)
    integral = float(np.trapz(irradiance, wavelength))
    target = float(irradiance_scale) * BASE_GLOBAL_POWER_W_M2
    if integral <= 0.0:
        raise ValueError("procedural spectrum has zero power")
    return irradiance * (target / integral)


def _make_world(spec):
    return {
        "seed": int(spec[0]),
        "spectrum_w_m2_nm": _spectrum_from_spec(spec),
        "cell_temperature_k": float(spec[4]),
        "fabrication_budget_caps": tuple(float(value) for value in spec[5]),
    }


def _public_problem(world):
    return {
        "wavelength_nm": BASE_WAVELENGTH_NM.tolist(),
        "spectral_irradiance_w_m2_nm": world["spectrum_w_m2_nm"].tolist(),
        "incident_power_w_m2": float(np.trapz(
            world["spectrum_w_m2_nm"], BASE_WAVELENGTH_NM
        )),
        "cell_temperature_k": world["cell_temperature_k"],
        "fabrication_budget_caps": list(world["fabrication_budget_caps"]),
        "archive_size": ARCHIVE_SIZE,
        "maximum_junction_count": MAX_JUNCTIONS,
        "bandgap_bounds_ev": list(BANDGAP_BOUNDS_EV),
        "optical_depth_bounds": list(OPTICAL_DEPTH_BOUNDS),
        "minimum_bandgap_separation_ev": MINIMUM_BANDGAP_SEPARATION_EV,
        "junction_overhead_cost": JUNCTION_OVERHEAD_COST,
        "optical_depth_cost": OPTICAL_DEPTH_COST,
        "absorption_model": (
            "1-exp(-optical_depth*sqrt(max(photon_energy/bandgap-1,0)))"
        ),
        "connection": "series_current_matched",
    }


def _numeric_vector(value, name):
    if isinstance(value, (str, bytes)):
        raise ValueError("%s must be a numeric sequence" % name)
    array = np.asarray(value)
    if array.ndim != 1 or array.size < 1 or array.size > MAX_JUNCTIONS:
        raise ValueError("%s has invalid length" % name)
    if array.dtype.kind not in "iuf":
        raise ValueError("%s must be real numeric" % name)
    array = array.astype(float)
    if not np.all(np.isfinite(array)):
        raise ValueError("%s must be finite" % name)
    return array


def _validate_design(value, problem, option_index):
    if not isinstance(value, Mapping) or set(value) != {
        "bandgaps_ev", "optical_depths"
    }:
        raise ValueError("each design must have exactly bandgaps_ev and optical_depths")
    gaps = _numeric_vector(value["bandgaps_ev"], "bandgaps_ev")
    depths = _numeric_vector(value["optical_depths"], "optical_depths")
    if gaps.size != depths.size:
        raise ValueError("bandgaps and optical depths must have equal length")
    low_gap, high_gap = map(float, problem["bandgap_bounds_ev"])
    low_depth, high_depth = map(float, problem["optical_depth_bounds"])
    if np.any(gaps < low_gap) or np.any(gaps > high_gap):
        raise ValueError("bandgap lies outside public bounds")
    if np.any(depths < low_depth) or np.any(depths > high_depth):
        raise ValueError("optical depth lies outside public bounds")
    if gaps.size > 1 and np.any(
        gaps[:-1] - gaps[1:]
        < float(problem["minimum_bandgap_separation_ev"]) - 1.0e-12
    ):
        raise ValueError("bandgaps must decrease with the public minimum separation")
    cost = (
        float(problem["junction_overhead_cost"]) * gaps.size
        + float(problem["optical_depth_cost"]) * float(np.sum(depths))
    )
    cap = float(problem["fabrication_budget_caps"][option_index])
    if cost > cap + 1.0e-10:
        raise ValueError("design exceeds its fabrication budget")
    return {
        "bandgaps_ev": gaps,
        "optical_depths": depths,
        "junction_count": int(gaps.size),
        "fabrication_cost": float(cost),
        "cost_utilization": float(cost / cap),
    }


def _validate_submission(value, problem):
    if not isinstance(value, Mapping) or set(value) != {"designs"}:
        raise ValueError("submission must contain exactly designs")
    designs = value["designs"]
    if not isinstance(designs, (list, tuple)) or len(designs) != ARCHIVE_SIZE:
        raise ValueError("designs must match archive_size")
    normalized = [
        _validate_design(design, problem, index)
        for index, design in enumerate(designs)
    ]
    signatures = {
        (
            tuple(np.round(row["bandgaps_ev"], 8)),
            tuple(np.round(row["optical_depths"], 8)),
        )
        for row in normalized
    }
    if len(signatures) != ARCHIVE_SIZE:
        raise ValueError("archive designs must be distinct")
    return normalized


def _absorptance(photon_energy_ev, bandgap_ev, optical_depth):
    above = np.maximum(photon_energy_ev / float(bandgap_ev) - 1.0, 0.0)
    return 1.0 - np.exp(-float(optical_depth) * np.sqrt(above))


def _blackbody_photon_flux_per_nm(wavelength_nm, temperature_k):
    wavelength_m = np.asarray(wavelength_nm, dtype=float) * 1.0e-9
    exponent = (
        PLANCK_J_S * LIGHT_M_S
        / (wavelength_m * BOLTZMANN_J_K * float(temperature_k))
    )
    return (
        2.0 * math.pi * LIGHT_M_S
        / wavelength_m ** 4
        / np.expm1(np.clip(exponent, 0.0, 700.0))
        * 1.0e-9
    )


def _device_performance(
    wavelength_nm,
    irradiance_w_m2_nm,
    temperature_k,
    bandgaps_ev,
    optical_depths,
    front_transmission=1.0,
):
    wavelength = np.asarray(wavelength_nm, dtype=float)
    irradiance = np.asarray(irradiance_w_m2_nm, dtype=float)
    gaps = np.asarray(bandgaps_ev, dtype=float)
    depths = np.asarray(optical_depths, dtype=float)
    if not (
        wavelength.ndim == irradiance.ndim == gaps.ndim == depths.ndim == 1
        and wavelength.size == irradiance.size
        and gaps.size == depths.size
        and np.all(np.isfinite(irradiance))
        and np.all(irradiance >= 0.0)
    ):
        raise ValueError("invalid detailed-balance inputs")
    incident_power = float(np.trapz(irradiance, wavelength))
    if incident_power <= 0.0:
        raise ValueError("incident spectrum has zero power")
    photon_energy_ev = HC_EV_NM / wavelength
    photon_energy_j = photon_energy_ev * ELEMENTARY_CHARGE_C
    photon_flux = irradiance / photon_energy_j
    blackbody_flux = _blackbody_photon_flux_per_nm(wavelength, temperature_k)
    transmission = np.full(wavelength.size, float(front_transmission), dtype=float)
    short_circuit = []
    dark_current = []
    absorbed_fractions = []
    for gap, depth in zip(gaps, depths):
        absorptance = _absorptance(photon_energy_ev, gap, depth)
        absorbed = transmission * absorptance
        short_circuit.append(
            ELEMENTARY_CHARGE_C * float(np.trapz(photon_flux * absorbed, wavelength))
        )
        # Independent radiative junction emission.  Luminescent coupling and
        # re-absorption by upper junctions are intentionally omitted.
        dark_current.append(
            ELEMENTARY_CHARGE_C
            * float(np.trapz(blackbody_flux * absorptance, wavelength))
        )
        absorbed_fractions.append(
            float(np.trapz(irradiance * absorbed, wavelength) / incident_power)
        )
        transmission *= 1.0 - absorptance
    jsc = np.asarray(short_circuit, dtype=float)
    j0 = np.maximum(np.asarray(dark_current, dtype=float), 1.0e-300)
    upper = float(np.min(jsc)) * (1.0 - 1.0e-12)
    if upper <= 0.0:
        return {
            "efficiency": 0.0,
            "power_w_m2": 0.0,
            "operating_current_a_m2": 0.0,
            "operating_voltage_v": 0.0,
            "short_circuit_currents_a_m2": jsc,
            "current_matching_ratio": 0.0,
            "absorbed_power_fractions": absorbed_fractions,
        }
    thermal_voltage = BOLTZMANN_J_K * float(temperature_k) / ELEMENTARY_CHARGE_C

    def power(current):
        voltage = thermal_voltage * np.sum(np.log1p((jsc - current) / j0))
        return float(current * voltage)

    optimum = minimize_scalar(
        lambda current: -power(current),
        bounds=(0.0, upper),
        method="bounded",
        options={"xatol": 1.0e-8},
    )
    current = float(optimum.x)
    voltage = thermal_voltage * float(np.sum(np.log1p((jsc - current) / j0)))
    pmax = max(0.0, float(current * voltage))
    return {
        "efficiency": float(pmax / incident_power),
        "power_w_m2": pmax,
        "operating_current_a_m2": current,
        "operating_voltage_v": voltage,
        "short_circuit_currents_a_m2": jsc,
        "current_matching_ratio": float(np.min(jsc) / np.max(jsc)),
        "absorbed_power_fractions": absorbed_fractions,
    }


def _warp_spectrum(wavelength_nm, irradiance, warp):
    wavelength = np.asarray(wavelength_nm, dtype=float)
    shifted = np.interp(
        wavelength / (1.0 + float(warp)),
        wavelength,
        np.asarray(irradiance, dtype=float),
        left=0.0,
        right=0.0,
    ) / (1.0 + float(warp))
    return np.maximum(0.0, shifted)


def _shift_configuration(problem, design, shift_name):
    wavelength = np.asarray(problem["wavelength_nm"], dtype=float)
    spectrum = np.asarray(problem["spectral_irradiance_w_m2_nm"], dtype=float)
    temperature = float(problem["cell_temperature_k"])
    gaps = np.asarray(design["bandgaps_ev"], dtype=float).copy()
    depths = np.asarray(design["optical_depths"], dtype=float).copy()
    front = 1.0
    if shift_name == "hot_cell":
        temperature += 25.0
    elif shift_name == "bandgap_process":
        gaps += np.where(np.arange(gaps.size) % 2 == 0, 0.045, -0.045)
    elif shift_name == "thin_absorbers":
        depths *= 0.82
        front = 0.97
    elif shift_name == "blue_spectrum":
        spectrum = _warp_spectrum(wavelength, spectrum, -0.035)
    elif shift_name == "red_spectrum":
        spectrum = _warp_spectrum(wavelength, spectrum, 0.035)
    elif shift_name == "combined":
        temperature += 20.0
        gaps += np.where(np.arange(gaps.size) % 2 == 0, -0.035, 0.035)
        depths *= 0.86
        front = 0.95
        spectrum = _warp_spectrum(wavelength, spectrum, 0.025)
    else:
        raise ValueError("unknown photovoltaic shift")
    return wavelength, spectrum, temperature, gaps, depths, front


def _performance_for_design(problem, design):
    return _device_performance(
        problem["wavelength_nm"],
        problem["spectral_irradiance_w_m2_nm"],
        problem["cell_temperature_k"],
        design["bandgaps_ev"],
        design["optical_depths"],
    )


def _shift_performances(problem, design):
    records = {}
    for name in SHIFT_NAMES:
        configuration = _shift_configuration(problem, design, name)
        records[name] = _device_performance(*configuration)
    return records


def baseline_policy(problem):
    designs = []
    for index, cap in enumerate(problem["fabrication_budget_caps"]):
        depth = min(
            float(problem["optical_depth_bounds"][1]),
            (
                float(cap) - float(problem["junction_overhead_cost"])
            ) / float(problem["optical_depth_cost"]),
        )
        designs.append({
            "bandgaps_ev": [1.55 + 0.03 * index],
            "optical_depths": [depth],
        })
    return {"designs": designs}


def _reference_submission(world, robust=False):
    table = ROBUST_REFERENCE_DESIGNS if robust else NOMINAL_REFERENCE_DESIGNS
    rows = table.get(int(world["seed"]))
    if rows is None:
        raise ValueError("reference designs are not calibrated")
    return {
        "designs": [
            {
                "bandgaps_ev": list(row[0]),
                "optical_depths": list(row[1]),
            }
            for row in rows
        ]
    }


def nominal_reference_policy(problem):
    # Audit-only fixed witness lookup by the exact public spectrum.  This is a
    # normalization replay, not a candidate-facing policy or general method.
    for spec in DEVELOPMENT_SPECS + HELDOUT_SPECS:
        world = _make_world(spec)
        expected = _public_problem(world)
        if np.array_equal(
            np.asarray(problem["spectral_irradiance_w_m2_nm"]),
            np.asarray(expected["spectral_irradiance_w_m2_nm"]),
        ):
            return _reference_submission(world, robust=False)
    raise ValueError("unknown photovoltaic reference spectrum")


def robust_reference_policy(problem):
    for spec in DEVELOPMENT_SPECS + HELDOUT_SPECS:
        world = _make_world(spec)
        expected = _public_problem(world)
        if np.array_equal(
            np.asarray(problem["spectral_irradiance_w_m2_nm"]),
            np.asarray(expected["spectral_irradiance_w_m2_nm"]),
        ):
            return _reference_submission(world, robust=True)
    raise ValueError("unknown photovoltaic reference spectrum")


def _normalized(value, baseline, reference):
    denominator = float(reference) - float(baseline)
    if denominator <= 1.0e-8:
        raise ValueError("photovoltaic reference does not improve baseline")
    return float(np.clip((float(value) - float(baseline)) / denominator, 0.0, 1.0))


def _score_world(world, submission):
    problem = _public_problem(world)
    candidate = _validate_submission(submission, problem)
    baseline = _validate_submission(baseline_policy(problem), problem)
    nominal_reference = _validate_submission(
        _reference_submission(world, robust=False), problem
    )
    robust_reference = _validate_submission(
        _reference_submission(world, robust=True), problem
    )
    options = []
    for index, design in enumerate(candidate):
        candidate_nominal = _performance_for_design(problem, design)
        baseline_nominal = _performance_for_design(problem, baseline[index])
        reference_nominal = _performance_for_design(problem, nominal_reference[index])
        candidate_shifts = _shift_performances(problem, design)
        baseline_shifts = _shift_performances(problem, baseline[index])
        robust_reference_shifts = _shift_performances(problem, robust_reference[index])
        candidate_worst = min(
            row["efficiency"] for row in candidate_shifts.values()
        )
        baseline_worst = min(row["efficiency"] for row in baseline_shifts.values())
        reference_worst = min(
            row["efficiency"] for row in robust_reference_shifts.values()
        )
        options.append({
            "option_index": index,
            "fabrication_budget": float(problem["fabrication_budget_caps"][index]),
            "junction_count": design["junction_count"],
            "fabrication_cost": design["fabrication_cost"],
            "cost_utilization": design["cost_utilization"],
            "nominal_efficiency": candidate_nominal["efficiency"],
            "nominal_power_w_m2": candidate_nominal["power_w_m2"],
            "current_matching_ratio": candidate_nominal["current_matching_ratio"],
            "nominal_score": _normalized(
                candidate_nominal["efficiency"],
                baseline_nominal["efficiency"],
                reference_nominal["efficiency"],
            ),
            "baseline_nominal_efficiency": baseline_nominal["efficiency"],
            "reference_nominal_efficiency": reference_nominal["efficiency"],
            "worst_shift_efficiency": candidate_worst,
            "baseline_worst_shift_efficiency": baseline_worst,
            "reference_worst_shift_efficiency": reference_worst,
            "robust_score": _normalized(
                candidate_worst, baseline_worst, reference_worst
            ),
            "shift_efficiencies": {
                name: row["efficiency"]
                for name, row in candidate_shifts.items()
            },
        })
    return {
        "valid": True,
        "reason": "",
        "score": float(np.mean([row["nominal_score"] for row in options])),
        "robust_score": float(min(row["robust_score"] for row in options)),
        "mean_nominal_efficiency": float(np.mean([
            row["nominal_efficiency"] for row in options
        ])),
        "minimum_shift_efficiency": float(min(
            row["worst_shift_efficiency"] for row in options
        )),
        "mean_current_matching_ratio": float(np.mean([
            row["current_matching_ratio"] for row in options
        ])),
        "mean_cost_utilization": float(np.mean([
            row["cost_utilization"] for row in options
        ])),
        "mean_junction_count": float(np.mean([
            row["junction_count"] for row in options
        ])),
        "options": options,
    }


def _invalid_row(reason):
    return {
        "valid": False,
        "reason": str(reason),
        "score": 0.0,
        "robust_score": 0.0,
        "mean_nominal_efficiency": 0.0,
        "minimum_shift_efficiency": 0.0,
        "mean_current_matching_ratio": 0.0,
        "mean_cost_utilization": 0.0,
        "mean_junction_count": 0.0,
        "options": [],
    }


def _evaluate_split(candidate, specs):
    rows = []
    for index, spec in enumerate(specs):
        if index:
            _reset_candidate_session(candidate)
        world = _make_world(spec)
        problem = _public_problem(world)
        try:
            row = _score_world(world, candidate(copy.deepcopy(problem)))
        except Exception as exc:
            row = _invalid_row("%s: %s" % (type(exc).__name__, exc))
        row["world_index"] = index
        row["world_seed"] = int(spec[0])
        rows.append(row)
    return rows


def _aggregate(rows):
    valid_rate = float(np.mean([row["valid"] for row in rows]))
    all_valid = valid_rate == 1.0
    return {
        "valid": all_valid,
        "valid_rate": valid_rate,
        "score": float(np.mean([row["score"] for row in rows])) if all_valid else 0.0,
        "robust_score": float(min(row["robust_score"] for row in rows)) if all_valid else 0.0,
        "mean_nominal_efficiency": float(np.mean([
            row["mean_nominal_efficiency"] for row in rows
        ])) if all_valid else 0.0,
        "minimum_shift_efficiency": float(min(
            row["minimum_shift_efficiency"] for row in rows
        )) if all_valid else 0.0,
        "mean_current_matching_ratio": float(np.mean([
            row["mean_current_matching_ratio"] for row in rows
        ])) if all_valid else 0.0,
        "mean_cost_utilization": float(np.mean([
            row["mean_cost_utilization"] for row in rows
        ])) if all_valid else 0.0,
        "mean_junction_count": float(np.mean([
            row["mean_junction_count"] for row in rows
        ])) if all_valid else 0.0,
    }


def _reset_candidate_session(design_tandem):
    reset = getattr(design_tandem, "reset_session", None)
    if callable(reset):
        reset()


def evaluate(design_tandem):
    development_rows = _evaluate_split(design_tandem, DEVELOPMENT_SPECS)
    _reset_candidate_session(design_tandem)
    heldout_rows = _evaluate_split(design_tandem, HELDOUT_SPECS)
    development = _aggregate(development_rows)
    heldout = _aggregate(heldout_rows)
    return {
        "combined_score": development["score"],
        "raw_score": development["score"],
        "valid": float(development["valid"]),
        "feasibility_rate": development["valid_rate"],
        "robustness_score": development["robust_score"],
        "heldout_policy_score": heldout["score"],
        "heldout_robustness_score": heldout["robust_score"],
        "heldout_feasibility_rate": heldout["valid_rate"],
        "development_mean_nominal_efficiency": development[
            "mean_nominal_efficiency"
        ],
        "heldout_mean_nominal_efficiency": heldout["mean_nominal_efficiency"],
        "development_minimum_shift_efficiency": development[
            "minimum_shift_efficiency"
        ],
        "heldout_minimum_shift_efficiency": heldout["minimum_shift_efficiency"],
        "development_mean_current_matching_ratio": development[
            "mean_current_matching_ratio"
        ],
        "heldout_mean_current_matching_ratio": heldout[
            "mean_current_matching_ratio"
        ],
        "development_mean_cost_utilization": development["mean_cost_utilization"],
        "heldout_mean_cost_utilization": heldout["mean_cost_utilization"],
        "development_mean_junction_count": development["mean_junction_count"],
        "heldout_mean_junction_count": heldout["mean_junction_count"],
        "candidate_instance_call_count": len(development_rows) + len(heldout_rows),
        "candidate_instance_valid_rate": float(np.mean([
            row["valid"] for row in development_rows + heldout_rows
        ])),
        "per_instance": development_rows + heldout_rows,
    }
