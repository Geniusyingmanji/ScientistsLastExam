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
deviations in `[1e-100,1e100]`, mean magnitudes at most `1e100`, and monotone sample ages for every record. A legacy `age_offsets_years` vector in
`[-300,300]` is still accepted when curves are absent; it is converted into clipped nominal-plus-offset
curves and scored on all 288 sample ages. With explicit curves, the offset vector may be omitted.

## Evaluation

Confidence is evaluated separately as `1 - (confidence - target)^2`. The target is
the actual mechanism-recovery score on a supported, non-abstaining world, and zero
for refusals or unsupported worlds. Thus a poor reconstruction with high confidence
cannot earn perfect confidence calibration. Invalid artifacts do not count as discovery
attempts; coverage counts valid, non-abstaining supported-world submissions.

- `combined_score` is chronology-aware temperature mechanism recovery above always abstaining.
- Supported worlds report coefficient of efficiency (CE), RMSE, sample-age MAE,
  adjacent-sample age-increment MAE, and Gaussian CRPS. Define
  `age_skill = exp(-age_MAE/65 - age_increment_MAE/12)` with ages in years and
  `probability_skill = exp(-mean_CRPS/0.45)` with temperatures in degrees C.
  Mechanism recovery is the cube root of `max(clip(CE,0,1),1e-12) * age_skill * probability_skill`.
  Local increments measure accumulation-rate recovery, so joining sparse dates
  cannot receive the same credit as reconstructing the intervening chronology.
- Null and resolvable nonstationary/nonlinear proxy worlds reward calibrated refusal.
- False discovery, correct refusal, supported coverage and probability calibration are separate.
- `robustness_score` uses held-out spectra, proxy mixes, dating noise and chronology curves.

This is a pseudoproxy benchmark. It does not reconstruct Earth's actual climate.

## Oracle and difficulty

The evaluator uses NumPy to align climate fields on the public time coordinate and calculate CE
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

Geophysics/UPbConcordiaInference is the closest neighbor: it buys dating measurements
and returns two scalar intercept ages on closed-form decay curves; it refuses event
histories outside a single lead-loss family and occupies discovery/evidence. Here the
artifact is 81 probabilistic temperatures plus 8x36 monotone ages, scored on CRPS and
local chronology shape, with calibration and cross-record adequacy axes; the taxonomy
is discovery/parameter_inversion. Geophysics/GravityInversion and
AtmosphericScience/RadiativeTransferFit also buy observations for field inversion,
but have no uncertain age-depth coordinate. EnergyBalanceModel and
ForcedSignalAttribution infer dynamics or forcing rather than chronology.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a
certified result. The runnable reference uses public inputs only. Reference methods,
calibration measurements, shortcut probes and ablation diagnostics are recorded in
the maintainer-facing `references/known_best.md`, which is not served to candidates.
They do not replace clean Linux sandbox replay, independent domain review,
Frontier-Eng overlap review or a frozen frontier-model calibration draw.

Each `proxy_catalog` row also supplies `calibration_temperature_c`, `calibration_proxy_values` (paired length-7 arrays), and scalar `calibration_noise_std`. These are noisy laboratory calibration observations of the proxy response, not the hidden historical climate series.

Each catalog row additionally supplies `chronology_model` (description), `accumulation_segments`
(integer), and `age_bounds_years` ([0,2000]). These fields describe the public
chronology contract; hidden accumulation rates are never candidate inputs.

The variable-accumulation construction is motivated by age-uncertain reconstruction methods in
[geoChronR](https://gchron.copernicus.org/articles/3/149/2021/gchron-3-149-2021.html);
this local synthetic generator is not an implementation or validation of that package.

## Frontier-Eng overlap comparison (2026-09-07)

无. Nearest catalog entries: predict_modality; denoising. Paid dating observations jointly constrain sample ages and climate reconstruction with unsupported-world refusal; FE predicts cell modalities or removes image/RNA noise without an age-depth chronology.

See `.research/chronology_assimilation_frontier_eng_overlap_2026-09-07.md` for the task-specific comparison against the pinned paper and available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.

## Measured capability ladder

Contributor Linux replay (NumPy 1.26.4 / SciPy 1.13.1); both splits use the same
method and fixed parameters. These measurements do not establish model difficulty.

| Method | Development | Held out | Development loss |
|---|---:|---:|---:|
| Full reference | 0.797985 | 0.714963 | 0.000000 |
| Without joint chronology refinement | 0.489000 | 0.440218 | 0.308985 |
| Replace final GP with unweighted mean / constant std | 0.775516 | 0.706424 | 0.022470 |
| Without diagonal age-error propagation | 0.797607 | 0.714278 | 0.000378 |
| Without laboratory calibration check | 0.547985 | 0.381630 | 0.250000 |
| Without cross-record coherence check | 0.547985 | 0.381630 | 0.250000 |
| Without either refusal check | 0.297985 | 0.048296 | 0.500000 |
| Best of 1008 fixed cheap strategies | 0.435979 | 0.387287 | 0.362006 |

The diagonal age-error approximation has only a small measured effect. The main
chronology capability is joint refinement from dates and shared proxy observations.

Each scientific world, including the first held-out world, starts a fresh sandbox
process; calls within one world share the same charged budget and candidate state.
