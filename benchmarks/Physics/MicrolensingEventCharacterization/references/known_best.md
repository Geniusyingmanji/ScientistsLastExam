# MicrolensingEventCharacterization reference results

All values in this file are produced by task-local code. Run:

```bash
python benchmarks/Physics/MicrolensingEventCharacterization/verification/analysis.py
python benchmarks/Physics/MicrolensingEventCharacterization/frontier_eval/run_eval.py \
  --candidate benchmarks/Physics/MicrolensingEventCharacterization/verification/reference_solver.py \
  --metrics-out /tmp/microlensing-reference.json
```

## Reference

The reference uses a broad r-band cadence, targeted epochs around the expected event center,
six g-band color checks, a grid point-lens fit, a periodic alternative and a low-signal refusal.
Its current task-local calibration is **0.560636** development and **0.770906** held out; the
reference is an anchor rather than a ceiling and leaves headroom in model selection and continuous
parameter recovery. The legal baseline is 0.000000.

## Model draws

With explicit `chat_thinking: disabled`, ten-proposal DeepSeek V4 Flash and Pro runs reached
**0.250000** and **0.260876**. Flash produced nine valid proposals and Pro eight; neither reached
the improved reference. These are descriptive calibration draws, not certification evidence.

## Baseline

The legal baseline takes six r-band observations and reports a fixed point-lens claim. It is
deliberately weak and is expected to normalize to zero.

## Difficulty ladder

The task-local analysis reports the reference, no-g-band and never-refuse ablations. The reference
is 0.560636 / 0.770906, no-g-band is 0.118333 / 0.191875, and never-refuse is 0.000000 /
0.191875. Each removes one scientific capability: color cross-checks, or calibrated
model-inadequacy refusal.

## Shortcut probe

`verification/calibrate.py` evaluates 4,116 policies over observation count, range refusal,
roughness, peak shape and one fixed time scale. The best development policy scores **0.276213**,
below the reference's **0.560636**; it reaches **0.444646** held out with only 0.333 model accuracy.
The tested shortcut does not replace joint point-lens, anomaly and periodic model comparison.

## Construction findings

The first reference scored 0.269340 and was narrowly beaten by the low-dimensional probe at
0.276213. An 81-policy development-only search over four public decision thresholds exposed an
under-built refusal/anomaly rule. The corrected truth-blind reference scores 0.560636 development
and improves held-out performance from 0.645906 to 0.770906 without changing worlds or scoring.
The benchmark remains a reduced-order microlensing laboratory, not a deployment prescription.

## Robustness

The evaluator rejects malformed outputs, duplicate observations, overspending, unknown epochs and
fabricated evidence. The reference is key-identical across consecutive evaluations. Reproduce the
reference parameter probe and shortcut sweep with:

```bash
python3 benchmarks/Physics/MicrolensingEventCharacterization/verification/calibrate.py
```
