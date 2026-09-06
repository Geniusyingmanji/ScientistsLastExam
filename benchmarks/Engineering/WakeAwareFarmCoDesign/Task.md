# WakeAwareFarmCoDesign — wind-farm layout and yaw co-design

Implement `design_wind_farm(problem)` and return a mapping containing `layout_xy_m` with shape
`[turbine_count,2]` and `yaw_by_direction_deg` with one yaw angle per public wind direction and
turbine. Every turbine must lie inside the rectangular boundary, respect minimum Euclidean
spacing, and stay within the yaw limit. Invalid designs are rejected, never repaired.

The deterministic trusted model rotates the farm into each wind direction, combines upstream
Gaussian/Jensen-style wake deficits, includes yaw-induced wake displacement and own-turbine power
loss, caps rated power, and integrates the public wind rose. `combined_score` is annual-value
improvement over a regular zero-yaw grid. The truth-blind runnable witness uses ten layout starts,
coordinate yaw search and one 80 m layout-refinement scale, scoring `0.741392`; the oracle's
180-start, 80/40/20 m search is score one. The scale remains uncapped. Held-out farm geometries and a sealed wind-direction,
wake-expansion and turbulence shift are reported separately.

The oracle is a reduced engineering wake model, not wind-tunnel or field truth. Before admission,
the trajectories and rankings must be independently reproduced in a pinned FLORIS version and
reviewed by a wind-energy specialist.

Use only the supplied problem mapping and deterministic NumPy/SciPy/standard-library CPU code.
No network, process creation, or reads from `verification/` and `frontier_eval/`.

References: Fleming et al., *Journal of Physics: Conference Series* 1618, 022028 (2020),
doi:10.1088/1742-6596/1618/2/022028; NREL FLORIS documentation.

## Complete public input contract

Numeric values below are the first public example; per-instance arrays and coefficients vary.
All keys and shapes are part of the contract; forecasts contain exactly `horizon_steps` samples.

| Key | Type, shape or meaning |
|---|---|
| `turbine_count` | 9 |
| `boundary_width_m` | 1900.0 |
| `boundary_height_m` | 1700.0 |
| `rotor_diameter_m` | 120.0 |
| `minimum_spacing_rotor_diameters` | 4.0 |
| `wind_directions_deg` | array [12] |
| `wind_speeds_m_s` | array [12] |
| `wind_probabilities` | array [12] |
| `yaw_limit_deg` | 25.0 |
| `air_density_kg_m3` | 1.225 |
| `power_coefficient` | 0.44 |
| `thrust_coefficient` | 0.8 |
| `wake_expansion_public` | 0.055 |
| `contract` | return layout_xy_m [n,2] and yaw_by_direction_deg [12,n] |

## 关系与区别 / Relationship to nearby tasks

ResilientPumpScheduling optimizes time allocation, CompositeLaminateStacking optimizes discrete order, and DiffractionGratingDesign optimizes optical propagation. This task jointly chooses spatial turbine positions and wind-direction-dependent yaw; its wake model is a reduced screening model.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

### Current reference and remaining difficulty

Ten seeded layout starts, coordinate yaw search and one 80 m feasible layout-refinement scale form the runnable witness; the evaluator independently uses 180 starts and 80/40/20 m refinement as score one. The witness scores `0.741392` development / `0.613817` held-out. More global restarts and finer feasible layout refinement are the explicit headroom. Cross-model robustness and independent FLORIS validation remain open. This calibration does not certify difficulty.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: UAVInspectionCoverageWithWind; DawnAircraftDesignOptimization. Joint static turbine locations and directional yaw optimize farm value with wake interactions and wind-rose transfer. FE optimizes flight coverage in wind or aircraft mass/geometry, without turbine-to-turbine wakes or wind-farm yield.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
