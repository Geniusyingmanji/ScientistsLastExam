"""Single-reheat Rankine-cycle equations used by the trusted evaluator."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from if97 import region2, saturation_state, saturation_temperature, state_ph, state_ps


DESIGN_COLUMNS = (
    "boiler_pressure_mpa",
    "main_steam_temperature_c",
    "reheat_pressure_fraction",
    "reheat_temperature_c",
)


def _quality(state: Mapping[str, float]) -> float:
    region = int(round(float(state["region"])))
    if region == 2:
        return 1.0
    if region == 4:
        return float(state["x"])
    return 0.0


def evaluate_cycle(
    design: Sequence[float],
    condition: Mapping[str, float],
) -> dict[str, float | bool | str]:
    """Evaluate one physical design under one operating condition.

    The design sets boiler pressure, main-steam temperature, the HP-exhaust
    pressure as a fraction of main-turbine inlet pressure, and reheat
    temperature.  Boiler and reheater pressure losses are operating-condition
    quantities, so the same hardware design can be tested under sealed shifts.
    """
    try:
        values = tuple(float(value) for value in design)
    except (TypeError, ValueError) as exc:
        raise ValueError("cycle design must contain four numeric values") from exc
    if len(values) != 4 or not all(math.isfinite(value) for value in values):
        raise ValueError("cycle design must contain four finite values")
    pressure, main_c, reheat_fraction, reheat_c = values

    required = (
        "condenser_pressure_kpa",
        "hp_turbine_efficiency",
        "lp_turbine_efficiency",
        "pump_efficiency",
        "boiler_pressure_loss_fraction",
        "reheat_pressure_loss_fraction",
        "max_boiler_pressure_mpa",
        "max_steam_temperature_c",
        "minimum_hp_exit_quality",
        "minimum_lp_exit_quality",
    )
    operating = {key: float(condition[key]) for key in required}
    if not all(math.isfinite(value) for value in operating.values()):
        raise ValueError("operating condition must be finite")

    condenser_pressure = operating["condenser_pressure_kpa"] / 1000.0
    main_pressure = pressure * (1.0 - operating["boiler_pressure_loss_fraction"])
    hp_exit_pressure = reheat_fraction * main_pressure
    lp_inlet_pressure = hp_exit_pressure * (
        1.0 - operating["reheat_pressure_loss_fraction"]
    )
    main_temperature = main_c + 273.15
    reheat_temperature = reheat_c + 273.15

    constraints = {
        "positive_pressure_order": (
            pressure > main_pressure > hp_exit_pressure > lp_inlet_pressure
            > 1.05 * condenser_pressure > 0.0
        ),
        "pressure_material_limit": pressure <= operating["max_boiler_pressure_mpa"],
        "temperature_material_limit": max(main_c, reheat_c)
        <= operating["max_steam_temperature_c"],
        "efficiency_bounds": (
            0.0 < operating["hp_turbine_efficiency"] <= 1.0
            and 0.0 < operating["lp_turbine_efficiency"] <= 1.0
            and 0.0 < operating["pump_efficiency"] <= 1.0
        ),
        "loss_bounds": (
            0.0 <= operating["boiler_pressure_loss_fraction"] < 0.2
            and 0.0 <= operating["reheat_pressure_loss_fraction"] < 0.2
        ),
        "if97_region_limit": pressure <= 15.0,
    }
    if not all(constraints.values()):
        return {
            "process_feasible": False,
            "failure": next(key for key, passed in constraints.items() if not passed),
            "thermal_efficiency": 0.0,
            "specific_net_work_kj_kg": 0.0,
            "hp_exit_quality": 0.0,
            "lp_exit_quality": 0.0,
            "energy_balance_residual_kj_kg": math.inf,
        }

    main_saturation = saturation_temperature(main_pressure)
    reheat_saturation = saturation_temperature(lp_inlet_pressure)
    constraints["main_superheat_margin"] = main_temperature >= main_saturation + 10.0
    constraints["reheat_superheat_margin"] = reheat_temperature >= reheat_saturation + 10.0
    if not all(constraints.values()):
        return {
            "process_feasible": False,
            "failure": next(key for key, passed in constraints.items() if not passed),
            "thermal_efficiency": 0.0,
            "specific_net_work_kj_kg": 0.0,
            "hp_exit_quality": 0.0,
            "lp_exit_quality": 0.0,
            "energy_balance_residual_kj_kg": math.inf,
        }

    state1 = saturation_state(condenser_pressure)["liquid"]
    assert isinstance(state1, dict)
    pump_isentropic = state_ps(pressure, state1["s"])
    pump_work_isentropic = pump_isentropic["h"] - state1["h"]
    state2_h = state1["h"] + pump_work_isentropic / operating["pump_efficiency"]
    state2 = state_ph(pressure, state2_h)

    state3 = region2(main_temperature, main_pressure)
    hp_isentropic = state_ps(hp_exit_pressure, state3["s"])
    state4_h = state3["h"] - operating["hp_turbine_efficiency"] * (
        state3["h"] - hp_isentropic["h"]
    )
    state4 = state_ph(hp_exit_pressure, state4_h)

    state5 = region2(reheat_temperature, lp_inlet_pressure)
    lp_isentropic = state_ps(condenser_pressure, state5["s"])
    state6_h = state5["h"] - operating["lp_turbine_efficiency"] * (
        state5["h"] - lp_isentropic["h"]
    )
    state6 = state_ph(condenser_pressure, state6_h)

    pump_work = state2["h"] - state1["h"]
    hp_work = state3["h"] - state4["h"]
    lp_work = state5["h"] - state6["h"]
    boiler_heat = state3["h"] - state2["h"]
    reheat_heat = state5["h"] - state4["h"]
    heat_input = boiler_heat + reheat_heat
    net_work = hp_work + lp_work - pump_work
    heat_rejected = state6["h"] - state1["h"]
    efficiency = net_work / heat_input if heat_input > 0.0 else 0.0
    hp_quality = _quality(state4)
    lp_quality = _quality(state6)
    residual = heat_input - heat_rejected - net_work

    constraints.update({
        "positive_heat_and_work": heat_input > 0.0 and net_work > 0.0,
        "hp_moisture_limit": hp_quality >= operating["minimum_hp_exit_quality"],
        "lp_moisture_limit": lp_quality >= operating["minimum_lp_exit_quality"],
        "energy_balance": abs(residual) <= 2.0e-8,
        "thermodynamic_efficiency": 0.0 < efficiency < 1.0,
        "reheat_adds_heat": reheat_heat > 0.0,
    })
    feasible = all(constraints.values())
    result: dict[str, float | bool | str] = {
        "process_feasible": feasible,
        "thermal_efficiency": efficiency,
        "specific_net_work_kj_kg": net_work,
        "heat_input_kj_kg": heat_input,
        "heat_rejected_kj_kg": heat_rejected,
        "pump_work_kj_kg": pump_work,
        "hp_turbine_work_kj_kg": hp_work,
        "lp_turbine_work_kj_kg": lp_work,
        "hp_exit_quality": hp_quality,
        "lp_exit_quality": lp_quality,
        "energy_balance_residual_kj_kg": residual,
        "main_turbine_inlet_pressure_mpa": main_pressure,
        "hp_exit_pressure_mpa": hp_exit_pressure,
        "lp_turbine_inlet_pressure_mpa": lp_inlet_pressure,
        "maximum_steam_temperature_c": max(main_c, reheat_c),
    }
    if not feasible:
        result["failure"] = next(
            key for key, passed in constraints.items() if not passed
        )
    return result
