# TransientChirpInference reference results

The deterministic task-local reference uses twelve H1 and twelve L1 observations, a grid fit for
constant-frequency and chirping phase models, a cross-detector localized-glitch test, and a
low-SNR refusal. It scores **0.641695** development and **0.728325** held out; the legal fixed-line
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

The intended ablations are H1-only cadence (loses detector-localization evidence), no chirp grid
(loses frequency-evolution recovery), and never-refuse (false discovery on low-SNR worlds).

## Shortcut probe

A fixed line or a peak-amplitude threshold cannot distinguish coherent chirps from lines and
detector-localized glitches across the shifted held-out worlds. A future low-dimensional sweep
must remain below the reference.

## Construction findings

This is a reduced-order waveform laboratory, not a replacement for matched filtering, calibration
inference, or detector-quality vetoes in a real observing run.

## Robustness

The evaluator rejects malformed outputs, duplicate observations, unknown epochs/detectors,
overspending, and fabricated evidence. Reference results require two identical full metric replays.
