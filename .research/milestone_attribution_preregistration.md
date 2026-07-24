# MA1/E52 milestone-component attribution micro-pilot

Status: protocol frozen for implementation; no agent milestone effect has been estimated.

Date: 2026-07-24 UTC

Initial task families:

- `ChemicalKinetics/ReactionMechanismFitting`
- `HeatTransfer/ConvectionDiffusionOpt`

## Question and evidence boundary

The experiment asks which edit, newly acquired observation, or interaction caused a selected
parent-to-child improvement. A chronological diff, component-score increase, or post-hoc narrative
does not identify that effect.

The pilot may establish a bounded causal contribution under one frozen task, parent state,
evaluator manifest and world panel. It cannot by itself establish a novel chemical/transport
mechanism, wet-lab or continuum-device validity, autonomous discovery, or a population-level model
capability.

Existing GPT-5.5 normal budget-one and budget-three runs for both initial tasks contain no positive
combined-score jump, and all three Convection conditions remain at zero. Reaction's selection-blind
budget-three open-loop batch contains one independently generated frozen-baseline candidate scoring
`0.342579`; because later proposals never inherit its artifact or feedback, it is not an iterative
feedback milestone. It also has development and heldout false-discovery rate `0.5`, so it fails the
planned science attribution gate. It may be retained only as a bundled retrospective analyzer smoke.
Existing truth-blind calibration policies are positive controls for the replay/analyzer:

- Reaction's two-temperature sparse fitter reaches combined score `0.4818355` but has development
  and heldout misspecified-world false-discovery rate `0.5`.
- Convection's near-symmetric single-experiment policy scores `0`, while adding the off-axis
  experiment with the same fitting/design pipeline scores `0.8956051473`.

If a new trajectory contains no eligible jump, the result is `eligible_milestones = 0`; a classical
control or hand-built witness must not be relabeled as an agent breakthrough.

## Frozen hypotheses

- `H32a`: a preregistered full child retains a domain-material improvement over its parent on the
  sealed vector outcome, not merely on the visible scalar.
- `H32b`: at least one component-only or leave-one-out contrast localizes a material share of that
  improvement; otherwise the jump remains bundled/non-attributable.
- `H32c`: for at least some milestones, the effect of two key components is non-additive.
- `H32d`: when a child both acquires observations and changes its method, a data-by-method factorial
  separates evidence gain from method gain.
- `H32e`: an apparent improvement that raises false discovery, violates a hard gate, or fails fresh
  confirmation is not a validated scientific insight.

These are hypotheses, not expected conclusions. Null, harmful and non-separable results are retained.

## Milestone sampling frame

A trajectory enters the sampling frame only if all of the following are available and hash-bound:

1. trusted parent and child artifacts plus their exact executable environments;
2. an append-only observation/result ledger identifying evidence available to each artifact;
3. one versioned evaluator/selector manifest and immutable development/sealed world panels;
4. complete parent-child ancestry, timestamps, budget and failure records;
5. a fresh confirmation reserve unused by search, milestone selection or component construction.

Before inspecting component replay outcomes, enumerate every adjacent valid parent-child pair and
apply the following eligibility rule:

- child visible development improvement exceeds the task's predeclared material `epsilon`, or its
  claim state changes among `propose/confirm/revise/retract/abstain`;
- artifacts differ by content hash and the child is executable;
- the event is not solely an infrastructure retry, duplicate evaluation or selector-only change;
- parent and child are both evaluable on the same frozen panels.

Use all eligible milestones when feasible. Otherwise select a seeded random sample stratified by
task and early/middle/late budget phase. Do not select by sealed score, narrative appeal, diff size,
or whether a clean component explanation is later found. Publish eligible, sampled, excluded and
non-separable counts with reason codes.

## Factor construction

Classify changed behavior before evaluating treatments. Each executable change belongs to one of:

1. `D`: observation/data acquisition or preprocessing;
2. `M`: scientific model, mechanism, equation or structural assumption;
3. `I`: estimation, uncertainty, support selection or refusal logic;
4. `O`: numerical optimizer/search or downstream design policy;
5. `P`: serialization, presentation or postprocessing that should not alter scientific content.

Store a machine-readable mapping from changed functions/files and evidence events to these factors.
Classification uses source semantics and dependency information without sealed outcomes. Ambiguous
changes retain all plausible labels and enter a sensitivity analysis.

For each milestone construct from the frozen parent:

- `parent` and independently rebuilt `full_child`;
- every dependency-closed component-only variant;
- every dependency-closed leave-one-component-out variant;
- rollback of the attributed component on the full child;
- a complete `2×2` for two key factors chosen by a predeclared task rule, not their observed effect;
- when `D` changed, `old_data/old_method`, `new_data/old_method`, `old_data/new_method`, and
  `new_data/new_method`.

For Reaction, the planned factors are assay plan (`D`), sparse reaction-support selection (`M`),
Arrhenius parameter refit plus uncertainty/refusal (`I`), and any numerical search change (`O`).
For Convection, they are midline versus off-axis experiment design (`D`), five-coefficient transport
model/inference (`M/I`), source-layout optimizer (`O`), and null/misspecification refusal (`I`).

Every variant is rebuilt from the parent rather than by successively editing another treatment.
Untouched code, evidence access, dependencies and environment hashes must match. A patch that cannot
run without another component is `non_separable`; its invalid score is not interpreted as a zero or
negative component effect. Dependency bundles may be analyzed as a separately named compound factor.

## Evaluation and outcomes

Evaluate treatments blind to their labels on the same immutable panels. Deterministic evaluators run
once after a replay determinism check. Stochastic evaluators use common random numbers and at least
five preregistered seeds per variant; seed repeats quantify evaluator uncertainty but do not create
independent milestone units.

Primary vector outcomes are:

- visible development and sealed/heldout score;
- mechanism/parameter/support recovery;
- prediction/extrapolation and downstream design utility;
- supported-world claim coverage;
- null/misspecified correct refusal and false-discovery rate;
- hard validity/feasibility, runtime, experiment units and trusted-oracle cost.

Reaction additionally reports support F1, rate-curve quality and interpolation/extrapolation.
Convection additionally reports parameter/mechanism quality, nominal/robust design quality and the
development-to-heldout gap. Aggregate score is retained but cannot override a failed hard gate.

The one-shot fresh confirmation reserve is evaluated only for a component attribution that passes
the sealed materiality and reliability gates. It never influences milestone or factor selection.

## Estimands

For outcome `Y`, report paired effects on common worlds/seeds:

- full-child effect: `Y(full) - Y(parent)`;
- component-only effect: `Y(component) - Y(parent)`;
- leave-one-out necessity: `Y(full) - Y(full-minus-component)`;
- rollback effect: `Y(full) - Y(rollback)`;
- two-factor interaction: `Y11 - Y10 - Y01 + Y00`;
- data-method interaction using the same formula on the data-by-method factorial.

Report the full vector and confidence interval/paired bootstrap distribution. A retained-effect ratio
may be shown only when the full-child denominator is material and sign-stable. Do not truncate harmful
effects or normalize a non-separable treatment to zero.

The top-level statistical unit is an independently selected parent milestone or procedural-world
lineage. Worlds and common-random-number seeds are paired repeated measures. For more than one parent,
use a hierarchical task/parent model or parent-level bootstrap; never treat every seed-world replay as
an independent breakthrough. Correct the preregistered family of component/interactions or present
simultaneous intervals; exploratory contrasts are labeled as such.

## Decision and wording rules

An edit/evidence component receives bounded causal-attribution language only if:

1. the full child materially exceeds the parent;
2. component-only, leave-one-out, rollback or interaction evidence points consistently to it;
3. the effect survives sealed or fresh worlds;
4. hard validity does not worsen and false discovery stays below the task gate;
5. the treatment is executable, dependency-closed and evidence-matched.

If only the full bundle works, report `bundled improvement; component attribution unresolved`. If new
data explain the gain but the method contrast does not, report evidence acquisition rather than method
discovery. If development rises but sealed/mechanism does not, report proxy optimization. If no agent
milestone qualifies, report the empty sampling frame without substitution.

## Implementation definition of done

- A hashed cohort manifest freezes trajectories, milestones, world panels, seed schedule and material
  thresholds before replay outcomes are read.
- A factor manifest records changed evidence, code, dependencies, component labels and ambiguity.
- The replay builder proves each treatment starts from the same parent and records non-separability.
- Synthetic tests cover additive, interacting, harmful, invalid and non-separable changes.
- Analysis reproduces paired estimands, hard-gate logic, multiplicity and failure-inclusive counts.
- The report binds every artifact/evidence/evaluator hash and states whether it is positive-control,
  micro-pilot or agent-milestone evidence.
