# AutocorrelationSequence — reference results and anchor confidence

Every score below is produced by running code in this directory.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate solution.py --metrics-out /tmp/baseline.json
python3 frontier_eval/run_eval.py --candidate verification/reference_construction.py --metrics-out /tmp/reference.json
```

## The anchors (genuinely open, actively improving)

| variant | published upper bound | source |
|---|---|---|
| unsigned (`C`) | 1.5028503020710076 | EinsteinArena benchmark certificate (90,000-step nonnegative construction) |
| signed (`C'`) | 1.4545548626983325 | Together AI, "New State-of-the-Art on the Third Autocorrelation Inequality" (2026), superseding a 2010 bound of 1.4581 (Matolcsi & Vinuesa) |

Both are real, currently-open records (the known *lower* bound on `C` is only 1.28,
Cloninger & Steinerberger 2017), so a candidate finding a sequence with a smaller ratio at
either variant would be a genuine, new, checkable improvement.

## Baseline — `solution.py`

A uniform (all-ones) step function. Its discrete autoconvolution ratio is exactly 2.0
regardless of length -- a scale-invariant fact, verified directly.

| variant | ratio | score |
|---|---|---|
| unsigned | 2.0 | 0.0000 |
| signed | 2.0 | 0.0000 |

## Reference — `verification/reference_construction.py`

Randomized coordinate hill-climbing from a triangular (tent-shaped) window plus jitter: 6
restarts, each running 8,000 single-entry perturbation steps with an annealed step size,
keeping only moves that strictly lower the ratio.

| variant | N | ratio | score |
|---|---|---|---|
| unsigned | 100 | 1.6787791169739776 | 0.6461 |
| signed | 20 | 1.6038469413448102 | 0.7263 |

`combined_score = 0.6862`. Measured directly by running
`verification/reference_construction.py` through the oracle above (runtime under 1s). A
tapered window is a real, standard starting point for minimizing autoconvolution/sidelobe
energy, but this plain local search does not reach either published bound, leaving real
headroom for a smarter search.

## What this task is not

This task scores the exact, finite, self-contained discretized object (a step-function
sequence and its exact discrete autoconvolution ratio, computed directly). It does not ask
for, and does not check, the continuous-analysis / Fourier machinery behind the original
problem's formal statement, nor the specific optimization method behind either cited
certificate -- those are separate, already-published results this task does not re-derive
or re-check.
