# Known best - AquiferPumpingInference

## Scoring

`combined_score` is clipped to `[0,1]`. Each split contains equally many supported confined and
unsupported worlds: 12+12 in development and 9+9 held out. The headline is the product of two
continuous quantities: mean supported-world parameter/prediction quality and mean unsupported-world
sealed-prediction quality. An unsupported prediction contributes only when the named family is
correct. Thus blanket `undetermined`, never refusing, and every fixed unsupported label are exactly
zero, while a lucky label without a usable family model cannot fill the unsupported axis.

Mechanism accuracy, false discovery, named-refusal rate, supported coverage, supported parameter
recovery, supported prediction, unsupported prediction, and their explicit counts remain separate.

## Scientific target

Design a pumping test under priced radius setup, recover confined-aquifer transmissivity and
storativity, predict sealed drawdown, and distinguish three public reduced-order alternatives:
leakage attenuation, a recharge image well, and delayed dual-porosity storage. The cited literature
motivates those alternatives; `Task.md` publishes the benchmark formulas and does not claim they
are the complete Hantush-Jacob or Moench solutions.

## Baseline

The shipped baseline records six legal observations at 25 m, then makes an overconfident confined
claim with lower-bound transmissivity, upper-bound storativity, and zero predictions. It is valid,
never abstains, and scores exactly `0.000000/0.000000` development/held out. This is the required
confidently wrong zero baseline, not a blanket-abstention exception.

## Reference

The truth-blind reference spends all 24 units at 25 m and 110 m: twelve setup units and six times
at each radius. It independently fits the confined and three published reduced-order families with
deterministic bounded five-start least squares, selects the minimum BIC, and predicts sealed
contexts with the selected family. It consumes only the public problem and charged callback.

On the final builder-replayed Linux structure it scores `0.636182` development and `0.691286` held
out. Mechanism accuracy is `0.916667/0.944444`, named-refusal rate is `0.833333/0.888889`, supported
parameter recovery is `0.943863/0.947318`, supported prediction is `0.836626/0.845050`, and
unsupported prediction is `0.705266/0.763185`. Complete repeated metrics are deterministic.

The reference is deliberately below the ceiling. It uses a fixed non-adaptive two-radius schedule,
point estimates, five deterministic starts, and BIC rather than posterior model averaging or an
uncertainty-aware sequential design. All ten two-radius pairs were replayed; 25 m + 110 m is the
development-best pair, so the remaining headroom is not an intentionally weak radius choice.

## Ablations and shortcut probe

| strategy | development | held out | mechanism | named refusal | unsupported prediction |
|---|---:|---:|---:|---:|---:|
| full two-radius reference | 0.636182 | 0.691286 | 0.916667/0.944444 | 0.833333/0.888889 | 0.705266/0.763185 |
| development-best one-radius half budget | 0.314589 | 0.402415 | 0.708333/0.777778 | 0.416667/0.555556 | 0.362931/0.448708 |
| fixed storativity | 0.031206 | 0.009477 | 0.916667/0.944444 | 0.833333/0.888889 | 0.075426/0.019495 |
| never refuse | 0.000000 | 0.000000 | 0.500000/0.500000 | 0.000000/0.000000 | 0.000000/0.000000 |
| three-threshold confined-fit probe | 0.023665 | 0.028897 | 0.708333/0.722222 | 0.416667/0.444444 | 0.025492/0.030898 |
| stronger confined-fit residual probe | 0.139929 | 0.156887 | 0.666667/0.777778 | 0.583333/0.555556 | 0.203855/0.180171 |

The one-radius result is not a deliberately weak schedule. A 210-policy scan covered every radius,
all six-of-seven unique-time schedules, and every three-times-doubled schedule. The development
winner uses 25 m at 90, 300, 900, 2700, 9000, and 86400 seconds. It loses `0.321593/0.288871` to
the full design.

The stronger cheap probe independently chooses its best pair from all ten radius pairs, fits only
the confined Theis model, and classifies with chi-square, radial residual, and normalized temporal
curvature summaries. It never evaluates an alternative-family equation. Its development-best
25 m + 220 m design reaches only 22.0% of the reference score. The executable shortcut contract
uses a 50% relative margin and also replays the earlier three-threshold probe.

A maintainer previously reported `0.884294` for a cheap candidate on an obsolete headline that
awarded full unsupported credit for a correct label. Its exact source was not published. The
current score removes that attack surface: correct naming without an accurate sealed prediction
has low continuous value. The stronger reproducible analog deliberately includes the same
confined-fit/residual-summary capability and remains below the reference on both splits.

## Model calibration

The September 8 and 9 DeepSeek Flash/Pro records predate the current contract and remain historical
only. After executable structure froze at clean revision `7c7a0139`, both exact model IDs passed a
visible-output smoke test with `thinking.type=disabled`. Two selection-blind first proposals per
model were scheduled at seeds 17 and 29 with proposal budget 1. Flash produced one valid candidate
at `0.192625/0.172372` and one measurement-contract violation; Pro produced one valid candidate at
`0.012719/0.000000` and one runtime-invalid candidate. Both valid candidates were securely replayed
twice with identical complete JSON and remained below the `0.636182` reference. Invalid cells are
retained as protocol failures, not counted as evidence of difficulty. This DeepSeek evidence is
supplementary and does not replace maintainer-native frontier-model D16 calibration.

The compact current record is `experiments/aquifer_pumping_admission_2026-09-17.json`. Prompts,
generated programs, endpoints, credentials, request logs, and run directories are excluded.

## Construction findings

Four red-team rounds found and corrected material construction errors:

- Measurement IDs originally embedded the world seed and leaked labels. They are now BLAKE2s
  coordinate/repeat digests independent of world and order; worlds are shuffled and candidate
  sessions reset for every world.
- Three unsupported worlds and a named-refusal multiplier made random labels coarse and profitable.
  The panels now contain 12/9 unsupported worlds, and unsupported credit is a continuous sealed
  prediction score gated by the correct family rather than a Bernoulli label multiplier.
- The first reference wasted budget at 220 m, while the published half-budget comparison used a
  weak design. The final reference is the development-best of all ten radius pairs, and the
  half-budget ablation is the development-best of 210 one-radius schedules.
- The old shortcut omitted a normal parameter fit, and the baseline abstained. The probes now fit
  confined parameters honestly, include a stronger self-contained residual attack, and the baseline
  is a valid overconfident zero-score claim. Invalid paths expose the same 43 keys as valid paths,
  return a bounded diagnostic reason, and cap evidence length.

## Robustness and limitations

- Malformed shapes, exceptions, non-finite values, overspending, overlong or fabricated evidence,
  an empty mapping, ID-only policies, blanket abstention, fixed labels, and never refusing fail
  closed or score exactly zero as applicable.
- Observation noise depends on world, coordinate, and repeat index rather than query order. IDs do
  not depend on world seed or world order.
- The oracle is a deterministic radial reduced-order laboratory, not a field-scale groundwater
  simulator. It omits partial penetration, pumping-well storage and skin, heterogeneity, anisotropy,
  nonlinear unconfined flow, irregular boundaries, correlated drift, and recovery after shutoff.

The confined equation follows Theis (1935), DOI `10.1029/TR016i002p00519`. The alternatives are
motivated by Hantush and Jacob (1955), DOI `10.1029/TR036i001p00095`; Ferris et al. (1962), DOI
`10.3133/wsp1536E`; and Moench (1984), DOI `10.1029/WR020i007p00831`.
