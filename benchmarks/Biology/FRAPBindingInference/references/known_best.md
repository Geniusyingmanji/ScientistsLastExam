# Known best - FRAPBindingInference

## Scoring

The hardened score averages the supported-world parameter/prediction/confidence composite and
multiplies it by the exact unsupported-family refusal rate. Supported claims count as mechanism
correct only when their continuous science score is at least `0.5`. This prevents constant
supported outputs, never-refuse policies, and fixed-label abstention from receiving a positive
headline score. Historical model draws below remain evidence for their recorded revision, not new
runs under the revised budget and score.

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

The truth-blind reference spends all 16 units at four times (`0.40`, `3.20`, `6.40`, and `25.60` s)
for each endpoint radius (`0.8` and `2.6` um). The eight measurements cost eight units and the two
first-use radius setups cost four units each. The time subset was selected from all 210 four-time
subsets using development score only. The solver fits the supported and three alternative families
with deterministic multi-start bounded search and uses a BIC margin for attribution. It scores
`0.927573` development and `0.890764` held
out, with full supported coverage, correct attribution of all six unsupported worlds, zero false
discovery, and exact replay. Its supported-world parameter score is `0.924884` development and
`0.862357` held out; prediction scores are `0.998214` and `0.993838`. Remaining headroom is primarily
continuous kinetic recovery under noise and improved measurement design, not a hidden normalization
constant.

## Ablations and shortcuts

| strategy | development | held out | dev refusal | held-out refusal |
|---|---:|---:|---:|---:|
| full priced two-endpoint reference | **0.927573** | **0.890764** | 1.000 | 1.000 |
| half budget: same four times at the stronger single endpoint | 0.109060 | 0.107372 | 0.333 | 0.333 |
| fixed binding rates | 0.000000 | 0.000000 | 1.000 | 1.000 |
| never refuse | 0.000000 | 0.000000 | 0.000 | 0.000 |
| blanket undetermined abstention | 0.000000 | 0.000000 | 0.000 | 0.000 |

The current shortcut is an actual low-dimensional model fit rather than a summary-statistic
threshold scan. Without an optimizer, it profiles mobile fraction in closed form and searches
1,200 supported parameter points, 120 anomalous-transport points, 462 two-pool points, and 2,016
spatial-binding points under the same priced 16-unit design. BIC comparison over those 3,798 points
scores `0.728143` development and `0.707547` held out, with correct refusal `1.0` on both splits.
The multi-start reference retains gaps of `0.199430` and `0.183217`.

## Model calibration

At task revision `c6bc78a`, `deepseek-v4-flash` and `deepseek-v4-pro` were smoke-tested with
visible `OK` replies and chat thinking explicitly disabled. Each received one selection-blind
`greedy_rewrite` proposal at seed 37. The Pro proposal was valid and scored `0.477786` development
and `0.342989` held out. Its parameter recovery was `0.937455`/`0.803967` and prediction score was
`0.998846`/`0.993916`, but it never rejected a misspecified world: false-discovery rate was 1 and
correct-refusal rate was 0 on both splits. Thus it demonstrates competent FRAP curve fitting while
remaining well below that revision's reference on the scientific model-checking requirement.

Flash first exhausted an 8000-token cap. A 16000-token replay completed in 7149 output tokens but
still produced a candidate-side array/scalar runtime error, so it yielded no valid proposal and is
not performance evidence. The compact record is
`experiments/deepseek_frap_binding_inference_calibration_2026-09-07.json`; generated programs,
prompts, endpoints, credentials, and request logs are excluded. Because the current revision halves
the measurement budget and changes headline aggregation, these are explicitly historical-only
protocol records and are not presented as current model scores.

## Construction findings

The first executable reference exposed two implementation defects before model calibration: the
spatial-binding family passed an array-valued off-rate through a scalar conversion, and prediction
scoring called a nonexistent scalar square helper. Both made valid reference outputs fail closed
and were corrected before the first model draw. That draw exposed a public-contract omission:
`Task.md` named `parameter_bounds` and `prediction_contexts` but did not state their container
shapes; both models made incompatible assumptions, so the shapes were documented before replay.

Maintainer review then exposed that the original 32-unit design made all four radii affordable and
that a coarse model grid nearly matched the reference. The budget was reduced to 16 and a four-unit
setup charge was added for first use of each radius, so the capable reference can afford two endpoint
radii while the half-budget ablation can afford one. The threshold-only shortcut was replaced by a
true 3,798-point model grid, and the headline score was gated by correct refusal. The stronger
single-endpoint ablation loses fault attribution (`0.333/0.333` correct refusal) and more than `0.78`
headline score on each split. Fixed-rate and never-refuse ablations show that kinetic recovery and
model comparison remain material.

## Robustness

Two direct reference evaluations are compared as complete dictionaries in the task test. The
evaluator fails closed on exceptions, empty and wrong-type returns, missing or extra keys,
non-finite and out-of-bounds numbers, malformed prediction arrays, fabricated or duplicate evidence,
and caught over-budget callback errors. A dedicated pricing test checks first-use, repeated-radius,
and new-radius charges. All scores are rounded to six decimal places, and immutable measurement IDs
are scoped to one world.

## Limitations and provenance

The oracle is a deterministic single-radial-mode abstraction. It omits the full bleach profile,
finite acquisition exposure, three-dimensional geometry, fluorophore photoswitching, cell motion,
measurement drift, and spatially resolved images. The supported binding model follows Sprague et
al. (2004), DOI `10.1529/biophysj.103.026765`. Model-inadequacy cases are motivated by Feder et al.
(1996), DOI `10.1016/S0006-3495(96)79846-6`, and the foundational FRAP measurement framework of
Axelrod et al. (1976), DOI `10.1016/S0006-3495(76)85755-4`.
