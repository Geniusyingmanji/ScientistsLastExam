# BOPTESTSupervisoryControl — cross-climate HVAC supervisory control

Implement `make_hvac_controller(problem)`. It returns a stateful callable that receives zone
temperatures, CO2, outdoor temperature, occupancy and the step index, then returns two-zone arrays
for `heating_kw`, `cooling_kw` and `ventilation_ach`. Actions must remain within public bounds;
simultaneous material heating and cooling in one zone is rejected.

The candidate receives weather, occupancy, price and carbon forecasts plus the declared thermal
model. The trusted deterministic emulator evolves two coupled RC zones and CO2 at 15-minute
resolution. Occupied comfort and IAQ are hard gates. Among feasible policies, `combined_score`
rewards lower energy cost, emissions, peak demand, discomfort and action movement above a shipped
rule controller, normalized by a truth-blind forecast controller. It is uncapped. Held-out heatwave
and cold-snap cases introduce forecast bias, sensor bias, plant-parameter drift and actuator loss.

This package implements the BOPTEST control contract and KPI structure in a light local emulator;
it does **not** claim to be an official BOPTEST test case. Candidate admission requires replay
against pinned BOPTEST FMUs/API and independent building-controls review.

Use deterministic NumPy/SciPy/standard-library CPU code only. No network, process creation, or
reads from `verification/` and `frontier_eval/`.

References: Blum et al., *Journal of Building Performance Simulation* 14(5), 586–610 (2021),
doi:10.1080/19401493.2021.1986574; IBPSA Project 1 BOPTEST documentation.

## Complete public input contract

Numeric values below are the first public example; per-instance arrays and coefficients vary.
All keys and shapes are part of the contract; forecasts contain exactly `horizon_steps` samples.

| Key | Type, shape or meaning |
|---|---|
| `sample_period_hours` | 0.25 |
| `horizon_steps` | 192 |
| `zone_count` | 2 |
| `outdoor_temperature_forecast_c` | array [192] |
| `occupancy_forecast` | array [192, 2] |
| `electricity_price_usd_kwh` | array [192] |
| `grid_carbon_kg_kwh` | array [192] |
| `comfort_bounds_occupied_c` | array [2]; [21.0, 25.0] |
| `co2_limit_ppm` | 1100.0 |
| `action_bounds` | mapping; fields listed below |
| `action_bounds.heating_kw` | array [2]; [0.0, 30.0] |
| `action_bounds.cooling_kw` | array [2]; [0.0, 30.0] |
| `action_bounds.ventilation_ach` | array [2]; [0.15, 1.8] |
| `observation_keys` | array [5]; ['step', 'zone_temperature_c', 'zone_co2_ppm', 'outdoor_temperature_c', 'occupancy'] |
| `thermal_model` | mapping; fields listed below |
| `thermal_model.zone_capacitance_j_k` | array [2]; [18000000.0, 15000000.0] |
| `thermal_model.envelope_ua_w_k` | array [2]; [620.0, 540.0] |
| `thermal_model.interzone_ua_w_k` | 180.0 |
| `contract` | factory returns stateful step(observation); each action key has two values |

Controller observations: `step` is a zero-based integer, `zone_temperature_c`, `zone_co2_ppm` and `occupancy` are length-2 arrays, and `outdoor_temperature_c` is scalar. Return length-2 `heating_kw`, `cooling_kw`, `ventilation_ach`. CO2 must remain below the published 1100 ppm limit in occupied samples. Thermal feasibility requires mean occupied excursion at most 0.10°C, maximum at most 0.50°C, and the fraction of occupied samples exceeding 0.05°C excursion at most 0.05. These are published in `comfort_tolerance` (`mean_excursion_c`, `maximum_excursion_c`, `violation_rate`). Heating/cooling capacity is 30 kW per zone, including enough capacity to make the declared shifted climates feasible. The CO2 update is `co2 += 4*occupancy - .25*ventilation*(co2-420)`. Thermal gains are `.095*occupancy + [.65,.45]` kW. The declared RC model advances with heating minus cooling and interzone exchange; ventilation currently affects CO2 and fan energy, not thermal exchange. Electricity uses heating COP 3.2, cooling COP 3.4 and fan `.55*ventilation**3`; the peak KPI uses delivered heat/cool plus fan power. These reduced-model choices require independent review.

## 关系与区别 / Relationship to nearby tasks

ResilientPumpScheduling submits an open-loop schedule and HeatExchangerDesign chooses a static component. Here a stateful two-zone controller receives forecasts and live temperature/CO2 observations across weather and actuator shifts.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

### Current reference and remaining difficulty

Forecast boundary tracking with online thermal disturbance estimation and one-step CO2 control. A load-compensated baseline and sufficient 30 kW capacity make all declared climates feasible. Public comfort excursion/rate tolerances replace permissive hidden thresholds; CO2 enforces the published limit. Anchor errors are separated from candidate errors. The optimization reference defines 1 by construction; a discovery reference is evaluated against the fixed recovery ceiling. Neither fact certifies difficulty.

## Frontier-Eng overlap comparison (2026-09-06)

同类不同题. Nearest catalog entries: hand_written_control; PIDTuning. Stateful two-zone heating/cooling/ventilation satisfies occupied temperature and CO2 gates under biased forecasts and actuator shifts. FE data-center control couples cooling with workload shifting and battery dispatch, optimizing carbon/water; PIDTuning controls flight. The HVAC/control-family overlap remains high risk and requires explicit maintainer acceptance.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
