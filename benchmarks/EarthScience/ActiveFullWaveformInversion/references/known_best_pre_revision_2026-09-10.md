> Archived pre-revision record. All references to current results below concern the old Gaussian-world oracle, not the September 11 revision.

# Reference and admission record — ActiveFullWaveformInversion

## 1. Reference method

The reference uses only public inputs and three paid shots at sources 3/15/28.
It fits a general smooth velocity correction, without assuming an anomaly count,
shape, location or sign. An exact tangent-linear derivative of the public discrete
wave recurrence replaces finite differences. Batched sensitivities support
trust-region least squares on 3x5, 5x8 and 7x11 cubic-interpolated grids. Spatial
first differences and a minimum-change prior control unsupported extrapolation;
the final stage balances receiver traces with a stated-noise floor after coarse
smoothed fits establish the arrival alignment. Its optimizer cache is local to
one stage and never crosses worlds.

Directional derivatives, including source/boundary perturbations, are checked
against an independently implemented oracle. Forward arrays also agree with the
oracle. Exploratory adjoint/L-BFGS, curvature-only regularization, finer grids
alone and early trace balancing regressed on development and were rejected.
The adopted implementation uses tangent sensitivities, not the rejected adjoint
optimizer. This is conventional regularized inversion, not a new physical law.

## 2. Scoring, noise independence and baseline

The score formula and velocity fields were not altered to improve the method.
The solver-only comparison was first made on a byte-identical oracle, with a
source freeze before additional-world confirmation. That oracle and previous
solver are preserved in `.research/pr20_fwi_evaluator_before_noise.py` and
`.research/pr20_fwi_reference_before.py`; `solver_confirmation_2026-09-09.json`
is the historical, pre-noise-fix report.

The subsequent review correction uses SeedSequence(seed, source, paid-call count,
world-kind tag) for independent deterministic noise streams. Paired supported and
structured-attenuation controls still share velocity, but no longer share normal
noise draws. A regression checks independent standardized noise and exact replay.
Because noise realizations changed, current numbers below were remeasured for
both references. They must not be mixed with the archived oracle's measurements.

The confident-background baseline remains exactly zero, as does always refusing.
Structural skill remains max(0, (exp(-1.5*r)-exp(-1.5))/(1-exp(-1.5))) for weighted
background-relative velocity error r. Sealed-waveform scoring, geometric mean and
normalization above always refusing are unchanged. Existing test bounds were not
lowered. The FWI wrapper now allows 600 seconds as requested; the paid budget is
still three shots. The timeout change is separate from scientific scoring.

## 3. Current reference, ablation and physical recovery

Current local results use Python 3.11, NumPy 1.24.4 and SciPy 1.10.1, matching the
CI library pins and the package's NumPy<2 constraint. These are macOS measurements;
Linux sandbox confirmation is recorded separately below.

| Method | Development | Held-out |
|---|---:|---:|
| Previous reference on current noise | 0.431671 | 0.299460 |
| Revised reference, one paid shot | 0.341045 | 0.448163 |
| Revised reference, three paid shots | 0.714101 | 0.660180 |

Both revised variants refuse all original unsupported worlds. One shot retains
source 3 with the same solver/stopping/regularization; three shots use 3/15/28.
This is an acquisition ablation, not an equal-computation comparison.

On the same current noise, mean velocity RMSE over all four development supported
worlds falls from **166.036 to 79.563 m/s**, and over all three held-out supported
worlds from **197.545 to 55.903 m/s**. Development structure skill increases from
0.226168 to 0.523095; waveform skill from 0.960312 to 0.985968. The gain therefore
includes improved latent structure, not just classification or waveform fitting.
Per-world failures and regressions are retained in the comparison report.

## 4. Low-dimensional spatial probes

The maintainer reported 0.359309/0.295580 for its 240-point spatial template and
0.259353/0.324567 after local refinement. Exact probe source and grid coordinates
were not supplied. `.research/pr20_fwi_spatial_probe.py` independently reconstructs
this family, with every grid coordinate explicit; it is not an exact-source replay.
Its forward solver is independently checked against the oracle.

| Probe on current noise | Development | Held-out |
|---|---:|---:|
| Background plus old central-shot classifier | 0.000000 | 0.000000 |
| Fixed-position lens, 19 amplitudes | 0.140991 | 0.238192 |
| Travel-time-only update | 0.000000 | 0.027797 |
| Spatial x/depth/amplitude search, 240 points | 0.042933 | 0.265730 |
| Spatial search + 243 width/position/amplitude refinements | 0.419285 | 0.362910 |
| Greedy two Gaussian anomalies, 2x240 searches | 0.410611 | 0.140848 |
| Greedy three anomalies, 3x240 searches | 0.184909 | 0.205779 |
| Revised reference | 0.714101 | 0.660180 |

The refined probe still exceeds the **old** witness's held-out score, so this is
not a weak comparator. It reaches 58.7%/55.0% of the revised reference. The tests
cover coarse, strict-gate, refined and greedy multi-anomaly variants on both
splits, requiring a margin of 0.15 and ratio below 70%. These are explicit local
regressions, not unilateral approval of the repository's admission policy.
The coarse and three-anomaly probes make a false discovery on development.
A better waveform fit can also erase residual-based refusal, an observed risk.

## 5. Additional worlds and calibration limits

The method was selected on original development worlds, then source-frozen before
12 predeclared additional supported worlds and five unsupported controls. The
list is in `.research/pr20_fwi_validation_plan.md`. The solver was not retuned
using their outcomes. The same list has now been remeasured on independent noise
under the CI library pins: previous reference **0.137516**, revised **0.459219**.
Both refuse all five unsupported controls. Revised supported coverage is **8/12**,
versus **7/12** previously. On the seven worlds both reconstruct, mean RMSE falls
from **211.679 to 77.545 m/s**. The paired denominator avoids selection bias from
changing coverage.

Four supported worlds remain refused. One is nearly indistinguishable from the
background at the acquired traces, one triggers the retained energy gate, and two
fail the final fit gate. These are failures under the current supported labels,
not claimed successful model-inadequacy refusals. Depth recovery remains limited.
The extra worlds are from the same procedural family, not independent geology or
secure server-held evidence. No frontier-model calibration or certification is
claimed. Levels 2/3 are diagnostic only, consistently in Task.md and the card.

## 6. Construction history and review follow-up

- September 9 review completion: independent noise streams; spatial/greedy probes;
  CI-pinned remeasurement; explicit diagnostic tiers; 600-second wrapper budget;
  taxonomy note; structured-attenuation certification description; source and task
  documentation reconciliation. The solver itself was not retuned in this step.
- Prior September 9 solver-only improvement: exact tangent Jacobian, regularized
  spatial field and late trace balancing; original-oracle/fresh-world evidence
  retained in `solver_confirmation_2026-09-09.json`.
- Earlier September 9 oracle revision: removed the positive background floor,
  added structured attenuation and measured one versus three paid shots.
- September 8: trusted runner delegation, confidence/coverage contract fixes and
  public forward-model disclosure.
- September 7: a fixed-lens shortcut beat the single-pass 3x5 witness; continuation
  replaced it. Its old 0.615339/0.427110 scores precede the score/world revision.

The old Linux report `method_diagnostics_2026-09-09.json` validates only the prior
solver/oracle. The 0.709144/0.675359 solver-only scores also refer to the pre-noise
oracle and a different local dependency version; they are not current results.

The citation arXiv:2003.14181 was checked on 2026-09-09 against its authoritative
record: William W. Symes, *Wavefield Reconstruction Inversion: an example* (2020),
https://arxiv.org/abs/2003.14181 . It is methodological background, not a published
performance claim for this synthetic benchmark. The maintainer confirmed the
available Frontier-Eng catalog scope on September 8; domain acceptance is pending.

## 7. Reproduction and evidence

`review_method_diagnostics_2026-09-09.json` records every current probe, source hash,
platform, per-world score and runtime. `review_confirmation_2026-09-09.json`
records paired physical errors and additional-world results on current noise.
The full local reference takes about 29.27 seconds and one shot 18.10 seconds
in that run; local timings do not predict Linux sandbox load. The cap is 600.

Real Linux sandbox validation at clean revision `05d15d2` used Python 3.12.3,
NumPy 1.26.4 and SciPy 1.13.1. Two full reference runs produced identical complete
metrics: 0.714100702 development / 0.660180262 held out, in 89.32 / 89.53 seconds.
The full contribution gate passed all 15 checks, including baseline execution,
deterministic replay and malformed candidates. The combined task/framework suite
passed 204 tests and 40 subtests with no skips; the clean audit covered 85 tasks.
`linux_validation_2026-09-09.json` includes source hashes, both metric dictionaries,
gate results and reproduction commands. Existing administrator permission was used
for namespace setup; the original candidate sandbox and host security settings
were unchanged. This contributor run does not substitute for GitHub CI approval
or independent domain review.

```sh
OPENBLAS_NUM_THREADS=1 python .research/pr20_fwi_diagnostics.py --output /tmp/fwi-methods.json
OPENBLAS_NUM_THREADS=1 python .research/pr20_fwi_confirmation.py --oracle current \
  --split fresh --methods old new --output /tmp/fwi-current-confirmation.json
OPENBLAS_NUM_THREADS=1 python .research/pr20_fwi_confirmation.py --oracle frozen \
  --split heldout --methods old new --output /tmp/fwi-archived-comparison.json
python -m pytest tests/test_fwi_discrete_inversion.py tests/test_new_earth_science_tasks.py \
  tests/test_pr9_earth_hardening.py tests/test_pr9_earth_contracts.py \
  tests/test_earth_pr_review_regressions.py -q
```

The task remains a candidate. Source publication, CI, real sandbox replay and
maintainer acceptance are separate from these local scientific comparisons.
