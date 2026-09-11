# DarkMatterRecoilAttribution — distinguish recoil laws across targets under a shared uncertain halo

Implement `infer_recoil(problem, experiment)` in `solution.py`. Buy target exposures,
combine recoil spectra with gain/background controls, then submit an interaction law
and mass, a valid null conclusion, or a refusal of the declared model family.

This is a controlled synthetic inverse problem. It does not identify the real dark
matter particle, estimate a physical cross-section, or cover every WIMP/axion/PBH theory.
The fixed source model uses elastic coherent scattering and a finite positive halo
basis. Halo-independent multi-target inference motivates it ([Cherry et al., 2014](https://arxiv.org/abs/1405.1420));
the finite basis and detector simplifications below define this task, not that paper.

## Forward model

For target mass number A and proton number Z, define mT=0.9315 A GeV,
μ=m mT/(m+mT), q=sqrt(2 mT E × 10⁻⁶) GeV and vmin=299792.458 q/(2μ) km/s,
where the bin centre E is in keV. Let r be the neutron/proton coupling ratio,
R=1.2 A^(1/3) fm, F²=exp[−(qR/0.1973269804)²/3], and q0=0.05 GeV.

```text
K[t,j,k] = width[j] * ((Z+(A-Z)*r)/100)^2 * F²
           * (q/q0)^p * (260/v[k]) * exp(-(vmin/v[k])²)
s[t,j] = sum_k K[t,j,k] * w[k],  w[k] >= 0
b[t,j] = width[j] * (beta[t]*exp(-E[j]/32) + 1.5)
science_counts[t,j] ~ Poisson(units * gain[t] * (s[t,j]+b[t,j]))
background_counts[t,j] ~ Poisson(units * 8 * gain[t] * b[t,j])
calibration_counts[t] ~ Poisson(units * 100 * gain[t])
```

All three targets share m, r and the three nonnegative speed amplitudes w, while
beta and gain vary by target. Rates/amplitudes are benchmark units. The supplied
widths define disjoint geometrically spaced bins and the displayed rate uses midpoint
quadrature. The Gaussian nuclear form factor, unboosted/untruncated isotropic speed
mixture, unit efficiency and lack of detector smearing are explicit approximations.
It is **not** a faithful LZ likelihood or a complete halo-independent analysis.

`contact` means p=0; `q2` means p=2 in the *rate*, not the amplitude.
`none` means no signal above the specified controlled background. An excess outside
the declared common-spectrum family requires `abstain`, not a forced best-fitting law.
Failed discrimination between the two laws also permits abstention. A null finding
does not assert that cosmic dark matter does not exist.

## Public problem — all keys

| Key | Meaning |
|---|---|
| `targets` | 3 dictionaries, each with `name`, `mass_number`, `protons`; index is the target requested |
| `energy_kev` | 18 positive bin centres shared across targets |
| `bin_widths_kev` | 18 positive corresponding bin widths |
| `speed_components_kms` | 3 Maxwell speed scales in km/s; amplitudes unknown |
| `budget_units` | total affordable exposure units (12) |
| `mass_bounds_gev` | legal fitted mass interval [10,250] |
| `coupling_ratio_bounds` | r in [0.5,1.5] |
| `interaction_laws` | supported positive models `contact`, `q2` |
| `background_scale_kev` | exponential background scale (32) |
| `flat_background_rate` | flat background density (1.5) |
| `calibration_rate` | known calibration density (100 counts per gain-unit) |
| `background_control_factor` | control/science background exposure ratio (8) |
| `reference_momentum_gev` | q0 (0.05) |

The detector design and all other public problem values are identical across
worlds and splits. Seeds, splits and physical parameters are not provided. Do not infer a world label from call order or retain information between
independent worlds. No access to other worlds is scientifically legitimate.

## Charged experiment

Call `experiment({"target": t, "units": n})`: t must be a Python integer 0–2,
n a positive Python integer, and the sum of n over calls may not exceed the budget.
Booleans are not integers for this API. Unknown or missing query keys invalidate
the campaign. An invalid/over-budget query permanently invalidates that world even
if caught. The sampler checks the budget before allocating a requested array.

The response has `target`, `units`, `counts` (18 integers), `background_counts`
(18 integers), `calibration_counts` (one integer). Controls arrive with each
exposure and their cost is included. Units use independent counter-seeded samples:
two one-unit queries equal a two-unit query after summing counts; revisiting a
target does not replay the first noisy sample. Each target has a separate counter.

## Submission

```python
return {"model": "contact", "mass_gev": 55.0, "confidence": 0.8, "abstain": False}
return {"model": "none", "confidence": 0.8}
return {"abstain": True, "confidence": 0.8}
```

`model` is required unless `abstain` is true. `mass_gev` must be finite and within
the supplied bounds for a positive model; it is ignored for `none`/abstention.
`abstain` defaults to false and must be boolean. `confidence` defaults to 1, is a
finite number in [0,1], and is confidence in the submitted *model decision*, not
the exact point mass. A wrong law is a false discovery; a mass error is tracked in
continuous mechanism recovery rather than silently redefined as a wrong law.

## Scoring and limitations

For a supported signal, choosing the correct law earns
`max(0, 1-abs(log(m_hat/m_true))/0.25)`; wrong law, null or refusal earns zero.
Correct `none` on null worlds and refusal on outside-family worlds each earn 1;
wrong answers and malformed worlds earn zero. The hidden development mixture has
20 signal, 4 null and 4 outside-family worlds, with blanket-refusal and blanket-null
utility 1/7. The selection metric is `max(0, (mean_utility-1/7)/(6/7))`. A perfect oracle scores 1; an all-abstain, all-none
or shipped baseline scores exactly 0. No noisy reference witness defines the ceiling.

The false-discovery rate uses **false positive model claims / all positive model
claims** (zero with no claims); counts and denominator accompany it. Correct refusal,
supported-world claim coverage, null correctness, confidence Brier error and heldout
recovery are separate evaluator-only diagnostics. Only development selection and
validity/feasibility reach search; no heldout rows or axes enter the feedback prompt.
Invalid worlds do not receive correct-refusal credit.

For each split, diagnostics expose `false_discovery_count / claim_count`,
`correct_refusal_count / refusal_world_count`, and
`supported_claim_count / supported_world_count`. Null correctness is
`none_correct_count / none_world_count`; validity is
`valid_world_count / world_count`, and mean exposure is
`experiment_units_sum / world_count`. These aggregates and the confidence Brier
mean are evaluator-only. Brier correctness concerns the law/null/refusal decision;
it does not treat a correct law with an inaccurate mass as a false discovery.

Finite observations may leave mass/halo degeneracy; estimation uncertainty and
adaptive exposure allocation are real limitations. Seeds are repository-visible:
this candidate package is not a server-held contamination-resistant challenge.
Expert difficulty and budget-dependent improvement remain unmeasured until model
calibration; do not call this a solution to an open cosmology problem.

## Measured construction checks

Builder checks compare full inference with reduced observations, restricted nuisance
models, constant-parameter decisions and single-target strategies; reviewer evidence
records the measurements and remaining limitations. These checks do not constitute
independent frontier-model calibration.

## 关系与区别 / nearest neighbours

- `Gravitation/PTAHellingsDowns`: paid observations, mechanism decisions and refusal;
  here continuous particle-mass recovery and nuclear-target energy spectra replace
  angular correlations between pulsar pairs.
- `ParticlePhysics/LookElsewhereAnomaly`: one scanned peak and global significance;
  here an entire shared physical spectrum across three targets and nuisance controls.
- `ParticlePhysics/DiscrepantMeasurements`: published estimates and discrepancy;
  here actively obtained counts and a nonlinear physical law.
- `Exoplanets/TransmissionSpectrumSpecies`: absorption species selection; here
  nuclear target dependence, halo nuisance and elastic recoil kinematics.
- `Physics/HiddenCouplingNetwork`: graph recovery, not multi-target recoil inference.

The construction/ablation and shortcut results are summarized in
`references/known_best.md` for reviewers; that file is not candidate-visible.
Only edit `solution.py`; deterministic CPU NumPy/SciPy, no network, processes or hidden
file reads. `sle.contract_lint` is a free optional shape utility, not a scoring oracle.

## Validation status

The public detector grid is shared across worlds. Source-bound construction checks
and their limitations are recorded in the review-only `references/known_best.md`.
Independent first-proposal calibration remains pending; the historical failed
calibration is retained. This task has not established frontier-model difficulty.
