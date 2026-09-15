# Reference and admission record

## 1. Runnable public-input method

The standalone reference fits each public timing family with a bounded finite-size
correction, tests known-noise goodness of fit, then checks class-likelihood separation.
Its design uses public bounds and costs only; there is no hidden modulus or seed.
The scale and the nuisance coefficient are fitted jointly. Remaining headroom is
adaptive experimental design and marginalization over scale/correction uncertainty.

### 1a. Maintainer construction and identifiability certificate

Wide worlds use log-noise sigma 0.16, bounds [8,384], and a uniform coefficient in
[-2,2]. Narrow ambiguity worlds use [64,72] and sigma 0.12; narrow supported controls
use exponential timing with the identical sigma 0.12 and correction in [-2,-1].
Their public problem mappings are identical, so neither domain nor noise metadata
is a refusal label. The class-separating slope must be measured. Scale uncertainty
on the narrow interval remains real headroom. The observed noise precision is public.
Misspecified worlds add `1.4*sin(3*log(m))` to log runtime; its exact form is hidden.

For each ambiguous world, pair linear and linearithmic families, match their scale
at the midpoint of the log-ratio range, and keep nuisance/noise identical. At any
size, conditional KL is squared log-mean difference divided by twice noise variance.
The chain rule bounds every adaptive transcript by `budget*max(KL_per_query/cost)`.
Under the declared independent Gaussian observation model, Pinsker yields equal-prior
binary accuracy at most 0.623423, even for a method told
both candidate parameter settings. This does not assert zero recoverable information;
it rules out reliable class identification. The counterpart is in the public family.
This statistical bound is not protection against memorizing the repository-visible
frozen seeds or lookup transcripts; generalization requires server-held fresh worlds.
A full-domain enumerator in `ambiguity_information_bound` independently computes
the bound. Narrow supported controls prevent bounds alone from serving as labels.

The class forms follow CLRS (ISBN 9780262033848); finite empirical measurement and
finite-size concerns are motivated by McGeoch (ISBN 9781107001732),
https://assets.cambridge.org/97811070/01732/excerpt/9781107001732_excerpt.pdf.
The particular noise/correction constants are original synthetic choices.

## 2. Baseline and normalization

The shipped legal baseline is confidently uninformative and scores zero. Full
abstention also scores zero, with distinct discovery coverage. See Task.md for the
complete numerical score. Invalid artifacts never become discovery attempts.
The budget is a hard constraint; the old 25% full-budget discount has been removed.
Probability-weighted extrapolation replaces winner-take-all class selection.

## 3. Capability ablations

`verification/replay_review.py` removes one capability at a time using legal public
inputs and charged callbacks. Current Linux measurements are in the table below;
all variants retain the original artifacts and remaining computations.

## 4. Low-dimensional shortcuts

The maintainer's old-head grid reached 0.863028 development / 0.858821 held out;
the untuned doubling ladder reached 0.792895 / 0.799391, above the old reference
0.710786 / 0.702993. The earlier “No low-dimensional family reaches the reference”
claim is withdrawn. The revised 2304-setting sweep varies ladders, RMS gates,
probability mass and inclusion of a bounded nuisance fit. Selection uses development
score; held-out performance of that same strategy is reported, not retuned.

## 5. Frontier-model calibration

No current-revision frontier-model draw has been completed. The package remains
candidate; neither these numerical probes nor unit tests establish the required
first-proposal admission criterion. Builder lineage remains complete with honestly
empty calibration lists, as clarified by the maintainer's withdrawn review item.
Historical local/macOS proposals are not frozen calibration evidence.

## 6. Construction errors and review revisions

The original jitter label demanded refusal despite recoverable classes. The original
reference explicitly used a hidden mod-three predicate; an efficiency discount then
hid intrinsic saturation. Those constructions have been replaced. An intermediate
small ensemble still let a nuisance-aware three-point probe win by chance; replicated
class/scale/nuisance worlds and a separate held-out ensemble now expose that failure.
Noise sweeps (0.08, 0.12, 0.16, 0.20) guided the chosen 0.16 instrument regime; this
is disclosed task design, not a blind calibration draw. Refusal labels derive from
model inadequacy or the pairwise information bound, never a high-noise label alone.
Integer-valued float sizes now match integer timings; one invalid world no longer
erases other valid results. The taxonomy follows the planned finite-n evidence
variant. Removed cross-PR findings are retained in their originating PR history.

## 7. Robustness and reproduction

Run from a clean Linux checkout with the repository's pinned NumPy/SciPy environment:

```bash
python benchmarks/ComputerScience/ScalingLawIdentification/verification/replay_review.py --output /tmp/review-replay.json
python benchmarks/ComputerScience/ScalingLawIdentification/frontier_eval/run_eval.py --candidate benchmarks/ComputerScience/ScalingLawIdentification/verification/reference_solver.py --metrics-out /tmp/reference.json
```

The replay records revision, clean-tree status, source hashes, Python/NumPy and OS.
It is a contributor numerical audit, not maintainer-owned frozen global evidence.
Linux sandbox replay and contribution checks are reported separately below.

## Current revision measurements

Linux direct replay from clean revision `bee50a353643`,
Python 3.12.3, NumPy 1.26.4 / SciPy 1.13.1. The machine-readable
[replay record](review_replay.json) binds the executable source hashes. Later
measurement declarations, documentation and regression additions do not change
these evaluator/reference/probe hashes.

| Method | Development | Held out | Development loss |
|---|---:|---:|---:|
| Full reference | 0.681348 | 0.644685 | 0.000000 |
| Without finite-size nuisance fitting | 0.052938 | 0.069044 | 0.628410 |
| Without model-adequacy test | 0.395634 | 0.358970 | 0.285714 |
| Without class-separation test | 0.460003 | 0.421387 | 0.221346 |
| Without either refusal check | 0.174288 | 0.135673 | 0.507060 |
| Best of 2304 fixed cheap strategies | 0.413705 | 0.360038 | 0.267643 |

The best fixed probe reaches 60.7% of the reference on development
and 55.8% on held out. This is the measured finite grid,
not a universal upper bound over algorithms. Parameters: `{"ladder": [8, 16, 32, 64, 128], "gate": 0.4, "mass": 1.0, "correction": true}`.

CI-pinned Python 3.10 / NumPy 1.24.4 / SciPy 1.10.1, through the actual
`frontier_eval/run_eval.py` sandbox wrapper: reference 0.681348 development /
0.644685 held out, valid 1. The fixed probe is standalone under
`verification/` and is declared in `TASK_CARD.shortcut_probe`, with a 30% relative
margin and 0.01 portability tolerance. The small optimizer/runtime differences
are reported rather than rounded away or mixed into one result.

On this Ubuntu host, unprivileged bubblewrap fails even for `/usr/bin/true`
with an RTM_NEWADDR loopback permission error. Native sandbox checks therefore
used a privileged trusted launcher, and CI-pinned checks used an isolated test
container. In both cases candidate UID/GID 65534, network/process isolation,
read-only mounts and seccomp restrictions were retained. Neither workaround
changed task or harness security policy.

### Reduced-design control retaining full inference

A stronger reduced-design control retains bounded nuisance fitting, known-noise
adequacy and likelihood-separation tests, and probability-weighted predictions.
Among 18 reduced-design/threshold settings explored, the development-selected
five-point ladder `(8, 32, 96, 192, 384)` with separation threshold `0.7` scores
**0.572169 development / 0.626147 held out** in the CI-pinned Linux sandbox.
This is **84.0% / 97.1%** of the reference: fewer measurements can nearly match
its held-out score when all inference capabilities are retained. The 2304-setting
single-RMS grid and its 30% guard cover only that declared restricted family;
they do not establish a universal shortcut gap or expert-level difficulty.
`verification/reference_sparse_control.py` is standalone;
`references/reduced_design_control.json` records provenance and full metrics.
Independent red teaming, fresh worlds and frontier-model calibration remain
necessary before scientific admission.

## Integration validation (2026-09-12)

Integrated upstream `dbed92712860`. Metadata now explicitly states
`difficulty: unmeasured` and `tier: candidate`; model difficulty is not established.
CI-pinned Linux compatibility tests at `a3a20e0f036a`: **184 passed, 17 subtests passed in 66.05s (0:01:06)**.
The task's real world-session isolation test passed separately. The full contribution
gate and the actual shared wrapper passed on `af0a1ddd8fff`; subsequent changes
only update runner regression tests. Public score output excludes held-out/internal
metrics, while the explicitly separate trusted sidecar retains full diagnostics.
The real reference scores remain 0.681348 development /
0.644685 held out, valid 1.

The earlier full suite on the `58e4b8e` integration had
1460 passed, 2 old-wrapper failures, 48 skipped and 511
passed subtests. Those failures are fixed and covered by the final compatibility
suite. The 48 historical-run skips are not passes. This is a prior full suite plus
a current-main compatibility suite, not a claim of a new full-suite GitHub green.
[`linux_validation.json`](linux_validation.json) records versions, revision scopes,
source hashes, gate details and the remaining admission work.
