# Frontier-Science plan gap audit

Audit date: 2026-07-19 (UTC), with the experiment roadmap extended after repeated full-text
EdgeBench comparison and the task inventory updated on 2026-07-25 through the
ElectrolyteConductivityDesign-v1 real-data replay.
Evidence base: `literature_matrix.md`,
`science_experiment_plan.md`, current source/tests, and the dated artifacts in `experiments/`.

## Executive decision

Keep the breadth-first expansion freeze: improve the admissible count by rebuilding high-value
quarantined packages one at a time, not by adding unchecked directories. P0 integrity and a
narrow P1 certification gate are now implemented, but the project has not passed the empirical
evidence gate needed for a benchmark release. The defensible current description is:

> A research prototype for cross-domain, executable, budget-constrained scientific generative
> optimization, with a seven-task internally certified core and a larger
> quarantined/candidate inventory.

Do not call simulator-score improvement “autonomous scientific discovery.” Reserve that claim
for work that separately demonstrates feedback learning, mechanism recovery, hidden-shift or
physical validation, and auditable claim–evidence provenance.

## As-built matrix

| Capability | Current status | Evidence | Remaining acceptance criterion |
|---|---|---|---|
| Candidate/oracle isolation | Implemented | Clean-revision security v27: 18/18 adversarial tests; Bubblewrap, no network, read-only mounts, resource/seccomp limits, typed RPC, fresh multi-world sessions and candidate-exception sanitization | Reproduce in clean Linux CI; document portability/non-Linux behavior |
| Fail-closed trusted metrics | Implemented | Clean-revision 55×2 v33: 55 deterministic, 55 valid, 55 fail-closed and zero infrastructure failures | Repair or quarantine every future invalid candidate oracle before certification |
| Task admission policy | Implemented, narrow | Trusted certification v44 records 7 certified / 34 candidate / 14 quarantined over 55 packages; ElectrolyteConductivityDesign passes exact source rebuilding, secure-baseline equivalence, physical identities, independent Arrhenius recalculation, assay isolation and confirmation separation | External electrochemistry/evaluator review, server-held formulations, new batches and complete-cell validation remain incomplete |
| Scientific validity of inventory | Audited, sparse | All original 50 packages passed adversarial admission; later substantive rebuilds and additions bring inventory to 55 and leave 41 internally admissible packages | Add approximately 9 net admissible tasks to reach about 50; hidden/generated instances and shortcut analysis remain mandatory |
| Unified trajectory/accounting | Implemented, protocol-smoked | Clean-revision two-seed baseline smoke; trajectory schema v2, hashes, AUC over `budget_units`, separate `oracle_calls`, wall/token/cost, seed, checkpoint/resume | Validate nonzero-budget schema-v2 artifact replay in CI and version future changes |
| Feedback controls | Implemented; strict pilot run | None/shuffled prompt-metric modes disclose true-score selection; strict selection-blind freezes parent/metrics; four-task n=3 pilot has no direction-stable lift and is not token-matched | Run token-matched ≥10 paired seeds with score-only, delayed/replayed and strict open-loop controls |
| Evaluator-only metric sealing | Implemented and integration-verified | Closed search-visible allowlist; search-state redaction/hash-keyed sidecars; candidate-controlled exception text mapped to a finite label-blind taxonomy; current 244-test suite; clean pinned OpenEvolve/TreeQuest/Shinka no-leak report `aff026d` | Extend from baseline smoke to nonzero-budget upstream runs before comparative claims |
| Official OpenEvolve adapter | Implemented, trusted baseline smoke | Explicit 0.2.26 adapter; clean-revision secure baseline passed under Python 3.10 | Run nonzero-budget/checkpoint integration and multi-seed study |
| TreeQuest AB-MCTS | Implemented, trusted baseline smoke | Real TreeQuest AB-MCTS-A ask/tell adapter; clean-revision secure baseline passed under Python 3.12 | Run nonzero-budget/checkpoint integration and multi-seed study |
| ShinkaEvolve | Implemented, trusted baseline smoke | Official runner/database adapter at pinned commit; clean-revision secure baseline passed under Python 3.10 | Run nonzero-budget/resume integration and token accounting audit |
| Classical/domain baselines | Partial | NMR, HeatExchanger, Reaction, Gravity, Ocean, Radiative, LowThrust and Climate rebuilds have truth-blind domain baselines exposing reconstruction/proxy/prediction, terminal-feasibility, experiment-design or mechanism/refusal gaps | Add random/quasi-random plus BO/CMA-ES/DE and one domain heuristic for each meaningful task family |
| Multi-seed benchmark evidence | Missing | Keyless GPT-5.5 Responses path is operational; 57 trusted normal single-run conditions cover 29 tasks and a separate four-task n=3 control pilot is negative/inconclusive | Certified-core and science-subset reports with paired uncertainty and portable raw trajectories |
| Multifidelity/Pareto | Candidate-level | HeatExchanger-v2 implements proxy/exact Pareto archives, measured false promotion and physical shifts | Add independent high-fidelity review/replication and at least one certified multifidelity task |
| Feedback learning claim | Negative pilot only | A strict open-loop control and three-replicate four-task pilot are complete; no direction-stable visible or sealed lift, and normal uses more tokens | Token-matched preregistered ≥10-replicate study with delayed/replayed and score-only controls |
| Mechanistic discovery | Candidate-level | ActiveLaw, NMR, Reaction, Gravity, Ocean, Radiative and Climate tasks separately score mechanisms, prediction, coverage, hidden shifts, false discovery and refusal | Add paired repeated studies, harder regimes and independent scientific validation |
| Validation/distribution shift | Calibration-level | Nominal/robustness and prediction/mechanism gaps recur across control, design and inverse tasks; ElectrolyteConductivityDesign additionally reaches `0.878/0.926` visible development/held-out optimization and `0.826/0.896` discovery-repeat robustness while all selected untouched-repeat confirmation axes remain zero | Paired repeated hidden-shift studies plus post-commit independent repeats, new batches/labs, higher-fidelity or physical confirmation and abstention cases |
| Research-integrity track | Partial | Immutable candidate/parent hashes and artifacts | Hypothesis–test–evidence records, failed branches, claim links and calibrated refusal |

## What the latest literature changes

The literature matrix separates four capabilities that the old plan collapsed:

1. **Optimization.** Frontier-Eng, AlphaEvolve, FunSearch and ShinkaEvolve justify executable,
   verifier-guided search, but also require real population/tree baselines and deep trajectories.
2. **Feedback learning.** LEAP and lab-in-loop feedback results make best-so-far AUC and
   shuffled/no-feedback controls necessary; terminal score alone cannot show learning.
3. **Scientific discovery.** CausaLab, CARTOGRAPH, DiscoveryWorld and recent epistemic-trace
   studies distinguish objective success from mechanism recovery, falsification, calibrated
   stopping, and response to model misspecification.
4. **Research integrity.** Xcientist/XScientist-style work and long-horizon systems motivate
   immutable lineage, failed branches, evidence links, and re-execution—not score-only logs.

EdgeBench adds a strong long-horizon comparator: its 134-task study motivates dual local/judge
feedback loops, evaluator-only trajectory snapshots, continuous-run versus restart controls,
context/memory ablations, submission-efficiency diagnostics and explicit curve forecasting.
Its official Codex setting also makes the feedback channel part of the treatment (12 hours,
30-minute evaluator-only auto-eval and a default 120-second agent submission cooldown). It does
not replace shuffled or strict selection-blind controls, and its aggregate best-so-far curves do
not establish mechanism recovery or independent scientific validation. Its public 51-task subset
contains only four tasks labeled Scientific Problems & ML. A deeper implementation audit adds
four cautions: invisible auto-eval snapshots participate in SForge's final-best selection;
stop-hooks/auto-resume, asynchronous judges and service incidents affect elapsed-time curves;
headroom-based task curation conditions the sampling frame; and nonlinear per-task score
transforms affect aggregate curve shape. The science-specific experiment matrix therefore now
separates committed, terminal and oracle-best artifacts, active and wall time, run attrition,
autonomous stopping, normalization sensitivity and knowledge access. Its minimum publishable
sequence is specified in `science_experiment_plan.md`.

A second pass through SForge and all 51 public task contracts adds a narrower set of protocol
corrections. Hidden auto-evaluation is score-blind but not behavior-blind: the generated prompt
tells agents when background measurement exists and asks them to keep evaluated paths runnable.
The observer also shares extraction and judge resources with the treatment, and repeated
unchanged stochastic snapshots can create a best-of-N advantage. The public BipedalWalker
contract is the only public task contract that explicitly states an hour budget, but its stated
two-hour window conflicts with the official 12-hour configuration. These are concrete reasons
to add a stable committed head, observer-isolated or post-run snapshots, hash deduplication and a
machine-checked prompt/config contract lint. EdgeBench's experience contrast also bundles the
artifact, workspace, feedback ledger, context and notes; its continuation appendix shows that
Goal/Ralph scaffolds can help or harm by task. The revised plan therefore factorizes memory and
continuation, separates local-loop from trusted-loop feedback, and treats model plus scaffold as
the evaluated system. These are implementation-derived deductions, not additional author claims.

A further incremental pass separates checkpoint time from horizon-conditioned policy and treats
model-mediated grading as part of the evaluator system. EdgeBench's main checkpoints come from
12-hour-aware runs; the public displayed best-model sets at 2h and 12h are disjoint on 19/51
tasks, which motivates but does not identify a horizon effect. SForge also exposes at least one
runtime-configurable LLM grader whose complete manifest is not naturally bound into the public
task/run hash chain. The revised plan therefore adds independent disclosed-horizon/random-censoring
experiments and blinded judge-anchor/duplicate/style-twin calibration. These are Frontier-Science
proposals, not revised EdgeBench results.

`arXiv:2601.21165` also creates a direct naming collision: *FrontierScience* already denotes an
expert-authored Olympiad/Research question benchmark. Public release should rename this project
or make the executable-optimization qualifier unavoidable.

## Protocol corrections now reflected in code

- Primary/co-primary metrics are terminal best feasible score and best-so-far AUC over charged
  proposal/benchmark `budget_units`; actual trusted-oracle executions are reported separately as
  `oracle_calls`.
- Five seeds are the runner default; confidence intervals use Student-t rather than a normal
  approximation at small sample size.
- `greedy_rewrite` is not called OpenEvolve. Official framework names map only to genuine
  optional upstream implementations and fail explicitly when unavailable.
- Candidate scoring is framework-independent and always crosses the secure evaluator.
- Checkpoint/resume, seed, candidate lineage hashes, wall/token/cost fields, and raw traces are
  standard artifacts.
- Old 50-task and pre-sandbox results are `UNTRUSTED_PRE_SANDBOX` and cannot support claims.

## Remaining plan deficiencies

### 1. Only calibration-level empirical P2 evidence exists

The keyless GPT-5.5 Responses path was restored and 57 trusted normal single-run conditions now
cover 29 tasks, with task-specific strict open-loop diagnostics on a subset. They expose
one-step saturation and multiple oracle defects, but there are still no valid five-seed
certified-core trajectories, no paired feedback-control result, and no nonzero-budget official-
backend search run. The project must distinguish “calibrated at budget one” from
“experimentally validated” everywhere.

### 2. Optional frameworks lack one reproducible environment

The host default is Python 3.8, OpenEvolve/Shinka require ≥3.10, and current TreeQuest requires
≥3.11. Add a uv/lock-based matrix, pinned commits, and smoke CI. Upstream framework token usage
is not uniformly exposed; cost fields must state missingness rather than report false zeros.

### 3. Seven certifications are internal, not external validation

Task cards and invariant tests are a strong filter, but domain review has not been independently
performed. Matrix multiplication and Cap Set public-known instances have contamination risk;
add time-held-out or procedurally generated instances. Normalization anchors need dated,
reproducible witnesses, not prose claims.

### 4. LLM-only search is an inadequate baseline suite

Recent results show classical optimization can dominate LLM agents. Add random/quasi-random,
Bayesian optimization or CMA-ES/DE when the artifact admits parameterization, and a domain
heuristic. Compare within-task ranks/performance profiles rather than averaging arbitrary scores
as the only headline.

### 5. Optimization remains the only credible track

The old plan promises multifidelity, Pareto objectives and broad autonomous discovery without
implementations. Create an explicit capability ladder:

- **Track O — Optimization:** best feasible artifact + best-so-far AUC over charged benchmark
  budget units, with separate oracle-call accounting. Near-term release target.
- **Track F — Feedback:** normal vs shuffled/delayed/no feedback, paired seeds.
- **Track M — Mechanism:** predictive score separated from equation/causal recovery.
- **Track V — Validation:** proxy/exact generalization, hidden shifts, optional physical tests.
- **Track R — Integrity:** hypotheses, tests, evidence, failed branches, provenance and refusal.

Track O is the only track close to runnable benchmark status. Track F has a negative/inconclusive
implementation pilot rather than positive evidence, and Track R has partial lineage artifacts;
none has sufficient empirical evidence.
Do not aggregate these tracks into one “science” score.

### 6. P0–P2 completion is infrastructural, not a release claim

The five latest dated reports were regenerated from clean source revision `40931fb`: all report
`execution_passed=true`, `trusted_evidence=true`, and `passed=true`. This closes the local
implementation/evidence work scheduled for P0–P2, but the P2 performance gate remains open:
the protocol smoke has budget zero, and each official-backend smoke evaluates only one baseline.
Accordingly, “P0–P2 implemented and recorded” must not be shortened to “benchmark validated.”

### 7. Submission feedback is both a learning channel and an attack surface

EdgeBench's stress tests recovered four concrete failure modes: reconstructing hidden targets
from 400+ detailed submissions, optimizing stochastic upper tails (best 1501 versus mean 484
over 311 trials), overfitting a reused evaluator seed, and writing across a trusted path. The
current project seals metrics and isolates candidate code, but the experiment plan still needs
an explicit agent-visible submission budget/cooldown, feedback-payload accounting, hidden seed
sets for stochastic tasks and evaluator-only periodic snapshots. Without these controls, a
longer curve may measure feedback bandwidth or best-of-N exploitation rather than science.

### 8. Observer-side best is not an autonomous scientific conclusion

SForge's public protocol chooses the final best across both agent submissions and invisible
auto-eval snapshots. That is defensible for measuring trajectory potential, but the agent could
not know which hidden snapshot to deploy or defend. Frontier-Science currently retains selected
candidate hashes, but long-horizon instrumentation must additionally preserve the explicit
agent/search commitment, the terminal workspace artifact and an evaluator-only snapshot best.
Discovery claims must use the committed artifact and report the hidden `oracle_selection_gap`.

### 9. Elapsed-time and aggregate curves need construction audits

Long runs conflate active reasoning, simulator work, judge queues, serving incidents, idle time
and resume scaffolds. Aggregating task-specific normalized scores then adds anchor, weighting and
headroom-selection assumptions. Before any scaling-law or learning-speed claim, report both
end-to-end and active-time estimands, full run attrition, initial/first-valid performance, and
sensitivity to score transforms, task/family weights, missing-run policies and task deletion.

### 10. Forced continuation conflicts with scientific stopping

A stop hook is useful for a fixed-horizon capability curve, but a scientist should stop or
abstain when evidence is sufficient, the model class is inadequate or another experiment has
negative value. Add an explicit signed commit/abstain/continue action and compare autonomous
stopping with forced continuation on supported, null and misspecified worlds. Score experiment
cost, false discoveries, commitment regret and whether continued work degrades a valid result.

### 11. Scientific knowledge access and human calibration remain unspecified

Disabling the Web prevents some leakage but also removes a normal scientific tool. The primary
science condition needs a dated frozen literature corpus with citation provenance, plus separate
no-literature and open-Web treatments and time/family-held-out novelty checks. EdgeBench's human
number is task-construction effort, not a matched expert baseline; collect a small stratified set
of expert one-shot and iterative trajectories under the same interface and budgets.

### 12. Measurement, state and acceptance policies remain bundled

The current trajectory design does not yet test whether periodic hidden measurement changes the
agent's branching/write behavior, whether observer work delays visible feedback, which retained
state channel causes a continuous-run advantage, or whether continuation scaffolding rather than
the model explains long-horizon differences. It also accepts every strictly positive visible
delta even when the change is below numerical resolution. Hartree--Fock's current calibration
shows why this matters: an approximately `9e-15` selection-score increase changes the selected
artifact while development and held-out robustness move in different directions. Long runs need
a stable committed head separate from scratch work, hash-aware snapshots, independent restart
pools, a local-feedback × trusted-feedback design, model/scaffold metadata and preregistered
numerical-`epsilon` plus scientific/Pareto acceptance policies.

### 13. Task contracts and scientific scope need explicit linting

A harness timeout cannot silently disagree with a prompt-stated horizon, and prefixes of a run
that knew it had a longer horizon are not independent short-budget policies. Add contract checks
over the disclosed/actual horizon, evaluator timeout, cooldown, submission paths and checkpoint
schedule. Also stratify method-prescriptive reproduction, method-neutral inference,
optimization and mechanism discovery. EdgeBench intentionally excludes vision-dominated tasks;
this project must either declare a structured-observation scope or create a separate calibrated
instrument/perception track rather than silently claiming all of science.

### 14. Curve smoothness can hide distinct scientific transitions

EdgeBench's absolute best-so-far curve combines a nonzero first attempt, becoming scoreable and
later quality improvements. That is especially unsafe here because many early artifacts are
protocol-invalid, runtime-invalid or scientifically infeasible. Add a hurdle/multistate analysis:
first-valid cumulative incidence, validity probability by budget, post-valid conditional quality,
and jointly sealed/mechanism-valid success. Dense monotone checkpoints are not independent data;
curve uncertainty must resample whole task-instance/run trajectories. Any scaling fit needs
prospective held-out forecasts against last-value, monotone, per-task plateau and repeated-sampling
baselines, not only aggregate `R²`.

EdgeBench's own candidate S-curves have nearly indistinguishable full-window RMSE, and its theory
assumes cut mixing, stable attainable support, concentrated midpoints/speeds, self-similar search
geometry and linear effort in wall time. Treat this as a falsifiable mechanism: test whether
material improvement intensity tracks `y(1-y)` and peaks near `y=0.5`; compare change-point,
multistage and mixture models. Scientific workflows may instead have separate validity,
optimization, validation and mechanism bottlenecks. A model-generation doubling claim additionally
requires a prospectively frozen task/scaffold panel rather than a retrospective rolling-frontier
fit.

### 15. Scientific conclusions are reversible but the trajectory schema is monotone

EdgeBench's theoretical frontier treats unlocked score units as irreversible, and this project's
schema likewise requires `best_score` to be monotone. That is appropriate for observer-side
optimization potential, not for the mechanism the system currently endorses. A later
intervention, regime shift or independent replication can invalidate an earlier claim. Add a
separate current-claim/event stream with evidence hashes and explicit propose/confirm/revise/
retract/abstain transitions. Score unsupported-claim exposure, retraction delay, confidence
revision and recovery under contradictory or misspecified evidence; never forward-fill the
historical maximum mechanism score as the current scientific belief.

### 16. Nominal task count, curve parameters and replicate floors can overstate evidence

Related procedural instances, shared simulators/data and common task templates reduce the
effective number of independent scientific worlds. At the same time, a three-parameter saturating
curve can obtain high level-fit `R²` while `Smax`, `tmid` and `beta` trade off outside a weakly
observed plateau. EdgeBench's full score tables also show that three-run task variance can be
large. Register task ancestry, hold out and resample whole lineages, report effective independent-
world count, require profile/bootstrap parameter intervals and post-inflection support, and size
confirmatory repeats from pilot variance plus a material-effect target rather than treating five
or ten seeds as universally sufficient.

### 17. Long-run calendar effects and milestone narratives need stronger designs

Serving stability varies through long runs, and staggered or sequential condition launches can
confound model/feedback contrasts with calendar day, service load or endpoint updates. Randomize
or rotate treatment order in task-instance blocks, pair conditions concurrently when possible,
and log the endpoint snapshot and UTC batch. Separately, a large score jump after bundled edits
does not identify which edit or scientific idea caused it. For selected milestones, replay the
parent, full child, component-only patches and rollback on the same sealed panel before making a
causal case-study attribution. MA1/E52 now preregisters milestone eligibility,
component/leave-one-out/rollback replay, key `2×2` interactions and a separate `old/new data ×
old/new method` contrast; the experiment remains unrun.

### 18. Task calibration and confirmatory estimates are not yet separated

Model trajectories currently help decide whether candidate tasks have headroom and scientific
value. Reusing the same worlds/runs to set thresholds, admit tasks and estimate headline curves
would create adaptive selection bias. Freeze admission using a declared pilot model/seed/world
panel, then evaluate fresh confirmatory seeds, procedural worlds and preferably later model
snapshots. Retain excluded, saturated and failed tasks in a public sampling-frame ledger; reused
pilot evidence remains exploratory.

### 19. Repeated sealed evaluation is validation, not fresh confirmation

Periodic evaluator-only snapshots protect the online search state, but analysts can still use
their trajectories to choose tasks, curve families, milestones and claims. Repeatedly inspected
sealed worlds therefore become adaptive validation evidence. Reserve a one-shot post-commit
world/seed panel or independent high-fidelity replication that is never used for search,
admission, fitting, stopping or interpretation; count all evaluator looks and refresh any
confirmation set that has influenced a decision.

### 20. Static answers and isolated tasks do not prove a reusable scientific workflow

Several current tasks score one frozen program or parameter set on fixed hidden worlds. That can
establish optimization or inverse-answer quality, but not that preprocessing, experiment design,
inference, uncertainty and claim generation form a reusable method. EdgeBench's Borden/Cape Cod
group also illustrates a richer scientific campaign—diagnosis, source inversion, monitoring and
remediation—whose stages share one system. Build at least one typed end-to-end campaign, replay
the committed workflow from raw observations on fresh procedural worlds, propagate uncertainty,
and use baseline/agent stage swaps to locate downstream decision gains. Count campaign stages as
one shared lineage for uncertainty, even if each is a useful task surface.

### 21. Long-horizon cohorts need measurement-health and manifest gates

Headroom alone does not make a task informative: a universal floor, early ceiling, invalidity or
fixed-artifact judge noise can all create misleading trajectories. Before allocating 6h/12h,
measure first-valid probability, baseline--reference separation, evaluator resolution and
repeatability, ceiling/floor mass, material post-2h gain and shortcut resistance. In addition,
bind every aggregate to a versioned machine-readable cohort manifest. EdgeBench arXiv v1 itself
uses one `36/39/19/13/19/8` family assignment in task specifications and another
`35/34/16/13/24/12` assignment in score tables; the same 134 IDs include 11 category moves.
Frontier-Science should fail closed when a claimed task count, task set, lineage, weight, score
transform or run-inclusion rule differs from the figure/table manifest.

### 22. Objective selection, event retention and recovery are not yet one trusted protocol

The current plan predeclares material/Pareto acceptance but does not yet require the prompt,
agent-visible incumbent cache, authoritative selector, signed commit, terminal endpoint,
dashboard and analysis to replay one versioned objective-selection contract. This matters because
the current EdgeBench release has three selector families across its public contracts, while its
generic prompt, local cache, judge and visualizer do not express or recompute them identically.
For science, selector disagreement can change which valid, safe or mechanism-supported artifact
is called “best,” not merely its display label.

The same source audit shows a second gap: convenient run history is lossy relative to evaluator
reports, periodic snapshots omit guaranteed `t=0` and terminal boundary evaluations, and judge
session/history state is process-local. Add a durable append-only ledger with complete raw report
and visible-feedback projections; force immutable baseline/first-valid/submission/commit/fixed-grid/
terminal sentinels; use artifact+evaluator+world-panel idempotency keys; and crash-test exactly-once
budget/evidence recovery. The source/hash-bound audit is
`.research/edgebench_contract_runtime_audit_2026-07-24.json`.

### 23. Curve shape is not yet invariant to score atoms or task order

EdgeBench's theory makes vanishing score granularity an explicit condition: a result represented
as many small score units yields smaller jumps than the same scientific outcome represented by a
few large gates. Its task-count plot reports lower fit error as the number of tasks grows, but the
paper and public source do not report a distribution over task permutations or subsamples; that
figure alone cannot establish that improvement comes from sample size rather than composition.
The present plan audits transforms and weights but not equivalent rubric partitions or the
distribution over task orders. Replay the same raw evidence under coarse/canonical/fine partitions
and random plus lineage-blocked task accumulation. If curve shape, parameter estimates, ranking
or forecast changes materially, report an evaluator-construction effect rather than a scaling law.

### 24. Same-task memory is not cross-task scientific learning

Current restart and memory controls test persistence within one task or one regime. EdgeBench's
aggregate theorem actually assumes tasks do not interact, so it supplies no evidence that a
scientific notebook learned on one system helps another. Add randomized related/unrelated/
misleading source→target curricula with answer-disjoint procedural worlds. Cross artifact-only,
raw-evidence, audited hypothesis/evidence and full-state transfer; measure target-only early gain,
mechanism transfer, false discovery, retraction and negative-transfer half-life.

### 25. Independent per-task budgets omit research portfolio decisions

Equal long budgets per task measure conditional single-task capability, not the ability to choose
which hypotheses, samples or projects deserve scarce instrument and confirmation resources.
Build a small blinded portfolio with a shared budget and signal/null/misspecified projects of
different cost and value. Compare equal/random allocation, cost-aware VOI or knowledge-gradient
baselines and agent allocation using fresh-confirmed portfolio utility, starvation, abandonment,
unsafe/false-discovery exposure and regret. Keep every offered project in the denominator.

### 26. Software-replay semantics omit drifting and irreversible laboratories

Exactly-once evaluator recovery is necessary but not sufficient when an assay consumes a sample,
an intervention changes the system, calibration drifts or parallel experiments return out of
order. Such actions cannot be rolled back or retried under the same idempotency key. Add a
server-stateful stress task with sample/calibration/intervention lineage, hidden drift/batches,
destructive measurements and random completion latency. Score drift detection, recalibration,
stale-result use, duplicate physical acts, safety and fresh-batch confirmation; use event/sample
cost or piecewise time when fixed cycles invalidate a log-time coordinate.

### 27. Wall time conflates search effort with feedback opportunity

EdgeBench models elapsed interaction time as a search-effort coordinate, but its official public
Codex configuration does not expose one uniform authoritative-feedback cadence: among 51 tasks,
44 use a 120-second submission cooldown, three use 216 seconds, one uses 2160 seconds and three
use zero, while observer auto-evaluation runs every 1800 seconds. Different judge and experiment
costs add further task-specific clocks. Splitting elapsed/active/queue time is necessary but does
not identify which clock governs learning. Add a randomized cadence experiment that holds active
compute, local calls, total feedback events/bits and confirmation budget fixed, then tests curve
collapse and forecasts on wall, active, experiment-cost, feedback-event and revealed-bit axes.
Without it, report hour-based curves descriptively rather than as an agent-intrinsic rate.

### 28. The proposed frontier graph has not been interventionally tested

Current curve checks test score granularity, material-event hazard and alternative functional
forms, but they do not manipulate the weighted-cut mixing or dependency topology invoked by the
EdgeBench mechanism. Build answer-disjoint procedural twins with matched marginal work-unit
difficulty, score mass, feedback and cost but well-mixed, chain, modular-single-bridge and
hierarchical graphs. Freeze predictions, randomize bridge/prerequisite availability and measure
plateaus, inflections, transfer and the bridge treatment effect. A curve fit alone cannot validate
the latent task graph; the topology intervention can support or falsify it.

### 29. Fixed task objectives omit scientific question formation

The current tasks, EdgeBench tasks and the planned portfolio all begin from author-specified
objectives or candidate projects. This measures problem solving and allocation, not whether the
agent can formulate a nontrivial, identifiable and falsifiable research question. Add a rich
procedural laboratory with fixed-question, candidate-menu and open-question arms. Require a
signed preregistration before new data and score fresh-world answerability, realized information
or decision value, confirmation, triviality, false discovery and deviation from the plan. Do not
use prose similarity or an LLM judge as the primary question-quality oracle.

### 30. Executable starters can anchor the claimed method discovery

Legal baselines reduce invalid runs, while prescribed starters and published methods make a task
tractable, but they also inject an initial scientific prior. Text-only workflow-hint ablations do
not isolate this executable path dependence. Randomize blank schema-only, neutral, plausible but
scientifically wrong, correct and diverse-choice starters on identical procedural worlds. Track
basin escape, exploration diversity, stale-mechanism retraction, sealed/mechanism validity and
structural distance from the starter. Until this is done, describe success as scaffold-conditioned
adaptation when the starting artifact substantially constrains the search.

### 31. Clean simulator observations bypass the instrument-to-claim problem

Most current tasks begin from structured arrays emitted by a trusted simulator. EdgeBench excludes
vision-dominated tasks to avoid a perception confound, yet its full science task notes include
sensor-fault diagnosis, dirty GNSS, ECG preprocessing, evidence extraction and image active
learning. A linked campaign alone does not identify measurement error: randomize oracle-clean,
reference-preprocessed and agent-built raw-data pipelines on paired latent worlds, inject realistic
calibration/censoring/channel faults and true anomalies, and propagate typed feature uncertainty
through mechanism, confirmation and decision regret. Until one such I6 task is run, state the
benchmark scope as structured-observation science.

### 32. Scientific transfer is not tested under equivalent representations

Score-partition replay tests evaluator construction, not whether a method survives harmless changes
of units, coordinates, channel order, grid numbering, spectral representation or symmetry gauge.
Add V4 metamorphic twins that preserve the latent physical world, canonicalize outputs only after
execution and pair them with non-equivalent physical controls. A task that succeeds only in one
schema can measure template matching even when its held-out scalar score is high. Use this as a
cheap admission gate across several task families.

### 33. Parallel candidates are not independent scientific replication

Neither restart/pass@k nor a shared-context critic estimates whether independent researchers reduce
correlated scientific error. Under a fixed total budget, compare a single agent, shared branches,
isolated investigators and blinded claim--evidence synthesis. The team must commit one conclusion
before fresh confirmation; evaluator-selected best member remains only an oracle envelope. Measure
hypothesis diversity, error correlation, minority correctness and false consensus before making a
multi-agent or collaborative-science claim.

### 34. Public scalar objectives do not establish reusable scientific value

An agent can optimize the exact score weights without producing a method useful to another
stakeholder. Pre-freeze a family of domain-valid utilities, reveal constraints but draw final
weights only after signed commit, and compare fixed-scalar artifacts with executable response
surfaces or Pareto sets. Report sealed weight-distribution regret, worst-case/CVaR regret, coverage
and safety. This differs from score granularity and portfolio allocation: U1 asks whether one
scientific artifact remains decision-useful when legitimate downstream preferences were unknown.

### 35. A long-run prefix is not a short-horizon scientific policy

EdgeBench reports `@2h/.../@12h` from agents assigned independent 12-hour runs. Those checkpoints
describe one long-horizon policy, but horizon knowledge can change how a scientist allocates early
exploration, expensive confirmation and stopping. The public 51-task table makes the practical
stakes visible: recomputing the best displayed model at 2h and 12h gives disjoint winner sets on
19/51 tasks. This is descriptive ranking drift, not a causal horizon effect. Randomize the true,
disclosed 2/6/12-hour deadline on matched task worlds, compare independent short-run endpoints
against 12-hour-aware prefixes, and add a hidden random-censoring arm. Budget and model rankings
must be labeled horizon-conditioned until this policy effect is measured.

### 36. Model-mediated judges are part of the experimental treatment

The public SForge documentation configures an LLM grader at runtime through
`SFORGE_JUDGE_MODEL` for at least one released task. The judge image pins grading code, but the
runtime judge identity and response configuration are not naturally part of the task image hash or
the persisted effective run configuration. This does not show that EdgeBench's reported score is
wrong; it exposes a reproducibility risk for future open-question, evidence-synthesis and report
tasks. Pin a complete judge manifest, repeatedly score blinded expert anchors, exact duplicates and
scientifically equivalent style/verbosity twins, and cross-check against executable outcomes plus
expert adjudication. Report judge noise, drift and rank reversals; do not promote a single mutable
rubric model to the primary scientific truth oracle.

### 37. Effective submissions do not identify calibrated feedback acquisition

An EdgeBench submission is counted effective when it improves the historical best, but the agent
chooses when to submit after inspecting local evidence. The ratio therefore bundles candidate
quality with endogenous request timing, cooldown, latency and task difficulty. In science the
external loop may be an expensive experiment, higher-fidelity solve or expert review, making
feedback acquisition itself a core decision. Under one fixed total feedback/confirmation budget,
compare agent-requested, fixed-grid, random, cost-aware VOI and end-only policies. Require a
pre-request prediction and action threshold, then score predicted-realized value calibration,
request-timing regret, redundant calls, false discovery and fresh-confirmed utility.

### 38. Public replay and sealed prospective validity are not the same evidence surface

EdgeBench reports its main curves on 134 tasks but releases 51 task contracts and no raw 38,000h
trajectory corpus or figure-analysis code. Its official README's public-51 aggregate is 5.1--7.1
points below the full-134 aggregate at 12h across all five displayed models. This does not identify
why the cohorts differ, but it proves an external reproducer cannot currently replay the same task
population as the headline estimate. Frontier-Science should maintain lineage-matched open-replay,
sealed-prospective and delayed-release pools, publish the delayed pool after a frozen cycle, and
measure open-to-sealed transport before pooling any claim. A fully public static leaderboard and a
fully hidden benchmark each solve only one side of the reproducibility--contamination tradeoff.

### 39. Model-assisted task construction can induce builder bias

The planned inventory uses GPT-5.5 calibration to test headroom and guide substantive task rebuilds.
That is productive development evidence, but a task repeatedly modified in response to one model's
failures, shortcuts and feedback interpretation is not automatically neutral when comparing that
model with others. Add builder/calibrator model, scaffold, triggering trajectory and freeze time to
every task lineage. On procedural families, cross-evaluate A-built, B-built and independent-expert-
built variants on fresh common worlds while excluding the tested solver from its final construction
round. If builder×solver interactions or rank reversals are material, headline aggregation must be
builder-balanced or leave-builder-out.

### 40. Feedback counts and bits overstate independent scientific evidence

Existing controls match submission counts, payload classes and revealed bits, but ten repeats on one
seed, ten correlated samples from one batch and ten independent interventions are not ten equivalent
scientific observations. Without world/sample/batch/instrument/intervention lineage, a smooth long-
horizon curve can be driven by pseudoreplication. Extend the event ledger with evidence ancestry and
report raw calls beside a preregistered lineage-clustered evidence effective sample size, information
gain and independent confirmation count. Exact repeats may estimate evaluator noise; they cannot
raise mechanism or replication evidence. Run matched fresh/correlated/duplicate-feedback arms before
claiming that more environment contact means more scientific learning. Define eESS for each estimand
and retain the highest-lineage cluster, intervention and independent-lab counts separately; a single
cross-task evidence scalar would recreate the aggregation problem this control is meant to expose.

### 41. A common wall-time axis does not imply a common observation process

EdgeBench describes host auto-evaluation at fixed intervals, but its public SForge implementation
uses two different trajectory-observation paths. Ordinary artifact tasks wait one full interval,
archive the live workspace and submit it asynchronously; the timer then waits another full interval
after that capture attempt rather than targeting an absolute wall-clock grid. In contrast, the
three public `game_mode=true` text-adventure contracts skip host auto-evaluation entirely. Their
score histories are produced when agent-driven game sessions close, and archived step records have
move/action/score but no wall-clock timestamp. Thus even within the eight-task public Games family,
three tasks are event-triggered live-state interactions and five are artifact submissions. This is
a released-code observation, not evidence about the unavailable raw trajectories or official fits.

For Frontier-Science, an improvement that occurred between two scored captures is interval-censored;
using the later capture or judge-completion time as the discovery time shifts AUC, takeoff, midpoint
and speed. The risk is larger when comparing replayable programs with asynchronous, consumptive or
irreversible experiments whose state cannot be re-evaluated from a file. Add an observation-kernel
audit: replay identical immutable event trajectories on dense, 5/15/30/60-minute, preregistered seeded-random-phase and
agent-event grids; retain scheduled/actual capture, state/artifact creation and judge times; report
interval-censored event metrics and curve/rank sensitivity. Keep path-dependent live-state tasks in
a separate stratum unless timestamped state transitions provide an equivalent measurement surface.

### 42. Endogenous experiment streams need design-aware inference

EdgeBench explicitly distinguishes benchmark-organized streams from its own endogenous long-task
stream: the agent chooses what to test, simulate and submit next, thereby changing what it observes.
That is a desirable optimization capability, but scientific estimators cannot generally treat the
resulting observations as an i.i.d. sample from a fixed design. The current plan tests experiment
informativeness, feedback value, repeated holdout use and evidence independence; it does not yet
test bias, interval coverage or support after adaptive acquisition. Add AD1 on answer-disjoint
procedural worlds: compare fixed randomized/balanced designs with agent-adaptive acquisition, and
cross adaptive data with naive versus policy-aware analysis using logged action probabilities or a
randomized exploration floor. Persist the eligible action set and policy state before each outcome.
Report effect/mechanism bias, coverage, FDR, propensity calibration and positivity violations; where
the policy assigns zero probability, refuse population inference rather than extrapolating. Fresh
confirmation validates the final claim but does not retrospectively calibrate an invalid interval.

### 43. Submission history is not a complete scientific result ledger

EdgeBench preserves submissions, evaluator snapshots, archives and conversation traces, while its
fast local loop remains agent-driven inside a writable workspace. Consequently, outer-loop history
does not provide an objective denominator for every local simulation, null result, failed run or
contradictory observation. Defining effective submissions by best-score improvement is appropriate
for optimization efficiency; using only effective submissions or selected milestones for science can
create a machine-scale file drawer and inflate effects. Add NR1: route every simulator/instrument/data
action through a trusted event server that durably records intent before returning the result. Compare
the resulting positive/null/contradictory/failed/censored ledger with the agent's submitted evidence
package under free-reporting, mandatory all-result manifest and blinded-synthesis arms. Score capture
completeness, sign-conditional reporting odds, effect inflation, claim reversal after full disclosure,
reproducibility and fresh confirmation. This is distinct from crash-safe retention (I5/E27): a result
can be durably stored by the system yet selectively omitted from the scientific claim.

### 44. Independent runs do not estimate futures conditional on the same research history

EdgeBench's nominally three independent 12-hour trials estimate unconditional run-to-run
variation, and its stateful comparison asks whether one continuous run beats six fresh 2-hour
attempts. Neither design clones one intermediate scientific state into repeated continuations.
That distinction matters because the paper's own stochastic frontier process conditions the
unlocking hazard on the full latent state `n(u)`, while the observed score is only a scalar
projection; modular or bottlenecked tasks may retain history not visible in the current score.
Add CF1/E51: at preregistered first-valid and mid-budget events, content-address and clone the full
artifact, context, evidence ledger, local-result cache, environment, pending-job and budget state
into multiple independently randomized equal-budget continuations. Compare within-parent
continuation variance with matched-score parents reached through different histories, including
wrong-mechanism histories. Report all descendants, lock-in/escape and sealed confirmation; the
parent checkpoint is the top-level unit and post-hoc best-child selection is forbidden. This is
distinct from restart depth/width, memory-channel ablation, starter randomization and independent
investigator replication. The source audit motivates the design but does not show excessive
path dependence in EdgeBench; its headline raw trajectories are unavailable.

### 45. A best artifact is not a calibrated set of competing hypotheses

The current plan records hypothesis/evidence updates, false branches and claim revision, but its
optimization loop and most trajectory summaries still center one incumbent. Early scientific
evidence can leave several mechanisms compatible, and deleting all but the development-score
leader can create confident path lock-in before a discriminating experiment is available. Add
HP1/E53 on early-ambiguous procedural worlds: compare one incumbent with a fixed-capacity explicit
hypothesis portfolio, model averaging and diverse branches; require executable predictions,
support/contradiction links, calibrated weights and elimination reasons. Score true-mechanism
retention, premature elimination, discriminating-test choice, false consensus, recovery and one
fresh-confirmed precommitted synthesis. This is not ordinary population diversity or best-of-K.

### 46. Scientific feedback sources are fallible treatment components

The plan separates local and trusted loops and audits judge stability, but it generally treats
received observations or critiques as having a known epistemic status. Real instruments,
simulators, automated graders, reviewers and collaborating laboratories can be systematically
biased, drift across regimes or share hidden ancestry. Add FR1/E54 with matched payload and cost:
cross visible/hidden/permuted source identity against calibrated, noisy, biased, drifting and
conflicting sources, with optional costly adjudication. Measure source-specific calibration,
evidence-weighting regret, blind following, drift detection, escalation, false discovery and
sealed recovery. J1 validates a judge from the evaluator side; FR1 evaluates whether the agent
learns whom to trust.

## Revised TODO plan

### P0/P1 closeout — completed locally, reproduce in CI

- [x] Trusted oracle / isolated candidate architecture and adversarial regression suite.
- [x] Current 54-package deterministic secure baseline and certification audit; all 54 weak
  baselines are valid, deterministic and fail closed.
- [x] Re-run the deterministic secure baseline, certification and security audits on the clean
  53-task RNAInverseDesign revision (v30/v40/v24).
- [x] Re-run full 332-test regression plus deterministic baseline, certification and security on
  the clean 54-task ProteinStabilityDesign candidate revision (v32/v42/v26).
- [x] Seven-task certified core, 34 candidates and 14 quarantined packages after admitting the
  source-rebuilt and model-calibrated ElectrolyteConductivityDesign replay; certification v44
  covers all 55 packages.
- [x] Re-run the full regression, deterministic baseline and security audits over the 55-package
  revision: full-suite v1 passes 347/347, baseline v33 passes 55×2 with no infrastructure
  failures, and security v27 passes 18/18.
- [x] Task-card/citation/invariant audit and dated machine-readable evidence.
- [ ] Add Linux CI reproduction of all dated audits (local clean-revision reproduction is done).
- [x] Replace the quarantined `ClimateScience/EnergyBalanceModel` with an active, identifiable
  response task containing long/short experiment-design contrast and explicit model mismatch.
- [x] Replace the fail-open `AcousticMetamaterials/BroadbandAbsorber` proxy with a
  distributed acoustic model, variable bands/geometries, held-out transfer and sealed
  angle/air/manufacturing shifts.
- [x] Replace the inconsistent two-coefficient `QuantumChemistry/HartreeFockSCF` toy with seven
  finite-basis systems, stable multistart references, a different-size held-out hard ring,
  physical geometry shifts, AO representation checks and occupied-virtual stability.
- [x] Replace fixed-scene `Acoustics/RoomImpulseResponse` reconstruction and its length crash
  with source-placement/six-surface treatment optimization over six rooms, independently
  checked image paths and Eyring decay, held-out transfer and five sealed shifts.
- [x] Replace evidence-free `WavePropagation/SeismicWaveInversion` with charged active
  CMP/offset/frequency acquisition, a nine-parameter layered model, prediction/mechanism/design
  separation, far-offset transfer and null/four-layer model-inadequacy refusal.

### P2a — reproducible protocol release

- [x] Unified trajectory schema v2, budget-unit AUC, separate oracle-call/cost fields, seeds,
  hashes, checkpoint/resume.
- [x] Add post-search compact trajectory snapshots with scalar sealed metrics and raw-trajectory
  hashes to future batch reports; backfill the current science calibrations with a trusted
  derived summary.
- [x] Greedy normal/none/shuffled prompt-metric modes and multi-seed statistics runner; scope is
  machine-readable and does not claim selection-blind feedback ablation.
- [x] Real optional OpenEvolve, TreeQuest AB-MCTS-A and ShinkaEvolve adapters.
- [ ] Add a locked Python 3.10/3.11 upstream environment and integration tests.
- [x] Restore a working, authorized LLM endpoint and record smoke metadata (keyless local
  Responses proxy; endpoint details remain git-ignored).
- [ ] Run ≥5 seeds on all seven certified tasks at 30/100/300 proposal/benchmark budget units;
  report the actual oracle-call counts separately.
- [ ] Publish raw trajectories, environment lock, paired uncertainty and performance profiles.

### P2b — missing controls

- [ ] Add random/quasi-random and parameterized BO/CMA-ES/DE baselines.
- [ ] Add at least one strong domain heuristic per certified task family.
- [ ] Audit upstream token/cost accounting and represent unavailable values as `null`/missing.
- [ ] Add direct one-shot LLM and restart-vs-depth allocation ablations.
- [ ] Add EdgeBench-style continuous-state versus six equal-budget independent restarts, with
  identical evaluator feedback schedules and both visible and sealed curves.
- [ ] Add agent-visible submission budgets/cooldowns, feedback-payload accounting and a
  scalar/aggregated/diagnostic feedback-bandwidth ablation.
- [ ] Compare agent-requested, fixed-grid, random, cost-aware VOI and end-only external feedback
  under one total budget; freeze a question/value/action-threshold card before each request.
- [ ] Add fixed-interval evaluator-only snapshots that never affect online selection or stopping.
- [ ] Require `t=0`, first-valid, every submission/commit, fixed-grid and terminal sentinel
  snapshots through the same immutable capture/evaluator path; reason-code missing boundaries.
- [ ] Make every snapshot an atomic content-addressed bundle and report three endpoint policies:
  agent/search committed, fixed-horizon terminal and evaluator-only snapshot oracle-best.
- [ ] Keep an explicit stable committed candidate head separate from scratch work; compare fixed
  disclosed snapshots, jittered schedule-blind snapshots and post-run event-snapshot replay.
- [ ] Isolate observer evaluation from visible judge resources, measure queue/throughput effects,
  and deduplicate unchanged deterministic hashes; aggregate stochastic re-evaluations over a
  preregistered seed panel rather than treating them as selectable candidates.
- [ ] Instrument asynchronous feedback lineage with submission hash, feedback-ready/read times
  and first descendant hash; do not attribute stale feedback to unrelated edits.
- [ ] Record artifact-created/submitted, judge-started/completed and feedback-read times, and
  predeclare whether submissions completed after the cutoff enter observer-side endpoints.
- [ ] Split wall time into active model, local tool/simulator, judge/queue, idle/resume and
  charged scientific experiment time; publish scheduled/started/completed/recovered/valid counts.
- [ ] Add an O0 one-shot/no-environment and first-valid baseline so pretrained competence is not
  counted as within-run learning.
- [ ] Add a hurdle/multistate trajectory analysis: reason-coded invalid states, first-valid
  cumulative incidence, validity probability by budget, conditional post-valid quality and joint
  sealed-plus-mechanism success.
- [ ] Add structural/behavioral diversity and genealogy-collapse diagnostics.
- [ ] Add HP1 competing-hypothesis controls on an early-ambiguous mechanism task: single incumbent,
  explicit portfolio, model averaging and diverse branches, with one pre-confirmation synthesis.
- [ ] Add adaptive allocation/stopping baselines (for example, SMC-style convergence control).
- [ ] Add a task-contract linter for prompt versus actual horizon, checkpoint schedule,
  evaluator timeout, cooldown, maximum submissions, submitted paths and deliverables.
- [ ] Extend contract linting to raw objective direction, validity/safety/confirmation gates,
  material epsilon, stochastic expectation/quantile, tie/Pareto and endpoint selection policy.
- [ ] Replay one versioned selector over every raw event and fail closed unless prompt/online/
  commit/terminal/dashboard/analysis incumbent artifact hashes agree.
- [ ] Replace summary/in-memory history as source of truth with an append-only durable event ledger
  retaining full raw reports, agent-visible feedback projection, artifact/evaluator/world hashes,
  event times, costs, failure/retry lineage and selector decisions.
- [ ] Add judge/work-container/network crash injection and idempotent recovery keyed by artifact +
  evaluator manifest + seed/world panel; reconcile exactly-once oracle/sample budgets and stale or
  duplicate feedback delivery.
- [ ] Add a measurement-health gate before long-horizon allocation: first-valid rate,
  baseline/reference separation, fixed-artifact judge noise, resolution, floor/ceiling mass,
  material post-2h headroom and shortcut resistance.
- [ ] Use independent runs disclosed their true horizon for budget comparisons; do not treat a
  horizon-aware long run's prefixes as counterfactual short-horizon executions.
- [ ] Randomize disclosed 2/6/12-hour horizons on matched worlds and add a preregistered hidden
  random-censoring arm; report exploration/confirmation allocation, prefix regret and rank reversals.
- [ ] Implement delayed-feedback controls and preregister paired Track F contrasts.
- [x] Implement a strict selection-blind open-loop control with frozen baseline parent/metrics,
  offline-only best selection, explicit parent-hash tests and machine-readable feedback scope.
- [ ] Add a narrower score-information-only control with matched parent programs and feedback
  message lengths; selection-blind currently tests the full value of iterative feedback.
- [x] Run a preregistered three-replicate strict-control implementation pilot on Pendulum,
  GateSynthesis, ActiveLawDiscovery and OPF; retain the negative/inconclusive result and token
  imbalance rather than promoting it to a Track F claim.
- [ ] Evaluate persistent scientific memory/world-model quality over long horizons, beyond
  checkpoint/resume correctness.
- [ ] Factor retained state into incumbent artifact, local result/cache, trusted-feedback ledger,
  hypothesis/evidence memory, conversation context and full workspace; use independently
  repeated restart pools rather than dependent subsets of one pool as replicates.
- [ ] Test memory on related-instance transfer and preregistered regime changes, measuring both
  useful transfer and stale-hypothesis/negative-transfer failures rather than same-task retention
  alone.
- [ ] Randomize related/unrelated/misleading source→target curricula with answer-disjoint target
  worlds; compare cold, artifact, raw-evidence, audited-notebook and full-state transfer.
- [ ] Cross continuous-session, Goal and fresh-context file-backed continuation under a fixed
  model/context/tool condition; always report the model--scaffold--context bundle.
- [ ] Run a 2×2 local simulator/test feedback × trusted-judge feedback ablation and account for
  calls, revealed information and scientific experiment cost in both loops.
- [ ] Report raw regressions, effective-submission rate, improvement magnitude, rollback latency
  and active-learning span rather than only the monotone best-so-far envelope.
- [ ] Recompute acceptance under strict-score, evaluator-noise `epsilon`, domain-materiality and
  Pareto/constraint-aware rules; report selection reversals and sealed/mechanism regret.
- [ ] Add a curve-construction audit over raw within-task gain, anchors, ranks, family-balanced
  weights, leave-one-task/family-out samples, missing-run policies and plausible score transforms.
- [ ] Replay identical raw evidence under coarse/canonical/fine score partitions and random plus
  lineage-blocked task accumulation orders; gate curve/ranking/forecast claims on robustness.
- [ ] Validate curve forecasts on held-out suffixes, runs, tasks and families against last-value,
  monotone, per-task plateau and repeated-sampling baselines; resample whole trajectories and
  report interval coverage rather than treating checkpoints as replicates.
- [ ] Test the proposed frontier mechanism using fixed-grid material-improvement hazards versus
  normalized progress, and compare single-sigmoid, change-point, multistage and mixture models.
- [ ] Gate `Smax`/`tmid`/`beta` and curve-derived speed interpretations on profile or whole-
  trajectory bootstrap intervals, parameter correlations, rolling-window stability and adequate
  post-inflection data; otherwise report observed-window gain/AUC/time-to-material-event only.
- [ ] Register task/data/oracle/template lineage, report nominal and effective independent-world
  counts, and hold out/resample complete lineages rather than sibling instances.
- [ ] Add builder/calibrator model, scaffold, triggering trajectory/task edit and freeze timestamp
  to task lineage; run builder-balanced/leave-builder-out sensitivity and a two-family A-built/
  B-built/expert-built cross-fit pilot.
- [ ] Freeze lineage-matched open-replay, sealed-prospective and delayed-release cohorts plus an
  untouched reserve; report open-to-sealed transport and independently replay each delayed release.
- [ ] Add world/sample/batch/instrument/intervention ancestry to the durable event ledger and report
  nominal calls/bits beside lineage-clustered eESS, information gain and independent confirmation.
- [ ] Replay sentinel-complete raw trajectories under dense-event, 5/15/30/60-minute,
  seeded-random-phase and agent-event observation kernels; report interval-censored first-valid/material
  event times, AUC/curve/rank sensitivity and snapshot age rather than treating capture time as edit time.
- [ ] For interactive, consumptive or irreversible tasks, retain timestamped state transitions and
  sensor observations and publish a separate live-state measurement stratum; do not infer missing
  fixed-grid states from session-close scores or artifact-style forward fill.
- [ ] Cross fixed randomized acquisition and agent-adaptive acquisition with naive and policy-aware
  inference on one active mechanism task; persist eligible sets/propensities and fail closed on
  positivity violations before making effect, mechanism or uncertainty claims.
- [ ] Route all local experiment actions on one active-science task through a trusted result ledger;
  compare free reporting, mandatory all-result manifests and blinded synthesis for selective
  omission, effect-size inflation and claim reversal after full-ledger disclosure.
- [ ] Add CF1 on two checkpointable procedural tasks: clone preregistered full-state parents into
  independently randomized equal-budget continuations, include matched-score/different-history
  and state-channel controls, and report conditional variance plus wrong-mechanism lock-in/escape
  without selecting the best descendant; start with ActiveLawDiscovery and EnergyBalanceModel-v2,
  which already separate supported/misspecified worlds and prediction from mechanism quality.
- [ ] Generate each admission/pilot/confirmatory/figure cohort from a hashed manifest and fail
  closed on task-count, task-set, lineage, weight, transform or run-policy drift.
- [ ] Separate pilot admission/calibration worlds and runs from fresh confirmatory seeds/worlds;
  retain excluded and saturated tasks in the sampling-frame ledger.
- [ ] Partition exploratory, periodically monitored validation and one-shot post-commit
  confirmation evidence; log adaptive hypothesis/evaluator looks and refresh any confirmation
  panel used for task, curve, milestone, stopping or claim selection.
- [ ] Randomize/rotate long-run treatment order within calendar blocks, concurrently pair task
  conditions where possible, and record UTC start, endpoint/model snapshot and service incidents.
- [ ] Determine confirmatory replicate allocation from pilot variance and a preregistered material
  effect/interval-width target; treat fixed seed counts as minimum screens, not proof of power.
- [ ] Add a 4--6-project shared-budget portfolio pilot with equal/random, cost-aware VOI and agent
  allocation; report fresh-confirmed utility, allocation regret and all abandoned projects.
- [ ] Add a feedback-clock pilot that fixes active work, scientific calls and total feedback
  events/bits while randomizing immediate/even/batched/jittered release; test wall/active/cost/
  event/bit curve collapse and held-out forecasts.
- [ ] Add matched well-mixed/chain/modular-bottleneck/hierarchical procedural twins plus a
  randomized bridge/prerequisite treatment before interpreting a scaling curve mechanistically.
- [ ] Freeze a prospective task/scaffold/weight panel before making any model-generation learning-
  speed or doubling-time claim; retain all scheduled systems and adjust for initial capability.
- [ ] Add equal-bit meaningful-label, permuted-label, unlabeled-component and scalar feedback
  conditions to distinguish scientific diagnostics from score-decomposition leakage.
- [ ] Pin runtime judge provider/model snapshot, rubric/prompt, sampling, tools/corpus and response
  hashes in the event manifest; fail closed when a rubric/LLM evaluator is not reproducibly identified.
- [ ] Calibrate every rubric/LLM evaluator on blinded anchors, exact duplicates and content-preserving
  style twins, with an independent judge and expert/executable adjudication for material disagreements.
- [ ] Add FR1 source-reliability treatments with calibrated/noisy, biased, drifting and conflicting
  channels crossed with visible/hidden/permuted source labels and a costed adjudication option.

### P3 — scientific validity and distinctiveness

- [x] Implement separate development/validation/mechanism trajectory retention and default
  search redaction; do not reduce them to one “science score”. Clean pinned integration confirms
  `robustness_score` stays out of all three official backend search states while remaining in
  trusted trajectories.
- [ ] Independently review all seven core tasks and generate hidden/time-held-out instances.
- [ ] Define task-family/time-held-out splits for search-policy training and transfer studies.
- [ ] Add one certified proxy/exact multifidelity task with measured rank correlation.
- [x] Add one intervention-based mechanism task and separate mechanism score (SCM-v1 is an
  on-ramp: GPT-5.5 reaches 0.983 at budget one, so harder regimes remain required).
- [x] Add an active dynamical-law candidate with budgeted experiments, sparse mechanism
  recovery, sealed rollout/shift validation, and null/misspecified refusal cases.
- [x] Add a distinct active systems-biology candidate with nonlinear signed regulation,
  CRISPRi/a-like experiment design, protected-readout intervention utility, sealed intervention
  transfer and label-blind null/latent-regulator refusal. The truth-blind nonlinear reference
  reaches about 0.90 development and 0.88 held-out joint quality with full supported coverage,
  full unsupported refusal and zero false discovery on the admission panel; this is synthetic
  task calibration, not biological discovery.
- [x] Add misspecification/refusal cases, false-discovery penalties and supported-world
  discovery coverage to the active-law, NMR, Reaction, Ocean, Radiative and Climate discovery candidates.
- [x] Replace sparse cavity centerline scoring with full-field equations, held-out Reynolds
  transfer, refinement checks and hard physics gates; budget-one/open-loop ceiling results keep
  the current task as an on-ramp pending harder procedural or multifidelity regimes.
- [ ] Add calibrated confidence, active stopping, and unnecessary-experiment metrics.
- [ ] Add explicit `commit`/`abstain`/`continue` artifacts and a forced-continuation ablation on
  supported, null and misspecified worlds; report commitment regret and post-commit degradation.
- [ ] Add a non-monotone current-claim ledger with propose/confirm/revise/retract/abstain events,
  confidence and evidence hashes; test contradictory evidence and score unsupported-claim
  exposure, revision/retraction delay and correct-mechanism recovery.
- [ ] Add hypothesis–test–evidence/belief-update artifacts, explicit exploration DAGs,
  failed branches, falsification metrics, and replay checks.
- [ ] Require executable method bundles for discovery/inference tasks and replay preprocessing,
  experiment selection, inference, uncertainty and claims from raw inputs on fresh worlds.
- [ ] Build one linked data-QC/inference/design/intervention campaign with typed handoffs,
  uncertainty propagation, final decision regret and baseline/agent stage-swap counterfactuals.
- [ ] Run MA1/E52 first on ReactionMechanismFitting-v2 and ConvectionDiffusionOpt-v2: select
  milestones by a preregistered material-event rule, replay parent/full-child/component-only/
  leave-one-out/rollback plus key `2×2` interactions on an identical sealed panel, and separate
  `old/new data × old/new method`; current normal short trajectories have no positive jump, while
  Reaction's one selection-blind open-loop candidate is non-iterative and fails the false-discovery
  gate, so classical contrasts remain analyzer controls rather than agent causal evidence.
- [ ] Add sequential-vs-parallel, tool-access, novelty, ensemble, and component ablations where
  the corresponding scaffold capability is claimed.
- [ ] Add one stateful laboratory stress task with calibration drift, sample depletion,
  irreversible interventions and out-of-order results; bind every observation to world/sample/
  calibration/intervention lineage and distinguish physical acts from evaluator retries.
- [ ] Add one open-question procedural laboratory with fixed/menu/open contracts and signed
  pre-data preregistration; score identifiability, fresh-confirmed information/decision value,
  triviality, false discovery and plan deviation.
- [ ] Randomize blank/neutral/plausible-wrong/correct/diverse executable starters on one discovery
  lineage and measure basin escape, exploration diversity, mechanism retraction and sealed transfer.
- [ ] Tag tasks as method-prescriptive reproduction, method-neutral inference, optimization or
  mechanism discovery, and run workflow-hint ablations before claiming method discovery.
- [ ] Declare the primary benchmark's structured-observation scope or add a separate instrument/
  perception track with calibration/extraction uncertainty propagated into scientific scores.
- [ ] Implement one paired raw-instrument I6 task with oracle-clean/reference/agent preprocessing,
  realistic sensor faults and uncertainty propagation to mechanism and decision regret.
- [ ] Add V4 unit/coordinate/channel/grid/spectral metamorphic twins plus non-equivalent physical
  controls to 4--6 tasks and fail admission on unexplained claim contradictions.
- [ ] Run one T1 equal-budget single/shared/isolated/blinded-synthesis pilot with a pre-confirmation
  team commit; report correlated error and false consensus, not member-wise oracle best.
- [ ] Run U1 on one multiobjective task with a prehashed utility family and post-commit sealed
  weights; compare scalar-specific and reusable Pareto/method artifacts by regret and safety.
- [ ] Add a prospective evidence-synthesis task whose executable screening/extraction/meta-analysis/
  next-study workflow is evaluated on duplicated, heterogeneous and selectively reported studies
  plus a fresh prospective confirmation study.

### P4 — release governance

- [ ] Resolve the FrontierScience naming collision before public release.
- [ ] Freeze license, data/model redistribution, contamination cutoff and refresh policy.
- [ ] Publish a delayed-release rotation schedule and criteria for refreshing the sealed reserve;
  a static public task set is reproducibility evidence, not the permanent prospective leaderboard.
- [ ] Release privacy-reviewed raw event logs, an immutable derived analysis table and a one-command
  figure/table rebuild; task/harness release alone is insufficient to replay empirical claims.
- [ ] Freeze a dated literature corpus and cross no-literature/frozen-corpus/open-Web access with
  public, time-held-out and family-held-out tasks; label recovered known results as reproduction.
- [ ] Add matched expert one-shot and iterative trajectories on a stratified optimization and
  mechanism/refusal subset, plus independent reproduction.
- [ ] Require high-fidelity or physical replication for every “discovery” claim.

## Go/no-go gates

- **v0.1-lite go:** all P2a items complete on the seven certified tasks, with no security or
  certification regression and at least one classical baseline.
- **Track F claim go:** normal feedback shows paired, repeated lift over strict selection-blind,
  shuffled and no-feedback controls—not only prompt-metric masking.
- **Discovery claim go:** the relevant system demonstrates feedback learning over controls,
  mechanism recovery or hidden-shift/intervention validity, independent high-fidelity/physical
  confirmation, calibrated stopping/refusal, and provenance review. Optimization-only results
  must remain labeled optimization.
- **Expansion go:** only after the certified core is empirically useful; directory count is not a
  milestone.
