# GroundwaterRemediationDesign — build a robust pump-and-treat Pareto archive

## Scientific setting

Pump-and-treat remediation trades contaminant removal and receptor protection against well,
energy and treatment cost. A cheap homogeneous transport proxy can promote a plan that fails
under heterogeneous velocity, dispersion, decay or continued source release. The candidate
therefore submits an archive of remediation plans rather than one arbitrarily weighted design.

Each plan is an array whose rows are

```text
[x_m, y_m, start_year, pumping_rate_m3_day]
```

The candidate receives one `problem` mapping with every public key below:

| key | meaning |
|---|---|
| `domain_size_m` | `[length,width]` |
| `horizon_years`, `evaluation_times_years` | remediation horizon and reporting times |
| `source_location_m`, `initial_contaminant_mass_kg` | public initial plume |
| `plume_components` | rows `[x_offset_m,y_offset_m,mass_fraction]` relative to source; fractions sum to one |
| `transport_step_days` | maximum internal integration step, split at each well activation |
| `longitudinal_sigma_m`, `transverse_sigma_m` | proxy plume scales |
| `groundwater_velocity_m_day`, `decay_per_day` | proxy transport parameters |
| `aquifer_thickness_m`, `effective_porosity` | concentration conversion |
| `receptor_locations_m`, `concentration_limit_kg_m3` | hard cleanup target |
| `well_count_bounds`, `pumping_rate_bounds_m3_day` | per-plan bounds |
| `max_total_pumping_m3_day`, `start_year_bounds` | operating bounds |
| `fixed_well_cost_usd`, `pumping_cost_usd_per_m3`, `discount_rate` | lifecycle cost model |
| `archive_size_bounds`, `well_columns` | artifact contract |

## Your task

```python
def design_remediation(problem):
    """Return {"plans": [plan_1, ..., plan_n]} with 4-16 unique plans."""
```

Every plan contains 1–5 unique wells. Coordinates must lie inside the domain, start years and
pumping rates must lie inside their public bounds, and total pumping must not exceed the public
limit. All values must be finite.

## Evaluation

The public proxy and hidden exact simulator report:

- remaining contaminant mass in kg;
- maximum receptor concentration in kg/m3 and cleanup compliance;
- discounted lifecycle cost in USD;
- total pumped water in m3; and
- the Pareto hypervolume for maximizing cleanup and minimizing lifecycle cost.

`combined_score` is normalized development exact-model hypervolume, floored at zero and uncapped
above the shipped reference. Regulatory compliance is a hard gate: a cheap plan cannot compensate
for receptor exceedance. The evaluator separately
retains proxy hypervolume, false promotion, held-out aquifers and the worst hidden velocity,
dispersion, decay and continued-release shift. `robustness_score` is the worst shifted normalized
hypervolume.

Evaluator-only per-problem diagnostics use the keys `split`, `problem_index`, `valid`, `score`,
`exact_feasibility_rate`, `raw_exact_hypervolume`, `raw_proxy_hypervolume`,
`mean_remaining_mass_kg`, `mean_lifecycle_cost_usd` and
`worst_shifted_raw_hypervolume`. Their values and split membership are never candidate inputs.

The transport model is a deterministic Gaussian-plume/capture approximation. It is not a site
remediation decision and requires MODFLOW or field replication before scientific use.

## Oracle and difficulty

The evaluator uses NumPy for shape-checked contaminant-mass and time-by-receptor concentration
histories and compliance reduction. The plume/capture physics remains the stated local
reduced-order model. Evaluator difficulty levels 1–3 tighten the receptor limit and strengthen
proxy-to-exact discrepancy and robustness stresses; level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep `design_remediation(problem)`.
- Deterministic Python/NumPy/SciPy code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Malformed, duplicated-only, non-finite or out-of-bound archives fail closed.

References: Erickson, Mayer & Horn (2002), DOI `10.1016/S0309-1708(01)00020-3`;
Deschaine, Lillys & Pintér (2013), DOI `10.1186/2193-2697-2-6`.

## 关系与区别 / Relationship to nearby tasks

ResilientPumpScheduling operates a tank, IceObservationNetworkDesign selects observations, and RadiativeTransferFit fits a forward model. This task selects wells, start times and pumping rates for a multi-component moving plume, returning a cost/cleanup Pareto archive.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

The surrogate advects each initial Gaussian component at the declared velocity. At every internal step, extraction is local `Q*C` evaluated at the current well coordinates and moving plume center. Remaining component mass is advanced with an exponential combined extraction/decay hazard; extracted plus decayed plus remaining mass equals initial mass. Spread variances grow by `16*t` and `4.4*t` m² with time in days. This replaces the obsolete capture-at-start approximation.

### Current reference and remaining difficulty

Public moving-plume mass-balance search over single wells and treatment transects, greedily selecting a hypervolume archive. Local extraction uses Q*C at the evolving plume position, with activation-aware integration and an extracted/decayed/remaining mass ledger. Three public initial plume components replace the spatially collapsed capture-at-start model. The optimization reference defines 1 by construction; a discovery reference is evaluated against the fixed recovery ceiling. Neither fact certifies difficulty.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: BatteryFastChargingProfile; EV2GymSmartCharging. Choose extraction-well locations, activation times and rates under contaminant transport, mass balance and receptor limits; FE controls battery charge. Shared time-dependent design does not share governing physics or the remediation objective.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
