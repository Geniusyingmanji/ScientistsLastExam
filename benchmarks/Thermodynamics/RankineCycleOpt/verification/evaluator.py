"""Trusted multi-condition single-reheat Rankine-cycle optimization oracle."""

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

from cycle import evaluate_cycle  # noqa: E402


RANKINE_V2 = True
MIN_ARCHIVE_SIZE = 4
MAX_ARCHIVE_SIZE = 16
MIN_NOMINAL_FEASIBLE = 4
DESIGN_COLUMNS = (
    "boiler_pressure_mpa",
    "main_steam_temperature_c",
    "reheat_pressure_fraction",
    "reheat_temperature_c",
)
DESIGN_BOUNDS = (
    (6.0, 15.0),
    (450.0, 600.0),
    (0.08, 0.45),
    (450.0, 600.0),
)


def _condition(
    name,
    split,
    condenser_pressure_kpa,
    hp_turbine_efficiency,
    lp_turbine_efficiency,
    pump_efficiency,
    boiler_pressure_loss_fraction,
    reheat_pressure_loss_fraction,
    max_boiler_pressure_mpa,
    max_steam_temperature_c,
    minimum_lp_exit_quality,
):
    operating = {
        "condenser_pressure_kpa": float(condenser_pressure_kpa),
        "hp_turbine_efficiency": float(hp_turbine_efficiency),
        "lp_turbine_efficiency": float(lp_turbine_efficiency),
        "pump_efficiency": float(pump_efficiency),
        "boiler_pressure_loss_fraction": float(boiler_pressure_loss_fraction),
        "reheat_pressure_loss_fraction": float(reheat_pressure_loss_fraction),
        "max_boiler_pressure_mpa": float(max_boiler_pressure_mpa),
        "max_steam_temperature_c": float(max_steam_temperature_c),
        "minimum_hp_exit_quality": 0.88,
        "minimum_lp_exit_quality": float(minimum_lp_exit_quality),
    }
    problem = {
        "schema_version": 2,
        "cycle_model": "IAPWS_IF97_regions_1_2_4_single_reheat",
        "design_columns": list(DESIGN_COLUMNS),
        "design_bounds": [list(bounds) for bounds in DESIGN_BOUNDS],
        "archive_size_bounds": [MIN_ARCHIVE_SIZE, MAX_ARCHIVE_SIZE],
        "operating_condition": copy.deepcopy(operating),
        "objective_scaling": {
            "thermal_efficiency_floor": 0.30,
            "thermal_efficiency_ceiling": 0.44,
            "specific_net_work_floor_kj_kg": 1100.0,
            "specific_net_work_ceiling_kj_kg": 1800.0,
        },
    }
    return {
        "name": str(name),
        "split": str(split),
        "operating_condition": operating,
        "problem": problem,
    }


INSTANCES = (
    _condition(
        "dev_temperate_reference", "development",
        8.0, 0.88, 0.90, 0.85, 0.030, 0.020, 15.0, 600.0, 0.88,
    ),
    _condition(
        "dev_warm_sink", "development",
        12.0, 0.87, 0.89, 0.84, 0.035, 0.025, 14.5, 585.0, 0.89,
    ),
    _condition(
        "dev_cold_sink", "development",
        5.0, 0.89, 0.91, 0.86, 0.025, 0.018, 14.0, 575.0, 0.88,
    ),
    _condition(
        "dev_aged_turbomachinery", "development",
        9.0, 0.84, 0.86, 0.78, 0.050, 0.040, 13.5, 560.0, 0.90,
    ),
    _condition(
        "heldout_hot_humid_sink", "heldout",
        14.0, 0.86, 0.88, 0.82, 0.040, 0.030, 14.2, 580.0, 0.90,
    ),
    _condition(
        "heldout_derated_retrofit", "heldout",
        6.5, 0.85, 0.87, 0.80, 0.045, 0.035, 12.5, 550.0, 0.91,
    ),
)
DEVELOPMENT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "development"
)
HELDOUT_INSTANCES = tuple(
    instance for instance in INSTANCES if instance["split"] == "heldout"
)


SHIFT_SPECS = (
    {
        "name": "hotter_cooling_water",
        "condenser_pressure_scale": 1.25,
    },
    {
        "name": "turbomachinery_wear",
        "hp_turbine_efficiency_delta": -0.040,
        "lp_turbine_efficiency_delta": -0.050,
        "pump_efficiency_delta": -0.070,
    },
    {
        "name": "pressure_loss_growth",
        "boiler_pressure_loss_delta": 0.025,
        "reheat_pressure_loss_delta": 0.025,
    },
    {
        "name": "materials_derating",
        "max_boiler_pressure_delta_mpa": -1.0,
        "max_steam_temperature_delta_c": -20.0,
    },
    {
        "name": "combined_aging_and_weather",
        "condenser_pressure_scale": 1.15,
        "hp_turbine_efficiency_delta": -0.025,
        "lp_turbine_efficiency_delta": -0.030,
        "pump_efficiency_delta": -0.040,
        "boiler_pressure_loss_delta": 0.012,
        "reheat_pressure_loss_delta": 0.012,
        "max_boiler_pressure_delta_mpa": -0.5,
        "max_steam_temperature_delta_c": -10.0,
    },
)


def _contains_bool(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (list, tuple)):
        return any(_contains_bool(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_bool(key) or _contains_bool(item) for key, item in value.items())
    if isinstance(value, np.ndarray) and value.dtype.kind == "b":
        return True
    return False


def _validate_archive(value, problem):
    if _contains_bool(value):
        raise ValueError("boolean archive values are not allowed")
    try:
        designs = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("archive must be a finite numeric matrix") from exc
    if designs.ndim != 2 or designs.shape[1] != len(DESIGN_COLUMNS):
        raise ValueError("archive must have shape (n, 4)")
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


def _shift_condition(condition, shift):
    changed = copy.deepcopy(condition)
    changed["condenser_pressure_kpa"] *= float(
        shift.get("condenser_pressure_scale", 1.0)
    )
    for key, delta_key in (
        ("hp_turbine_efficiency", "hp_turbine_efficiency_delta"),
        ("lp_turbine_efficiency", "lp_turbine_efficiency_delta"),
        ("pump_efficiency", "pump_efficiency_delta"),
        ("boiler_pressure_loss_fraction", "boiler_pressure_loss_delta"),
        ("reheat_pressure_loss_fraction", "reheat_pressure_loss_delta"),
        ("max_boiler_pressure_mpa", "max_boiler_pressure_delta_mpa"),
        ("max_steam_temperature_c", "max_steam_temperature_delta_c"),
    ):
        changed[key] += float(shift.get(delta_key, 0.0))
    return changed


def _evaluate_archive(designs, condition):
    return [evaluate_cycle(row, condition) for row in np.asarray(designs, dtype=float)]


def _pareto_indices(records):
    feasible = [
        index for index, record in enumerate(records)
        if bool(record["process_feasible"])
    ]
    front = []
    for index in feasible:
        record = records[index]
        efficiency = float(record["thermal_efficiency"])
        work = float(record["specific_net_work_kj_kg"])
        dominated = any(
            other != index
            and float(records[other]["thermal_efficiency"]) >= efficiency - 1e-13
            and float(records[other]["specific_net_work_kj_kg"]) >= work - 1e-9
            and (
                float(records[other]["thermal_efficiency"]) > efficiency + 1e-13
                or float(records[other]["specific_net_work_kj_kg"]) > work + 1e-9
            )
            for other in feasible
        )
        if not dominated:
            front.append(index)
    return tuple(front)


def _quality(problem, record):
    scaling = problem["objective_scaling"]
    efficiency = (
        float(record["thermal_efficiency"])
        - float(scaling["thermal_efficiency_floor"])
    ) / (
        float(scaling["thermal_efficiency_ceiling"])
        - float(scaling["thermal_efficiency_floor"])
    )
    work = (
        float(record["specific_net_work_kj_kg"])
        - float(scaling["specific_net_work_floor_kj_kg"])
    ) / (
        float(scaling["specific_net_work_ceiling_kj_kg"])
        - float(scaling["specific_net_work_floor_kj_kg"])
    )
    return float(np.clip(efficiency, 0.0, 1.0)), float(np.clip(work, 0.0, 1.0))


def _hypervolume(problem, records):
    points = [_quality(problem, records[index]) for index in _pareto_indices(records)]
    unique_efficiencies = sorted(set(x for x, _ in points if x > 0.0))
    area = 0.0
    previous = 0.0
    for efficiency in unique_efficiencies:
        height = max(
            (work for x, work in points if x >= efficiency - 1e-15),
            default=0.0,
        )
        area += (efficiency - previous) * max(height, 0.0)
        previous = efficiency
    return float(np.clip(area, 0.0, 1.0))


def _baseline_archive(problem):
    condition = problem["operating_condition"]
    pressure_high = min(
        float(problem["design_bounds"][0][1]),
        float(condition["max_boiler_pressure_mpa"]) - 1.25,
    )
    pressure_low = max(float(problem["design_bounds"][0][0]), pressure_high - 3.0)
    temperature_high = min(
        float(problem["design_bounds"][1][1]),
        float(condition["max_steam_temperature_c"]) - 25.0,
    )
    temperature_low = max(
        float(problem["design_bounds"][1][0]), temperature_high - 45.0
    )
    rows = []
    for fraction in np.linspace(0.0, 1.0, 8):
        pressure = pressure_low + fraction * (pressure_high - pressure_low)
        main_temperature = temperature_low + 0.65 * fraction * (
            temperature_high - temperature_low
        )
        reheat_temperature = temperature_low + (0.35 + 0.65 * fraction) * (
            temperature_high - temperature_low
        )
        reheat_fraction = 0.14 + 0.10 * fraction
        rows.append((pressure, main_temperature, reheat_fraction, reheat_temperature))
    return np.asarray(rows, dtype=float)


REFERENCE_SOBOL = {
    "dev_temperate_reference": {
        "seed": 9321, "power": 11,
        "nominal": (383, 1751, 1859, 423, 1311, 1739, 23, 51, 119, 149,
                    175, 235, 247, 295, 387, 407),
        "robust": (1859, 2015, 1739, 655, 831, 1311, 1927, 0, 1, 2, 5, 6,
                   7, 10, 11, 12),
    },
    "dev_warm_sink": {
        "seed": 9322, "power": 11,
        "nominal": (551, 611, 1837, 671, 1523, 767, 1003, 1791, 1967, 7, 15,
                    63, 133, 203, 251, 299),
        "robust": (1523, 223, 1791, 0, 3, 4, 6, 9, 10, 12, 14, 17, 18, 22,
                   26, 27),
    },
    "dev_cold_sink": {
        "seed": 9323, "power": 11,
        "nominal": (262, 1882, 1642, 858, 1402, 1462, 1654, 486, 54, 86, 170,
                    233, 356, 378, 410, 458),
        "robust": (1642, 282, 1978, 0, 3, 5, 7, 10, 13, 15, 19, 20, 21, 24,
                   25, 27),
    },
    "dev_aged_turbomachinery": {
        "seed": 9324, "power": 11,
        "nominal": (1978, 390, 1782, 1582, 1830, 21, 81, 86, 180, 282, 288,
                    350, 504, 534, 576, 623),
        "robust": (1582, 390, 1358, 1825, 742, 3, 7, 15, 17, 19, 20, 25, 27,
                   30, 33, 35),
    },
    "heldout_hot_humid_sink": {
        "seed": 9325, "power": 11,
        "nominal": (1385, 393, 949, 1993, 607, 1865, 26, 57, 125, 157, 165,
                    185, 233, 255, 277, 301),
        "robust": (949, 607, 0, 2, 4, 7, 8, 10, 13, 18, 20, 21, 28, 31, 34,
                   35),
    },
    "heldout_derated_retrofit": {
        "seed": 9326, "power": 11,
        "nominal": (4, 628, 1908, 1354, 220, 19, 1700, 52, 91, 324, 382, 395,
                    443, 524, 539, 613),
        "robust": (1354, 124, 1315, 19, 301, 5, 13, 17, 25, 33, 35, 38, 41,
                   53, 57, 65),
    },
}
CALIBRATED_ANCHORS = {
    "dev_temperate_reference": {
        "baseline_nominal_hypervolume": 0.45817671116762587,
        "reference_nominal_hypervolume": 0.6337774731201494,
        "baseline_shifted_hypervolumes": (
            0.4095007813603086, 0.2977962198969881, 0.4460942783992582,
            0.45817671116762587, 0.3264059682282639,
        ),
        "reference_shifted_hypervolumes": (
            0.47390863035166464, 0.35410614680400937, 0.5147306851723913,
            0.5283452265805713, 0.3839467516644685,
        ),
    },
    "dev_warm_sink": {
        "baseline_nominal_hypervolume": 0.2957915977312599,
        "reference_nominal_hypervolume": 0.4188772339951581,
        "baseline_shifted_hypervolumes": (
            0.2552784142085323, 0.17492101532331666, 0.285809428678901,
            0.2957915977312599, 0.19404802622811965,
        ),
        "reference_shifted_hypervolumes": (
            0.3213015850906002, 0.2323215809681128, 0.35703799860644947,
            0.3686541278269374, 0.2526498307452724,
        ),
    },
    "dev_cold_sink": {
        "baseline_nominal_hypervolume": 0.5145460060306123,
        "reference_nominal_hypervolume": 0.6672878854698431,
        "baseline_shifted_hypervolumes": (
            0.46464713364380944, 0.3428598215870096, 0.502101133733511,
            0.5145460060306123, 0.37489766313076245,
        ),
        "reference_shifted_hypervolumes": (
            0.5330564556096585, 0.40248866628866226, 0.5740027320833729,
            0.5878142219355531, 0.43583012747368866,
        ),
    },
    "dev_aged_turbomachinery": {
        "baseline_nominal_hypervolume": 0.19776831887363497,
        "reference_nominal_hypervolume": 0.300729724450286,
        "baseline_shifted_hypervolumes": (
            0.16656637795827464, 0.10198739993780521, 0.18988292913494137,
            0.19776831887363497, 0.11759689953561125,
        ),
        "reference_shifted_hypervolumes": (
            0.20952201541994925, 0.13760256673474963, 0.23668967322659218,
            0.2457828486433836, 0.15452014302236597,
        ),
    },
    "heldout_hot_humid_sink": {
        "baseline_nominal_hypervolume": 0.22636959323328898,
        "reference_nominal_hypervolume": 0.3449200481392878,
        "baseline_shifted_hypervolumes": (
            0.19069899230317136, 0.12405625737290443, 0.21754844280665794,
            0.22636959323328898, 0.13937896940883676,
        ),
        "reference_shifted_hypervolumes": (
            0.23504364421890186, 0.16329280095738666, 0.2664715568847174,
            0.27652824509524765, 0.17891479588057801,
        ),
    },
    "heldout_derated_retrofit": {
        "baseline_nominal_hypervolume": 0.2433608928222019,
        "reference_nominal_hypervolume": 0.35643580540062564,
        "baseline_shifted_hypervolumes": (
            0.20930283465452879, 0.13480982804238079, 0.2346711826705231,
            0.2433608928222019, 0.15329407201048365,
        ),
        "reference_shifted_hypervolumes": (
            0.25862716412242687, 0.1746630906518818, 0.287521889439883,
            0.2977860678414193, 0.19507724977093957,
        ),
    },
}


def _sobol_design_pool(problem, seed, power=11):
    unit = qmc.Sobol(d=4, scramble=True, seed=int(seed)).random_base2(int(power))
    bounds = np.asarray(problem["design_bounds"], dtype=float)
    return qmc.scale(unit, bounds[:, 0], bounds[:, 1])


def _reference_archive(instance, kind):
    record = REFERENCE_SOBOL[instance["name"]]
    pool = _sobol_design_pool(
        instance["problem"], record["seed"], record.get("power", 11)
    )
    return pool[np.asarray(record[str(kind)], dtype=int)].copy()


def _reference_archives(kind):
    return {
        instance["name"]: _reference_archive(instance, kind)
        for instance in INSTANCES
    }


def _normalized(value, baseline, reference):
    denominator = float(reference) - float(baseline)
    if denominator <= 1e-10:
        raise RuntimeError("reference hypervolume does not exceed baseline")
    return float(np.clip((float(value) - float(baseline)) / denominator, 0.0, 1.0))


def _archive_diagnostics(instance, designs, nominal, shifted):
    problem = instance["problem"]
    front = _pareto_indices(nominal)
    front_records = [nominal[index] for index in front]
    nominal_hypervolume = _hypervolume(problem, nominal)
    shifted_hypervolumes = [
        _hypervolume(problem, records) for records in shifted
    ]
    feasible_count = sum(bool(record["process_feasible"]) for record in nominal)
    return {
        "archive_size": len(designs),
        "nominal_feasible_count": feasible_count,
        "nominal_feasibility_rate": feasible_count / len(designs),
        "pareto_front_size": len(front),
        "raw_nominal_hypervolume": nominal_hypervolume,
        "raw_shifted_hypervolumes": shifted_hypervolumes,
        "worst_shifted_raw_hypervolume": min(shifted_hypervolumes),
        "shift_feasibility_rates": [
            float(np.mean([record["process_feasible"] for record in records]))
            for records in shifted
        ],
        "mean_front_efficiency": (
            float(np.mean([row["thermal_efficiency"] for row in front_records]))
            if front_records else 0.0
        ),
        "maximum_front_efficiency": (
            max(float(row["thermal_efficiency"]) for row in front_records)
            if front_records else 0.0
        ),
        "mean_front_specific_net_work_kj_kg": (
            float(np.mean([row["specific_net_work_kj_kg"] for row in front_records]))
            if front_records else 0.0
        ),
        "maximum_front_specific_net_work_kj_kg": (
            max(float(row["specific_net_work_kj_kg"]) for row in front_records)
            if front_records else 0.0
        ),
        "minimum_front_hp_exit_quality": (
            min(float(row["hp_exit_quality"]) for row in front_records)
            if front_records else 0.0
        ),
        "minimum_front_lp_exit_quality": (
            min(float(row["lp_exit_quality"]) for row in front_records)
            if front_records else 0.0
        ),
        "maximum_front_energy_balance_residual_kj_kg": (
            max(abs(float(row["energy_balance_residual_kj_kg"])) for row in front_records)
            if front_records else 0.0
        ),
    }


def _score_instance(design_rankine_archive, instance):
    try:
        returned = design_rankine_archive(copy.deepcopy(instance["problem"]))
        designs = _validate_archive(returned, instance["problem"])
        nominal = _evaluate_archive(designs, instance["operating_condition"])
        shifted_conditions = [
            _shift_condition(instance["operating_condition"], shift)
            for shift in SHIFT_SPECS
        ]
        shifted = [
            _evaluate_archive(designs, condition) for condition in shifted_conditions
        ]
        diagnostics = _archive_diagnostics(instance, designs, nominal, shifted)
        if diagnostics["nominal_feasible_count"] < MIN_NOMINAL_FEASIBLE:
            raise ValueError("archive has fewer than four nominal-feasible designs")
        anchors = CALIBRATED_ANCHORS[instance["name"]]
        score = _normalized(
            diagnostics["raw_nominal_hypervolume"],
            anchors["baseline_nominal_hypervolume"],
            anchors["reference_nominal_hypervolume"],
        )
        shift_scores = [
            _normalized(value, baseline, reference)
            for value, baseline, reference in zip(
                diagnostics["raw_shifted_hypervolumes"],
                anchors["baseline_shifted_hypervolumes"],
                anchors["reference_shifted_hypervolumes"],
            )
        ]
        return dict({
            "name": instance["name"],
            "split": instance["split"],
            "valid": True,
            "score": score,
            "robustness_score": min(shift_scores),
            "shifted_scores": shift_scores,
            "anchors": copy.deepcopy(anchors),
        }, **diagnostics)
    except Exception as exc:
        return {
            "name": instance["name"],
            "split": instance["split"],
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "score": 0.0,
            "robustness_score": 0.0,
            "archive_size": 0,
            "nominal_feasible_count": 0,
            "nominal_feasibility_rate": 0.0,
            "pareto_front_size": 0,
            "raw_nominal_hypervolume": 0.0,
            "raw_shifted_hypervolumes": [0.0 for _ in SHIFT_SPECS],
            "shift_feasibility_rates": [0.0 for _ in SHIFT_SPECS],
        }


def _reset_candidate_session(candidate):
    reset = getattr(candidate, "reset_session", None)
    if callable(reset):
        reset()


def evaluate(design_rankine_archive):
    if set(CALIBRATED_ANCHORS) != {instance["name"] for instance in INSTANCES}:
        raise RuntimeError("Rankine-v2 calibration anchors are incomplete")
    records = []
    for index, instance in enumerate(INSTANCES):
        if index:
            _reset_candidate_session(design_rankine_archive)
        records.append(_score_instance(design_rankine_archive, instance))
    development = [record for record in records if record["split"] == "development"]
    heldout = [record for record in records if record["split"] == "heldout"]
    development_valid = sum(bool(record["valid"]) for record in development)
    heldout_valid = sum(bool(record["valid"]) for record in heldout)
    development_score = float(np.mean([record["score"] for record in development]))
    heldout_score = float(np.mean([record["score"] for record in heldout]))
    valid = development_valid == len(development)
    return {
        "combined_score": development_score if valid else 0.0,
        "valid": 1.0 if valid else 0.0,
        "feasibility_rate": float(np.mean([
            record["nominal_feasibility_rate"] for record in development
        ])),
        "raw_score": development_score if valid else 0.0,
        "robustness_score": float(np.mean([
            record["robustness_score"] for record in development
        ])),
        "heldout_policy_score": heldout_score if (
            heldout_valid == len(heldout)
        ) else 0.0,
        "heldout_robustness_score": float(np.mean([
            record["robustness_score"] for record in heldout
        ])),
        "heldout_feasibility_rate": float(np.mean([
            record["nominal_feasibility_rate"] for record in heldout
        ])),
        "development_shift_feasibility_rate": float(np.mean([
            np.mean(record["shift_feasibility_rates"]) for record in development
        ])),
        "heldout_shift_feasibility_rate": float(np.mean([
            np.mean(record["shift_feasibility_rates"]) for record in heldout
        ])),
        "development_mean_front_efficiency": float(np.mean([
            record.get("mean_front_efficiency", 0.0) for record in development
        ])),
        "heldout_mean_front_efficiency": float(np.mean([
            record.get("mean_front_efficiency", 0.0) for record in heldout
        ])),
        "development_mean_front_specific_net_work_kj_kg": float(np.mean([
            record.get("mean_front_specific_net_work_kj_kg", 0.0)
            for record in development
        ])),
        "heldout_mean_front_specific_net_work_kj_kg": float(np.mean([
            record.get("mean_front_specific_net_work_kj_kg", 0.0)
            for record in heldout
        ])),
        "candidate_instance_call_count": len(records),
        "candidate_instance_valid_rate": float(np.mean([
            record["valid"] for record in records
        ])),
        "per_instance": records,
    }
