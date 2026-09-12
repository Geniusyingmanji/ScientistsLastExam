# TransientChirpInference reference results

## Current admission: candidate after long-baseline reference repair

The [2026-09-12 cadence repair](../../../../experiments/transient_chirp_reference_cadence_2026-09-12.json)
binds clean source `0bc037e277fee8857b035ef9d61359a9c22985a3`. The reference now distributes
twelve paired H1/L1 epochs across the full public 0--18 day window and uses the selected
line fit's amplitude for line claims. This design was selected from public-contract reasoning
and development `combined_score` only; held-out metrics were first inspected after the design
was frozen, and no subsequent tuning occurred.

On pinned Linux with the trusted driver and bubblewrap, the reference scores
**0.8804117954** development and **0.8972976728** held out. The frozen five-slope witness
remains **0.6611830495** development. The unchanged 20 percent guard line is
**0.7043294363**, leaving the witness 0.0431463868 below it. The full task contribution gate
passes with structural, runtime and shortcut phases passed; difficulty remains unassessed and
external gravitational-wave review remains pending, so the task remains a candidate.

Thirteen fixed policies were each replayed twice: all 780 world evaluations were valid and all
13 complete metric pairs were identical. The 28 Linux task/guard tests plus four subtests passed.
No full-repository suite, new model draw or maintainer-owned global evidence refresh was run.

## Prior hold after reference range repair

The [2026-09-12 reference-range review](../../../../experiments/transient_chirp_reference_bounds_2026-09-12.json)
binds clean source `55e6f83ad8b3b9239c87391978ad38041ea6fb88`, including main
`dbed927128606051ffe483f4b5f192366dbad313` and the current trusted framework.
The old coarse slope grid ended at 0.04; its three local refinements could reach at most
0.042625, below the public 0.05 limit. Extending the grid to 0.05 preserves every old grid
entry and the 0.002 spacing. Fixed noiseless public-formula regressions at slopes
0.041, 0.045, 0.049 and 0.05 verify frequency/slope recovery without hidden-world tuning.

The reference, baseline, original development-selected probes and declared reduced policies
were frozen before 24 independent Linux sandbox calls. All 720 world evaluations were valid;
all 12 complete metric pairs matched. The reference still scores 0.821949084347924 and the
five-slope witness 0.6611830494930327, above the unchanged 20 percent margin's strict
0.6575592674783393 line. C remains blocked. There are 27 passing Linux task/guard tests,
zero failures and zero skips, including the four boundary cases. No new model D campaign
or modern trusted formal coverage is claimed. The prior 87 task packages are unchanged;
the inventory contains 88 tasks while global evidence retains its original 87-task scope.

Fixed reference/probe source remains public in `verification/` for reproduction. New complete
metrics, execution receipts and captured execution copies are private outside Git. The older
report's private-program wording refers to captured copies, not the published source.

## Original independent shortcut guard before range repair

The [2026-09-12 independent Linux report](../../../../experiments/transient_chirp_shortcut_guard_2026-09-12.json)
binds clean source `8134f597b5f5cf194ae5f4eb1d0046e5087d0b79`. The published five-slope
witness is now available as `verification/probe_fixed_five_slope.py` and registered in the
machine-readable guard. Its factory and development-selected parameters are unchanged.
The reference, baseline and witness were each evaluated twice through the real trusted
sandbox: all 30 worlds were valid and each complete metric pair was identical.

The reference scored 0.821949084347924 and the witness 0.6611830494930327. The declared
20 percent margin requires a score strictly below 0.6575592674783393; the witness exceeds
that line by 0.0036237820146934885. The full contribution check performed 13 actual
evaluations and returned 15 passed checks, one failed shortcut guard and zero skips.
The earlier baseline-only guard did not test this condition. Scientific admission stays
on hold; neither the margin nor the measured scores are adjusted to turn it into a pass.

The first Python 3.8 fixture run retained one failure and 25 passes. Dictionary union
raised before a score assertion and made the malformed-output matrix fail for the wrong
reason. A separate fixture-only commit uses dictionary unpacking; all 26 Linux tests
then passed with zero skips. Earlier shape checks that never reached validation are not
counted as effective coverage. Full metrics and captured execution copies stay private outside Git;
the fixed reference and probe source is published in `verification/`.

## Current reference and baseline

The current clean Linux replay at `0bc037e277fee8857b035ef9d61359a9c22985a3` uses the
trusted driver and bubblewrap. The reference scores **0.8804117954** development and
**0.8972976728** held-out normalized score. The baseline and blanket refusal each score zero.
All thirteen replay policies were valid and their complete metrics were identical on two runs each.
The reference locally refines its coarse frequency/slope fit, so its reported frequency is not tied
to a discrete grid.

Reference mechanism accuracy is 10/10 development and 12/12 held-out. FDR is 0/10 and 0/12 claims;
correct refusal is 4/4 in both splits. Coverage is 10/10 and 12/12 supported worlds. Mechanism
accuracy now measures labels, while `*_science_score` retains the separate unnormalized composite.
Both splits also have a consistently normalized score (`combined_score` / `robustness_score`).

The full-baseline fixed cadence remains non-adaptive and fits H1 rather than a joint detector
likelihood. Finite-grid slope error, adaptive observation design and coherent joint fitting provide
headroom; this is not a full compact-binary waveform solver or an optimal observation policy.

## Current ablation ladder

| Policy | Development normalized | Held-out normalized |
|---|---:|---:|
| Reference | 0.880412 | 0.897298 |
| First-twelve-epoch cadence | 0.821766 | 0.685347 |
| H1 only | 0.480612 | 0.476616 |
| No chirp grid | 0.459307 | 0.377229 |
| Reference with all reported slopes fixed at 0.02 | 0.692985 | 0.695588 |
| Never refuse | 0.000000 | 0.000000 |

Restricting only the cadence loses 0.058646 development and 0.211951 held-out score, demonstrating
that the added temporal baseline contributes real recovery and transfer capability. The constant-slope
comparison retains fitted labels and amplitudes; losing 0.187427 development score demonstrates that
slope estimation contributes real credit, including on line worlds.
The H1-only and no-chirp-grid implementations retain their documented simpler refusal rules;
they are operational reduced policies, not claims that all other decisions are identical.

## Current shortcut probes

| Probe | Policies | Development selected | Held-out report |
|---|---:|---:|---:|
| Maintainer noise/sign-count rule | 1 | 0.000000 | 0.000000 |
| Original peak/RMS/roughness family | 2916 | 0.440667 | 0.286497 |
| Noise/RMS/sign-count/fixed-slope family | 1620 | 0.565033 | 0.459472 |
| No-fit RMS/median/sign-count morphology family | 216 | 0.584719 | 0.519672 |
| No-fit morphology with five-slope lookup | 324 | 0.661183 | 0.556308 |

The author's earlier expanded grid varies paired sample count, glitch threshold, amplitude refusal, uncertainty
refusal, sign-count difference and fixed chirp slope. The selected enhanced parameters are
`(12, 0.28, 0.08, 0.05, 0, 0.006)`. Selection uses development score only; held-out metrics are
reported after selection, not used for tuning. The author reported the original sweep as
trusted in-process Linux analysis and then replayed selected programs through the sandbox.
The current independent review reuses those preselected parameters without rerunning any grid;
the current sandbox reference, selected policies and ablations are reported above.

The 216-policy morphology family varies H1 sample count, RMS refusal, median-magnitude glitch
threshold, sign-count difference and fixed chirp slope. Its selected parameters are
`(15, 0.10, 0.10, 2, 0.006)`; it performs no waveform fitting. The added 324-policy family also
scans the review-supplied five-slope lookup tables; its selected member is
`(16, 0.08, 0.08, 7, [0.0, 0.006, 0.018, 0.028, 0.028], 1)`.

The review-supplied lookup-table family is the strongest measured no-fit family. It reaches 75.1%
of reference development and 62.0% held out, leaving gaps of 0.219229 and 0.340990. Continuous
initial-frequency recovery prevents a fixed slope table from collecting full coherent parameter
credit. Regression tests pin the maintained witnesses and their positive gaps on both splits.
No exhaustive algorithmic upper bound is claimed.

Reproduce on Linux:

```bash
python benchmarks/Physics/TransientChirpInference/verification/calibrate.py --output /tmp/chirp-sweep.json
python benchmarks/Physics/TransientChirpInference/verification/replay_review.py \
  --sweep /tmp/chirp-sweep.json --output /tmp/chirp-replay.json
```

## Historical model draws before range repair

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
The later reference-range repair was motivated by the public parameter bounds. These old model
records retain their original source bindings and are not current-source or frontier-model D evidence.

## Current construction findings

PR48 review exposed noise-sigma label leakage and an untested sign-count shortcut. All families
now share sigma=0.04; ambiguity is low amplitude rather than a distinct uncertainty label. Slow
chirps are paired with constant-frequency lines matched in midpoint phase/frequency. Tests verify
overlapping early/late sign-count features in both splits. The supported recovery term now weighs
0.50 (formerly 0.10 for chirp slope), with slope error tested for lines as well; its tolerance is
0.003 cycles/day^2. Model credit is 0.30 and amplitude credit is 0.20; confidence is a separate diagnostic.
Glitches use event-time recovery for the same parameter term, avoiding irrelevant free credit.

The score subtracts all-refusal reward and multiplies by correct-refusal rate. The latter makes
never-refusing fits zero; it is an explicit additional design choice. Four-axis counts and
denominators are derived from actual claims, including incorrect ones in coverage. Public inputs
are copied per world; `reset_session()` is called only when the candidate object defines that hook,
so ordinary module-level state is retained. Invalid candidates receive a zero headline with matching
result-key structure. A separate confidence-calibration diagnostic scores
wrong declarations, rather than presenting raw submitted confidence as calibration evidence.

## Current robustness and evidence

The earlier ali Linux contribution gate passed with only the zero baseline registered, and the
original independent guard correctly failed on the published stronger witness. The clean
26-call cadence replay and current contribution gate pass the same unchanged margin without
changing the evaluator, worlds, budget, frozen witness or threshold rule.
The task tests cover noise-label independence,
sign-count collisions, line-slope penalties, independent metric bookkeeping, claim/refusal
denominators, session reset, selected-probe separation and 11 malformed output cases. Standard
CLI bad candidates and the external run_eval path are checked separately. No full-repository
test suite or maintainer-owned global evidence refresh is run for this revision.
Compact records: `experiments/transient_chirp_review_replay_2026-09-11.json` and
`experiments/transient_chirp_deepseek_review_2026-09-08.json`; the current repair record is
`experiments/transient_chirp_reference_cadence_2026-09-12.json`.

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
