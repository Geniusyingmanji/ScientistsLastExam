# Reference and admission record — ActiveFullWaveformInversion

## 1. Reference method and scope

The reference fits a smooth velocity correction using only public physics and paid
shots at 9/15/21. This central aperture was selected on development diagnostics;
heldout and confirmation scores did not select it. Explicit source subsets in the
budget audit are used unchanged. Coarse-to-fine fitting, minimum-change/spatial regularization and late trace
balancing remain in place. Exact discrete derivatives are the default; a numerical finite-difference comparison
is available in the audit. They are an implementation choice:
finite differences should converge to the same solution. They are not an additional
scientific capability and their use alone does not establish difficulty.
The old global-energy refusal gate was removed: supported velocity changes can also
change signal energy. Near-null detection and post-fit model adequacy remain separate.

## 2. World and scoring revision

The September 10 review found a continuous Gaussian probe above the old reference.
The new truth family is a smooth random Fourier field, independent of both the
Gaussian probe's shape family and the reference interpolation grid. It covers the
whole depth range. Acquired and sealed records extend from 210 to 300 samples to
observe later arrivals. Both splits contain ten supported worlds with disjoint
seeds, followed by three unsupported controls with separately seeded noise.

The unsupported reasons are unresolved near-null structure, incorrect source timing,
and attenuation over heterogeneous structure. Every regime varies with seed. Near-null
means spatial variation below the **joint** noise scale, not merely below each
sample’s noise. A regression bounds the noise-normalized squared waveform
separation for any three-shot sequence, including repeats, below 0.001 on the
shipped and predeclared confirmation nulls. The null remains a common negative
control; its independent noise draws are not new geological-transfer evidence.
Only the source-timing and attenuation controls test new non-null misspecification. Source delay is
an interpolated delayed source response, whereas attenuation acts inside the wave
recurrence. These are distinct physical departures; whether a candidate separates
their causes is not established merely by counting its correct refusals.

The structural and sealed-waveform formulas are unchanged. In particular deep cells
already participated in the metric: the repair puts genuine signal there instead of
claiming a new weighting fixed an old omission. The baseline and all-refusal scores
must remain exactly zero. The expanded instance distribution changes historical
score comparability; no old score is relabelled as a result on the new oracle.

## 3. Reference and acquisition measurements

Clean Linux measurements on the revised world family:

| Acquisition policy | Development | Heldout |
|---|---:|---:|
| Best single on development: 15 | 0.512128 | 0.391881 |
| Best pair on development: 9/21 | 0.620585 | 0.469126 |
| Final fixed triple: 9/15/21 | 0.664800 | 0.551567 |
| Previous fixed triple: 3/15/28 | 0.546014 | 0.535452 |

All five single shots and all ten pairs were evaluated. The heldout maxima across
those sweeps are 0.467643 (single 9) and 0.502308 (pair 21/28); these are disclosed
as post-hoc diagnostics, not used to select the reference. The third-shot gain over
the development-selected pair is 0.044215 development / 0.082441 heldout. This is
a point comparison of fixed acquisition policies, not proof of a universal budget
advantage or an optimal adaptive policy.

The final reference correctly refuses all three unsupported worlds in each split,
with supported coverage 1.0 / 0.9. Remaining headroom comes from imperfect spatial
reconstruction and one supported heldout refusal. Its fixed interpolation grids,
regularization and source plan leave opportunities for better inversion; exact
derivatives alone are not an explanation of that headroom.

## 4. Continuous shortcut families

`.research/pr20_fwi_continuous_probe.py` is an independent implementation with its
own checked propagator and numerical finite differences. It fits one or three blobs,
then five with a noise discrepancy stop, then five with the additional depth cap.
Every stage starts from a 240-point spatial/amplitude grid. No evaluator/reference
imports, seed lookup or reference-spline coefficients enter the probe.

The old maintainer measurements were **0.820084/0.561552**, against the old
reference **0.714101/0.660180**. The previously published 58.7%/55.0% ratios were
only measurements of an incomplete family, not bounds. Existing 0.15 margin and
70% ratio guards are retained and extended to continuous fitting on both splits.
Exact maintainer source remains unavailable; the new probe is a reconstruction of
its described methods, not a claim of exact-source replay. The continuous probes
use the fixed outer aperture 3/15/28. The exhaustive source sweep applies to the
reference inversion, not every probe/source combination. These finite families
therefore establish measured regression guards, not an upper bound on all
continuous fitting, joint multi-blob optimization or adaptive acquisition.

Each family sweeps 50 final-fit refusal thresholds from 0.02 to 1.00. Fitting is
cached only for threshold postprocessing, followed by an uncached full replay at
the development-selected threshold:

| Continuous family | Selected threshold | Development | Heldout | Maximum heldout across sweep |
|---|---:|---:|---:|---:|
| One Gaussian | 0.32 | 0.020892 | 0.009515 | 0.009515 |
| Three Gaussians | 0.18 | 0.044213 | 0.035202 | 0.056006 |
| Five with noise stop | 0.24 | 0.051192 | 0.000000 | 0.045501 |
| Five with noise stop and depth cap | 0.22 | 0.136683 | 0.059821 | 0.059821 |

Even the post-hoc maxima over all 200 tested policies retain the existing 0.15
absolute margin and 70% ratio guards on both splits. The strongest measured
ratios are 20.56% development / 10.85% heldout; they describe this finite sweep,
not a universal upper bound. The original default-threshold measurements, including
zero scores, are retained in the raw evidence rather than substituted for this
stronger test.

## 5. Sampling uncertainty and confirmation

The audit reports stratified world-bootstrap intervals (20,000 draws) and supported
world standard errors. The final reference has development 95% interval
[0.586477, 0.733683] (supported standard error 0.039673) and heldout interval
[0.353602, 0.714032] (standard error 0.097611).

On the predeclared separate seeds, the unchanged central reference scores
**0.459468 / 0.538004**, with intervals [0.253282, 0.651284] /
[0.339053, 0.708603]. The default depth-capped continuous probe scores **0 / 0**;
this confirmation did not sweep its refusal thresholds. The lower development
score is retained as evidence of sample variation, without seed or solver retuning. The sample remains small and procedural; intervals are not
claims about independent geology. `--fresh` uses predeclared separate seeds, without
choosing them based on scores. Model calibration and external domain review remain
pending. These diagnostics do not certify the task.

## 6. Construction errors and history

A self-check found that the first near-null amplitude was below pointwise noise
but detectable by aggregating traces (best-three squared separation about 3435
and 3270). It was reduced before the two final same-source sandbox confirmations. The near-null is explicitly
a shared negative control, rather than using tiny seed differences to claim
independent geological worlds.

The first September 11 exploratory redesign used curved layers. It failed: the
reference development score was about 0.209, while a continuous depth-capped probe
scored about 0.358. It was rejected rather than reported as successful hardening.
Interpolation-grid texture experiments also produced unstable recovery. A batched
central-difference implementation was rejected because its full evaluation was
slower than the existing tangent implementation; it did not change the physics. The random
Fourier family was selected using development diagnostics, before confirmation;
this is builder development, not independent validation.

The September 10 review also showed that removing exact derivatives preserved score,
and that the best one/two-shot scores were 0.575212/0.691962 on the old oracle.
Those corrections supersede the earlier causal and acquisition claims. Full prior
history is retained in `known_best_pre_revision_2026-09-10.md`; all September 9 JSON
reports concern that archived oracle. Historical Linux command arrays mention Focal
because it was present before the PR split; no Focal task remains in this package.

## 7. Reproduction and evidence

```sh
OPENBLAS_NUM_THREADS=1 python scripts/audit_fwi_revision.py --output /tmp/fwi-review.json
OPENBLAS_NUM_THREADS=1 python scripts/audit_fwi_revision.py --methods reference finite_difference --budget-sweep --output /tmp/fwi-budget.json
OPENBLAS_NUM_THREADS=1 python scripts/audit_fwi_revision.py --fresh --methods reference gaussian_depth --output /tmp/fwi-fresh.json
for family in one three stop depth; do
  OPENBLAS_NUM_THREADS=1 python scripts/audit_fwi_thresholds.py --family "$family" --output "/tmp/fwi-threshold-$family.json"
done
python scripts/audit_fwi_null_compatibility.py --output /tmp/fwi-null-compatibility.json
python -m pytest tests/test_fwi_discrete_inversion.py tests/test_new_earth_science_tasks.py tests/test_pr9_earth_hardening.py tests/test_pr9_earth_contracts.py tests/test_earth_pr_review_regressions.py -q
```

The expanded 26-world evaluation exceeded the former 600-second cap in the Linux
method audit (700 seconds for the preceding fixed triple under concurrent load).
The wrapper and card now permit 1200 seconds; metadata gives a 900-second wall-time
estimate, not a second timeout. Two final same-source real Linux sandbox runs took
618.68 and 607.13 seconds under concurrent diagnostic load, with exactly identical
full metrics and valid=1. The final evaluator/reference/wrapper hashes are recorded
in `review_revision_2026-09-11.json`. The higher compute cost is a limitation of this
revision, not evidence of greater scientific difficulty.

The evidence JSON includes complete per-world scores, all source subsets, threshold
sweeps and uncached replays. Original runs retain their original revisions. The
first source/probe runs preceded the central-aperture choice and the near-null
correction; explicit subsets are unchanged, and the included 124 full-row
compatibility checks prove that the near-null correction leaves all recorded
policies unchanged, including confirmation controls. Earlier records are not
relabeled as final-head evaluations.

Validation completed in stages: 44 FWI tests; 14 final numerical/null/source checks;
102 Linux integration tests with eight subtests; contribution gate 15/15. A separate
Linux run of the repository tests excluding the five FWI files passed 1175 tests
and 508 subtests, with 50 skips. These staged runs are not presented as a single
final-head full-suite run; GitHub CI is the final-head integration check.

Publishable measurements require a clean Linux checkout and real sandbox replay.
Diagnostic reports retain source hashes, revision, dirty state, dependencies and
per-world failures. Global frozen evidence is maintained separately by maintainers.
Virieux & Operto (2009), DOI `10.1190/1.3238367`, supports the FWI methodology;
Symes (2020), arXiv `2003.14181`, is methodological background. Neither publication
claims performance on this synthetic world family.
