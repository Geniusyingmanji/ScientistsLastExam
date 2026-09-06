# UPbConcordiaInference reference results

All values below are computed by code in this task package.

## Reproducing

```bash
python benchmarks/EarthScience/UPbConcordiaInference/verification/analysis.py
python benchmarks/EarthScience/UPbConcordiaInference/frontier_eval/run_eval.py \
  --candidate benchmarks/EarthScience/UPbConcordiaInference/verification/reference_solver.py \
  --metrics-out /tmp/upb-reference.json
```

## Reference

`verification/reference_solver.py` is truth-blind. It selects the six domains with the highest
published signal quality, buys analytical precision, fits a single point on Wetherill concordia
and a weighted straight discordia with two concordia intercepts, then refuses when neither family
fits the stated uncertainties.

| metric | development | held out |
|---|---:|---:|
| normalized mechanism | **0.913758** | 0.818262 |
| history accuracy | 1.000 | 1.000 |
| crystallization-age score | 0.905640 | - |
| lead-loss-age score | 0.800828 | - |
| false-discovery rate | 0.000 | 0.000 |
| correct-refusal rate | 1.000 | 1.000 |
| discovery coverage | 1.000 | 1.000 |

This is not a ceiling. The fit ignores the published ratio-error correlation, its grain selection
optimizes signal quality rather than expected information about both discordia intercepts, and its
age search is a fixed grid. These leave continuous age-estimation headroom below the score ceiling
of 1.0 and a visible development-to-held-out gap.

## Model draws

The public contract and oracle were frozen at commit `984bb73`. Both exact model IDs passed a
visible-output smoke test, and both configurations recorded `chat_thinking: disabled`. Each model
then ran two replicate identifiers, three proposals, `greedy_rewrite`, normal feedback. These are
calibration draws, not population model-performance claims.

| model | replicate | proposal 1 | proposal 2 | proposal 3 | best |
|---|---:|---:|---:|---:|---:|
| `deepseek-v4-flash` | 17 | invalid | invalid | 0.231 | 0.231 |
| `deepseek-v4-flash` | 43 | invalid | 0.176 | 0.560 | **0.560** |
| `deepseek-v4-pro` | 17 | invalid/0.000 | 0.145 | 0.203 | 0.203 |
| `deepseek-v4-pro` | 43 | 0.262 | 0.175 | 0.262 | 0.262 |

All four first proposals are below the reference's 0.914, so the admission line holds. Flash seed
43 shows a substantive trajectory: its final proposal reaches 0.625 history accuracy, 0.721
lead-loss-age score, 1.0 refusal and 0.875 supported coverage, but retains 0.286 false discovery.
Its held-out mechanism score is 0.546. Pro seed 17 improves age estimates across feedback but never
refuses unsupported histories; Pro seed 43 refuses correctly but covers only half the supported
worlds. The sanitized record is
`experiments/deepseek_upb_concordia_calibration_2026-09-06.json`.

## Baseline

`solution.py` measures one domain in `screen` mode and always reports a fixed 1000 Myr concordant
history. It is valid on every world and has `combined_score = 0.000000`; it has full discovery
coverage but false-discovery rate 0.8 and no age credit.

## Difficulty ladder

| strategy | score | held out | false discovery | refusal | coverage |
|---|---:|---:|---:|---:|---:|
| weighted fit, six highest-signal analytical domains | **0.913758** | 0.818262 | 0.000 | 1.000 | 1.000 |
| same fit, only three analytical domains | 0.861378 | 0.609470 | 0.000 | 1.000 | 1.000 |
| six evenly spaced domains | 0.900583 | 0.819950 | 0.000 | 1.000 | 1.000 |
| six contiguous domains | 0.549874 | 0.382775 | 0.200 | 0.000 | 1.000 |
| eighteen screen measurements | 0.493680 | 0.487200 | 0.200 | 0.000 | 1.000 |
| ignore reported uncertainties | 0.000000 | 0.000000 | 0.800 | 0.000 | 1.000 |
| never refuse | 0.663758 | 0.532547 | 0.200 | 0.000 | 1.000 |
| round event ages to 50 Myr | 0.553047 | 0.562267 | 0.000 | 1.000 | 1.000 |

The budget buys age precision and held-out transfer; domain coverage is needed to expose two-event
histories; uncertainty weighting, continuous ages and refusal each carry score.

## Shortcut probe

`verification/analysis.py` evaluates 192 strategies that convert each isotope ratio separately to
an apparent age, threshold median discordance and apparent-age spread, and choose three to six
domains by one of three simple rules. They never fit the coupled concordia or a discordia.

The best reaches **0.344581** development and 0.378502 held out, with 0.625 history accuracy, zero
lead-loss-age score and 0.625 discovery coverage. This is well below the reference's 0.913758.

## Construction findings

- The first reference used loose 90/120 Myr tolerances and scored 0.982. Tightening them to 15/25
  Myr made event-age quality a real axis and left reproducible headroom.
- Splitting unsupported histories by arbitrary grain-id parity made experimental design physically
  opaque. The final generator separates the two loss episodes by the public domain-position
  coordinate, so broad domain sampling has an interpretable purpose.
- The first refusal threshold missed one development multi-event suite. Direct reduced-residual
  checks showed all supported discordias below 2.25 and all unsupported suites above 11.1; the
  fixed threshold of 8 separates the declared worlds without using truth at evaluation time.

## Robustness

The reference is key-identical across consecutive evaluations. The baseline is valid and exactly
zero, and a valid blanket-refusal method is exactly zero after normalization. Repeated-grain and
over-budget calls, malformed outputs, non-finite ages, unsupported labels and fabricated evidence
identifiers are caught per world and score invalid rather than raising from the evaluator. On
Linux, `check_task_contribution.py` passes every gate, all three standard bad candidates score
invalid without crashing, and the reference scores 0.913758 through the secure subprocess path.
