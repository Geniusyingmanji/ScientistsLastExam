# Reference and admission record

## 1. Runnable public-input method

The standalone reference uses charged dates to initialize monotone age-depth curves,
then jointly fits the public positive-accumulation family and an 81-point common
climate with sparse nonlinear least squares. Gaussian-process reconstruction uses
the refined ages and an approximate diagonal dating-error variance. Laboratory
calibration and cross-record coherence are separate adequacy tests. No seeds,
true ages, climate spectrum or evaluator imports are used.

Joint posterior uncertainty, correlated chronology errors and adaptive dating remain
headroom. The diagonal propagation approximation is included as an ablation; a tiny
score delta must not be described as evidence of a separate demanding capability.

The pseudoproxy context is Amrhein et al., DOI 10.1029/2020GL090485, and Badgeley
et al., DOI 10.5194/cp-16-1325-2020. The public positive-accumulation synthetic model
is inspired by age-uncertain reconstruction, not a reproduction of a published
climate reconstruction. All field and dating constants are in the local evaluator.

## 2. Baseline and normalization

The shipped legal baseline is confidently uninformative and scores zero. Full
abstention also scores zero, with distinct discovery coverage. See Task.md for the
complete numerical score. Invalid artifacts never become discovery attempts.
Chronology skill is exp(-age_MAE/65 - age_increment_MAE/12). Adjacent-sample
increments penalize an interpolant whose dated endpoints are right but accumulation
between them is wrong. Exact fields and ages achieve unit supported mechanism skill.

## 3. Capability ablations

`verification/replay_review.py` removes one capability at a time using legal public
inputs and charged callbacks. Current Linux measurements are in the table below;
all variants retain the original artifacts and remaining computations.

## 4. Low-dimensional shortcuts

The maintainer's old-head cheap strategy reached 0.698764 / 0.682105 versus
reference 0.736298 / 0.708775 (94.9% / 96.2%). Previous affine/offset probes retained
the reference climate and missed this direction. The new 1008-setting sweep varies
sample count, endpoint convention, constant standard deviation, calibration gate
and coherence gate. It buys dates, linearly interpolates, and averages unweighted
records. The best development strategy's held-out score is reported without retuning.

## 5. Frontier-model calibration

No current-revision frontier-model draw has been completed. The package remains
candidate; neither these numerical probes nor unit tests establish the required
first-proposal admission criterion. Builder lineage remains complete with honestly
empty calibration lists, as clarified by the maintainer's withdrawn review item.
Historical local/macOS proposals are not frozen calibration evidence.

## 6. Construction errors and review revisions

The previous score rewarded sparse interpolation almost as much as the reference,
while the reference never used proxy observations to refine chronology. Local
increment scoring and joint inference repair those two issues together. The old
known_best text listed unrelated mass/time/instrument tests that did not exist; that
template text and the external-fork “current comparison” link have been removed.
Nearest-neighbor documentation now includes UPbConcordiaInference, GravityInversion
and RadiativeTransferFit. SystemExit/KeyboardInterrupt fail closed during direct
oracle diagnostics. The wrapper retains its trusted subprocess and explicit timeout.

## 7. Robustness and reproduction

Run from a clean Linux checkout with the repository's pinned NumPy/SciPy environment:

```bash
python benchmarks/EarthScience/ChronologyAssimilation/verification/replay_review.py --output /tmp/review-replay.json
python benchmarks/EarthScience/ChronologyAssimilation/frontier_eval/run_eval.py --candidate benchmarks/EarthScience/ChronologyAssimilation/verification/reference_solver.py --metrics-out /tmp/reference.json
```

The replay records revision, clean-tree status, source hashes, Python/NumPy and OS.
It is a contributor numerical audit, not maintainer-owned frozen global evidence.
Linux sandbox replay and contribution checks are reported separately below.

## Current revision measurements

Linux direct replay from clean revision `b111593e7b9a`,
Python 3.12.3, NumPy 1.26.4 / SciPy 1.13.1. The machine-readable
[replay record](review_replay.json) binds the executable source hashes. Later
measurement declarations, documentation and regression additions do not change
these evaluator/reference/probe hashes.

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

The best fixed probe reaches 54.6% of the reference on development
and 54.2% on held out. This is the measured finite grid,
not a universal upper bound over algorithms. Parameters: `{"n": 5, "std": 0.3, "chi_gate": 1.5, "coherence_gate": 0.2, "edge": 0}`.

CI-pinned Python 3.10 / NumPy 1.24.4 / SciPy 1.10.1, through the actual
`frontier_eval/run_eval.py` sandbox wrapper: reference 0.797115 development /
0.715310 held out, valid 1. The fixed probe is standalone under
`verification/` and is declared in `TASK_CARD.shortcut_probe`, with a 30% relative
margin and 0.01 portability tolerance. The small optimizer/runtime differences
are reported rather than rounded away or mixed into one result.

On this Ubuntu host, unprivileged bubblewrap fails even for `/usr/bin/true`
with an RTM_NEWADDR loopback permission error. Native sandbox checks therefore
used a privileged trusted launcher, and CI-pinned checks used an isolated test
container. In both cases candidate UID/GID 65534, network/process isolation,
read-only mounts and seccomp restrictions were retained. Neither workaround
changed task or harness security policy.

Current difficulty ladder (same Linux direct environment):

| Level | Development | Held out |
|---|---:|---:|
| 1 | 0.797985 | 0.714963 |
| 2 | 0.605235 | 0.540224 |
| 3 | 0.510818 | 0.441745 |

The joint refinement removes about 0.309 development points when ablated. The
diagonal error-propagation effect is only about 0.0004; it is a numerical
approximation, not evidence for an independent expert capability.

## Integration validation (2026-09-12)

Integrated upstream `dbed92712860`. Metadata now explicitly states
`difficulty: unmeasured` and `tier: candidate`; model difficulty is not established.
CI-pinned Linux compatibility tests at `ff5223e012c8`: **195 passed, 17 subtests passed in 121.08s (0:02:01)**.
The task's real world-session isolation test passed separately. The full contribution
gate and the actual shared wrapper passed on `c7312e30689d`; subsequent changes
only update runner regression tests. Public score output excludes held-out/internal
metrics, while the explicitly separate trusted sidecar retains full diagnostics.
The real reference scores remain 0.797115 development /
0.715310 held out, valid 1.

The earlier full suite on the `58e4b8e` integration had
1473 passed, 2 old-wrapper failures, 48 skipped and 511
passed subtests. Those failures are fixed and covered by the final compatibility
suite. The 48 historical-run skips are not passes. This is a prior full suite plus
a current-main compatibility suite, not a claim of a new full-suite GitHub green.
[`linux_validation.json`](linux_validation.json) records versions, revision scopes,
source hashes, gate details and the remaining admission work.
