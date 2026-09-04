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
      age_offsets_years: one finite offset for every proxy, or [] when abstaining
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
deviations, and one finite age offset per record. Every returned age offset must lie in
`[-300, 300]` years.

## Evaluation

- `combined_score` is chronology-aware temperature mechanism recovery above always abstaining.
- Supported worlds report coefficient of efficiency (CE), RMSE, age-offset MAE and CRPS.
- Null and resolvable nonstationary/nonlinear proxy worlds reward calibrated refusal.
- False discovery, correct refusal, supported coverage and probability calibration are separate.
- `robustness_score` uses held-out spectra, proxy mixes, dating noise and chronology offsets.

This is a pseudoproxy benchmark. It does not reconstruct Earth's actual climate.

## Oracle and difficulty

The evaluator uses `xarray` to align climate fields on the public time coordinate and calculate CE
and RMSE. The pseudoproxy physics remains the stated local reduced-order model. Evaluator
difficulty levels 1–3 increase chronology offsets, proxy noise and dating noise; level 1 is the
shipped default and every level remains inside the public `[-300, 300]` offset contract.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Invalid or overspent dating calls invalidate the world even when caught.

References: Amrhein et al. (2020), DOI `10.1029/2020GL090485`; Badgeley et al. (2020),
DOI `10.5194/cp-16-1325-2020`.
