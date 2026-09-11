> Shared-grid revision, 2026-09-11: all public problem values now match across
> worlds and splits. Earlier results below use the historical variable energy
> grid and are not current-source measurements. Latent parameter draw
> positions, class/mass coverage, scoring and budget are retained.
> The reference now uses a charged pilot and local Fisher allocation; the
> historical equal-allocation reference remains separately executable.
> `revision_replay.json` fixes the new replay before evaluation. The old D16
> failure is preserved and cannot be cleared by these engineering measurements.

# DarkMatterRecoilAttribution: witness and construction record

## 1. Reference and sources

`verification/reference_profile.py` is the revised, truth-blind Poisson-deviance
witness described in the shared-grid revision below. It reads only `problem` and charged observations. Three mass starts jointly
profile the speed weights, coupling ratio, target backgrounds and calibration gains;
null, residual and law-separation checks allow refusal. It is not a published record.
Score 1 follows from exact parameters and correct decisions, not a reference literal.

[Cherry et al., arXiv:1405.1420](https://arxiv.org/abs/1405.1420) motivates common
velocity structure and target-dependent kinematics for momentum-dependent scattering.
The three unboosted Maxwell components, Gaussian form factor and midpoint detector
model are our explicit approximations. An independent numerical quadrature of the
normalized Maxwell speed density checks the inverse-speed kernel in the task tests.
No LZ likelihood or experimental data is copied; [LZ v3](https://arxiv.org/abs/2410.17036v3)
is not the simulator's ground truth and does not define its normalization.

The revised outside-family construction uses the same allowed kernel at each target,
but target masses are separated around a log-mass interval. A single target has an
exact supported-world twin, including its sampled counts and controls. This is a
synthetic joint-consistency test, not a claim that real particles have target-dependent
mass. Tests check those twins at all three targets, including full-budget acquisition.

## 2. Baseline

The legal baseline buys one xenon unit then asserts a 10 GeV contact signal. All
supported masses are at least 22 GeV, so it receives no parameter credit. Incorrect
positive claims on null/outside-family worlds also receive none.

Each split now contains 20 supported, 4 null and 4 outside-family worlds. Blanket
`none` and blanket `abstain` each have mean utility 1/7. Normalization is
`max(0, (mean_utility - 1/7)/(6/7))`; both blanket strategies and the baseline score
exactly zero, while a perfect oracle scores 1. Perfectly distinguishing only null and
refusal can still earn 1/6. This limited non-discovery credit is explicit; coverage
and claim denominators are reported separately. Heldout remains diagnostic only.

## 3. Ablation ladder

Run on Linux with Bubblewrap:

```bash
OPENBLAS_NUM_THREADS=1 python3 scripts/audit_dark_matter_recoil.py \
  --output experiments/dark_matter_recoil_revision_2026-09-10.json
```

The audit evaluates the baseline and unchanged reference twice in the real sandbox,
and each reference ablation through the same boundary. `one_unit` buys one rather
than four units per target; `ignore_gain` fixes gain to unity; `fixed_halo` constrains
all three speed amplitudes to be equal. Scores can vary slightly with SciPy version:
the original audit and external review differed by about 2e-4 on one ablation.

Linux sandbox measurements at clean source commit `fcddf932` (Python 3.12.3,
NumPy 1.26.4, SciPy 1.13.1), recorded with full precision and provenance in
`experiments/dark_matter_recoil_revision_2026-09-10.json`:

| Strategy | Development | Heldout | Development loss vs reference |
|---|---:|---:|---:|
| baseline | 0.000000 | 0.000000 | 0.548485 |
| reference | 0.548485 | 0.499983 | 0.000000 |
| one_unit | 0.366034 | 0.235572 | 0.182450 |
| ignore_gain | 0.341713 | 0.223420 | 0.206771 |
| fixed_halo | 0.438222 | 0.540079 | 0.110262 |

The fixed-halo restriction improves heldout by 0.040096. This can reflect finite-data
regularization and mass/halo degeneracy; it does not support a claim that free halo
fitting is always necessary. No seed was selected to make every ablation lose on
heldout. The reference refuses all four development outside-family worlds, but only
three of four heldout ones; heldout false-discovery rate is 1/21. These are small
synthetic samples, not population guarantees or calibrated discovery significance.

Baseline runs took 9.94 / 9.73 seconds; reference runs took 36.12 / 36.07 seconds,
12.0% of the 300-second runner timeout. Each pair's complete metrics JSON was
identical. The outer `frontier_eval/run_eval.py` also returned the same reference
score and valid=1; a nonexistent candidate retained its failure diagnostic.

Local CI-pinned NumPy 1.24.4 / SciPy 1.10.1 gave reference 0.548432 / 0.499973;
the largest ablation discrepancy was 0.000623 on ignored-gain heldout. This is
cross-version numerical sensitivity, not within-version nondeterminism. The tests
assert scientific separation and invariants rather than those score literals.

## 4. Shortcut probe

The completed probe has all four decisions: `none`, `contact`, `q2`, `abstain`.
It scans every target with 1, 3 and 12 units, excess and hardness thresholds,
48 constant masses, and two versions of a three-bin narrow-peak residual (Poisson
standardized and fractional). The infinite peak threshold includes the old no-refusal
family. In total it evaluates 233,280 configurations using cached observations.
Selection uses development only; the selected candidate is evaluated once on heldout.
The vectorized selection result is checked against the actual public-input candidate
callback. This is a finite builder search, not an exhaustive algorithmic upper bound.

| Probe | Development | Heldout | Interpretation |
|---|---:|---:|---|
| Best four-way single-target strategy | 0.249535 | 0.130670 | development-selected once |
| Any constant mass, perfect law/null/refusal decisions | 0.296772 | 0.294044 | exact per-split upper bound |

The legal selected strategy uses one germanium unit; its configuration is recorded
in the JSON report. It reaches 45.5% of reference on development. The constant-mass
bounds are stronger than the reviewer's attack: every classification is granted
correct, including negative worlds. They reach 54.1% / 58.8% of reference. These are
builder oracle-assisted bounds, **not** legal zero-query candidates.

The constant bound covers the entire legal interval [10,250], not a discrete mass
sweep: utility is piecewise linear in log mass, so testing every true mass, its
±0.25 log-radius breakpoints and legal endpoints finds the exact maximum.

Regression tests and the audit fail unless that bound is at most 0.6 times reference
on both splits. The selected four-way strategy must stay below 0.7 times reference
and at least 0.15 below it on both splits. The test calls the same full probe as the
evidence audit, rather than a hand-picked weaker member of its family.

Historical evidence is retained in `experiments/dark_matter_recoil_2026-09-10.json`.
The original 480-strategy audit omitted refusal, so its reported 0.380949 maximum was
not the four-way family's maximum. The external reviewer found 0.507354 against
reference 0.523729; using reference decisions and constant mass 57.8 yielded 0.657182.
Run `.research/pr72_review_reproduction.py` to remeasure original commit `a222b592`
with the completed probe and exact constant bounds. Our expanded family also finds
a legal full-budget xenon shortcut scoring 0.644077 on the original development set;
its development-selected heldout score is only 0.084405. It labels oracle-assisted bounds
separately from legal candidates and records source hashes and environment versions.

### Fixed-probe machine contract (2026-09-11 integration)

`TASK_CARD.yaml::shortcut_probe` executes the unchanged reference and two fixed
single-file candidates through the current sandbox. `shortcut_fixed_mass.py` is
the complete reference with only the final positive mass replaced by 57.8, a
faithful derivative of the disclosed reviewer strategy; the original reviewer
single-file bytes are unavailable. `shortcut_four_way.py` preserves the author's
`peak_features` and `probe_answer` function source and the previously
development-selected configuration `[1, 1, 60, 2, 95.83680934806682, 1, 0.5]`.
Neither candidate imports the oracle, reads repository data, or searches parameters.
The fixed-mass derivative still performs the full reference fit and is an ability
ablation, not a cheap-compute shortcut.

The declarations come from eight independent fixed sandbox replays at task head
`8497bd455d3090087e6a15e99fb85f5fae75e5cd`, runtime
`2660c38a413fb7281d0e7012a6446eb384a934d1`, Python 3.8.10,
NumPy 1.24.4 and SciPy 1.10.1 with BLAS/OMP threads fixed to one. Full metrics were
identical within each pair, and all 448 world records were valid. See
`references/shortcut_replay_provenance.json` for original candidate hashes,
source segments, score/count aggregates and private-original hashes; the full
independent report is on branch `codex/sle-shortcut-revalidation` at
`.research/pr72_shortcut_review_2026-09-11.{md,json}`.

| Fixed candidate | Development | Heldout |
|---|---:|---:|
| reference | 0.5486397428 | 0.5000127063 |
| reference decisions, mass 57.8 | 0.2903389817 | 0.2439422043 |
| previously selected four-way probe | 0.2495350510 | 0.1306702190 |

The machine guard retains the previously declared 30% relative separation on the
development selection score, with absolute numerical matching tolerance 1e-6.
These declarations are specific to the pinned environment; the differing historical
scores above are not interchangeable. The guard does not re-run the grid, establish
its current optimum, or replace the exact constant-mass bound or model calibration.
The current integration changes the wrapper, documents the contract and adds
aggregate numerators/denominators; world generation, scores, reference and fixed
candidate bytes remain unchanged. Its complete metric payload therefore differs
from the historical replay even if all shared scalar scores match. Fresh current
contribution checks must be recorded separately, not relabelled as the historical run.

## 5. Frontier draw

The 2026-09-11 fixed campaign ran three independent first proposals from
`gpt-5.6-sol`, reasoning `high`, maximum output 16384 tokens, selection-blind
budget 1, evaluator timeout 300 seconds. Seed labels 0/1/2 identify replicates,
not controlled provider randomness. The clean source was `9516d4b0fc9ddcb6d2853ee7a39448fc851e549b`,
task package `07665fb4eb5481af5296db7edbcfb67dc4a0321db01ef472048f1988f1a1784d`,
and runtime `8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`.
The source and complete method measurements were frozen before the plan/draws.

| Seed label | Development | Heldout | Valid worlds | Admission interpretation |
|---|---:|---:|---:|---|
| 0 | 0.5855425654 | 0.5953141420 | 56/56 | Exceeds the predeclared 0.5486397428 reference: D16 fails |
| 1 | unavailable | unavailable | 49/56 | Evaluation reached its timeout; partial results do not establish difficulty |
| 2 | 0.2802699453 | 0.3347217998 | 56/56 | Below reference in this single complete proposal |

The incomplete draw's raw development/heldout numbers were 0.5485267106 and
0.3092163689; they remain in the operator record and are not used as a complete
scientific score. Its incumbent stayed at the baseline, which must not be
reported as that model's first-proposal score. Total reported usage was 44696
tokens; price was unavailable. There were three baseline evaluations and three
proposal evaluations, with no adaptive retries, new candidate selection or
post-draw task changes. All three scheduled cells, including the incomplete one,
remain in the denominator.

See `experiments/dark_matter_recoil_first_draw_review_2026-09-11.json` and
`.research/pr72_admission_review_2026-09-11.md` for source bindings, independent
receipt/trajectory checks and private original-file hashes. That JSON is an
operator admission review, not a frozen benchmark cohort or certification.
These subsequent card/reference-note changes are documentation-only; no old
manifest or source hash was rewritten. The task remains `candidate` and is held
from merging because the first fully valid draw reaches its reference. No
long-horizon or independent external-domain conclusion is established.

## 6. Construction errors and corrections

- Earlier drafts conflated mass error with a false law discovery, omitted bin widths,
  and used plug-in gains. These were corrected before external review. Charged,
  counter-keyed sampling and sticky query failure were already present.
- PR 72 review exposed five of six development signal masses sharing one scoring
  window. The revision keeps both base seeds and the physical mass interval, expands
  to 20 signals per split, and partitions log mass into 20 paired strata with bounded
  within-stratum jitter. Each pair assigns one mass to each law at random. This
  prevents both aggregate clustering and a law-specific constant-mass advantage.
- An initial revision independently stratified the laws: its perfect-decision constant
  bound still reached 63.5% of heldout reference. Pairing the strata makes coverage a
  generator invariant instead of relying on two independently lucky draws. Both
  splits informed construction checks and must not be called fresh confirmation.
- The original unsupported worlds had obvious narrow peaks and the probe omitted
  refusal. Both defects are removed: every target marginal now belongs exactly to a
  supported kernel, while shared-mass consistency fails jointly; the probe includes
  refusal, all targets, and both sparse and full-budget single-target acquisitions.
- Changed mixture weights are derived from the actual class counts, including null
  correctness denominators. Blanket decisions and the oracle ceiling are rechecked.
- Candidate-visible reference/ablation/shortcut scores were removed from `Task.md`.
  PTAHellingsDowns is now named explicitly as a nearest neighbour, and copied neural
  test terms, dead branches, unused imports and single-element parametrizations are
  removed. The inventory uses the repository's half-width punctuation.

## 7. Robustness, contamination and remaining headroom

The two base seeds remain 731500 and 941700. Physical mass and law are not exposed
in public problems; controls and call budgets do not name the split. Processes and
private temporary filesystems reset between every world. The Linux regression tests
both Python globals and a `/tmp` marker through actual Bubblewrap.

All seeds are nevertheless repository-visible, and both splits were inspected during
construction. A real evaluation needs a server-held reissue and external domain
review. The exact constant bound and marginal-twin checks hold for the implemented
families; neither excludes arbitrary learned or multi-target shortcuts.

The unchanged reference uses equal allocation and point estimates. Adaptive target
allocation and treatment of mass/halo uncertainty remain possible improvements.
It does not attain perfect joint-family rejection on heldout; no artificial optimizer
failure or hidden-answer lookup was introduced to lower its score. The expanded
56-world campaign retains the 12-unit per-world budget and 300-second runner timeout;
metadata allows 120 seconds for evaluation, subject to measured hardware load.


## Shared-grid two-stage reference replay, 2026-09-11

At frozen source `8561acb7d6154f3831de18d7f0fcaf71b4443733`, all eight predeclared methods ran twice in the real Linux candidate sandbox. All 56 worlds were valid and complete metrics were identical within each pair. Environment: Python 3.12 / NumPy 1.26.4 / SciPy 1.13.1, one numerical thread. Full originals are private; aggregate scalars, source bindings and hashes are in `experiments/dark_matter_recoil_shared_grid_methods_2026-09-11.json`.

| Method | Development | Heldout | Units/world |
|---|---:|---:|---:|
| reference | 0.5368049832 | 0.5480087151 | 12 |
| fixed_mass | 0.2903389817 | 0.2439422043 | 12 |
| four_way | 0.2796988413 | 0.0890035523 | 1 |
| one_unit | 0.2974342757 | 0.2830546042 | 3 |
| ignore_gain | 0.2778624264 | 0.2578446537 | 12 |
| fixed_halo | 0.3574036313 | 0.5080162656 | 12 |
| equal_allocation | 0.5241998858 | 0.4243700582 | 12 |
| legacy_equal_reference | 0.5242741474 | 0.4243840652 | 12 |

All four declared ability removals lose on both splits. The equal-allocation development loss is only 0.012605, while its heldout loss is 0.123639; do not turn this finite constructed comparison into independent difficulty evidence.

The exact constant-mass bounds, determined by unchanged latent masses, are still 0.296772 / 0.294044, about 55.28% / 53.66% of the revised reference. Existing 60% constant-mass and 70% four-way regression requirements were preserved. Both splits have participated in construction; neither is fresh confirmation.

The subsequent development-only public-validity repair affects heldout-only malformed returns. It does not change any all-valid method result; its final-package contribution replay is recorded separately. The original failed first-draw campaign remains bound to its historical source and is not compared against this new reference as if it had been rerun. New independent, predeclared model calibration and external domain review remain necessary.

### Candidate-prompt boundary correction, 2026-09-12

The prior revision accidentally appended reference implementation instructions and
quantitative ablation results to `Task.md`, reintroducing the prompt disclosure
identified in the September 10 review. They are moved here verbatim. The forward
model, public keys, query protocol, score, constraints and executable candidates
are unchanged. Existing evaluation receipts retain their original source hashes;
a model draw must bind the corrected prompt and cannot reuse the old prompt hash.


The current review-only reference buys a one-unit pilot on each target, fits
both recoil laws and all detector/background/halo nuisances, then allocates the
remaining nine units using estimated Fisher information for log mass after
profiling nuisance directions. Both pilot law fits enter the design, weighted
by their relative likelihood. Final inference reuses all paid observations.
The equal-allocation method is retained for direct comparison. This local
approximation is not a globally optimal design or calibrated posterior.

A public-input audit replaced the continuously world-varying energy grid with
a shared detector grid. Prior numerical evidence describes the earlier grid.
New methods and ability removals are fixed in `references/revision_replay.json`;
source-bound validation and a new independent model calibration are required.
The previously failed first proposal remains recorded.

Shared-grid Linux replay (NumPy 1.26.4 / SciPy 1.13.1): reference development
0.536805 / heldout 0.548009. Removing pilot-based allocation, extra exposure,
gain handling or free halo weights lowers development score by approximately
0.0126, 0.2394, 0.2589 or 0.1794. Fixed single-target and constant-mass probes
remain separated under the existing guards. These constructor measurements
do not resolve the historical D16 failure or establish independent difficulty.
