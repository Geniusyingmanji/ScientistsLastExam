# Frozen point-predictor source validation

`source_validation.py` implements a **post-hoc development diagnostic** designed
after the d1 results were inspected. It conditions on d1's eight saved point
predictors and measures their bias on the eight original source conditions.
It does not replace the A=yes, B=partial, C=scoped-readiness review, alter p1/p2
negatives, assess an entire model family, or assign a discovery grade.

The fixed plan is `calibration/material-source-validation/plan.json` under the
central private artifact root. Its exact byte SHA256 is embedded in the new
entry point. There are no CLI overrides for seeds, sample size, tolerances or
statistical method. The one-noise-SD threshold is a new declared practical
tolerance fixed before these new readings; it is not an exact-truth test or a
threshold inferred from old target outcomes. Reused development worlds remain
development worlds despite independently keyed measurement noise.

## Fixed observations and point predictions

The original four d1 instances each contribute their unchanged `relaxation`
and `cubic_memory` v1 snapshots. Fifty original input files are hash-checked
before and after the run. The original material World, protocol and JSON binder
must also match their frozen d1 source hashes. Snapshots are restored through
the existing public JSON binder; candidate code is executed only by a fresh
`CandidateProxy` with a 15-second call allowance and 2048 MB limit.

The design uses negative/positive resets and matching-sign constant fields of
magnitude 1, 1.15, 1.3 and 1.5. Recorded times are 0, .5, 1, 2, 3, 5, 8, 12, 20,
40 and 80 seconds. Every one of the 64 model/spec combinations is predicted
twice in separate sandboxes, requiring exact duplicate outputs. All 128
successful executions, coefficients/source bindings and the fixed specs are
durably sealed together before **any new World construction or observation**.
The code never imports or executes a source-fitting routine.

Only then are 16 fresh observations collected for each of the 32 instance/spec
combinations: exactly 512 World calls. Both models use the same readings. Every
call has a fresh private namespace/key; the fixed material implementation adds
independent, untruncated Gaussian noise of known SD 0.006 to each cell. The
original source observations and target observations do not enter the new
statistic. No old target results are read to choose a threshold or new design.

## Statistical derivation and boundary

Exclude time zero from inference, leaving D=8×10=80 cells per model. For a
frozen point prediction p, true cell means μ and n=16 fresh replicates,
sqrt(n)(p−mean(y))/σ is a vector of independent unit-variance Gaussians with
fixed mean sqrt(n)(p−μ)/σ. Consequently

```
Q = n * sum(((p - mean(y)) / sigma)**2)
Q ~ noncentral_chi_square(df=D, nc=lambda)
lambda = n * sum(((p - mu) / sigma)**2)
normalized_true_bias_RMS = sqrt(lambda / (n*D))
```

No parameters are fitted to the new readings, so there is no fitted-parameter
degrees-of-freedom subtraction. The eight original fits and their noisy reset
estimates are held fixed; this is a conditional point-bias estimand, not an
interval for fitting uncertainty. Noise independence is used here because the
pinned material World implementation generates independent Gaussian cells. It
was not assumed for the original fitted residuals in the d1 review.

Use α=.05/8 per model. At the observed Q, `ncx2.cdf(Q,80,lambda)` decreases
with λ. The lower λ endpoint solves CDF=1−α/2; the upper solves CDF=α/2.
When the CDF at λ=0 is already at or below an endpoint's target, that endpoint
is set to zero. Extremely small Q thus yields [0,0]. This includes λ=0 for
the lower-tail observations that an untruncated two-sided inversion would
exclude. Coverage at λ=0 is conservative (1−α/2); for λ>0 the two possible
noncoverage tails still each have probability at most α/2. Bonferroni gives
at least 95% simultaneous coverage for all eight bias parameters even though
models share readings and their statistics are correlated.

CDF values must be finite and within [0,1]. Bracketing has at most 64 doublings
and λ≤1e8; Brent inversion has at most 200 iterations and verifies the final
CDF residual ≤1e-9. Nonfinite, nonmonotone, unbracketed or failed roots fail
closed. The interval is transformed monotonically by sqrt(λ/(16×80)).
`ncx2.interval()` and `ppf()` return observation-space distribution intervals
or quantiles and are not used as noncentrality confidence intervals. See the
[SciPy ncx2 API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ncx2.html).

For the normalized RMS interval [l,u], report:

- u≤1: `compatible_at_declared_tolerance`;
- l>1: `incompatible_at_declared_tolerance`;
- otherwise: `inconclusive`.

The nonnegative moment estimate sqrt(max(Q−80,0)/(16×80)) is descriptive,
not an unbiased RMS estimate or an MLE claim. Even a compatible result concerns
only this program's mean bias on these selected source cells. It cannot establish
model truth, validity of a whole mechanism family or unseen-condition accuracy.

## Runtime and artifacts

The fixed work deadline is 1180 seconds, leaving 20 seconds within the 1200-second
wall ceiling for cleanup and reporting. Each predictor and World call receives
at most 15 seconds and no more than remaining work time. Production is sequential;
completed predictions and readings are journaled using the cleanup reserve even
when they return just after the work deadline. The next call cannot start.
Set BLAS/OMP threads to one. The remote operator should additionally enforce a
1200-second subprocess watchdog, including interpreter startup and any stalled
filesystem/cleanup operations. The eight model fits are not rerun.

The output directory must not exist; it is created 0700. It contains
`summary-public.json` and `private/`. Raw readings, seeds, noise keys, coefficients,
candidate sources, input hashes, prediction seal and chained events stay private.
The public summary uses anonymous instance indices, explicit scripted-reference
identity, model labels, counts, Q/CI/classification and bounded failure categories;
it has no seed, raw readings, fitted coefficients, model API usage or token claims.

All four planned case rows are recorded before work. Any failed prediction,
nondeterminism, observation, statistic or integrity check stops without a retry.
Remaining cases are explicitly unattempted. Partial raw data and computed rows
are retained; incomplete runs clear public classification values and mark
`conclusions_valid=false`. A whole-cohort prediction failure permits zero new
World observations. Existing output paths and old d1/p1/p2 artifacts are never
overwritten.

Run only on the operator's frozen Linux source, for example:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m env.hysteresis_material.source_validation \
  --input /absolute/material-research-driver-reference-d1 \
  --plan /absolute/calibration/material-source-validation/plan.json \
  --output /absolute/new-material-source-validation-output
```

Local tests use numeric arrays, synthetic snapshot JSON and fake executor/World
boundaries; they never start a real World or CandidateProxy. A separate fixed-seed
statistical fixture may use at most 2000 total Gaussian simulations, with exact
coverage counts and Monte Carlo uncertainty saved without reseeding or tuning.
The fixture is a numerical sanity check, not a proof of the coverage theorem.
