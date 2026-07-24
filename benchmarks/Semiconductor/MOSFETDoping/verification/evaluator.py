"""Trusted multi-device silicon nMOS halo-profile design oracle."""

from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import qmc


VERIFICATION_DIR = Path(__file__).resolve().parent
if str(VERIFICATION_DIR) not in sys.path:
    sys.path.insert(0, str(VERIFICATION_DIR))

from device import PROFILE_COLUMNS, evaluate_device  # noqa: E402


MOSFET_DOPING_V2 = True
MIN_ARCHIVE_SIZE = 4
MAX_ARCHIVE_SIZE = 16
MIN_NOMINAL_FEASIBLE = 4
DESIGN_BOUNDS = (
    (15.3, 17.4),
    (15.3, 18.25),
    (15.3, 18.25),
    (0.06, 0.34),
    (0.66, 0.94),
    (0.035, 0.18),
)
OBJECTIVE_SCALING = {
    "on_current_floor_ma_per_um": 0.075,
    "on_current_ceiling_ma_per_um": 0.65,
    "off_current_log10_ceiling_na_per_um": 3.0,
    "off_current_log10_floor_na_per_um": -6.0,
}
CONSTRAINTS = {
    "minimum_threshold_v": 0.16,
    "maximum_threshold_v": 0.68,
    "minimum_on_current_ma_per_um": 0.075,
    "maximum_dibl_v": 0.14,
    "maximum_subthreshold_swing_mv_dec": 115.0,
    "maximum_random_dopant_sigma_v": 0.035,
    "maximum_dose_cm2": 3.0e12,
    "maximum_active_doping_cm3": 3.7e18,
    "maximum_log_gradient_per_fraction": 25.0,
}


def _device(
    name,
    split,
    channel_length_nm,
    oxide_eot_nm,
    supply_voltage_v,
    temperature_k,
    flatband_voltage_v,
    body_depth_nm,
):
    condition = {
        "channel_length_nm": float(channel_length_nm),
        "oxide_eot_nm": float(oxide_eot_nm),
        "supply_voltage_v": float(supply_voltage_v),
        "temperature_k": float(temperature_k),
        "flatband_voltage_v": float(flatband_voltage_v),
        "body_depth_nm": float(body_depth_nm),
        "width_um": 1.0,
        "constraints": copy.deepcopy(CONSTRAINTS),
    }
    problem = {
        "schema_version": 2,
        "device_model": (
            "screened_poisson_charge_sheet_caughey_thomas_compact_nmos"
        ),
        "design_columns": list(PROFILE_COLUMNS),
        "design_bounds": [list(bounds) for bounds in DESIGN_BOUNDS],
        "archive_size_bounds": [MIN_ARCHIVE_SIZE, MAX_ARCHIVE_SIZE],
        "device": copy.deepcopy(condition),
        "objective_scaling": copy.deepcopy(OBJECTIVE_SCALING),
    }
    return {
        "name": str(name),
        "split": str(split),
        "device": condition,
        "problem": problem,
    }


# Development and held-out calls are interleaved so call order cannot reveal the split.
INSTANCES = (
    _device("dev_reference_40nm", "development", 40, 1.50, 0.80, 300, -0.50, 85),
    _device("heldout_short_low_v", "heldout", 28, 1.05, 0.65, 310, -0.47, 60),
    _device("dev_thin_oxide_32nm", "development", 32, 1.20, 0.70, 300, -0.48, 70),
    _device("heldout_long_hot", "heldout", 65, 2.00, 0.95, 340, -0.56, 115),
    _device("dev_long_warm", "development", 55, 1.80, 0.90, 325, -0.54, 105),
    _device("dev_cold_operation", "development", 45, 1.40, 0.80, 275, -0.52, 90),
)
DEVELOPMENT_INSTANCES = tuple(
    row for row in INSTANCES if row["split"] == "development"
)
HELDOUT_INSTANCES = tuple(
    row for row in INSTANCES if row["split"] == "heldout"
)


SHIFT_SPECS = (
    {"name": "hot_operation", "temperature_delta_k": 35.0},
    {"name": "effective_channel_shortening", "channel_length_scale": 0.93},
    {
        "name": "oxide_and_flatband_shift",
        "oxide_eot_scale": 1.08,
        "flatband_voltage_delta_v": 0.025,
    },
    {
        "name": "activation_and_diffusion",
        "activation_fraction": 0.84,
        "diffusion_blur_fraction": 0.012,
    },
    {"name": "source_drain_reversal", "reverse_source_drain": True},
    {
        "name": "combined_process_and_operation",
        "temperature_delta_k": 25.0,
        "channel_length_scale": 0.95,
        "oxide_eot_scale": 1.05,
        "flatband_voltage_delta_v": 0.020,
        "activation_fraction": 0.90,
        "diffusion_blur_fraction": 0.008,
    },
)


# Built by scripts/calibrate_mosfet_v2.py from fixed scrambled-Sobol pools.  These are strong
# reproducible witnesses, not certificates of a global Pareto optimum.
REFERENCE_SOBOL = {
    "dev_reference_40nm": {
        "seed": 260724, "power": 11,
        "nominal": (682, 349, 1824, 485, 1410, 626, 841, 2045, 1310, 1550,
                    1858, 1498, 808, 2040, 821, 386),
        "robust": (1330, 169, 2034, 90, 591, 702, 1781, 432, 1151, 2,
                   1962, 830, 1628, 772, 1600, 1949),
    },
    "heldout_short_low_v": {
        "seed": 260725, "power": 11,
        "nominal": (138, 1637, 510, 82, 289, 1804, 962, 922, 1598, 1917,
                    122, 420, 1214, 1858, 1350, 1228),
        "robust": (920, 292, 1765, 236, 791, 1684, 809, 1208, 1228, 567,
                   1795, 482, 1358, 699, 1961, 407),
    },
    "dev_thin_oxide_32nm": {
        "seed": 260726, "power": 11,
        "nominal": (1266, 693, 1642, 1314, 1229, 1342, 553, 1210, 52, 450,
                    725, 818, 1988, 650, 1582, 77),
        "robust": (1422, 1497, 24, 1099, 1320, 1572, 421, 961, 550, 606,
                   1164, 1800, 1760, 424, 2041, 1659),
    },
    "heldout_long_hot": {
        "seed": 260727, "power": 11,
        "nominal": (1087, 1335, 135, 1635, 720, 271, 975, 0, 1031, 563,
                    543, 1395, 1421, 887, 840, 1960),
        "robust": (1435, 717, 403, 1713, 1831, 1957, 1039, 1469, 935,
                   2009, 563, 1023, 687, 1239, 735, 1941),
    },
    "dev_long_warm": {
        "seed": 260728, "power": 11,
        "nominal": (1010, 430, 885, 938, 1542, 1605, 434, 634, 912, 1856,
                    1461, 314, 1114, 1418, 2006, 1080),
        "robust": (1552, 1348, 314, 1718, 121, 860, 530, 80, 270, 88,
                   1886, 1034, 624, 1466, 1089, 888),
    },
    "dev_cold_operation": {
        "seed": 260729, "power": 11,
        "nominal": (1893, 921, 1029, 1317, 1551, 205, 149, 1645, 1073,
                    1777, 1642, 565, 673, 1927, 77, 597),
        "robust": (301, 1151, 1170, 185, 1757, 1509, 1474, 1836, 1181,
                   1453, 1629, 2031, 1251, 1568, 265, 1311),
    },
}
CALIBRATED_ANCHORS = {
    "dev_reference_40nm": {
        "baseline_nominal_hypervolume": 0.44049999549170415,
        "reference_nominal_hypervolume": 0.6021565333350363,
        "baseline_shifted_hypervolumes": (
            0.307865752758699, 0.44017774249952374, 0.41399981639080025,
            0.43041626067221506, 0.44049999549170415, 0.33137581602125543,
        ),
        "reference_shifted_hypervolumes": (
            0.4527148791670644, 0.5992566765066475, 0.541132744292832,
            0.5957407092731214, 0.5889375562155663, 0.4690924001229216,
        ),
    },
    "heldout_short_low_v": {
        "baseline_nominal_hypervolume": 0.3675275779542334,
        "reference_nominal_hypervolume": 0.4717865212437461,
        "baseline_shifted_hypervolumes": (
            0.2614269736431374, 0.36729039190929, 0.33658190511318875,
            0.36294886058858966, 0.3675275779542334, 0.2797179205712751,
        ),
        "reference_shifted_hypervolumes": (
            0.35429000052099624, 0.468492883732063, 0.4256816723873299,
            0.4664571886384361, 0.46855807039840813, 0.3716402209327662,
        ),
    },
    "dev_thin_oxide_32nm": {
        "baseline_nominal_hypervolume": 0.41680686480383144,
        "reference_nominal_hypervolume": 0.5431645034149495,
        "baseline_shifted_hypervolumes": (
            0.29898538915475315, 0.4168525419260881, 0.3831423286916819,
            0.4114328432723307, 0.41680686480383144, 0.3178730132208075,
        ),
        "reference_shifted_hypervolumes": (
            0.4077077896958566, 0.5391355313281349, 0.49249382829515653,
            0.535737805401298, 0.5397055729276992, 0.427437348279477,
        ),
    },
    "heldout_long_hot": {
        "baseline_nominal_hypervolume": 0.26894452141215913,
        "reference_nominal_hypervolume": 0.45730425908176603,
        "baseline_shifted_hypervolumes": (
            0.15479323452557422, 0.2640234515057002, 0.27075434513457003,
            0.24872863068247641, 0.26894452141215913, 0.1847676812045957,
        ),
        "reference_shifted_hypervolumes": (
            0.3188639672194978, 0.4275862980871787, 0.3899352697759931,
            0.4203309939870395, 0.43327447294463983, 0.33259082571034526,
        ),
    },
    "dev_long_warm": {
        "baseline_nominal_hypervolume": 0.33699943475007477,
        "reference_nominal_hypervolume": 0.5279479059030665,
        "baseline_shifted_hypervolumes": (
            0.2102834491345274, 0.33553694905757137, 0.3312063257324888,
            0.32062001485697433, 0.33699943475007477, 0.2432304175870945,
        ),
        "reference_shifted_hypervolumes": (
            0.37653671590808674, 0.5013401903194157, 0.45554013490706025,
            0.49632127301529716, 0.5074313043338211, 0.39037902445837847,
        ),
    },
    "dev_cold_operation": {
        "baseline_nominal_hypervolume": 0.589095907875794,
        "reference_nominal_hypervolume": 0.7521352119444288,
        "baseline_shifted_hypervolumes": (
            0.417526412299843, 0.5896708787510319, 0.5487521746617002,
            0.5731646280527705, 0.589095907875794, 0.44533093041137156,
        ),
        "reference_shifted_hypervolumes": (
            0.5749925274616581, 0.7437346188667766, 0.7083373950407502,
            0.7441193693366265, 0.7386101934197781, 0.6029794615305671,
        ),
    },
}


def _contains_bool(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains_bool(item) for item in value)
    if isinstance(value, dict):
        return any(
            _contains_bool(key) or _contains_bool(item)
            for key, item in value.items()
        )
    if isinstance(value, np.ndarray) and value.dtype.kind == "b":
        return True
    return False


def _validate_archive(value, problem):
    if _contains_bool(value):
        raise ValueError("boolean doping-profile values are not allowed")
    try:
        designs = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("archive must be a finite numeric matrix") from exc
    if designs.ndim != 2 or designs.shape[1] != len(PROFILE_COLUMNS):
        raise ValueError("archive must have shape (n, 6)")
    minimum, maximum = problem["archive_size_bounds"]
    if not (minimum <= len(designs) <= maximum):
        raise ValueError("archive size is out of bounds")
    if not np.all(np.isfinite(designs)):
        raise ValueError("archive contains non-finite values")
    for column, bounds in enumerate(problem["design_bounds"]):
        if np.any(designs[:, column] < float(bounds[0]) - 1e-12):
            raise ValueError("archive value below public bound")
        if np.any(designs[:, column] > float(bounds[1]) + 1e-12):
            raise ValueError("archive value above public bound")
    if len(np.unique(designs, axis=0)) < MIN_ARCHIVE_SIZE:
        raise ValueError("archive must contain at least four unique designs")
    return designs.copy()


def _evaluate_archive(designs, device, process=None):
    return [
        evaluate_device(row, device, process)
        for row in np.asarray(designs, dtype=float)
    ]


def _quality(problem, record):
    scaling = problem["objective_scaling"]
    drive = (
        float(record["on_current_ma_per_um"])
        - float(scaling["on_current_floor_ma_per_um"])
    ) / (
        float(scaling["on_current_ceiling_ma_per_um"])
        - float(scaling["on_current_floor_ma_per_um"])
    )
    log_leakage = math.log10(max(
        float(record["off_current_na_per_um"]), 1.0e-300
    ))
    leakage = (
        float(scaling["off_current_log10_ceiling_na_per_um"]) - log_leakage
    ) / (
        float(scaling["off_current_log10_ceiling_na_per_um"])
        - float(scaling["off_current_log10_floor_na_per_um"])
    )
    return float(np.clip(drive, 0.0, 1.0)), float(np.clip(leakage, 0.0, 1.0))


def _pareto_indices(problem, records):
    feasible = [
        index for index, record in enumerate(records)
        if bool(record["process_feasible"])
    ]
    qualities = {index: _quality(problem, records[index]) for index in feasible}
    front = []
    for index in feasible:
        drive, leakage = qualities[index]
        dominated = any(
            other != index
            and qualities[other][0] >= drive - 1e-13
            and qualities[other][1] >= leakage - 1e-13
            and (
                qualities[other][0] > drive + 1e-13
                or qualities[other][1] > leakage + 1e-13
            )
            for other in feasible
        )
        if not dominated:
            front.append(index)
    return tuple(front)


def _hypervolume(problem, records):
    points = [
        _quality(problem, records[index])
        for index in _pareto_indices(problem, records)
    ]
    unique_drive = sorted(set(drive for drive, _ in points if drive > 0.0))
    area = 0.0
    previous = 0.0
    for drive in unique_drive:
        height = max(
            (leakage for x, leakage in points if x >= drive - 1e-15),
            default=0.0,
        )
        area += (drive - previous) * max(height, 0.0)
        previous = drive
    return float(np.clip(area, 0.0, 1.0))


def _baseline_archive(_problem):
    rows = []
    for background in np.linspace(16.4, 17.0, 8):
        rows.append((background, 15.3, 15.3, 0.16, 0.84, 0.08))
    return np.asarray(rows, dtype=float)


def _sobol_pool(spec):
    sample = qmc.Sobol(
        d=len(DESIGN_BOUNDS), scramble=True, seed=int(spec["seed"])
    ).random_base2(m=int(spec["power"]))
    lower = np.asarray([bounds[0] for bounds in DESIGN_BOUNDS], dtype=float)
    upper = np.asarray([bounds[1] for bounds in DESIGN_BOUNDS], dtype=float)
    return lower + sample * (upper - lower)


def _reference_archive(instance, kind):
    spec = REFERENCE_SOBOL[instance["name"]]
    indices = spec[str(kind)]
    return _sobol_pool(spec)[np.asarray(indices, dtype=int)]


def _normalized_hypervolume(candidate, baseline, reference):
    denominator = float(reference) - float(baseline)
    if denominator <= 1e-12:
        raise RuntimeError("invalid MOSFET hypervolume normalization")
    return float(np.clip(
        (float(candidate) - float(baseline)) / denominator, 0.0, 1.0
    ))


def _summarize_records(records):
    feasible = [record for record in records if record["process_feasible"]]
    if not feasible:
        return {
            "minimum_threshold_voltage_v": 0.0,
            "maximum_dibl_v": 1.0e6,
            "minimum_on_current_ma_per_um": 0.0,
            "minimum_log10_on_off_ratio": -1.0e6,
            "maximum_subthreshold_swing_mv_dec": 1.0e6,
            "maximum_random_dopant_sigma_v": 1.0e6,
        }
    return {
        "minimum_threshold_voltage_v": float(min(
            record["threshold_voltage_v"] for record in feasible
        )),
        "maximum_dibl_v": float(max(record["dibl_v"] for record in feasible)),
        "minimum_on_current_ma_per_um": float(min(
            record["on_current_ma_per_um"] for record in feasible
        )),
        "minimum_log10_on_off_ratio": float(min(
            record["log10_on_off_ratio"] for record in feasible
        )),
        "maximum_subthreshold_swing_mv_dec": float(max(
            record["subthreshold_swing_mv_dec"] for record in feasible
        )),
        "maximum_random_dopant_sigma_v": float(max(
            record["random_dopant_sigma_v"] for record in feasible
        )),
    }


def _score_instance(design_doping_archive, instance):
    try:
        designs = _validate_archive(
            design_doping_archive(copy.deepcopy(instance["problem"])),
            instance["problem"],
        )
        nominal = _evaluate_archive(designs, instance["device"])
        nominal_feasible = sum(
            bool(record["process_feasible"]) for record in nominal
        )
        if nominal_feasible < MIN_NOMINAL_FEASIBLE:
            raise ValueError("fewer than four nominally feasible profile designs")
        shifted = [
            _evaluate_archive(designs, instance["device"], shift)
            for shift in SHIFT_SPECS
        ]
        anchors = CALIBRATED_ANCHORS[instance["name"]]
        candidate_hypervolume = _hypervolume(instance["problem"], nominal)
        nominal_score = _normalized_hypervolume(
            candidate_hypervolume,
            anchors["baseline_nominal_hypervolume"],
            anchors["reference_nominal_hypervolume"],
        )

        shifted_scores = []
        shifted_hypervolumes = []
        shifted_feasible_rates = []
        shifted_feasible_counts = []
        for shift_index, candidate_records in enumerate(shifted):
            feasible_count = sum(
                bool(record["process_feasible"])
                for record in candidate_records
            )
            shifted_feasible_counts.append(feasible_count)
            shifted_feasible_rates.append(feasible_count / len(designs))
            candidate_shift_hv = (
                _hypervolume(instance["problem"], candidate_records)
                if feasible_count >= MIN_NOMINAL_FEASIBLE else 0.0
            )
            shifted_hypervolumes.append(candidate_shift_hv)
            shifted_scores.append(_normalized_hypervolume(
                candidate_shift_hv,
                anchors["baseline_shifted_hypervolumes"][shift_index],
                anchors["reference_shifted_hypervolumes"][shift_index],
            ))
        robustness_score = float(min(shifted_scores))
        diagnostics = _summarize_records(nominal)
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "nominal_score": nominal_score,
            "robustness_score": robustness_score,
            "archive_size": len(designs),
            "nominal_feasible_count": nominal_feasible,
            "nominal_feasibility_rate": nominal_feasible / len(designs),
            "pareto_front_size": len(_pareto_indices(instance["problem"], nominal)),
            "raw_nominal_hypervolume": candidate_hypervolume,
            "raw_shifted_hypervolumes": shifted_hypervolumes,
            "shifted_scores": shifted_scores,
            "shift_feasible_counts": shifted_feasible_counts,
            "shift_feasibility_rates": shifted_feasible_rates,
            "anchors": copy.deepcopy(anchors),
            **diagnostics,
        }
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "nominal_score": 0.0,
            "robustness_score": 0.0,
            "archive_size": 0,
            "nominal_feasible_count": 0,
            "nominal_feasibility_rate": 0.0,
            "pareto_front_size": 0,
            "raw_nominal_hypervolume": 0.0,
            "raw_shifted_hypervolumes": [0.0] * len(SHIFT_SPECS),
            "shifted_scores": [0.0] * len(SHIFT_SPECS),
            "shift_feasible_counts": [0] * len(SHIFT_SPECS),
            "shift_feasibility_rates": [0.0] * len(SHIFT_SPECS),
        }


def evaluate(design_doping_archive):
    expected_instances = {instance["name"] for instance in INSTANCES}
    if set(REFERENCE_SOBOL) != expected_instances:
        raise RuntimeError("MOSFET-v2 Sobol references are incomplete")
    if set(CALIBRATED_ANCHORS) != expected_instances:
        raise RuntimeError("MOSFET-v2 calibration anchors are incomplete")
    records = []
    for index, instance in enumerate(INSTANCES):
        records.append(_score_instance(design_doping_archive, instance))
        if index + 1 < len(INSTANCES):
            reset = getattr(design_doping_archive, "reset_session", None)
            if callable(reset):
                reset()
    development = [row for row in records if row["split"] == "development"]
    heldout = [row for row in records if row["split"] == "heldout"]
    development_valid = sum(bool(row["valid"]) for row in development)
    heldout_valid = sum(bool(row["valid"]) for row in heldout)
    development_score = float(np.mean([
        row["nominal_score"] for row in development
    ]))
    heldout_score = float(np.mean([
        row["nominal_score"] for row in heldout
    ]))
    valid = development_valid == len(development)
    return {
        "combined_score": development_score if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": float(np.mean([
            row["nominal_feasibility_rate"] for row in development
        ])),
        "raw_score": development_score if valid else 0.0,
        "robustness_score": float(np.mean([
            row["robustness_score"] for row in development
        ])),
        "heldout_policy_score": (
            heldout_score if heldout_valid == len(heldout) else 0.0
        ),
        "heldout_robustness_score": float(np.mean([
            row["robustness_score"] for row in heldout
        ])),
        "heldout_feasibility_rate": heldout_valid / len(heldout),
        "development_shift_feasibility_rate": float(np.mean([
            value for row in development for value in row["shift_feasibility_rates"]
        ])),
        "heldout_shift_feasibility_rate": float(np.mean([
            value for row in heldout for value in row["shift_feasibility_rates"]
        ])),
        "development_mean_nominal_feasible_rate": float(np.mean([
            row["nominal_feasibility_rate"] for row in development
        ])),
        "heldout_mean_nominal_feasible_rate": float(np.mean([
            row["nominal_feasibility_rate"] for row in heldout
        ])),
        "candidate_instance_call_count": len(records),
        "candidate_instance_valid_rate": (
            sum(bool(row["valid"]) for row in records) / len(records)
        ),
        "per_instance": records,
    }
