# ScalingLawIdentification — finite-size evidence for empirical complexity

## Scientific setting

An asymptotic class can fit measured runtimes poorly because of finite-size effects,
or fit well while remaining indistinguishable from an adjacent class over the
accessible input sizes. Infer class probabilities and the asymptotic scale from
charged timing observations. Refuse inadequate models or insufficient evidence for
class identification. This is a synthetic empirical-algorithmics experiment, not a
proof of any real program's asymptotic complexity.

## Submission and observation contract

```python
def identify_scaling_law(problem, time_run, budget_units):
    return {"class_probabilities": {...}, "scale": ..., "abstain": ..., "confidence": ...}
```

Every public `problem` key:

| Key | Meaning |
|---|---|
| `classes` | constant, logarithmic, linear, linearithmic, quadratic, exponential |
| `class_shapes` | respectively c, c*log2(m), c*m, c*m*log2(m), c*m^2, c*2^(m/8) |
| `size_bounds` | inclusive integer query domain for this experiment; may vary |
| `cost_tiers` | sizes <=64 cost 1, <=192 cost 2, <=384 cost 3 |
| `budget_units` | 18 units, also passed as the third argument |
| `log_noise_std` | known standard deviation of independent Gaussian log timing error |
| `nuisance_model` | log(runtime_ms) = log(c*f(m)) + a*64/m; unknown a in [-2,2] |
| `noise_note` | observation-noise description; repeated sizes receive fresh errors |
| `refusal_note` | refuse model inadequacy or budget/domain-limited class ambiguity |

`time_run(size)` returns `{size, runtime_ms, budget_cost}`. Python/NumPy integers
and finite integer-valued floats (such as `16.0`) are equivalent. Booleans,
strings, fractional sizes, out-of-domain requests and overspending are invalid.
Caught callback violations invalidate that world. Other valid worlds keep their
scores; aggregate `valid` means at least one valid development world, while
`feasibility_rate` reports the fraction.

`class_probabilities` contains exactly the six named keys with finite scalar
probabilities in [0,1], summing to one within 1e-6. It is required even on
abstention. Return `scale: None` on abstention; otherwise a finite scale in
[1e-12,1e12]. `abstain` is boolean and `confidence` is a finite scalar in [0,1].
The finite-size nuisance coefficient need not be submitted.

## Scoring

On supported worlds, mechanism recovery is the geometric mean of true-class
probability, `exp(-2*abs(log(scale/true_scale)))`, and the probability-weighted
skill of asymptotic runtime extrapolation to size 700. Each class contributes its
probability times `exp(-2*abs(log(prediction/truth)))`. This scores the asymptotic
component c*f(700), with the finite-size correction removed. No argmax is used
for extrapolation and no score discount is imposed for spending the budget.

Inadequate or observationally ambiguous worlds reward refusal only. The average
mechanism score is normalized above the always-abstain score and clipped to [0,1].
Full abstention therefore scores exactly zero. Mechanism, confidence, class/scale/
extrapolation skill, false discovery, correct refusal and coverage are reported
separately with denominators on both splits. Confidence predicts intrinsic response
quality, including correct refusal, and is scored by one minus squared error.

Two distinct failures matter: rejection of every family by the data, and multiple
families agreeing with the data despite accurate observations. A narrow query
interval alone does not imply refusal: well-separated families can still be
identified when measurement precision is sufficient.

## Rules

Only edit `solution.py`. Use deterministic Python/NumPy/SciPy/stdlib code; no
network/process creation or reading `verification/` or `frontier_eval/`. The
`sle.contract_lint` helpers are available for local artifact shape checks.

## 关系与区别 / Relationship to nearby tasks

SequenceLawRecovery recovers exact integer recurrences. ActiveLawDiscovery selects
experiments for physical laws; ComplexBoseLaw fits complex many-body responses;
ChronoamperometryLawID separates electrochemical transient families. Here the
artifact is empirical evidence for a timing class after nuisance correction,
including bounded-n nonidentifiability. This follows the evidence variant in the
repository's next-task plan and occupies discovery/evidence.

## References and admission

CLRS, *Introduction to Algorithms*, ISBN 9780262033848 supports the class forms.
McGeoch, *A Guide to Experimental Algorithmics* (2012), ISBN 9781107001732,
[Cambridge excerpt](https://assets.cambridge.org/97811070/01732/excerpt/9781107001732_excerpt.pdf),
motivates finite experiments, runtime measurement and finite-size effects. The
specific correction/noise family is an original reduced synthetic model; the book
does not validate its constants.

This package remains candidate. The standalone reference reads only this public
contract and charged responses. Current shortcut and ablation results are recorded
below and in `references/known_best.md`; they do not establish expert difficulty or
replace a clean frontier-model calibration draw.

Frontier-Eng overlap: no equivalent complexity-inference task was found; nearest
MallocLab, MLA, FlashAttention and TriMul optimize implementations. The task-specific
review is `.research/scaling_law_identification_frontier_eng_overlap_2026-09-07.md`.
The requested 95-entry source remains unreconciled with the pinned 78-row/84-expanded
catalog and requires maintainer resolution.

## Measured capability ladder

Contributor Linux replay (NumPy 1.26.4 / SciPy 1.13.1); both splits use the same
method and fixed parameters. These measurements do not establish model difficulty.

| Method | Development | Held out | Development loss |
|---|---:|---:|---:|
| Full reference | 0.681348 | 0.644685 | 0.000000 |
| Without finite-size nuisance fitting | 0.052938 | 0.069044 | 0.628410 |
| Without model-adequacy test | 0.395634 | 0.358970 | 0.285714 |
| Without class-separation test | 0.460003 | 0.421387 | 0.221346 |
| Without either refusal check | 0.174288 | 0.135673 | 0.507060 |
| Best of 2304 fixed cheap strategies | 0.413705 | 0.360038 | 0.267643 |

Each scientific world, including the first held-out world, starts a fresh sandbox
process; calls within one world share the same charged budget and candidate state.

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
