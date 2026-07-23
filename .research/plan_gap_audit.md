# Frontier-Science plan gap audit

Audit date: 2026-07-19 (UTC), with the experiment roadmap extended after a full-text
EdgeBench comparison and the task inventory updated on 2026-07-23 through
ConvectionDiffusionOpt-v2.
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
| Candidate/oracle isolation | Implemented | Clean-revision security v15: 18/18 adversarial tests; Bubblewrap, no network, read-only mounts, resource/seccomp limits, typed RPC, fresh multi-world sessions and candidate-exception sanitization | Reproduce in clean Linux CI; document portability/non-Linux behavior |
| Fail-closed trusted metrics | Implemented | Clean-revision 51×2 v21: 51 deterministic, 51 valid, 51 fail-closed and zero infrastructure failures after the ConvectionDiffusionOpt-v2 findings update | Repair or quarantine every future invalid candidate oracle before certification |
| Task admission policy | Implemented, narrow | Current manifest: 7 certified / 26 candidate / 18 quarantined; the latest rebuilds add active inverse/discovery candidates, LowThrustTransfer-v2, full-field LidDrivenCavity-v2, Climate-v2, BroadbandAbsorber-v2, Distillation-v2, HartreeFockSCF-v2, RoomImpulseResponse-v2 and ConvectionDiffusionOpt-v2 | Independent domain + evaluator reviews are still declarations, not completed external review |
| Scientific validity of inventory | Audited, sparse | All original 50 packages passed adversarial admission; ActiveLawDiscovery brings inventory to 51 and substantive rebuilds now leave 33 internally admissible packages | Rebuild high-value families and add approximately 17 net admissible tasks to reach about 50; hidden/generated instances and shortcut analysis remain mandatory |
| Unified trajectory/accounting | Implemented, protocol-smoked | Clean-revision two-seed baseline smoke; trajectory schema v2, hashes, AUC over `budget_units`, separate `oracle_calls`, wall/token/cost, seed, checkpoint/resume | Validate nonzero-budget schema-v2 artifact replay in CI and version future changes |
| Feedback controls | Implemented; strict pilot run | None/shuffled prompt-metric modes disclose true-score selection; strict selection-blind freezes parent/metrics; four-task n=3 pilot has no direction-stable lift and is not token-matched | Run token-matched ≥10 paired seeds with score-only, delayed/replayed and strict open-loop controls |
| Evaluator-only metric sealing | Implemented and integration-verified | Closed search-visible allowlist; search-state redaction/hash-keyed sidecars; candidate-controlled exception text mapped to a finite label-blind taxonomy; 212-test suite; clean pinned OpenEvolve/TreeQuest/Shinka no-leak report `aff026d` | Extend from baseline smoke to nonzero-budget upstream runs before comparative claims |
| Official OpenEvolve adapter | Implemented, trusted baseline smoke | Explicit 0.2.26 adapter; clean-revision secure baseline passed under Python 3.10 | Run nonzero-budget/checkpoint integration and multi-seed study |
| TreeQuest AB-MCTS | Implemented, trusted baseline smoke | Real TreeQuest AB-MCTS-A ask/tell adapter; clean-revision secure baseline passed under Python 3.12 | Run nonzero-budget/checkpoint integration and multi-seed study |
| ShinkaEvolve | Implemented, trusted baseline smoke | Official runner/database adapter at pinned commit; clean-revision secure baseline passed under Python 3.10 | Run nonzero-budget/resume integration and token accounting audit |
| Classical/domain baselines | Partial | NMR, HeatExchanger, Reaction, Gravity, Ocean, Radiative, LowThrust and Climate rebuilds have truth-blind domain baselines exposing reconstruction/proxy/prediction, terminal-feasibility, experiment-design or mechanism/refusal gaps | Add random/quasi-random plus BO/CMA-ES/DE and one domain heuristic for each meaningful task family |
| Multi-seed benchmark evidence | Missing | Keyless GPT-5.5 Responses path is operational; 41 trusted normal single-run conditions cover 21 tasks and a separate four-task n=3 control pilot is negative/inconclusive | Certified-core and science-subset reports with paired uncertainty and portable raw trajectories |
| Multifidelity/Pareto | Candidate-level | HeatExchanger-v2 implements proxy/exact Pareto archives, measured false promotion and physical shifts | Add independent high-fidelity review/replication and at least one certified multifidelity task |
| Feedback learning claim | Negative pilot only | A strict open-loop control and three-replicate four-task pilot are complete; no direction-stable visible or sealed lift, and normal uses more tokens | Token-matched preregistered ≥10-replicate study with delayed/replayed and score-only controls |
| Mechanistic discovery | Candidate-level | ActiveLaw, NMR, Reaction, Gravity, Ocean, Radiative and Climate tasks separately score mechanisms, prediction, coverage, hidden shifts, false discovery and refusal | Add paired repeated studies, harder regimes and independent scientific validation |
| Validation/distribution shift | Calibration-level | Nominal/robustness and prediction/mechanism gaps recur across control, design and inverse tasks; Radiative adds a protocol-valid perfect-refusal/zero-coverage case, Climate adds near-unit prediction with weak mechanism and false model claims, LowThrust separates numerical integration error from terminal feasibility, and BroadbandAbsorber separates nominal band transfer from manufacturing-envelope robustness | Paired repeated hidden-shift studies plus independent high-fidelity or physical confirmation and abstention cases |
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

The keyless GPT-5.5 Responses path was restored and 41 trusted normal single-run conditions now
cover 21 tasks, with task-specific strict open-loop diagnostics on a subset. They expose
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
causal case-study attribution.

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

## Revised TODO plan

### P0/P1 closeout — completed locally, reproduce in CI

- [x] Trusted oracle / isolated candidate architecture and adversarial regression suite.
- [x] Current 51-package deterministic secure baseline and certification audit; all 51 weak baselines are valid, deterministic and fail closed.
- [x] Seven-task certified core, 26 candidates and 18 quarantined packages after all
  admission waves and the current substantive rebuilds.
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
- [ ] Add fixed-interval evaluator-only snapshots that never affect online selection or stopping.
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
- [ ] Add adaptive allocation/stopping baselines (for example, SMC-style convergence control).
- [ ] Add a task-contract linter for prompt versus actual horizon, checkpoint schedule,
  evaluator timeout, cooldown, maximum submissions, submitted paths and deliverables.
- [ ] Use independent runs disclosed their true horizon for budget comparisons; do not treat a
  horizon-aware long run's prefixes as counterfactual short-horizon executions.
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
- [ ] Separate pilot admission/calibration worlds and runs from fresh confirmatory seeds/worlds;
  retain excluded and saturated tasks in the sampling-frame ledger.
- [ ] Partition exploratory, periodically monitored validation and one-shot post-commit
  confirmation evidence; log adaptive hypothesis/evaluator looks and refresh any confirmation
  panel used for task, curve, milestone, stopping or claim selection.
- [ ] Randomize/rotate long-run treatment order within calendar blocks, concurrently pair task
  conditions where possible, and record UTC start, endpoint/model snapshot and service incidents.
- [ ] Determine confirmatory replicate allocation from pilot variance and a preregistered material
  effect/interval-width target; treat fixed seed counts as minimum screens, not proof of power.
- [ ] Freeze a prospective task/scaffold/weight panel before making any model-generation learning-
  speed or doubling-time claim; retain all scheduled systems and adjust for initial capability.
- [ ] Add equal-bit meaningful-label, permuted-label, unlabeled-component and scalar feedback
  conditions to distinguish scientific diagnostics from score-decomposition leakage.

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
- [ ] For selected large trajectory jumps, replay parent, full child, component-only patches and
  rollback on an identical sealed evaluator panel before attributing a milestone to an insight.
- [ ] Add sequential-vs-parallel, tool-access, novelty, ensemble, and component ablations where
  the corresponding scaffold capability is claimed.
- [ ] Tag tasks as method-prescriptive reproduction, method-neutral inference, optimization or
  mechanism discovery, and run workflow-hint ablations before claiming method discovery.
- [ ] Declare the primary benchmark's structured-observation scope or add a separate instrument/
  perception track with calibration/extraction uncertainty propagated into scientific scores.

### P4 — release governance

- [ ] Resolve the FrontierScience naming collision before public release.
- [ ] Freeze license, data/model redistribution, contamination cutoff and refresh policy.
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
