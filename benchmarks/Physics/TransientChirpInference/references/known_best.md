# TransientChirpInference reference results

## Historical version

The following measurements use revision c9e75ce's worlds and score. They are historical only,
not performance claims for the PR48 hardening revision. In these historical tables, held-out
is the old unnormalized composite, not normalized robustness or model accuracy. The old
mechanism_score name also denoted that composite; the revised key measures accuracy instead.

The deterministic task-local reference uses twelve H1 and twelve L1 observations, a grid fit for
constant-frequency and chirping phase models, a cross-detector localized-glitch test, and a
low-SNR refusal. It scores **0.808362** development and **0.853325** held out; the legal fixed-line
baseline scores **0.000000**. These values are from the final local oracle and were replayed twice
on the clean Linux calibration tree.

## Baseline

The legal baseline samples six H1 epochs and reports a fixed line with zero slope. It is valid but
has no detector-coherence or waveform-model comparison capability, so the normalized score is zero.

## Model draws

With explicit `chat_thinking: disabled`, five-proposal DeepSeek V4 Flash and Pro runs reached
**0.244951** and **0.271171**. All five proposals for each model were valid; one was accepted in
each run. These are descriptive calibration draws, not certification evidence.

## Difficulty ladder

| strategy | development | held out | model accuracy (dev/held) | false discovery (dev/held) | refusal (dev/held) |
|---|---:|---:|---:|---:|---:|
| full reference | **0.808362** | **0.853325** | 0.833 / 0.833 | 0.000 / 0.000 | 1.000 / 1.000 |
| H1 only; no detector coherence | 0.648322 | 0.607440 | 0.667 / 0.667 | 0.000 / 0.125 | 1.000 / 0.500 |
| no chirp grid; line fit only | 0.313594 | 0.485325 | 0.500 / 0.500 | 0.125 / 0.125 | 0.500 / 0.500 |
| never refuse | 0.475029 | 0.603325 | 0.833 / 0.833 | 0.375 / 0.375 | 0.000 / 0.000 |

The full reference is deliberately below 1.0: one supported world in each split remains
misclassified, and its fixed event time and finite grids leave continuous-recovery headroom.

## Shortcut probe

`verification/calibrate.py` evaluates 2,916 policies over observation count and three
peak/amplitude thresholds. The best development policy scores **0.600015**, below the reference's
**0.808362**; it falls to **0.351875** held out with 0.167 model accuracy and 0.500 false-discovery
rate. The tested shortcut therefore does not replace chirp fitting and detector-coherence logic.

## Construction findings

The first reference scored 0.641695 and was narrowly beaten by the H1-only ablation at 0.648322.
The cause was a low-SNR noise spike passing the localized-glitch test. Requiring a minimum H1
event peak repaired that under-built reference rather than changing the worlds or score; all
numbers above were then regenerated. This remains a reduced-order waveform laboratory, not a
replacement for matched filtering, calibration inference, or detector-quality vetoes in a real
observing run.

## Robustness

The evaluator rejects malformed outputs, duplicate observations, unknown epochs/detectors,
overspending, and fabricated evidence. Two consecutive full reference metric payloads are
key-identical. Reproduce the table and shortcut sweep with:

```bash
python3 benchmarks/Physics/TransientChirpInference/verification/calibrate.py
```
