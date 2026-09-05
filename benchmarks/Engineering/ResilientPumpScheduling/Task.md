# ResilientPumpScheduling — tariff-aware water-distribution operation

Implement `schedule_pumps(problem)` and return `{"pump_speed": [...]}` with one speed in `[0,1]`
for each of 24 hourly intervals. A running pump must be at or above
`minimum_operating_speed`; zero means off. The ramp limit applies between consecutive running
hours, with startup/shutdown completed inside one hourly interval. Each on-run, including the
last run in the horizon, must last at least `minimum_run_hours`; the initial pump is off.

The frozen extended-period oracle balances forecast-error-adjusted demand, pump inflow and tank
storage. It computes pump energy from flow, static head, the speed-dependent head curve and
wire-to-water efficiency. Every nominal hour must keep tank volume within bounds and remote-node
pressure above 20 m; terminal storage must recover to its published target. Submissions are
rejected rather than clipped or repaired.

`combined_score` is development energy-cost savings above a conservative constant-speed schedule,
normalized by a truth-blind public-demand-band commitment search with convex dispatch subproblems. Scores
are uncapped. Held-out systems, 12% demand growth and a four-hour peak-period pump outage are
reported separately and cannot be selected against.

This compact model preserves the storage, tariff, pressure and outage couplings needed for a local
benchmark. It is not an EPANET hydraulic certification. Engineering claims require replay in a
frozen EPANET/WNTR network and independent water-systems review.

Public keys include the demand and tariff series, pump capacity/head/efficiency, tank limits,
terminal target and ramp limit. Use deterministic NumPy/SciPy/standard-library CPU code only; no
network, process creation, or reads from `verification/` and `frontier_eval/`.

References: EPA, *EPANET 2.2 User Manual*, EPA/600/R-20/133 (2020); Guidolin et al.,
*Drink. Water Eng. Sci.* 7, 53–63 (2014), doi:10.5194/dwes-7-53-2014.

## Complete public input contract

Numeric values below are the first public example; per-instance arrays and coefficients vary.
All keys and shapes are part of the contract; forecasts contain exactly `horizon_steps` samples.

| Key | Type, shape or meaning |
|---|---|
| `horizon_hours` | 24 |
| `time_step_hours` | 1.0 |
| `demand_forecast_m3_h` | array [24] |
| `electricity_usd_kwh` | array [24] |
| `pump_capacity_m3_h` | 165.0 |
| `pump_static_head_m` | 36.36 |
| `pump_speed_head_coefficient_m` | 18.0 |
| `wire_to_water_efficiency` | 0.78 |
| `tank_initial_volume_m3` | 820.0 |
| `tank_minimum_volume_m3` | 310.0 |
| `tank_maximum_volume_m3` | 1510.0 |
| `terminal_minimum_volume_m3` | 820.0 |
| `maximum_speed_change` | 0.55 |
| `minimum_operating_speed` | 0.65; stable operating range when on |
| `minimum_run_hours` | 2; minimum consecutive on duration |
| `running_auxiliary_power_kw` | 2.5; electrical auxiliary draw while on |
| `startup_cost_usd` | 0.30 per off-to-on event, including the initial start |
| `contract` | zero or stable operating speed, minimum run and on-to-on ramp rules |

## 关系与区别 / Relationship to nearby tasks

GroundwaterRemediationDesign chooses remediation wells and an archive, BSM1AerationControl closes an effluent feedback loop, and BOPTESTSupervisoryControl controls zone conditions. This task submits a 24-hour open-loop pump schedule for a single storage system; it has no pipe-network hydraulic solve.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

### Current reference and remaining difficulty

Public-demand-band block-exchange commitment search with linear storage/pressure constraints and fixed-mask convex dispatch. Replaces tariff coordinate moves with constrained convex optimization. No invented 0.92-baseline anchor is used when the reference fails; an invalid anchor is an infrastructure error. This remains a single-tank surrogate, not a pipe-network solver. The optimization reference defines 1 by construction; a discovery reference is evaluated against the fixed recovery ceiling. Neither fact certifies difficulty.

The cost adds running auxiliary electricity at the current tariff and the startup charge to
hydraulic electricity and speed variation. This creates a genuine discrete commitment decision:
an all-on continuous optimum can lose to a schedule that stores water and shuts down at expensive
hours. The public reference alternates feasible 2–4 hour commitment-block changes and bounded
continuous dispatch, with two passes; it is a heuristic, not a global optimality certificate.
Minimum speed, run time and auxiliary load are synthetic equipment assumptions requiring domain
review. The model still has only one pump and one tank, and outage resilience remains a separate
reported diagnostic rather than part of the nominal objective.
