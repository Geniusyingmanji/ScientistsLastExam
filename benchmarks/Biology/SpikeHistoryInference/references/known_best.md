# Known best - SpikeHistoryInference

## Scoring

For supported worlds, candidate quality is 70% four-parameter recovery, 20% sealed-context
prediction, and 10% confidence calibration. A wrong supported-family diagnosis makes that world's
quality zero. The headline is the mean supported-world quality multiplied by the exact named
refusal rate over unsupported worlds. It is clipped to `[0, 1]`; both valid blanket abstention and
never refusing are exactly zero.

Family-diagnosis accuracy is reported independently over every world with split-level correct and
total counts. False discovery, correct refusal, supported coverage, attempted discovery, parameter
recovery, prediction, confidence, and held-out transfer remain separate diagnostics.

## Scientific target

Recover stimulus drive and an exponential refractory history kernel while distinguishing three
structured violations: a positive burst component, a mixture of latent trial gains, and a
stimulus-dependent refractory effect.

## Baseline

The shipped baseline returns in-bounds fixed parameters and an `undetermined` abstention. It is
valid and scores `0.000000` on both development and held-out worlds.

## Reference

The truth-blind reference searches an exponential time constant, fits regularized logistic models,
and compares public-data likelihoods for flexible history, trial effects, and stimulus-history
interaction. To reduce finite-spike MLE variance it shrinks each reported parameter by 5% toward
the corresponding public-bound midpoint before producing sealed predictions. This fixed public
prior does not inspect hidden world parameters or labels.

The reference scores `0.697016` development and `0.829388` held out. It covers every supported
world, gives the correct family for all eleven worlds, correctly refuses all six unsupported
worlds, has zero false discovery, and replays exactly. Its supported parameter-recovery scores are
`0.601879/0.769280`. The reference is a capable task-local witness, not a claim of optimal neural
system identification; remaining headroom is finite-sample refractory-parameter estimation and
better regularized likelihood modeling.

## Ablations and shortcuts

| strategy | development | held out | dev refusal | held refusal |
|---|---:|---:|---:|---:|
| shrinkage point-process reference | **0.697016** | **0.829388** | 1.000 | 1.000 |
| fixed refractory tau = 20 ms | 0.617365 | 0.751527 | 1.000 | 1.000 |
| public-bound midpoint parameters, reference diagnosis | 0.496777 | 0.328371 | 1.000 | 1.000 |
| 1,728-strategy moment/constant-parameter sweep | 0.402102 | 0.166566 | 0.667 | 0.667 |
| reference fit, never refuse | 0.000000 | 0.000000 | 0.000 | 0.000 |
| mean-rate-only, never refuse | 0.000000 | 0.000000 | 0.000 | 0.000 |
| blanket undetermined abstention | 0.000000 | 0.000000 | 0.000 | 0.000 |

The reproducible shortcut in `verification/shortcut_probe.py` selects on development from 1,728
strategies combining low-order moment thresholds with constant gain, amplitude, and tau profiles.
It does not fit a point-process likelihood. Its best development strategy misses one unsupported
family on each split and abstains on one held-out supported world. The reference retains gaps of
`0.294914` development and `0.662822` held out.

## Model calibration

At task revision `156927e2`, one `greedy_rewrite` first proposal per model used replicate identifier
731, temperature 0.7, selection-blind feedback, and explicit `chat_thinking: disabled`. Both
proposals were valid under that revision. DeepSeek v4 Flash scored `0.000000/0.195556`; DeepSeek v4
Pro scored `0.417694/0.298301`. Flash abstained on every supported world, while Pro falsely claimed
all unsupported worlds.

Independent review later changed world coverage, headline scoring, world-session isolation, and
the reference. Therefore the credential-free record
`experiments/spike_history_inference_deepseek_calibration_2026-09-07.json` is explicitly
`historical_only`; none of its scores is presented as current-contract performance. Prompts,
generated source, endpoints, credentials, request logs, and local run directories are excluded.

## Construction findings

Builder checks established deterministic generation, correct-refusal separability, malformed-input
failure behavior, and the initial ablation ladder. Independent maintainer recomputation then found
five material defects: loose parameter tolerances rewarded constants, a 1,728-strategy moment
shortcut was stronger than disclosed, candidate state crossed world boundaries, supported
mechanism credit ignored the submitted diagnosis, and the reference omitted standard shrinkage.

Hardening narrowed parameter tolerances relative to the supported-world span, expanded held-out
supported parameters within the unchanged public bounds, made headline credit depend jointly on
supported inference and exact unsupported refusal, reset candidate sessions at every world, and
added fixed public-prior shrinkage to the reference. A public-bound midpoint ablation now loses
`0.200239/0.501017`, and fixed tau loses `0.079651/0.077861`.

## Robustness

Two reference evaluations are compared as complete dictionaries. The evaluator fails closed on
exceptions, non-mappings, missing or extra keys, non-finite and out-of-bound values, malformed or
empty prediction arrays, bad confidence/refusal types, and fabricated or insufficient evidence.
Candidate-visible inputs are deep-copied, so in-process mutation cannot alter trusted validation or
produce a valid NaN score. A stateful regression candidate verifies one `reset_session` call for
each of the eleven worlds. Wrong supported-family claims, fixed-label abstention, never refusing,
and blanket abstention all receive zero headline credit.

## Limitations and provenance

The generator is a discrete-time conditional Bernoulli abstraction, not raw electrophysiology. It
omits coupled populations, spike sorting, continuous-time jitter, waveform information, long-term
adaptation, and experimental drift beyond the stated alternatives. The scientific model follows
Truccolo et al. (2005), DOI `10.1152/jn.00697.2004`; Paninski (2004), DOI
`10.1088/0954-898X/15/4/009`; and Pillow et al. (2008), DOI
`10.1038/nature07140`.
