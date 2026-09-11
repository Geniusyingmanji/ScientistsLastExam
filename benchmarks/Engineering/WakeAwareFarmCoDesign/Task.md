# WakeAwareFarmCoDesign — wind-farm layout and yaw co-design

Implement `design_wind_farm(problem)` and return `layout_xy_m` with shape
`[turbine_count, 2]` plus `yaw_by_direction_deg` with one yaw angle per public
wind direction and turbine. Every turbine must lie inside the rectangular
boundary, respect minimum Euclidean spacing, and stay within the yaw limit.
Invalid designs are rejected rather than repaired.

## Complete public objective

For wind direction `d`, rotate the layout into wind axes and process turbines
from upwind to downwind. For an upwind turbine `i` and downstream turbine `j`,
with `dx = down_j - down_i > 0` and yaw `γ_i` in radians:

```
R      = rotor_diameter_m / 2
k      = wake_expansion_public
a      = 0.5 * (1 - sqrt(1 - Ct))
sigma  = R + k * dx
center = cross_i + 0.5 * Ct * cos(γ_i)^2 * sin(γ_i) * dx
delta_i = 2*a*cos(γ_i)^2 / (1 + k*dx/R)^2
          * exp(-0.5*((cross_j-center)/sigma)^2)
u_eff,j = u_d * max(0, 1 - sqrt(sum_i delta_i^2))
P_j     = 0.5*rho*pi*R^2*Cp*u_eff,j^3*cos(γ_j)^yaw_power_exponent
V       = sum_d p_d * sum_j P_j * 8760 / 1e9  # GWh
```

This is a deliberately reduced Gaussian/Jensen screening model. It does not
claim to reproduce the complete Bastankhah or FLORIS implementations. The
Gaussian deficit, yaw-deflection and approximately `cos^1.9` own-power-loss
choices follow those model families; their ranking on these instances still
requires pinned FLORIS and wind-energy review.

The task scores two capabilities separately:

```
layout_score = (V(layout, 0) - V(base_layout, 0)) / anchor_layout_gain
yaw_control_score = (V(layout, yaw) - V(layout, 0)) / anchor_yaw_gain
combined_score = sqrt(max(0, layout_score) * max(0, yaw_control_score))
```

The component anchors are the best layout gain and best yaw increment found in
a stronger reproducible search envelope. The scale is floored at zero and
uncapped above one. This decomposition is intentional: a spread-out zero-yaw
layout and a yaw policy on the unchanged baseline layout each demonstrate only
one capability and therefore receive combined score zero. Per-axis values remain
visible in `per_instance`; a zero combined score must not be misreported as zero
single-axis engineering value.

Held-out farm geometries and a separate `k=0.074`, wind-direction `+7 deg`
robustness evaluation never control `combined_score`.

Use only the supplied problem mapping and deterministic NumPy/SciPy/standard-
library CPU code. Do not access the network, create processes, or read
`verification/` or `frontier_eval/`.

References: Fleming et al., *J. Phys.: Conf. Ser.* 1618, 022028 (2020),
doi:10.1088/1742-6596/1618/2/022028; Bastankhah & Porte-Agel,
*J. Fluid Mech.* 806, 506–541 (2016), doi:10.1017/jfm.2016.595;
NREL FLORIS documentation at https://nrel.github.io/floris/.

## Complete public input contract

The numeric values below are the first public example. Direction, speed and
probability arrays always have the same length, which fixes the yaw row count.

| Key | Type, shape or first-example value |
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
| `yaw_power_exponent` | 1.88 |
| `contract` | return layout `[n,2]` and yaw `[number of directions,n]` |

## Ablation ladder and shortcut interpretation

On the 2026-09-12 revision, the runnable joint reference scores `0.782836`
development and `0.782388` heldout. Its development mean axes are `0.714964`
layout and `0.864917` yaw control; every instance has positive yaw GWh gain.

| Candidate family | Layout capability | Yaw capability | Combined score |
|---|---:|---:|---:|
| regular layout, zero yaw | baseline | none | 0.000000 |
| improved/reference layout, zero yaw | positive | none | 0.000000 |
| regular layout, coordinate-refined yaw | none | positive | 0.000000 |
| complete layout/yaw reference | 0.714964 mean | 0.864917 mean | 0.782836 |

Thus the earlier repulsion/spreading probe (previously 0.509220 under the old
single total-value score) is retained as evidence that layout alone is useful,
not described as joint co-design. Every zero-yaw layout family now has combined
score zero by definition while its `layout_score` remains inspectable. Frontier-
model calibration is still required to test shortcuts that optimize both axes.

## 关系与区别 / Relationship to nearby tasks

`StructuralEngineering/TrussWeightMinimization` changes member sizes,
`Thermodynamics/HeatExchangerDesign` builds a thermal Pareto archive, and
`Optics/DiffractionGratingDesign` changes an optical propagation geometry. This
task couples static turbine placement to a direction-indexed wake-steering
control schedule and scores the two contributions separately. No removed or
unmerged task is used as its nearest neighbor.

## Admission status

This package remains a **candidate**. The deterministic local measurements above
do not replace a clean Linux sandbox replay, a frozen first-proposal model draw,
server-held wind roses, pinned FLORIS comparison, or independent wind-energy
review. See `references/known_best.md` for history and reproduction details.

## Frontier-Eng overlap comparison

No matching task was found in the pinned catalog. The nearest entries are
`UAVInspectionCoverageWithWind` and `DawnAircraftDesignOptimization`, which
optimize aircraft trajectories or aircraft design rather than inter-turbine wake
coupling and directional yaw control. The catalog-count discrepancy remains an
open maintainer decision; see `.research/pr9_frontier_eng_overlap_2026-09-06.md`.
