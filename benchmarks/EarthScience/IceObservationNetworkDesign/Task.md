# IceObservationNetworkDesign — design a cost-aware ice-sheet observing system

## Scientific setting

Ice-sheet projection uncertainty depends strongly on which velocities, elevations, thicknesses,
grounding-line positions and basal-radar transects are observed. Observation System Simulation
Experiments (OSSEs) evaluate proposed measurements by generating synthetic observations,
assimilating them with a fixed method, and measuring the resulting forecast improvement. This
task asks for observation networks, not for an inferred basal-friction field.

The candidate receives one `problem` mapping with these public keys:

| key | meaning |
|---|---|
| `observation_catalog` | list of index, type, normalized x/y, year, cost and noise |
| `proxy_sensitivity` | public observation-by-state sensitivity matrix |
| `prior_covariance` | public state prior covariance |
| `forecast_matrix` | public map from state to forecast quantities |
| `forecast_names`, `forecast_units` | grounding line, mass loss and sea-level equivalent |
| `budget_units` | maximum cost of each design |
| `selection_size_bounds` | minimum and maximum selected observations |
| `archive_size_bounds` | required number of distinct designs |

## Your task

```python
def design_ice_observation_network(problem):
    """Return {"plans": [indices_1, ..., indices_n]} with 4-16 unique plans."""
```

Each plan is a one-dimensional list of 3–10 unique integer catalog indices. The sum of catalog
costs must not exceed `budget_units`.

## Evaluation

A deterministic linear-Gaussian OSSE draws fixed hidden states and observation errors, applies a
fixed Kalman update using the public proxy, and evaluates forecasts under evaluator-only
sensitivity and dynamics shifts. It reports:

- grounding-line RMSE in m;
- twenty-year mass-loss RMSE in Gt;
- sea-level-equivalent RMSE in mm;
- continuous ranked probability score (CRPS);
- posterior covariance trace and log determinant;
- observation cost; and
- forecast-skill-versus-cost Pareto hypervolume.

`combined_score` is normalized development exact-OSSE hypervolume, floored at zero but not capped.
The shipped truth-blind reference searches eight coarse budget levels and scores `0.679581`.
The oracle's score-one anchor uses the same public method at every integer budget from five through
eighteen, so the headroom is specifically low-cost Pareto coverage. Posterior trace/log determinant are diagnostics, not the primary objective:
an overconfident proxy cannot beat poor hidden
forecast skill. `robustness_score` is the worst sensitivity/noise/dynamics shift.

Evaluator-only per-problem diagnostics use the keys `split`, `problem_index`, `valid`, `score`,
`raw_exact_hypervolume`, `raw_proxy_hypervolume`, `grounding_line_rmse_m`,
`mass_loss_rmse_gt`, `sea_level_rmse_mm`, `mean_normalized_crps`, `posterior_trace` and
`posterior_logdet`. Their values and split membership are never candidate inputs.

This is a reduced-order OSSE and not a mission design recommendation.

## Oracle and difficulty

The evaluator uses NumPy to align ensemble/forecast dimensions and calculate forecast RMSE and
normalized CRPS. The ice dynamics and observation operators remain the stated local
linear-Gaussian OSSE. Evaluator difficulty levels 1–3 increase observation noise, proxy-to-exact
model discrepancy and sealed physical stresses; level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep `design_ice_observation_network(problem)`.
- Deterministic Python/NumPy/SciPy code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Malformed, duplicated, out-of-range or over-budget plans fail closed.

References: Choi et al. (2025), DOI `10.5194/tc-19-5423-2025`; Edwards et al. (2023),
DOI `10.5194/tc-17-4661-2023`.

## 关系与区别 / Relationship to nearby tasks

GroundwaterRemediationDesign changes remediation actions, ActiveFullWaveformInversion acquires waveforms for inversion, and ChronologyAssimilation acquires dates. This task selects a budgeted sensor archive for a six-state linear-Gaussian forecast surrogate, not a nonlinear ice-flow solver.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

### Current reference and remaining difficulty

Unit-normalized forecast A-optimal greedy selection with budget-feasible exchange refinement. Normalizing each forecast by its prior standard deviation prevents meters from dominating millimeters. Three exchange passes improve the greedy archive; nonlinear ice-flow validation is still pending. The coarse-budget runnable reference scores `0.679581` development / `0.554644` robustness against the dense-budget anchor. A probe using the previously omitted low-cost budgets exceeded the old anchor, which is why those budgets are now included in score one. This calibration does not certify difficulty.

## Frontier-Eng overlap comparison (2026-09-06)

同类不同题. Nearest catalog entries: CarAerodynamicsSensing; MuonTomography. Both choose observations. Here a costed mixed instrument subset reduces three ice forecast errors under correlated noise and dynamics shifts; FE selects car-surface pressure locations or muon detector geometry. Whether this observation-design family is sufficiently distinct remains a maintainer judgment.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
