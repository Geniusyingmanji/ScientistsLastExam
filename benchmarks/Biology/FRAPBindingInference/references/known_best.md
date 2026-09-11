# Known best - FRAPBindingInference

## Scoring

`combined_score` is clipped to `[0, 1]`. A valid `undetermined` blanket abstention is exactly zero.
The task-local reference is an evaluation anchor for a reduced-order FRAP laboratory, not a claim
of optimal experimental design or in-cell validation.

## Scientific target

Recover diffusion, mobile fraction, and reversible binding rates from recovery curves at multiple
bleach radii, predict unseen radius/time contexts, and attribute three resolvable failures of the
shared reaction-diffusion family.

## Baseline

The shipped baseline makes one early measurement and returns an `undetermined` abstention with
fixed in-bounds parameters. It is valid and scores `0.000000` on both splits.

## Reference

The truth-blind reference measures eight times at all four radii, fits the supported and three
alternative families with deterministic multi-start bounded search, and uses a BIC margin for
attribution. It scores `0.965603` development and `0.958000` held out, with full supported coverage,
correct attribution of all six unsupported worlds, zero false discovery, and exact replay. Its
supported-world parameter score is `0.941998` development and `0.886749` held out; the remaining
headroom is mainly continuous binding-rate recovery under measurement noise.

## Ablations and shortcuts

| strategy | development | held out | dev refusal | held-out refusal |
|---|---:|---:|---:|---:|
| full cross-radius reference | **0.965603** | **0.958000** | 1.000 | 1.000 |
| two radii only | 0.901797 | 0.921424 | 1.000 | 1.000 |
| omit the latest intermediate time | 0.917655 | 0.865443 | 1.000 | 1.000 |
| fixed binding rates | 0.622044 | 0.595200 | 1.000 | 1.000 |
| never refuse | 0.469603 | 0.362800 | 0.000 | 0.000 |
| blanket undetermined abstention | 0.000000 | 0.000000 | 0.000 | 0.000 |

The 192-strategy summary-statistic sweep searches plateau, half-time, curve-shape and late-tail
thresholds plus fault-ordering rules without a joint reaction-diffusion fit. Its best development
strategy scores `0.369094` development and `0.386000` held out, with correct-refusal rate `0.666667`
on both splits. It does not approach the reference.

## Model calibration

Fresh DeepSeek Flash and Pro results are recorded only after the oracle and public contract are
committed. Generated programs, prompts, endpoints, credentials, and request logs are excluded.

## Construction findings

The first executable reference exposed two implementation defects before model calibration: the
spatial-binding family passed an array-valued off-rate through a scalar conversion, and prediction
scoring called a nonexistent scalar square helper. Both made valid reference outputs fail closed
and were corrected before freezing. The final task requires multiple bleach radii because one
recovery curve cannot reliably separate a slow diffusing population from reversible binding. The
two-radius ablation retains much of the score but loses continuous parameter accuracy; fixed-rate
and never-refuse ablations show that kinetic recovery and model comparison remain material.

## Limitations and provenance

The oracle is a deterministic single-radial-mode abstraction. It omits the full bleach profile,
finite acquisition exposure, three-dimensional geometry, fluorophore photoswitching, cell motion,
measurement drift, and spatially resolved images. The supported binding model follows Sprague et
al. (2004), DOI `10.1529/biophysj.103.026765`. Model-inadequacy cases are motivated by Feder et al.
(1996), DOI `10.1016/S0006-3495(96)79846-6`, and the foundational FRAP measurement framework of
Axelrod et al. (1976), DOI `10.1016/S0006-3495(76)85755-4`.
