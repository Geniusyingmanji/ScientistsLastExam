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
