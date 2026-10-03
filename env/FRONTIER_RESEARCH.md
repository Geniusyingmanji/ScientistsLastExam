# First new-world prospective cohort

This is an exploratory research-process pilot, separate from the historical
prediction-score cohorts. It has no aggregate 0–100 score and no automatic
discovery-depth grade. The first five packages are `molecular_forces`,
`climate_response`, `catalyst_aging`, `field_ecology`, and `phase_equilibria`.
Their README files distinguish synthetic mechanisms, public apparatus facts,
legacy-task adaptations and remaining limitations. Numerical correctness is not
difficulty calibration: strong inverse-model baselines remain future work.

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
