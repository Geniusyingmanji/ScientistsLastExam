# TransitTimingAttribution reference record

This candidate uses a deterministic reduced-order transit-timing laboratory. The reference policy
compares a quadratic clock against periodic planet/activity models by least-squares/BIC, and
abstains on poor residual fit or insufficient model separation.

## Current baseline and reference

Clean executable revision `1b7f39e1fe96dec95d85a74ea82a4bc87851aecc`, replayed on ali Linux
with the trusted driver and bubblewrap on 2026-09-08. Every entry below was valid and its complete
metrics were identical on two runs. Reproduce using `verification/replay_probes.py`.
Compact evidence: `experiments/transit_timing_review_replay_2026-09-08.json`.

| Candidate | Development | Held-out |
|---|---:|---:|
| Baseline, one measurement then refusal | 0.000000 | 0.000000 |
| Truth-blind reference, three follow-ups | 0.900201 | 0.901472 |

Reference mechanism accuracy is 5/5 development and 6/6 held-out; false discovery is 0/5 and
1/7 claims; correct refusal is 3/3 and 3/4 unsupported worlds; coverage is 5/5 and 6/6.
It still falsely claims one unsupported held-out signal. The headline now penalizes this error;
supported-only mechanism accuracy remains a separate diagnostic. Remaining capability headroom
includes adaptive follow-up scheduling and calibrated out-of-family rejection, not missing a
standard supported-model fit. The reference code was not tuned to these new worlds.

## Ablation ladder

| Reference change | Development | Held-out |
|---|---:|---:|
| No activity model | 0.549472 | 0.336474 |
| Forecast fixed to zero | 0.833582 | 0.480681 |
| Refusal disabled, supported fitting unchanged | 0.000000 | 0.000000 |
| Family C, 210-point non-fit grid | 0.717580 | 0.888285 |
| Only three follow-ups | 0.877308 | 0.533911 |
| Four follow-ups | 0.889497 | 0.548430 |

The budget was reduced from eight to four after review found the old k>=3 ladder nearly flat.
The new ladder is not monotone on development: two follow-ups beat four by 0.007772.
This is a limitation of the fixed schedule, not evidence that all four measurements are essential.
No seeds or candidate thresholds were selected to manufacture a monotone ladder.

## Shortcut probes

Blanket refusal, each fixed mechanism with constant period/forecast, the old six-position
`order_keyed` counter, and reference fitting with refusal disabled all score exactly zero on both
splits. Each makes legal measurements where a claim is required. The counter reads no timing data;
the sandbox restarts its module state for every instance. Independently seeded shuffling and
unequal split lengths also remove the old sequence contract. Raw mechanism accuracy alone can
still reward chance family guesses; it is not the discovery composite.

These are targeted regression probes, not a measured upper bound over all low-dimensional
grids. Public finite period grids remain a reduced-order limitation requiring external review.

## Construction errors

Maintainer review on 2026-09-08 exposed two failures in revision 61b458a: unsupported claims had
zero headline penalty, and fixed instance order let a no-data counter recover mechanisms.
The revised score gates period/forecast credit on a correct mechanism and includes all worlds,
subtracting blanket-refusal reward. An intermediate clean replay (6cc4f11) showed that this
additive correction alone still gave a fitted never-refuse policy 0.289497/0.231240. The final
score therefore also multiplies by correct-refusal rate. Both refusal extremes now score zero.
This multiplier is an explicit task-design choice, not a claim that the maintainer prescribed it.

Development now has eight instances and held-out ten, with multiple independent phase/noise
draws of the unsupported mixture. This expands refusal denominators but does not introduce new
physical refusal families. Instance-local sessions, invalid-result key parity, sticky query errors,
and a trusted subprocess run_eval replace the previous unsafe convenience path.

## Robustness

The full task-specific contribution gate passed 15/15. Related regression tests passed 74 tests;
the task unit suite covers 15 fault cases including caught overspend, duplicate/invented evidence,
nonfinite parameters, exceptions and malformed outputs. The three standard CLI bad candidates
were all scored invalid. Successful and invalid evaluator results have identical key sets.
No full-repository tests or global evidence refresh were run; candidate status is unchanged.
Historical DeepSeek evidence below is not relabeled as current performance. No new model draw
was required by the maintainer's revised merge conditions; this revision reports deterministic
candidate replays only.

## Historical baseline and reference

The following 2026-09-05 results use the old supported-only score and eight follow-ups.
They are not calibration of the revised refusal-aware, four-follow-up evaluator.

Server replay (2026-09-05, provisional candidate calibration):

- baseline: `combined_score = 0.0000`, valid `1.0`; one legal follow-up is taken and the candidate
  abstains everywhere;
- truth-blind reference: development supported-world mean `0.9034`, held-out supported-world mean
  `0.8992`; development false-discovery rate `0.0` with correct unsupported refusal `1.0`;
- held-out validation has one residual unsupported-world false discovery (`false-discovery rate
  0.1667` over six claims), so the reference is not treated as a ceiling or certification evidence;
- reference uses eight legal follow-up timings, a least-squares/BIC comparison of clock,
  planet and activity models, and a forecast at a future unmeasured transit.

## Historical model draws

DeepSeek Flash calibration after enabling the chat-wire `thinking: disabled` compatibility path
(temperature `0.0`, `greedy_rewrite`, budget 3, 2026-09-05):

- seed 11: three valid proposals, best development `0.4777`, held-out `0.2170`, development /
  validation false-discovery rates `0.5` / `0.6667`, coverage `0.8` / `0.4`;
- seed 12: one valid proposal out of three, best development `0.5719`, held-out `0.5201`, development
  and validation false-discovery rates `0.4`, coverage `0.8` / `0.8`;
- earlier runs without the chat compatibility fix consumed the output budget entirely in hidden
  reasoning and returned zero visible response bytes; those protocol-incomplete runs are not model
  performance evidence.

Values remain provisional until server-held families, independent photodynamical replication and
external astronomy review. The exact-descriptor ceiling is evaluator-recomputed, not a claim of
photodynamical optimality. Scientific grounding includes Agol et al. (DOI
`10.1111/j.1365-2966.2005.08922.x`) and Holman and Murray (DOI `10.1126/science.1107822`).
