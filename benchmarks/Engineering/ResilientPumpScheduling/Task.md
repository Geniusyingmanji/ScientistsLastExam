# ResilientPumpScheduling — tariff-aware water-distribution operation

Implement `schedule_pumps(problem)` and return `{"pump_speed": [...]}` with one speed in `[0,1]`
for each of 24 hourly intervals. Adjacent speeds must respect `maximum_speed_change`.

The frozen extended-period oracle balances forecast-error-adjusted demand, pump inflow and tank
storage. It computes pump energy from flow, static head, the speed-dependent head curve and
wire-to-water efficiency. Every nominal hour must keep tank volume within bounds and remote-node
pressure above 20 m; terminal storage must recover to its published target. Submissions are
rejected rather than clipped or repaired.

`combined_score` is development energy-cost savings above a conservative constant-speed schedule,
normalized by a truth-blind storage-feasible tariff coordinate search. Scores
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
