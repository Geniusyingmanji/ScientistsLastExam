# Population drift: registered experimental ensemble world

`population_drift` is the thirteenth registered world, available through explicit
experimental selection. It exposes expectation readouts of finite two-type
populations. It is outside completed GPT cohorts and the audited seven-world
null bank; registration does not establish calibrated difficulty or discovery.
This source tree and manifest are operator-owned; `World.describe()` is the
public instrument contract. Native isolation and integration verification are
recorded separately from the frozen scientific checks.

The [separate precision diagnostic](NUMERICAL_DIAGNOSTIC.md) investigates two
retained reference discrepancies. Its narrow result leaves the original
failures and partial numerical verdict intact.

The intended scientific exercise is to use population size, initial composition
and calibrated controls to distinguish accounts of ensemble evolution. Mean
frequency alone may omit informative finite-population variation. An accurate
predictor of a few moments does not establish a unique microscopic mechanism.
Author numerical verification does not establish discovery, difficulty,
contamination resistance or empirical population-genetics validity.

## What the observation means

Each experiment freshly prepares an ideal ensemble of well-mixed populations,
each containing exactly N individuals, k0 of type A. The latent state of each
replicate is a continuous-time Markov chain on counts 0 through N. The instrument
computes expectation functionals of that distribution; it does not draw an
individual random path or a finite collection of paths. It is synthetic, not a
wet-lab experiment.

For x=k/N, the four clean channels are:

| Channel | Definition |
|---|---|
| `mean_A_frequency` | E[x] |
| `mean_mixedness` | E[2x(1−x)] |
| `boundary_A` | P(k=N) at the requested time |
| `boundary_B` | P(k=0) at the requested time |

Mixedness refers to two independent label draws **with replacement within a
replicate**, then averaged over replicates. It differs from
`2E[x](1−E[x])`; the latter misses between-replicate variation. The boundary
channels are **current occupancies**. They are not first-passage probabilities,
permanent fixation or absorption probabilities when mutation permits boundary
exit. With no label mutation the endpoints are absorbing in this model, but that
special case is not used as the general name or interpretation of the channels.

Independent additive Gaussian sensor noise, SD0.002 on each coordinate, is added
after the expectation calculation. It is unclipped, including at time zero, so
noisy probabilities can leave [0,1] and noisy coordinates can violate exact clean
relations. Internal genetic drift is already integrated into the distribution;
it is not this Gaussian noise. There is no finite-replicate/binomial sampling
noise. Repeated calls receive fresh noise only when the owning task assigns fresh
keys.

## Private finite-state model and clock convention

At state i, the private relative A reproduction weight and parent probability are

```
r_i = exp(s + h (2 i/N − 1) + selection_bias)
b_i = i r_i / (i r_i + N − i)
```

The private symmetric newborn mutation probability is m. The additional public
flip probability is a, acting independently after the underlying inheritance
process. Their composition is μ=m+a−2ma. Thus the probability that a newborn is
A is z_i=μ+(1−2μ)b_i. Replacement attempts occur at a fixed Poisson rate N per
time unit, including attempts with no count change. Parent and replaced
individual are sampled independently, so they can be the same individual.
The generator, in row-vector convention, is

```
Q[i,i+1] = (N−i) z_i
Q[i,i−1] = i (1−z_i)
Q[i,i]   = −Q[i,i+1] − Q[i,i−1]
p(t)     = delta_k0 exp(Q t)
```

This fixed-attempt Poissonized Moran convention is an author choice. Some
literature uses unnormalized reproduction rates or other time conventions;
their rate parameters cannot be substituted without conversion. The exponential
frequency-dependent weight and the particular parameter domains are author
assumptions, not estimated biological quantities.

The private generator uses four operator strata: neutral (s=h=m=0), constant
selection (signed s, h=m=0), frequency dependence (signed h, s=m=0), and symmetric
mutation (m>0, s=h=0). Absolute generated s is uniform in [.15,.55], absolute h in
[.45,1.0], and m in [.003,.02]; signs are independently drawn where relevant.
Separate SHA256-derived RNG streams choose structure and parameters without
rejection or outcome-based selection. The broad kernel allows s in [-1,1], h in
[-2,2] and m in [0,.05]. The two neutral development seeds necessarily have the
same clean dynamics and differ only in sensor-noise streams; they do not provide
two distinct neutral mechanisms. This menu and its ranges are absent from the
public description.

Under zero selection, frequency dependence and mutation, up and down rates both
equal N x(1−x). Consequently E[x]=x0 and
E[2x(1−x)]=2x0(1−x0)exp(−2t/N). At N=2,k0=1, the full distribution is
P1=exp(−t), P0=P2=(1−exp(−t))/2. These independently derived identities are
fixed analytic implementation checks.

## Public controls and API

`population_size` is an integer from 2 through 32; `initial_A` is an integer from
0 through that size. `times` contains 1–33 strictly increasing values in [0,60],
with zero optional. Optional `selection_bias` is a constant calibrated log
relative reproduction-weight offset in [-.5,.5], default zero. Optional
`newborn_flip_probability` is the independent newborn flip probability in [0,.1],
default zero. Neither control acts directly on an existing individual's label.
All calls freshly prepare the specified initial population. Sampling does not
change dynamics. Unknown fields, booleans, nonfinite values, noninteger counts,
duplicate/unordered times and oversized lists fail validation.

The clean time-zero vector is the assigned
`[x0,2*x0*(1-x0),1(k0=N),1(k0=0)]`. Reproducing assigned preparation or channel
definitions alone has no mechanism-identification value. The shared policy excludes
assigned initial readouts and applies the public lag described below.

`World(seed)` supplies `describe`, `validate`, `cost`, `run` and `panel`. A run
returns only `axis`, `channels` and `values`. `run(spec, noise_key="...")` adds
reproducible noisy readout for that key, seed and canonical spec. The task must
provide a fresh key for a new measurement. The clean `noise_key=None` route and
private `_operator_stratum` constructor override are for trusted operators only.
Noise keys must be null or text of at most256 characters.

Cost is `8+n_times*ceil((N+1)/8)+ceil(last_time/10)`, at most179. Production uses
at most33 dense matrix exponentials of matrices with at most33 states. Each
requested time is computed from the original delta initial state, ensuring
sample-grid invariance. Guards enforce finite rates, nonnegative off-diagonals,
zero generator row sums, probability mass and probability bounds. The production
kernel does not clip probabilities or renormalize them; floating deviations are
accepted only within declared tolerances. An exhausted work budget or invalid
numeric result fails closed.

`panel(panel_seed, kind, count=8)` constructs parameter-blind specs without
executing them. Kinds are `development`, `conditions` and `interventions`. These
panels do not certify structural holdout or scientific difficulty. Some
coordinates and preparations can be low information.

## Conditional registration and public eligibility

The registered version is `population_drift-0.1.0-experimental`; task catalog
0.1.7 and claim eligibility 0.10 add it. Both arms must select the same time;
readouts must be at least **0.25 replacement-clock units** after preparation.
This inclusive minimum lag was declared before integration smoke tests. It is
an administrative pilot temporal resolution, not a fitted time constant or a
claim of detectability. Time-zero facts cannot receive claim credit. Boundary
preparations remain eligible at later times because the candidate does not know
whether the underlying process permits escape; eligibility never consults the
hidden stratum, parameters, seed or clean response.

The four declared channels and canonical control fields alone enter public
evidence packets, with `times` bound to the observation axis. Prospective
measurements receive nonempty fresh keys from the trusted runner; key reuse is
rejected before World execution. The approved sensor model has additive
Gaussian SD 0.002 and zero noise-mean bias bound. Replicates assess sensor
uncertainty on an expectation readout, not independent realized population paths.
The World object, clean route, parameters, full count distribution, source,
seeds, manifests, reference code and private strata are not candidate payloads.
Native sandbox verification remains a separately recorded integration check.

Eligibility is not an exhaustive independence or relevance test. Channel
identities, duplicate effects and transformations supplied by the instrument
still require scientific evidence review. Prediction scores and paired effect
verification do not certify unique rates, microscopic mechanisms or discovery
depth. This world has no audited null bank or calibrated difficulty claim.

The prototype's original 13 files were saved byte for byte before registration.
Kernel, generator, reference and baseline source remain unchanged; the World
module has only a registration docstring change. The public version changes from `prototype` to `experimental`; since
the declared version participates in keyed observation hashing, noisy streams
belong to that version. The original author/review observations remain bound to
the original prototype source and are never regenerated or substituted.

## Independent review retained at integration

The frozen independent review reports **A partial** (model/numerics), **B yes**
within a bounded synthetic expressibility scope, and **C partial** pending
adapters and native verification. All 17 fixed comparisons of the four public
expectation readouts passed; maximum absolute error was **9.2078e-13**. Two
strict full-distribution DOP853 comparisons remained above the frozen **2e-9**
threshold: **2.84520124e-9** and **3.31985232e-9**. They were not retried or turned
into passes. Agreement with the independently constructed uniformization
reference suggests a reference precision limitation, but does not establish its
exact cause or a global numerical bound.

That review counted **45 solver evaluations and 5 World wrappers**, with four
valid wrappers linked to one solver child each and one validation failure with
no child. There were 54 passing and two failed diagnostics, no unexpected
execution failures, and 93 passing read-only arithmetic checks. All 72 author
baseline predictions were recomputed without new physics: two records improved
15 of 24 queries and worsened nine. The evidence does not establish uniformly
helpful transfer. The author study separately counted 95 solver evaluations and
65 wrappers; integration smoke calls are not additions to either research batch.

The reviewed maximum-row corner included t=0 and therefore 32 positive-time
matrix exponentials. A separate fixed **33-positive-time** integration corner
is reserved for root-owned native verification; it checks execution and bounded
work, not independent numerical accuracy. Read its recorded result before
claiming that path passed. All independent review judgments are same-family and
provisional; a canonical integrity audit and cross-family review were not run.

## Baseline and independent reference

The weak baseline uses only public records. With no records it repeats the known
initial readout. With records it selects the nearest control/preparation feature
vector, interpolates that source's residual from its initial readout, and adds
it to the query's initial readout. It restores the assigned time-zero vector.
It imports no kernel, generator, world or reference and does not fit a private
model. It can transfer badly when size, preparation or controls change; it can
also produce finite predictions outside physical probability bounds. It is an
empirical comparator, not a scientific oracle. All errors and regressions are
retained rather than tuning its behavior to the selected seeds.

`reference.py` reconstructs the offspring event probabilities independently.
It forms the tridiagonal uniformization transition operator P=I+Q/N and evaluates
the Poisson-weighted sum of delta_k0 P^k. It does not import production dynamics,
validation or `expm`. Poisson weights use
`exp(-lambda+k*log(lambda)-gammaln(k+1))`, with lambda=N*t and t=0 handled exactly.
This avoids starting a recurrence from underflowed exp(−lambda) at lambda=1920.
For the largest requested lambda, fixed L=40 defines
K=ceil(lambda+sqrt(2lambda L)+2L). The implementation sums k=0..K, at most2500
terms, and records an upper-tail Chernoff bound and mass diagnostics. For legal
maximum lambda the fixed rule uses2393 terms. There is no outcome-dependent
tail adjustment, clipping or renormalization.

The production matrix exponential and independent uniformization approximate
the same finite-state CTMC solution in floating arithmetic. They are different
numerical implementations of the same assumptions, not independent empirical
evidence that those assumptions describe real populations.

## Fixed author verification and accounting

The external frozen plan specifies eight fixed private development seeds, four
operator strata twice, and **one** scientific batch. It plans95 solver
evaluations, with a hard cap100, 30 process CPU seconds and120 wall seconds.
There are separately65 World wrapper attempts. The 64 valid wrappers each have
one solver child; an intentionally invalid-noise-key wrapper has none. Three
semigroup transition-matrix calls are each charged as solvers. The ledger has
explicit parent-child IDs, so World and its nested kernel are never counted
twice as separate solver evaluations. All production physics fixtures,
independent references and failures count. Eight additional noisy/clean wrapper
sets and eight uniformization references support the fixed development records;
no model API or candidate is called.

Tests include neutral moment/full-distribution identities, no-mutation endpoints,
mutation symmetry, semigroup composition, the legal high-N/control corner,
sample-grid equality, deterministic key replay and fresh sensor noise. Three
injected failures check the work cap, invalid key and nonfinite generator.
Every began/ended event is flushed to an append-only ledger; resource exits retain
partial reports. An exclusive campaign-start file prevents accidental reruns.
No seeds, thresholds, tail limits or difficulty parameters may change based on
observed outcomes. Source hashes are frozen before the batch.

All 0/1/2-record baseline predictions on the three fixed fresh queries are
retained. RMSE/MAE include all four positive-time coordinates, including
low-information coordinates; only assigned t=0 is excluded. These are author
diagnostics, not shared task scores or discovery scores. No improvement threshold
is a pass condition.

The fixed contrasts compare neutral N8/N32 ensembles, and a constructed s=.4
account versus h=.8 at N16,k12 and N16,k4. The latter pair shares the initial
relative reproduction weight at x=.75 only; it is not promised to have the same
finite-time response. Changed preparation can provide a diagnostic contrast,
but no finite collection of contrasts proves unique mechanism identification.

Pure interface fixtures never import or instantiate Kernel/World or call a
reference. They validate specs, compile source, inspect imports/manifests and
exercise synthetic public-record algebra. Run them using a Python environment
with NumPy/pytest, disabling bytecode and pytest caches. The completed author batch is bound to its frozen prototype source; do not
rerun it from the integrated revision. Its historical entrypoint is `python -B -m env.population_drift.calibrate --plan
/absolute/path/plan.json --output /absolute/path/new-run-directory`. Run that
scientific batch only once under the frozen plan. The author cannot independently
review this module.

## Primary sources and scientific limits

[Moran, Random processes in genetics (1958), publisher abstract](https://www.cambridge.org/core/journals/mathematical-proceedings-of-the-cambridge-philosophical-society/article/abs/random-processes-in-genetics/9EEED52D6AE22A026036F32D9B1CA07C)
establishes the individual replacement and mutation setting. Only the abstract
was verified, not inaccessible full text.

[Crawford and Suchard, Transition probabilities for general birth-death processes,
author manuscript](https://arxiv.org/html/1111.6644) supplies the finite
birth–death forward-equation/matrix-exponential framework and discusses how
mutation permits exit from monomorphic boundary states (§§1,2.1,3.3). Its exact
rate normalization differs from this prototype. This module does not implement
the paper's continued-fraction algorithm.

The indexed primary-paper [Fluctuating Selection in the Moran](https://pmc.ncbi.nlm.nih.gov/articles/PMC5340338/)
equation9a supports fitness-weighted parent selection followed by uniform
replacement. Direct PMC access returned a CAPTCHA, so no complete direct access
is claimed. The independent mutation composition and bounded exponential weight
used here are explicit model construction, not inferred empirical parameters.

There is no changing population size within a run, spatial structure, diploidy,
linked loci, recombination, immigration or finite-sample path inference. The
instrument's expectation readout is deliberately simpler than experimental
measurement. Numeric agreement on fixed cases does not certify all legal inputs,
scientific challenge, calibration for real organisms or unique causal discovery.
