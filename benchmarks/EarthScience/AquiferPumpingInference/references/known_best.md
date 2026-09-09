# Known best - AquiferPumpingInference

## Scoring

`combined_score` is clipped to `[0,1]`. For each split it is the mean continuous quality on the
five supported confined worlds multiplied by the exact named-refusal rate on the three unsupported
worlds. Thus blanket `undetermined`, never refusing, and any fixed unsupported label are exactly
zero. Mechanism accuracy, false discovery, correct refusal, supported coverage, parameter recovery,
prediction, and their explicit counts remain separate.

## Scientific target

Design a pumping test under priced radius setup, recover confined-aquifer transmissivity and
storativity, predict sealed drawdown, and distinguish three public reduced-order alternatives:
leakage attenuation, a recharge image well, and delayed dual-porosity storage. The cited literature
motivates those alternatives; `Task.md` publishes the benchmark formulas and does not claim they
are the complete Hantush-Jacob or Moench solutions.

## Baseline

The shipped baseline opens one radius, records one early observation, and returns `undetermined`
with in-bounds parameters. It is valid and scores `0.000000` on development and held-out worlds,
with zero attempted-discovery rate.

## Reference

The truth-blind reference spends all 24 units: two endpoint radii cost twelve setup units and six
times at each radius cost twelve measurement units. It independently fits the confined and three
published reduced-order benchmark formulas with deterministic bounded multi-start least squares,
then uses BIC and a margin rule for attribution. It only consumes the public problem and charged
measurement callback and the reduced-order formulas published in `Task.md`.

On the final builder-replayed Linux revision it scores `0.622081` development and `0.793352` held
out. Mechanism accuracy is `0.875/1.000`, supported coverage is `0.800/1.000`, correct refusal is
`1.000/1.000`, and false discovery is zero. Parameter recovery is `0.674984/0.819008`; sealed
prediction is `0.455605/0.671059`. Two complete in-process replays are identical.

The reference is deliberately below the ceiling. Its noisy two-radius design leaves one supported
development world unresolved, and it uses unweighted least squares, a small fixed start set, and
point predictions rather than uncertainty-aware design or inference. Better radius/time allocation,
noise-aware weighting, and posterior model comparison can improve both supported recovery and
refusal without reading evaluator state.

## Ablations and shortcut probe

| strategy | development | held out | mechanism | correct refusal |
|---|---:|---:|---:|---:|
| full two-radius reference | 0.622081 | 0.793352 | 0.875/1.000 | 1.000/1.000 |
| one radius, half budget | 0.000000 | 0.192774 | 0.625/0.750 | 0.000/0.333 |
| fixed storativity | 0.351835 | 0.431246 | 0.875/1.000 | 1.000/1.000 |
| never refuse | 0.000000 | 0.000000 | 0.625/0.625 | 0.000/0.000 |

The one-radius strategy consumes 12 units, exactly half the full design's budget, and loses more
than 0.42 development and 0.60 held-out score. The task test pins a gap greater than 0.10 on both
splits.

The reproducible 128-strategy probe in `verification/shortcut_probe.py` first performs an honest
confined nonlinear fit and prediction. It then sweeps only three residual thresholds: chi-square
per observation, cross-radius residual contrast, and early-to-late residual contrast. The best
development-selected settings `(2.0, -3.0, -4.0)` score `0.481859/0.525816`, with mechanism
accuracy `0.875/0.875`, false-discovery rate `0.125/0.125`, and correct refusal `0.667/0.667`.
This measures the strongest tested low-dimensional diagnostic shortcut rather than handicapping it
with fixed parameters or zero predictions.

## Model calibration

The September 8 DeepSeek record predates the current identifier, world-order, pricing, noise, and
headline-score revision. It remains historical protocol evidence, but its scores are not current
task performance and are not compared with the revised reference.

On clean scoring revision `2293a80fd1`, DeepSeek v4 Flash and Pro each received one proposal with
seed 845, temperature 0.7, `greedy_rewrite`, and explicitly sent `thinking: disabled`. Both exact
model IDs first returned `AQ_SMOKE_OK`. Flash used a 16000-token cap and returned 4498 output
tokens; Pro used an 8000-token cap and returned 3694. Both proposals were valid, but both returned
`undetermined` on every world, so development and held-out combined score, mechanism score,
correct refusal, coverage, and attempted-discovery rate are all zero. This is an honest blanket
abstention rather than a runner or parsing failure, and neither first proposal reaches the
truth-blind reference.

The compact current record is
`experiments/aquifer_pumping_deepseek_calibration_2026-09-09.json`. Generation used a temporary
two-field provider compatibility patch to send the configured chat thinking mode; the patch was
removed before both candidates were replayed through the secure evaluator on a clean worktree.
Generated code, prompts, endpoints, credentials, and logs are excluded.

## Construction findings

Three review rounds produced concrete changes:

- The initial builder checks removed an over-conservative reference abstention and replaced a
  two-radius ablation with a genuinely one-radius comparison, but did not expose the larger budget
  and security failures below.
- The first model calibration found a valid strong confined fit and a high-false-discovery result,
  but did not trigger changes to hidden worlds or scoring. That evidence is now historical because
  the public contract changed.
- An independent maintainer red team found that `measurement_id` encoded the world seed, the
  observation budget was nearly inert, the shortcut probe omitted a normal fit, extreme policies
  scored above zero, invalid and successful metrics had different key sets, and the alternative
  formulas were not public. IDs are now BLAKE2s coordinate/repeat digests independent of world,
  split worlds are deterministically shuffled, radius setup is charged, the noise and score scale
  are recalibrated, the shortcut begins with a confined fit, the headline requires named refusal,
  both metric paths expose the same 40 keys, and all reduced-order formulas appear in `Task.md`.

## Robustness and limitations

- Twelve malformed output mutations, overspending, an empty mapping, an ID-only policy, blanket
  abstention, and never refusing all fail closed or score exactly zero as applicable.
- Measurement noise depends on world, coordinate, and repeat index rather than query order. IDs do
  not depend on world seed or world order, and candidate session state is reset between worlds.
- Two evaluations of the reference are key-identical; invalid and successful evaluations return
  the same 40 top-level metric keys.
- The oracle is a deterministic radial reduced-order laboratory, not a full groundwater simulator.
  It omits partial penetration, pumping-well storage and skin, heterogeneity, anisotropy, nonlinear
  unconfined flow, irregular boundaries, correlated instrument drift, and recovery after shutoff.

The confined equation follows Theis (1935), DOI `10.1029/TR016i002p00519`. The alternatives are
motivated by Hantush and Jacob (1955), DOI `10.1029/TR036i001p00095`; Ferris et al. (1962), DOI
`10.3133/wsp1536E`; and Moench (1984), DOI `10.1029/WR020i007p00831`.
