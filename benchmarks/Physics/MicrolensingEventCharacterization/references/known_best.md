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
Its current task-local calibration is **0.269340** development and **0.645906** held out; the
reference is an anchor rather than a ceiling and leaves headroom in model selection and continuous
parameter recovery. The legal baseline is 0.000000.

## Model draws

No model draw has been run. The task remains a candidate.

## Baseline

The legal baseline takes six r-band observations and reports a fixed point-lens claim. It is
deliberately weak and is expected to normalize to zero.

## Difficulty ladder

The task-local analysis reports the reference, no-g-band and never-refuse ablations. The reference
is 0.269340 / 0.645906, no-g-band is 0.118333 / 0.191875, and never-refuse is 0.000000 /
0.191875. Each removes one scientific capability: color cross-checks, or calibrated
model-inadequacy refusal.

## Shortcut probe

The main low-dimensional shortcut is a fixed point-lens claim or a threshold on peak range without
model comparison. It is expected to remain below the active reference because binary anomalies and
periodic variability require targeted temporal evidence.

## Construction findings

The benchmark is a reduced-order microlensing laboratory, not a deployment prescription. It was
chosen to fill a photometric-lensing gap distinct from Doppler planets, transit timing and
transmission-spectrum composition.

## Robustness

The evaluator rejects malformed outputs, duplicate observations, overspending, unknown epochs and
fabricated evidence. The reference must be key-identical across two consecutive evaluations before
the task is submitted.
