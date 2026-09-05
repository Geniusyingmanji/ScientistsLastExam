# WakeAwareFarmCoDesign — wind-farm layout and yaw co-design

Implement `design_wind_farm(problem)` and return a mapping containing `layout_xy_m` with shape
`[turbine_count,2]` and `yaw_by_direction_deg` with one yaw angle per public wind direction and
turbine. Every turbine must lie inside the rectangular boundary, respect minimum Euclidean
spacing, and stay within the yaw limit. Invalid designs are rejected, never repaired.

The deterministic trusted model rotates the farm into each wind direction, combines upstream
Gaussian/Jensen-style wake deficits, includes yaw-induced wake displacement and own-turbine power
loss, caps rated power, and integrates the public wind rose. `combined_score` is annual-value
improvement over a regular zero-yaw grid, normalized by a truth-blind jittered-layout and
coordinate-yaw witness. It is uncapped. Held-out farm geometries and a sealed wind-direction,
wake-expansion and turbulence shift are reported separately.

The oracle is a reduced engineering wake model, not wind-tunnel or field truth. Before admission,
the trajectories and rankings must be independently reproduced in a pinned FLORIS version and
reviewed by a wind-energy specialist.

Use only the supplied problem mapping and deterministic NumPy/SciPy/standard-library CPU code.
No network, process creation, or reads from `verification/` and `frontier_eval/`.

References: Fleming et al., *Journal of Physics: Conference Series* 1618, 022028 (2020),
doi:10.1088/1742-6596/1618/2/022028; NREL FLORIS documentation.
