# Known best - SpikeHistoryInference

## Scoring

`combined_score` is clipped to `[0, 1]` and normalized so valid blanket abstention is exactly zero.
The reference is an evaluation anchor for a reduced-order point-process laboratory, not a claim of
optimal neural-system identification.

## Scientific target

Recover stimulus drive and an exponential refractory history kernel while distinguishing three
structured violations: a positive burst component, a mixture of latent trial gains, and a
stimulus-dependent refractory effect.

## Baseline

The shipped baseline returns in-bounds fixed parameters and an `undetermined` abstention. It is
valid and scores `0.000000` on both development and held-out worlds after normalization.

## Reference

The truth-blind reference searches an exponential time constant, fits regularized logistic models,
and compares public-data likelihoods for flexible history, trial effects, and stimulus-history
interaction. It scores `0.902708` development and `0.898349` held out, with full supported
coverage, correct refusal of all six unsupported worlds, zero false discovery, and exact replay.

## Ablations and shortcuts

Fixing the refractory time constant at 20 ms scores `0.875529/0.879114`; retaining the reference
parameter fits but never refusing scores `0.396403/0.299746`; mean-rate-only inference scores
`0.233776/0.178887`. A reproducible 192-strategy sweep in `verification/shortcut_probe.py` searches
low-dimensional trial-rate overdispersion, delayed-spike lift, and stimulus-conditioned history
contrast thresholds. Its best development strategy reaches `0.693965` development and `0.684804`
held out while missing one of three unsupported families on each split. It does not reach the
reference and retains a `0.333333` false-discovery rate.

## Model calibration

Fresh DeepSeek Flash and Pro first-proposal results will be recorded only after the oracle is
committed. The compact experiment record will exclude prompts, generated programs, endpoints,
credentials, and request logs.

## Limitations and provenance

The generator is a discrete-time conditional Bernoulli abstraction, not raw electrophysiology. It
omits coupled populations, spike sorting, continuous-time jitter, waveform information, long-term
adaptation, and experimental drift beyond the stated alternatives. The scientific model follows
Truccolo et al. (2005), DOI `10.1152/jn.00697.2004`; Paninski (2004), DOI
`10.1088/0954-898X/15/4/009`; and Pillow et al. (2008), DOI `10.1038/nature07140`.
