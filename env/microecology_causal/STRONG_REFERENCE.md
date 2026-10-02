# Author-informed reference — trusted operator material

This diagnostic knows the **three-structure menu, exact ODE family, fixed carbon
yields, temperature law, all nominal kinetic values, and the ±12% parameter box**.
It does not know which structure, numerical parameters, or anonymous peak mapping
were sampled for an instance. It is not autonomous discovery, an agent-equivalent
baseline, or evidence that the public task is trivial without data. The original
registered empirical baseline is unchanged. Do not attach this document or this
reference's source/results to a candidate's public problem.

`strong_baseline.fit(records, limits=...)` accepts only 1–16 public records plus
reducible compute ceilings. Each record contains `spec`, `observation` and
optional public `id`/`cost`; extra fields, hidden annotations, nonfinite numbers,
invalid axes/shapes and private payloads are rejected. The fitter never receives
or constructs a World, instance seed, private stratum, true parameter values,
private peak indices or evaluation panel. It has no file, network, random seed
generator or parameter-sampler access. Explicit `Kernel(Parameters(...),
structure)` calls implement its declared model-family prior.

There are 18 discrete possibilities: three structures times six permutations of
the three public peak labels. Eleven continuous parameters are active in the
inhibitory-feedback structure. The other two structures have ten active
parameters; their unused consumer-inhibition constant stays at its nominal value
and is not reported as identified.

The fixed bounded algorithm is:

1. Evaluate all 18 nominal-parameter candidates on the same records.
2. Within each structure, retain only its best nominal peak mapping.
3. Run at most three bounded local least-squares fits, one for each retained
   mapping. Optimize multipliers inside [0.88,1.12]. Keep the best fully evaluated
   model even if a limit interrupts an optimizer.

The objective compares observations with the expected zero-clipped Gaussian
readout, `x*Phi(x/sigma) + sigma*phi(x/sigma)`, and weights residuals by the public
noise standard deviations. This is noise-weighted least squares, not an exact
censored likelihood, Bayesian posterior, or statistical structure certificate.
Returned predictions represent the latent clean concentrations for comparison
with the existing clean-target prediction metrics.

Defaults per fit are **60 CPU seconds, 90 wall seconds, 234 residual attempts**:
18 screens plus up to 72 attempts in each of three local fits. Finite-difference
Jacobian calls count as attempts, including attempts interrupted before all
records complete. SciPy also has a 12-iteration-function-evaluation cap per local
fit; the explicit callback counter is the binding total-call safeguard because
SciPy's `nfev` does not count every numerical-Jacobian call. Remaining CPU/wall
time is divided over the remaining structure fits. Limits may be lowered, never
raised through this API.

Time checks occur before each trajectory and event-delimited ODE segment. They
are cooperative: one bounded numerical solve may finish after its deadline.
The report records actual process CPU/wall time rather than claiming a hard
real-time bound. It also records screening coverage, attempted/completed
residuals, trajectory attempts, optimizer stop reasons, convergence, local best
parameters/loss and Jacobian rank where available. Rank or convergence alone
does not establish practical identifiability. If even screening is interrupted,
partial coverage and a missing/best-available model remain explicit.

Only one nominally selected peak mapping per structure is optimized. That
heuristic can miss a mapping whose parameters require more adjustment. Local
optimization can miss the best fit or hit a parameter bound. Exact restricted
observational equivalences remain possible: for example, a starvation trajectory
can fit a death constant while saying nothing about the full interaction
structure. No extra restarts or unbounded computation are added after seeing a
failure.

## Fixed development calibration

`strong_calibration.source_specs()` returns a fixed, versioned nested sequence
of 16 legal protocols, identical across instances. The first eight include four
inoculum backgrounds, depletion of each anonymous fraction, and a nutrient feed.
The next eight add depletions under another inoculum background, temperatures,
initial nutrient/inoculum variations, and a temperature-switch history. This is
an **author-informed source design**, using knowledge of useful interventions;
it is not an adaptive agent's discovery process or a prescribed public answer.

Only development seeds **7, 46, 1439, 8743**, and source budgets **8 and 16**, are
accepted. Noise keys make the first eight noisy records identical between the
two budgets for a given development instance. Fit jobs are independent; no fit
is warm-started from the other budget or from private labels. No formal seed or
old benchmark report is used.

The operator constructs public source records and calls `fit(records)`.
`fit-private.json` is written, flushed and hashed **before** new disjoint
`conditions`/`interventions` panels are generated. Only then does the operator
compute clean test outcomes and compare the frozen reference and existing
empirical baseline, both using the same source records. The private report's
actual-structure annotation is accessed only after freezing the fitted result.
Private source/fit hashes are checked again after evaluation. The separate
fitter never sees these evaluation objects or files.

Full calibration is intended for the frozen remote CPU source, not an unbounded
local search:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m env.microecology_causal.strong_calibration \
  --seeds 7,46,1439,8743 --budgets 8,16 --workers 2 \
  --cpu-seconds 60 --wall-seconds 90 --residual-attempts 234 \
  --panel-count 4 --output /private/calibration/microecology-causal-author-reference-v1
```

There are eight fits, at most 480 nominal fit CPU seconds in total, plus source
generation and frozen evaluation overhead. Use at most four worker **processes**;
LSODA is not reentrant across concurrent threads. The default is two processes.
The new output directory is mode 0700 with private files mode 0600 and no
overwrite. The command has no model API or ledger path.

Private output retains source records, fitted parameters/peak mappings/labels,
all optimizer diagnostics, frozen-fit hashes and raw evaluation traces. Public
summary contains only budgets, timings, validity/failure counts and errors/scores
by condition/intervention and record budget. Job failures keep planned experiment
counts and unavailable counts. Prediction failures score zero within completed
job reports; undefined errors remain null. Mean error/score denominators are
explicit, and failed jobs are never silently treated as completed calibration.

The prewritten operator plan is stored under central
`calibration/microecology-causal-strong-reference/analysis-plan.json`. A local
one-residual plumbing smoke was kept separate from the full remote calibration.

The frozen `5acae27b` source then completed all eight planned fits on Linux.
Every fit used all 234 residual attempts and retained its best available model;
**none met the optimizer convergence criterion**. There were no job failures or
invalid held-out predictions. Actual fit CPU time ranged from 22.07 to 48.07
seconds. No retry or larger search was added after seeing these outcomes.

| Source records | Query type | Author reference mean NRMSE | Author reference mean prediction score | Empirical baseline mean score |
|---|---|---:|---:|---:|
| 8 | Conditions | 0.0005512 | 99.4508 | 14.4370 |
| 8 | Interventions | 0.0004797 | 99.5218 | 9.0637 |
| 16 | Conditions | 0.0004066 | 99.5947 | 14.4912 |
| 16 | Interventions | 0.0004083 | 99.5929 | 9.0704 |

Each row contains 16 queries from four reused development instances. These are
prediction-only diagnostics, not the pilot's prediction-plus-claim composite or
an independent estimate of agent ability. The 8/16 comparison is not a model
scaling result. Accurate frozen predictions establish learnability for this
small sample under the declared strong prior and fixed source design; optimizer
nonconvergence and parameter uncertainty remain explicit limitations.

The private result archive SHA-256 is
`32ec667b3ad89e0e0784091f7decef59442317f44ae768df83e4fe97a91bab15`.
It retains all fits, source observations, queries and failures without putting
raw calibration records in the repository or public progress report.

```sh
python -m pytest env/microecology_causal/tests/test_strong_baseline.py -q
```

Good future fits would demonstrate learnability under a strong correct family
prior and fixed author-chosen experiments. Poor fits or nonconvergence would show
limitations of this bounded estimator/design, not prove fundamental task
difficulty. Neither outcome establishes autonomous mechanism discovery.
