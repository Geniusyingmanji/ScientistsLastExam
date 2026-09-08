# MicrolensingEventCharacterization reference results

Task-local diagnostics and clean Linux replay are separate. To reproduce the review comparisons
through the trusted driver and bubblewrap, run:

```bash
python benchmarks/Physics/MicrolensingEventCharacterization/verification/replay_review.py \
  --output /tmp/microlensing-review.json
python benchmarks/Physics/MicrolensingEventCharacterization/frontier_eval/run_eval.py \
  --candidate benchmarks/Physics/MicrolensingEventCharacterization/verification/reference_solver.py \
  --metrics-out /tmp/microlensing-reference.json
```

## Reference

The reference uses 18 r-band observations at a broad cadence and targeted epochs around the
expected event center, a grid point-lens fit, a periodic alternative and a low-signal refusal.
The former six g-band queries contributed evidence IDs only, not fit data or color checks.
They have been removed. All event families share the same band scaling, so this reduced-order
oracle does not implement the classic achromatic-lensing versus chromatic-variability test.
Its current task-local calibration is **0.560636** development and **0.770906** held out; the
reference is an anchor rather than a ceiling and leaves headroom in model selection and continuous
parameter recovery. The legal baseline is 0.000000.

Here and in the historical tables below, development means `combined_score` (normalized),
whereas held-out means `heldout_mechanism_score` (an unnormalized composite). They are not
the same normalization. In particular, 0.770906 held-out is not a normalized held-out headline.
The reference mislabels both development variable-source worlds as binary lenses; variable-source
recognition is an explicit source of remaining headroom.

## Model draws

With explicit `chat_thinking: disabled`, ten-proposal DeepSeek V4 Flash and Pro runs reached
**0.250000** and **0.260876**. Flash produced nine valid proposals and Pro eight; neither reached
the improved reference. These are descriptive calibration draws, not certification evidence.

## Baseline

The legal baseline takes six r-band observations and reports a fixed point-lens claim. It is
deliberately weak and is expected to normalize to zero.

## Corrected ablations and weak-policy comparisons

Removing the six unused g queries from the reference preserves scientific metrics exactly;
only mean budget use changes from 24 to 18. This is a zero-effect removal, not a difficulty step.
`analysis.py` now reports this comparison and a genuine reference-without-refusal variant
separately from its simple threshold policies.

The previously labeled "no-g-band" result, 0.118333 / 0.191875, is actually a fixed point-lens
policy with range-threshold refusal. The previously labeled "never-refuse" result,
0.000000 / 0.191875, is that weak fixed policy without refusal, not the reference without refusal.
Both are retained under descriptive `weak_threshold_*` names; neither establishes that a
reference capability is necessary. The earlier color-ablation claim is withdrawn.

## Shortcut probe

`verification/calibrate.py` evaluates 4,116 policies over observation count, range refusal,
roughness, peak shape and one fixed time scale. The best development policy scores **0.276213**,
below the reference's **0.560636**; it reaches **0.444646** held out with only 0.333 model accuracy.
That sweep excludes uncertainty. PR46 review supplied a stronger six-observation shortcut:
refuse when the first reported uncertainty exceeds 0.05, otherwise make a constant point-lens
claim. The maintainer measured 0.300 development. Thus 0.276213 is only the maximum within
the recorded range/roughness grid, not a general shortcut ceiling. A matching public-input probe
is included in `replay_review.py`. The uncertainty separation remains a known limitation; this
revision corrects the unsupported evidence claims without changing the frozen worlds or scores.

## Construction findings

The first reference scored 0.269340 and was narrowly beaten by the low-dimensional probe at
0.276213. An 81-policy development-only search over four public decision thresholds exposed an
under-built refusal/anomaly rule. The corrected truth-blind reference scores 0.560636 development
and improves held-out performance from 0.645906 to 0.770906 without changing worlds or scoring.
The benchmark remains a reduced-order microlensing laboratory, not a deployment prescription.

PR46 review found that the earlier analysis compared different algorithms while calling them
reference ablations, and that g-band measurements were unused. The corrected analysis uses
the same reference implementation with explicit measurement/refusal switches. Regression tests
verify that arbitrary g flux values cannot change the decision and that the reference now buys
only 18 r-band observations. The 81-policy threshold selection is also disclosed in card lineage.
Another nonblocking review limitation remains: one development variable-source period exceeds
the public output limit of 20 days, so exact recovery is not attainable on that instance.

## Robustness

The evaluator rejects malformed outputs, duplicate observations, overspending, unknown epochs and
fabricated evidence. The reference is key-identical across consecutive evaluations. Reproduce the
reference parameter probe and shortcut sweep with:

```bash
python3 benchmarks/Physics/MicrolensingEventCharacterization/verification/calibrate.py
```
