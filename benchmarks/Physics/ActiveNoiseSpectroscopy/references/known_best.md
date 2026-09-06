# ActiveNoiseSpectroscopy — measured construction evidence

All measured numbers below come from the task-local evaluator on the construction worktree. They
are design evidence, not clean-revision certification, device evidence, or a frontier-model
calibration.

## 1. Scientific anchors

Sung et al. (Nature Communications 10, 3715, 2019; DOI
`10.1038/s41467-019-11699-4`, arXiv `1903.01043`) experimentally reconstructed both the PSD and
bispectrum of engineered non-Gaussian dephasing noise. Their filter-function equations separate
the decay controlled by the second cumulant from the phase controlled at leading order by the
third cumulant. Norris, Paz-Silva and Viola (PRL 116, 150503, 2016; DOI
`10.1103/PhysRevLett.116.150503`) provide the non-Gaussian qubit-noise spectroscopy foundation.

This task uses an exact stationary random-telegraph process rather than truncating a cumulant
series. The Gaussian comparison is constructed to share its complete two-point correlation and
Lorentzian PSD.

## 2. Baseline and reference

| policy | dev score | heldout score | dev heldout-prediction | dev FDR | dev unsupported FPR | dev correct refusal | dev unwarranted refusal | shots/world |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no-measurement generic claim baseline | 0.0000 | 0.0000 | 0.3678 | 0.5000 | 1.0000 | 0.0000 | 0.0000 | 0 |
| always abstain | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 | 0 |
| one longest-Ramsey phase + generic parameters | 0.3933 | 0.3699 | 0.3664 | 0.0000 | 0.0000 | 1.0000 | 0.2500 | 12000 |
| shipped six-filter reference | 0.9406 | 0.8823 | 0.8848 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 23400 |

The reference is a strong reproducible witness, not a known optimum. It uses three fixed starts in
a bounded nonlinear least-squares fit. Better shot allocation, likelihood fitting of binomial
counts, adaptive Fisher-information design, and joint model selection all remain available.

## 3. Capability ablations

The no-measurement baseline shows that remembering a plausible noise model is worth zero. The
one-phase policy spends half the budget and cleanly finds the asymmetric sources, but misses every
symmetric supported source and its parameter guesses predict sealed controls poorly. Adding
multiple Ramsey durations identifies the decay envelope; balanced and offset echoes separate rate,
variance and occupancy; comparing one-fluctuator and Gaussian fits recovers the symmetric source.

The build also tested reduced shot allocations. Their single fixed binomial realizations are not
monotone in shot count, so they are not presented as a calibrated learning curve. Multi-seed shot
replication is required before making a quantitative budget-scaling claim.

## 4. Shortcut probes

- **PSD only:** structurally incapable of distinguishing the paired Gaussian and telegraph worlds,
  because their covariance and Lorentzian PSD are identical by construction.
- **Any nonzero phase means non-Gaussian:** catches biased single fluctuators but misses the
  symmetric supported fluctuator; the measured one-control implementation scores 0.3933.
- **Always claim:** pays one precision-weighted unit for every unsupported structural claim; the
  shipped generic baseline is clipped to zero and has unsupported FPR 1.
- **Always refuse:** correct on every null/misspecified/ambiguous world but has zero supported
  coverage and therefore scores exactly zero.
- **Correct label, generic parameters:** receives only continuous parameter recovery and low sealed
  prediction; heldout controls are not returned to candidate code.

No frontier model has seen the task. These probes establish failure of obvious low-dimensional
rules, not doctoral difficulty or long-horizon headroom.

## 5. Identifiability and refusal

All eight development and seven heldout worlds are fixed before any model calibration. Every
supported world has a complex-response Jacobian of rank three for rate, variance and occupancy.
On development worlds, the exact maximum full-budget KL divergences against the same-rate,
same-variance Gaussian over the complete legal control panel are approximately
`155.7, 763.3, 96.8, 738.2` for the four supported sources. Their best free-rate/free-variance
Gaussian complex-response RMSEs are `0.0450, 0.0957, 0.0365, 0.0705`; the supported screen requires
at least `0.02`. The weak single-source refusal world has matched-Gaussian KL approximately
`0.0047`, so Pinsker bounds total-experiment variation distance by
`sqrt(KL/2) < 0.049`; the existence of this close Gaussian alternative is enough to withhold the
single-fluctuator claim. Its local
Jacobian remains rank three but is poorly conditioned, illustrating why family separation and
parameter identifiability are not the same claim.

The finite design panel is the entire legal experiment space, so the matched-alternative KL bound
is exhaustive for this candidate task, including adaptive allocations. Conversely, large KL to
the same-parameter Gaussian does not prove separation from every nuisance-parameter Gaussian; the
profiled residual is a construction screen, not a global identifiability theorem. Neither check is
a claim about arbitrary continuous controls or a real device.

## 6. Determinism, security and robustness

The evaluator uses only fixed-size analytic/linear-algebra operations. Gaussian coherence has an
independent direct-covariance quadrature check. Shot streams are keyed by world, exact control and
quadrature and consumed sequentially: `N` shots in one call equal the sum of legal chunks totaling
`N`. Overspend, invalid duration, unordered or crowded pulses, noninteger shots, malformed output,
nonfinite parameters, and a raising callable all fail closed without escaping `evaluate`.

## 7. Remaining gates

1. Independent quantum-control/noise-spectroscopy review of conventions, parameter ranges and the
   finite-panel KL ambiguity gate.
2. Independent finite-pulse or stochastic-trajectory oracle comparison.
3. Clean Linux sandbox replay and repository-wide contribution checks after registry integration.
4. Frozen HY3 and additional-model calibration with multiple model and shot-noise seeds.
5. Server-held procedural worlds before any hardness, contamination-resistance, or device-science
   claim.
