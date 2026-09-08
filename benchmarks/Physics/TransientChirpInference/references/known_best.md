# TransientChirpInference reference results

## Current reference and baseline

Executable revision `94cda555f5cd1cd5488566b900e592609d178b89` was frozen before the new model
draws. Clean ali Linux trusted-driver/bubblewrap replays gave reference **0.7871224443** development
and **0.7234283087** held-out normalized score. The baseline and blanket refusal each score zero.
All ten replay policies were valid and complete metrics were identical on two runs each.
The reference's fitting grid, cadence and decision thresholds were not tuned to the revised worlds;
only a redundant, unused duplicate grid fit was removed.

Reference mechanism accuracy is 9/10 development and 10/12 held-out. FDR is 0/9 and 1/11 claims;
correct refusal is 4/4 in both splits. Coverage is 9/10 and 11/12 supported worlds. Mechanism
accuracy now measures labels, while `*_science_score` retains the separate unnormalized composite.
Both splits also have a consistently normalized score (`combined_score` / `robustness_score`).

The t=0..11 reference cadence misses a late localized event in each split. Finite-grid slope error,
remaining slow-chirp/line confusion and more adaptive observation design provide headroom; this
is not a full compact-binary waveform solver or an optimal observation policy.

## Current ablation ladder

| Policy | Development normalized | Held-out normalized |
|---|---:|---:|
| Reference | 0.787122 | 0.723428 |
| H1 only | 0.692047 | 0.643030 |
| No chirp grid | 0.479101 | 0.479147 |
| Reference with all reported slopes fixed at 0.02 | 0.487122 | 0.431762 |
| Never refuse | 0.000000 | 0.000000 |

The constant-slope comparison retains fitted labels and amplitudes; losing 0.300000 development
score demonstrates that slope estimation now contributes real credit, including on line worlds.
The H1-only and no-chirp-grid implementations retain their documented simpler refusal rules;
they are operational reduced policies, not claims that all other decisions are identical.

## Current shortcut probes

| Probe | Policies | Development selected | Held-out report |
|---|---:|---:|---:|
| Maintainer noise/sign-count rule | 1 | 0.000000 | 0.000000 |
| Original peak/RMS/roughness family | 2916 | 0.418415 | 0.214259 |
| Noise/RMS/sign-count/fixed-slope family | 1620 | 0.627261 | 0.543909 |

The expanded grid varies paired sample count, glitch threshold, amplitude refusal, uncertainty
refusal, sign-count difference and fixed chirp slope. The selected enhanced parameters are
`(12, 0.28, 0.08, 0.05, 0, 0.006)`. Selection uses development score only; held-out metrics are
reported after selection, not used for tuning. The sweep is trusted in-process Linux analysis;
the selected policies, reference and ablations are then independently executed through the
trusted driver and bubblewrap. The direct and sandbox results agree.

The original heuristic no longer ties the reference. The retuned heuristic still achieves about
80% of reference development score, so this is a measured gap of 0.159862, not proof that every
low-dimensional method is weak. New regression tests pin a >0.10 gap on both splits for this
registered selected probe. No claim of an exhaustive algorithmic upper bound is made.

Reproduce on Linux:

```bash
python benchmarks/Physics/TransientChirpInference/verification/calibrate.py --output /tmp/chirp-sweep.json
python benchmarks/Physics/TransientChirpInference/verification/replay_review.py \
  --sweep /tmp/chirp-sweep.json --output /tmp/chirp-replay.json
```

## Current model draws

One proposal each from `deepseek-v4-flash` and `deepseek-v4-pro`, seed 29, temperature 0,
greedy_rewrite, normal feedback, `run-role=calibration`, 16000 output-token cap, on clean revision
94cda55. Both exact IDs passed a visible-output smoke check first. The existing YAML specified
`chat_thinking: disabled`, but the old client ignores that field; a local-only in-memory adapter
therefore injected `thinking: {type: disabled}` into every chat request. No provider/runtime patch,
endpoint, credential, generated program or prompt is included in the PR.

| Model | Valid proposals | Development | Held-out normalized |
|---|---:|---:|---:|
| DeepSeek V4 Flash | 1/1 | 0.000000 | 0.000000 |
| DeepSeek V4 Pro | 1/1 | 0.245075 | 0.298082 |

Flash made valid claims on every world and never refused: its mechanism accuracy was 7/10 and
8/12, but refusal was 0/4 on both splits. Zero is therefore a decision/scoring outcome, not an API
failure or evidence that no inference was performed. Pro refused 3/4 ambiguous worlds on each
split. Both draws remain below reference. A single draw per model cannot establish broad
difficulty or the frontier-model entry condition; DeepSeek is not represented as a frontier draw.
There were no oracle or reference changes after seeing these model results.

## Current construction findings

PR48 review exposed noise-sigma label leakage and an untested sign-count shortcut. All families
now share sigma=0.04; ambiguity is low amplitude rather than a distinct uncertainty label. Slow
chirps are paired with constant-frequency lines matched in midpoint phase/frequency. Tests verify
overlapping early/late sign-count features in both splits. The supported recovery term now weighs
0.50 (formerly 0.10 for chirp slope), with slope error tested for lines as well; its tolerance is
0.003 cycles/day^2. Model credit is 0.20, amplitude 0.20 and correct-claim confidence 0.10.
Glitches use event-time recovery for the same parameter term, avoiding irrelevant free credit.

The score subtracts all-refusal reward and multiplies by correct-refusal rate. The latter makes
never-refusing fits zero; it is an explicit additional design choice. Four-axis counts and
denominators are derived from actual claims, including incorrect ones in coverage. Candidate
sessions reset between worlds, public inputs are copied, and invalid candidates receive a zero
headline with matching result-key structure. A separate confidence-calibration diagnostic scores
wrong declarations, rather than presenting raw submitted confidence as calibration evidence.

## Current robustness and evidence

Full task contribution gate: 15/15 on ali Linux. The task tests cover noise-label independence,
sign-count collisions, line-slope penalties, independent metric bookkeeping, claim/refusal
denominators, session reset, selected-probe separation and 11 malformed output cases. Standard
CLI bad candidates and the external run_eval path are checked separately. No full-repository
test suite or maintainer-owned global evidence refresh is run for this revision.
Compact records: `experiments/transient_chirp_review_replay_2026-09-08.json` and
`experiments/transient_chirp_deepseek_review_2026-09-08.json`.

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
