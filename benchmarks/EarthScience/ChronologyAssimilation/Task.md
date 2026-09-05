# ChronologyAssimilation — date proxy records and reconstruct a climate history

## Scientific setting

Paleoclimate reconstruction is limited by both proxy noise and chronology uncertainty. Apparent
climate disagreement may disappear after dating correction, while a nonstationary or nonlinear
proxy response should not be forced into a public linear proxy system. The candidate purchases a
small number of dates, aligns multiple proxy records and returns a probabilistic temperature
history or an explicit refusal.

Each item in `proxy_catalog` contains these public keys:

| key | meaning |
|---|---|
| `proxy_index` | stable integer record identifier |
| `proxy_type` | one of `tree`, `coral`, `sediment`, `ice` |
| `nominal_age_years` | ascending sample ages before present |
| `values` | standardized proxy observations |
| `noise_std` | stated observation standard deviation |
| `sensitivity` | public linear temperature sensitivity |
| `site_weight` | public representativeness weight |

## Your task

```python
def reconstruct_climate(time_grid_years, proxy_catalog, date_sample, budget_units):
    """Return:
      temperature_mean: length len(time_grid_years), or [] when abstaining
      temperature_std:  positive length len(time_grid_years), or [] when abstaining
      sample_ages_years: monotone [8,36] ages in [0,2000], or [] when abstaining
      age_offsets_years: optional legacy [8] constant-offset alternative
      confidence: finite scalar in [0,1]
      abstain: bool

    date_sample(proxy_index, sample_indices) returns:
      proxy_index: selected record
      sample_indices: selected integer indices
      dated_age_years: noisy independent ages for those samples
      date_noise_std_years: stated dating uncertainty
      budget_cost: charged units
    """
```

A dating call may request 1–10 unique valid samples from one record and costs
`1 + ceil(n_samples/5)`. Total cost may not exceed 16. The returned time grid is ascending. A
non-abstaining reconstruction must contain finite means, strictly positive finite standard
deviations, and monotone sample ages for every record. A legacy `age_offsets_years` vector in
`[-300,300]` is still accepted when curves are absent; it is converted into clipped nominal-plus-offset
curves and scored on all 288 sample ages. With explicit curves, the offset vector may be omitted.

## Evaluation

- `combined_score` is chronology-aware temperature mechanism recovery above always abstaining.
- Supported worlds report coefficient of efficiency (CE), RMSE, sample-age MAE and CRPS.
- Null and resolvable nonstationary/nonlinear proxy worlds reward calibrated refusal.
- False discovery, correct refusal, supported coverage and probability calibration are separate.
- `robustness_score` uses held-out spectra, proxy mixes, dating noise and chronology curves.

This is a pseudoproxy benchmark. It does not reconstruct Earth's actual climate.

## Oracle and difficulty

The evaluator uses `xarray` to align climate fields on the public time coordinate and calculate CE
and RMSE. The pseudoproxy physics remains the stated local reduced-order model. Evaluator
difficulty levels 1–3 use 6, 9 and 12 positive accumulation segments, respectively,
with increasing offset and noise uncertainty. Segment durations are lognormal (log standard
deviation 0.65), normalized to a 2000-year interval, followed by a bounded offset and clipping.
This gives monotone nonlinear age-depth maps. The original offset is a generative nuisance, not
a separately scored hidden parameter. Level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Invalid or overspent dating calls invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning a reconstruction.

References: Amrhein et al. (2020), DOI `10.1029/2020GL090485`; Badgeley et al. (2020),
DOI `10.5194/cp-16-1325-2020`.

## 关系与区别 / Relationship to nearby tasks

EnergyBalanceModel fits climate dynamics, ForcedSignalAttribution identifies forcing mechanisms, and ProspectiveMetaAnalysis synthesizes study evidence. This task pays for chronology observations, reconstructs a common climate series and tests proxy response adequacy against calibration observations.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

Each `proxy_catalog` row also supplies `calibration_temperature_c`, `calibration_proxy_values` (paired length-7 arrays), and scalar `calibration_noise_std`. These are noisy laboratory calibration observations of the proxy response, not the hidden historical climate series. They make a shared nonlinear response testable even when all historical proxies agree on that transformed series.

### Current reference and remaining difficulty

Calibration-tested, dated Gaussian-process reconstruction with propagated age error and coherence refusal. Public noisy proxy calibration observations make shared nonlinear response misspecification testable. Five sparse dates support shape-preserving age-depth interpolation. The posterior still approximates shared chronology errors diagonally. The optimization reference defines 1 by construction; a discovery reference is evaluated against the fixed recovery ceiling. Neither fact certifies difficulty.

Each catalog row additionally supplies `chronology_model` (description), `accumulation_segments`
(integer), and `age_bounds_years` ([0,2000]). The reference interpolates sparse dates with PCHIP
and performs GP climate reconstruction; it does not know hidden accumulation rates. Joint
age/climate posterior sampling and adaptive dating remain possible improvements.

The variable-accumulation construction is motivated by age-uncertain reconstruction methods in
[geoChronR](https://gchron.copernicus.org/articles/3/149/2021/gchron-3-149-2021.html);
this local synthetic generator is not an implementation or validation of that package.
