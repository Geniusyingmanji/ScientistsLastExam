# First new-world prospective cohort

This is an exploratory research-process pilot, separate from the historical
prediction-score cohorts. It has no aggregate 0–100 score and no automatic
discovery-depth grade. The first five packages are `molecular_forces`,
`climate_response`, `catalyst_aging`, `field_ecology`, and `phase_equilibria`.
Their README files distinguish synthetic mechanisms, public apparatus facts,
legacy-task adaptations and remaining limitations. Numerical correctness is not
difficulty calibration: strong inverse-model baselines remain future work.

## Task-to-apparatus conversion

| Historical discovery task | New package | What changes |
|---|---|---|
| ForceFieldCalibration | `molecular_forces` | Measure energy and forces in chosen geometries; discover quantitative accounts rather than recover a prescribed formula. |
| EnergyBalanceModel | `climate_response` | Select heating histories; reservoir equations/family menu are hidden and alternate predictive accounts are allowed. |
| CatalystDeactivationLab | `catalyst_aging` | Schedule complete fresh laboratories with coupons and calibration controls; history effects and instrument drift can be investigated. |
| OccupancyDetectionDesign | `field_ecology` | Replace a fixed 48-site realization with fresh 64-site panels; investigate habitat and survey mechanisms through repeated sampling. |
| PhaseDiagramDiscovery | `phase_equilibria` | Measure continuous spectra under chosen compositions/preparations/hold times; no exact phase-set answer matching. |

These are reimplementations with documented changes in preparation/noise semantics,
not interchangeable rescoring of old tasks. The new evaluation never checks a
candidate's explanation against a hidden family label or exact golden answer.

## Design frozen before model calls

The authorized design is three fresh hidden instances per environment, with two
independent agent episodes per instance: 30 episodes. Each episode permits at
most 24 GPT-5.6 requests. The new campaign ledger caps all requests, including
failed attempts, at 720. It never reuses or expands the historical ledger.
Instances used in development are excluded; no test outcomes select seeds.
Paired episodes share hidden physics, not analysis state or measurement keys.
The six episodes per environment represent three instance clusters, not six
independent hidden worlds. There are no retries or replacement episodes after
scientific or transport failure.

The model is explicitly `gpt-5.6-sol` (the GPT-5.6 API identity), with medium
reasoning, chat transport, maximum 8,000 output tokens per request, and a
180-second request timeout. Code, public descriptions, prompts, decoding,
episode identities and resource budgets are hashed before execution. Private
seeds, credentials, raw transport and unredacted operator artifacts stay out of
the repository and report.

## Interaction and evidence

`python -m env.research_runner freeze --workflow frontier ...` selects
`sle-research-agent-0.2`; the original comparison workflow remains the default.
The agent uses `experiments`, `analyze`, `preregister`, and `finish` JSON actions.
These are runner actions, not a deployed MCP server. A future MCP transport can
wrap the same trusted actions without exposing simulator internals.

A preregistration retains the existing `rivals` list field for compatibility,
but accepts one predictor under `predictive_validation` or `regime_transfer`.
Two genuine alternatives remain available; `mechanism_discrimination` requires
two. Each predictor is run twice in a fresh isolated process, and its code,
complete output, scalar readout, tolerance and replication plan are durably
sealed before the independent test observations. No target refitting is allowed.

The scalar readout is a predeclared weighted sum of channel-scaled measurements.
Its fixed uncertainty radius is the declared bias bound plus a conservative
Chebyshev radius. Within-experiment dependence is allowed. Replicates and
separate preparations must be independent. A fixed alpha budget of 0.05 is split
over the maximum three tests **within one episode**. This is not a simultaneous
95% guarantee for all 30 episodes. The report is descriptive; it does not pool
selected positive tests into a model-wide statistical claim.

For one predictor, outcomes are:

- `scoped_predictive_adequacy`: the whole uncertainty interval is inside its
  predeclared tolerance band.
- `candidate_refuted`: the intervals are disjoint.
- `inconclusive`: neither condition holds. Nonrejection is not adequacy.

These outcomes concern the selected scalar readout, not the whole returned
trajectory or a unique mechanism. A wide tolerance is visible in the result.
Scientific review assesses informative test selection, known instrument
identities, alternative explanations, scope, and how failures changed the
model. A revision must cite a completed counterexample, use changed predictor
source, cite the counterexample observations and choose a fresh target. The
old sealed failure is retained without forcing its predictor into the next test.

`frontier_semantics.py` identifies measured conditions per readout. Changing
unrelated molecular batch rows, later climate forcing, later catalyst events,
or other surveyed habitat rows cannot make an observed readout unseen. Empty
holders and catalyst blanks are reference controls, not targets. Static index
zero and habitat zero are legitimate measured coordinates. These rules remove
specific aliases; they do not prove scientific novelty or exhaust every
mathematical equivalence.

## Preparation semantics

Catalyst history is the complete ordered schedule **inside** an experiment;
each repeated call starts a fresh laboratory. It is not a persistent laboratory
session or the legacy concurrency task. Field ecology samples independent new
64-site populations per habitat stratum and call, preserving occupancy across
visits within a panel. Its measurement error is a correlated discrete fraction,
with unbiased marginal standard deviation at most 0.0625, not Gaussian noise.
The other four apparatuses use declared independent, unclipped Gaussian noise.
Finite phase annealing does not certify thermodynamic equilibrium.

## Scope of integration

All five packages implement the shared World contract and are explicitly
registered as experimental. Their prospective runner and readout semantics are
the supported evaluation path for this cohort. Historical paired-claim scoring,
historical evidence-packet schemas, and historical apparatus-remapping profiles
are not silently promoted to these new worlds. The new report uses a separate
allowlisted export with linked chronological evidence. Hash-chain replay checks
artifact consistency; operator chronology additionally relies on the retained
trusted execution record and frozen source archive.

Report API completion, scientific test outcomes, and reviewed findings
separately. Preserve incomplete, invalid and infrastructure-failed episodes in
the denominator. Any depth assessment is a qualified evidence review, never a
simulator-family label match or a claim of contamination-proof novelty.

## Engineering checks for the frozen first run

The run freezes commit `5e59b3ebc9526a34030ffc6d556abf430a38d42d`.
Local checks passed 1,830 tests and 42 subtests, with six platform-dependent
skips. On g450/Python 3.8, the frozen five-world, research-runner and affected
compatibility suite passed all 358 tests, including the real isolated
single-predictor workflow. An earlier native security/integration pass completed
251 tests without failures.

A broader native historical-world sweep stopped at 747 passes and three errors:
two optical semantics tests and one orbital strong-reference test require
`math.nextafter`, absent from Python 3.8. Those test files are unchanged from
the prior commit. This is retained as a historical test-runtime limitation,
not presented as a complete native full-suite pass or a new-world failure.


## Separate interface-repair cohort (v0.3)

The original 30 episodes closed after 138 requests: six completed, 18 terminated
on invalid actions and six failed on transport. They remain immutable and retain
their original denominator. The public instructions omitted the eight-spec batch
cap; phase and other valid scientific plans consequently stopped before sampling.
An opt-in `--workflow frontier_repair` (`sle-research-agent-0.3`) makes driver
limits, action templates and the existing uncertainty calculation explicit. It
validates whole experiment batches and preregistration schemas before dispatch.
Schema-only errors return bounded public feedback and consume an ordinary model
turn. Once a predictor or measurement is dispatched, failures remain terminal.
The statistical rules, noise models, tolerances and per-episode alpha are unchanged.

Before any v0.3 call, freeze 30 new episodes (five worlds × three new instances ×
two repeats), each capped at 19 requests: at most 570 more requests. They use the
same global 720-request ledger, with 138 already spent and at least 12 reserved
unused; no automatic replacement or retries. New instance seeds exclude all
original and development instances. This is a separately sampled exploratory
cohort, not a controlled estimate of improvement over v0.2: prompts, schema
recovery and request cap changed. Original and repaired results must be reported
separately. No selected successful episode replaces an original failure.


## Closed execution totals

The repaired cohort used 401 requests: 29/30 episodes submitted research reports,
and one stopped after a revised candidate program failed during prediction.
There were 22 pre-dispatch schema rejections; their requests remained charged.
Seventy completed prospective tests yielded 50 scoped adequacy, four scoped
candidate discrimination, six single-candidate refutations, three both-candidate
refutations and seven inconclusive results. Fifteen tests supplied counterexamples
to 18 candidate instances. These are descriptive counts of selected tests, not
independent discoveries or a scientific-success rate.

Both cohorts together used 539 of 720 requests, including six transport failures;
181 requests remain unused. No failed episode was replaced. The final repaired
cohort's 29/30 submission rate must not be interpreted as a causal improvement
from the original 6/30: instances, instructions and turn limits changed.

The v0.3 focused local suite passed 129 tests (four platform skips); the same
native Linux suite passed all 133 tests, including real isolation checks. These
are engineering evidence; they do not calibrate scientific difficulty.
