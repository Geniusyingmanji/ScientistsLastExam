# Adding a computational science world

An environment provides repeatable interventions and measurements. A task asks
what can be learned from them. A numerical score measures predictive behavior;
an evidence review assesses what the investigation established. Keep these three
contracts separate when extending SLE.

## Package and information boundary

Create `env/<name>/` with `world.py`, `world.json`, `README.md`, examples and
tests. The experimental worlds also separate `protocol.py` (public controls and
validation), `kernel.py` (private dynamics), `baseline.py` (public-data inference)
and `SCIENTIFIC_NOTES.md` (operator assumptions and limitations). This separation
makes review easier; filesystem isolation still comes from the shared runner.

The operator owns simulator source, instance seeds, structures, parameter values,
noise keys, evaluation panels and clean outputs. The candidate receives the
public apparatus description and observations obtained through its budgeted
actions. Do not mount a new environment's source into analysis or prediction
workers. Use the existing isolated analysis and prediction services.

The batch interface resets preparation at each query while keeping the hidden
instance fixed. An experiment can contain a history or timed interventions.
Persistent cultures, evolving inventories or irreversible experiments require an
explicitly different stateful protocol; do not silently simulate persistence
through a global cache. The original microecology CLI has its own persistent
laboratory interface.

## Scientific design before API trials

Write an operator plan before collecting development results:

1. Specify observables, units, legal controls, reset/event semantics, noise and
   finite numerical-work limits. Distinguish assigned values from observations
   whose response depends on unknown dynamics.
2. State the questions the apparatus can address. Include a concrete ambiguity:
   two accounts that agree under a restricted design and a permitted intervention
   that can separate those particular accounts. Record cases that remain
   unidentifiable within the budget.
3. Choose development instances and numerical checks before looking at results.
   Bound the number of trajectories, fitting attempts, CPU and wall time. If
   generation strata matter, balance using private labels before observations;
   these labels are not answers supplied to a grader.
4. Use an analytic limit or an independently implemented numerical reference.
   Check event boundaries, extreme legal controls, observation resolution and
   discretization error relative to measurement noise. Retain failed checks and
   record why a later implementation or plan differs.
5. Measure useful baseline behavior on fresh queries. Record exactly what a
   baseline knows: empirical records, supplied equation families, parameter
   bounds, fixed experiment design or author knowledge. Keep strong authored
   references separate from candidate/model results.

A low nearest-neighbor score does not establish scientific difficulty. A high
author-informed score shows learnability under that information and design,
without proving that an agent can find the design or infer the model family.
Likewise, a sampled class name need not uniquely describe the mechanism at every
control setting. Scope conclusions to observed behavior.

Random parameters and renamed channels prevent literal reuse of one numerical
answer. They do not establish resistance to training contamination. New
structures, private instance generation and prospective intervention tests make
memorized descriptions less sufficient; contamination resistance still requires
separate evidence. Public simulator code can itself become training material.

## Current shared integration points

The pilot uses explicit adapters. Register a world only when each applicable
adapter is implemented or deliberately rejects it. There is no silent default
noise, initial state, timing rule or candidate presentation.

| File | Addition or check |
| --- | --- |
| `registry.py` | Name, module export and experimental status. `world.py` must export `World` and `baseline`. |
| `task_profiles.py` | Explicit applicability; revise the catalog without rewriting existing profile science. |
| `claim_semantics.py` | Observable channels, axis and minimum lag, events and assigned/clamped values as appropriate. |
| `prospective_runner.py` | Observation-noise and clipping-bias contract. A new noise model needs a justified statistical bound. |
| `calibration.py` | Public initial-value semantics, or an explicit absence of an assigned initial state. |
| `evidence_packet.py` | Allowlisted public spec fields and axis; unknown worlds fail closed. |
| `presentation_profiles.py` | Audited input bindings if shared catalog/policy metadata changes. Preserve old projected scientific content. New apparatus-only projections need separate review. |
| `prediction_semantics.py` | Optional assigned-cell diagnostics. Unsupported semantics remain explicitly unavailable. |
| `README.md`, `TASKS.md` | Public coverage, status and applicability. |

The paired-claim timing policy and prospective comparison protocol are different
contracts. A timing filter does not prove that a proposed contrast is meaningful.
In particular, successful discrimination between a correct program and a program
that mishandles a publicly assigned value is weak scientific evidence. Document
this distinction; do not turn a protocol verdict into a mechanism certificate.

Do not append a new world to an old cohort or calibration manifest. Old results
retain their original source, presentation, budgets and scoring. Add a new
integration test that checks public-description invariance across hidden
instances, baseline shape, timing semantics and relevant archive adapters.
Retain existing prompt fingerprints after normalizing only the declared catalog
or policy revision fields.

## Task and evidence design

The existing orientations are open discovery, mechanism discrimination and regime
transfer. They use the same apparatus. A useful task can expose a question without
naming a phenomenon that the agent must report. For example, a circular orbit can
fit several force laws; a history-dependent response can arise from slow dynamics
or multiple stable states. Let the agent choose and justify an informative test.

The research runner can freeze two executable point predictors, a contrast,
tolerances and replication count before collecting fresh observations. It can
retain a refuted program and test a revision on a new condition. Both-refuted and
inconclusive outcomes are legitimate research records. Choosing the nearer of
two predictions is not enough: a task must allow both to fail.

Check whether the alternatives were plausible from their source evidence.
Preserve source residuals and fit failures. Distinguish a fitted point predictor
from its entire parameterized family, fresh-readout uncertainty from parameter
uncertainty, and finite-horizon behavior from an asymptotic law. An unaltered
model predicting several new conditions demonstrates transfer; locating an
empirical validity boundary requires additional evidence.

Use [DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md) for exact manual evidence anchors
and six separate dimensions. Reference checks and recorded ordering are
mechanical; meaningful rivals, explanatory scope and scientific conclusions
remain review judgments. Preserve reviewer disagreement. Do not retroactively
apply a new requirement to a frozen model score.

## Development status and release

- **Prototype:** isolated package and bounded development evidence, not selectable
  through the shared registry.
- **Experimental:** explicit selection works, relevant shared adapters and
  numerical checks exist, limitations are documented. This is not membership in
  a formal model evaluation.
- **Evaluated:** a named, frozen model cohort has raw records and explicit
  denominators. Keep model completion, infrastructure completion, prediction and
  scientific evidence separate.

These are descriptions of available evidence, not automatic quality grades.
Before comparing research budgets, calibrate baseline headroom, failures,
prospective evidence and uncertainty. Freeze matched instances and evaluation
panels while varying one resource or interface factor; record independent
experiment noise explicitly. Run from immutable source and one campaign ledger,
preserving failed and incomplete instances. See [PAIRED_DESIGN.md](PAIRED_DESIGN.md).

Publish aggregate results and disclosed limitations. Keep seeds, future targets,
raw private manifests and credentials in operator artifacts. A sanitized HTML
progress report is produced by `env.progress_report`; ordinary episode reports
and scientific receipt archives are private evidence.
