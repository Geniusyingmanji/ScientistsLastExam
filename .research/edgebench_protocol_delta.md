# EdgeBench → Frontier-Science protocol delta

Date: 2026-07-23 UTC, rechecked and extended 2026-07-24. Sources: EdgeBench arXiv:2607.05155v1 full text; public SForge
repository revision `a87350ab80eeb320b13cb71d1b0c3ffcc20a670f`; official Codex experiment
configuration; and the public 51-task Hugging Face dataset at revision
`47846a4c3669ad447e0ea984833b0d352460c5f9`. The arXiv API, upstream `main` and dataset were
rechecked on 2026-07-24 and still resolve to v1 and these revisions. EdgeBench results
below are author-reported; implementation observations are labeled separately.

## What EdgeBench actually establishes

- The full study has 134 tasks in six families and aims for three independent 12-hour runs per
  task–model pair. Appendix G notes that a few cells still contain fewer than three valid runs
  after rolling recovery, so run coverage must remain explicit.
- Its official Codex defaults are 12 hours, host auto-evaluation every 30 minutes and a
  120-second agent submission cooldown, with larger task-specific cooldowns where judging is
  slow. Auto-eval scores current artifacts but does not return the results to the agent.
- The public SForge documentation defines the final result as the best result across both
  agent-initiated submissions and invisible auto-eval snapshots. This is a useful observer-side
  optimization statistic, but it retrospectively uses an oracle the agent cannot use to commit
  its own final artifact.
- On a 17-task subset, one stateful 12-hour run scores 43.0 versus 36.1 for the best of six
  independent 2-hour restarts. This is evidence that retained state can beat equal-time repeated
  sampling; it is not a shuffled/no-feedback identification of the causal value of judge scores.
- On a 42-task subset, a 1M context beats 200k by 4.4 points at 12 hours even with external
  workspace state. The retained information channel is therefore an experimental factor.
- The gravitational-wave case makes trajectory quality concrete: 224 explicit submissions plus
  23 hidden auto-evaluations produced only 27 improvements of at least 0.1 percentage points.
  Raw regressions, targeted rollback and improvement magnitude carry information that the
  monotone best-so-far envelope hides.
- The reported log-sigmoid fit is a population-level result across many heterogeneous tasks, not
  a claim that an individual task should have a smooth sigmoid curve.
- EdgeBench deliberately selects tasks with an unsaturated ceiling and an iterative workflow.
  The resulting curve is therefore conditional on a headroom-enriched sampling frame, not an
  estimate for arbitrary scientific work. Its recorded 57.2-hour mean human effort is task
  construction effort, not a matched-budget human trajectory baseline.
- SForge keeps sessions alive with a stop hook and auto-resume, and its judge may evaluate
  asynchronously while the agent continues editing. These are real deployment variables, but
  they make stopping quality, feedback lineage and active compute distinct from elapsed time.
- The public harness supports task-specific nonlinear and piecewise 0--100 score transforms.
  Aggregate curve shape and fitted speed are consequently conditional on normalization anchors,
  task weights and the set of admitted tasks.
- The public 51-task release contains only four items labeled `Scientific Problems & ML`:
  BipedalWalker RL, Borden source inversion, D-ABIC gravity inversion and graph node
  classification. The full 39-task science/ML category mixes prediction, solver implementation,
  method reproduction, inverse problems and optimization. Category membership is not evidence
  of autonomous scientific discovery.

## Protocol mapping

| EdgeBench element | Adopt directly | Science-specific extension in this project |
|---|---|---|
| Isolated work and ephemeral judge environments | Keep Bubblewrap candidate/oracle separation, network isolation and trusted metric sidecars | Independently replay equations/simulators and bind every scientific claim to immutable artifacts |
| Fast local loop + slower authoritative judge | Allow public local tests; rate-limit agent-visible trusted evaluation | Separate visible nominal feedback from evaluator-only held-out, physical-shift, mechanism, stability and false-discovery measurements |
| Host auto-eval | Fixed-interval current-artifact snapshots whose results never enter agent/search state | Charge the calls, mark them distinctly, use atomic content-addressed snapshots, and prohibit hidden snapshot scores from selecting the primary committed result |
| Continuous run vs six restarts | Add equal-budget stateful versus restart conditions | Match proposal calls, visible submission schedule/cooldown, tool access and feedback payload; report token and wall-time mismatches rather than hiding them |
| Full submission history | Retain raw score, best-so-far, diffs, failures and later regressions | Add development–validation gap, mechanism/prediction gap, false discoveries, refusal, experiment cost and independent replication over time |
| Effective-submission rate | Report fraction and magnitude of true incumbent improvements | Also report validated-discovery rate per experiment/oracle call, rollback latency and active-learning span |
| Context ablation | Compare full, summarized and frozen/no scientific memory | Score whether memory contains correct hypotheses, falsified branches and calibrated beliefs—not merely more tokens |
| Best submission as final result | Retain best feasible score and AUC as observer-side optimization metrics | Report agent-committed, terminal-workspace and hidden-snapshot oracle-best artifacts separately; science claims use a deployable committed artifact, and stochastic tasks additionally require expectation/median and uncertainty |
| Stop hook and auto-resume | Use them for a fixed-horizon capability curve and log every intervention | Add an agent-controlled stopping/refusal condition; score stopping correctness, cost and post-stop degradation rather than forcing endless experimentation in every estimand |
| Asynchronous authoritative judging | Preserve throughput where judging is slow | Bind submitted artifact hash, feedback-ready/feedback-read time and every descendant; stale feedback cannot be credited as causing an earlier or unrelated improvement |
| Aggregate time curve | Fit alternative saturating models only after a large repeated task population exists | Use active model time, local tool/simulator calls, visible submissions, judge/queue wait, trusted oracle calls, tokens/cost and wall time as separate axes; require held-out-task/time forecasting and transformation sensitivity |
| Headroom-based task selection | Keep headroom as a headline-task admission criterion | Retain saturated on-ramps, null/misspecified and unsolvable cases in a separate reliability sampling frame so scaling and refusal claims are not conditioned only on improvable tasks |
| Rich component feedback | Treat scalar, component and diagnostic payloads as distinct conditions | Compare meaningful labels with label-permuted/equal-bit diagnostics to distinguish physical bottleneck discovery from following score weights |

## Controls added because of EdgeBench's hacking evidence

EdgeBench reports hidden-target reconstruction after more than 400 detailed submissions,
stochastic upper-tail exploitation with best 1501 versus mean 484 over 311 submissions,
overfitting a reused evaluator seed and writing through an exempt trusted path. Frontier-Science
therefore requires:

1. a predeclared agent-visible submission budget and cooldown;
2. scalar/aggregated feedback by default, with diagnostic feedback treated as a separate
   information-bandwidth condition;
3. hidden seed ensembles and expected-performance reporting for stochastic tasks;
4. integrity checks over every writable path and exact candidate/source hashes;
5. evaluator-only snapshots that cannot be queried or observed by the agent; and
6. a feedback-resolution audit showing that repeated outputs cannot cheaply solve for hidden
   targets.

## Additional science-specific deductions from the implementation

1. **Separate three endpoint policies.** For every run retain (a) the artifact explicitly
   committed by the agent/search policy, (b) the workspace artifact at the fixed horizon, and
   (c) the evaluator-only best among all snapshots. Report `oracle_selection_gap =
   sealed(oracle_best) - sealed(committed)`. The third is a diagnostic upper bound, not an
   autonomously selected scientific conclusion.
2. **Decompose prior capability from learning.** Add a matched one-shot/no-environment baseline
   and report gain from the first valid artifact, not only total score. Time to first valid
   artifact, time to first new validated mechanism and sealed gain per revealed feedback event
   answer different questions.
3. **Use two time estimands.** End-to-end wall time legitimately measures deployability, while
   active model/tool time and charged scientific experiment cost measure algorithmic efficiency.
   Queueing, judge latency, service incidents, resumptions and idle time must be explicit rather
   than silently absorbed into a single learning-speed parameter.
4. **Treat run attrition as an outcome.** Publish scheduled, started, completed, recovered and
   valid run counts with reason-coded exclusions. Report both valid-run scientific performance
   and an operational estimand that retains infrastructure/model failures; fitting only survivors
   can bias long-horizon comparisons.
5. **Audit aggregate-curve construction.** Predeclare score transforms and task weights, then
   repeat fits under raw within-task improvement, anchor-normalized gain, task ranks, family-
   balanced weighting, leave-one-task/family-out samples and plausible anchor perturbations.
   A curve or model ordering that depends on one normalization is not a scaling law.
6. **Make snapshot and feedback lineage atomic.** A host snapshot taken while files are being
   edited can capture a transient mixed artifact. Snapshot only committed content-addressed
   bundles, and attribute a feedback-driven edit only to descendants created after that feedback
   was received.
7. **Freeze the knowledge environment.** Science tasks need literature, unlike tasks where Web
   access can simply be disabled. Compare frozen-corpus, open-Web and no-literature conditions,
   log cited evidence and apply time/family-held-out novelty checks so retrieval or reproduction
   is not mislabeled discovery.
8. **Add matched expert trajectories.** Task-author effort does not calibrate agent performance.
   On a small stratified subset, collect expert one-shot and iterative trajectories under the
   same feedback, experiment and wall/compute budgets, including confidence, stopping and failed
   hypotheses.

## Second-pass implementation findings

These are protocol deductions from the released SForge code, official configuration and public
task contracts, not additional empirical claims by the EdgeBench authors.

1. **Hidden auto-evaluation is score-blind but not behavior-blind.** SForge's generated prompt
   tells the agent that a background process periodically evaluates its files and explicitly asks
   it to keep submitted paths runnable and representative of its current best solution. The
   measurement schedule can therefore change branch management, risk taking and write timing even
   though scores remain hidden. This matters more in science, where scratch calculations and
   partially written hypotheses are often temporarily invalid. Keep a stable, explicitly
   committed candidate head separate from a scratch workspace; compare schedule-disclosed,
   schedule-blind/jittered and no-online-snapshot conditions.
2. **Evaluator-only measurement can consume the treatment's resources.** Auto-eval archives the
   live workspace and submits to the same judge service used by agent-visible evaluations. It may
   add CPU/I/O load or judge queue contention and is therefore not automatically a passive
   observer. Use a separate observer queue or evaluate immutable event snapshots after the run;
   measure any effect of snapshotting on model/tool throughput and visible-feedback latency.
3. **Repeated identical snapshots need hash-aware semantics.** Auto-eval is exempt from agent
   submission limits and cooldowns, and SForge's final policy can choose across auto-eval results.
   Re-evaluating an unchanged stochastic artifact can therefore create an uncharged best-of-N
   advantage merely because it remained in the workspace longer. Deduplicate identical hashes for
   deterministic judges; for stochastic judges, aggregate preregistered seed replicates into an
   expectation and uncertainty interval rather than treating them as distinct selectable
   candidates.
4. **The declared horizon must agree everywhere.** The official Codex YAML gives every public
   task a 43,200-second horizon, but the released `bipedalwalker_locomotion_rl` contract tells the
   agent it has a two-hour window, requests a submission within 30 minutes and says to work until
   close to that limit. This concrete contract/config mismatch can alter training allocation and
   stopping behavior. Add a machine-checked contract lint over prompt, harness timeout, checkpoint
   schedule, evaluator timeout and cooldown; estimate horizon effects with independent runs whose
   disclosed horizon matches the actual cutoff.
5. **The experience ablation bundles several state channels.** A continuous run retains the
   incumbent artifact, scratch workspace, local datasets/caches, authoritative feedback history,
   natural-language context and any external notes, whereas a restart removes all of them. The
   reported contrast establishes value of that bundle, not which scientific memory caused it.
   Factor artifact-only, local-results-only, feedback-ledger-only, summarized hypothesis/evidence
   memory and full-state retention. Test whether later proposals actually cite and correctly use
   retained evidence rather than merely inheriting a better program.
6. **Continuation scaffolds are part of the evaluated system.** Appendix G.3 reports highly
   heterogeneous effects from Goal and file-backed Ralph-loop variants, including large positive
   and negative task-level changes. Cross-model comparisons are additionally crossed with Codex
   versus Claude Code and different context limits. Report a model--scaffold bundle unless the
   scaffold, context, tool and continuation factors are held fixed or factorially ablated.
7. **Restart subset enumeration is not replication.** EdgeBench estimates the no-experience curve
   from size-`k` subsets of six two-hour terminal scores. The combinatorial subsets are dependent
   views of one restart pool and do not create new experimental units. Frontier-Science should use
   independently repeated restart pools paired to task instances, retain pool-level uncertainty
   and distinguish terminal-best sampling from within-restart trajectory AUC.
8. **Any strictly larger score is too permissive near a numerical ceiling.** Effective-submission
   rate and online incumbent selection can count changes below evaluator resolution. The current
   Hartree--Fock calibration gives an internal example: an approximately `9e-15` visible gain can
   select an artifact with a qualitatively different robustness tradeoff. Predeclare an
   evaluator-noise/resolution-based `epsilon`, scientifically material effect thresholds and a
   Pareto/constraint-aware commit rule; report how many nominal improvements survive each rule.
9. **Deadline eligibility and causal feedback eligibility differ.** SForge stops auto-eval at the
   horizon and then drains pending judge jobs. An artifact submitted before the cutoff can be
   scored after it, but feedback completed after the cutoff cannot have caused in-horizon work.
   Record artifact creation, submission, judge start/finish and feedback-read times; predeclare
   whether post-cutoff completions enter observer-side scoring and exclude them from feedback-use
   attribution.
10. **The local loop is not separately identified.** EdgeBench deliberately permits
    unlimited local tests, simulators and agent-created validation splits while gating only the
    authoritative judge. For scientific automation, local simulation, data analysis and physical
    measurement have different costs and epistemic value. Instrument both loops and run a
    two-by-two local-feedback × trusted-feedback ablation before attributing improvement to the
    judge or to "environment learning" in general.
11. **Task guidance spans discovery to prescribed reproduction.** Public science tasks range from
    open source inversion to a prompt that names a 2025 D-ABIC paper and asks the agent to port its
    method. Stratify method-prescriptive reproduction, method-neutral inference, optimization and
    mechanism discovery; ablate workflow hints. A long trajectory on a prescribed method is not
    evidence that the method was discovered.
12. **Structured-data scope is not full scientific scope.** EdgeBench explicitly excludes tasks
    whose main difficulty is visual understanding so that perception does not confound iterative
    reasoning. Frontier-Science should either state the same structured-observation scope or add a
    separate instrument/perception track that propagates calibration, segmentation and extraction
    uncertainty into mechanism and validation scores instead of silently mixing it into them.

## Third-pass curve and claim findings

These deductions come from re-reading the scaling-law, learning-speed and case-study sections
against the current science calibrations. They are not additional empirical results from the
EdgeBench authors.

1. **A single absolute-score curve conflates bootstrapping with optimization.** EdgeBench fits
   absolute best-so-far performance with a three-parameter curve whose lower asymptote is zero,
   even though its learning-speed slice has nonzero first-attempt performance and its
   gravitational-wave case begins with the qualitatively distinct event of creating a scoreable
   pipeline. Frontier-Science has many protocol-invalid, runtime-invalid or scientifically
   infeasible early proposals, so one smooth mean would mix interface competence with scientific
   progress. Use a hurdle/multistate analysis: cause-specific time to first valid artifact,
   probability of validity by budget, quality conditional on validity, and probability of a
   jointly sealed-and-mechanism-valid result. Fit gain from a preregistered first-valid or one-shot
   baseline rather than forcing all prior competence into the same learning curve.
2. **Dense checkpoints do not create independent evidence for a curve.** A best-so-far trajectory
   is monotone and serially dependent, and cross-task averaging makes it smoother by construction.
   Resample whole task-instance/run trajectories, not timepoints. Forecast tests should freeze the
   model before the held-out suffix and include held-out runs, tasks/families and eventually model
   generations. Compare against last-value-carried-forward, monotone interpolation, empirical
   per-task plateaus and repeated-sampling baselines; report interval coverage and held-out error,
   not only in-sample or level-dominated `R²`.
3. **The proposed mechanism is testable rather than implied by fit.** EdgeBench reports RMSEs of
   `0.390`, `0.398`, `0.402` and `0.404` for four three-parameter S-curve families and explicitly
   says the data cannot empirically separate the symmetric families. Its frontier account assumes
   cut mixing, concentrated task midpoints/speeds, stable attainable support, self-similar search
   geometry and effort approximately linear in elapsed time. Test its distinctive prediction on
   fixed-grid, materially thresholded events: the improvement hazard should track
   `y(1-y)` and peak near normalized progress `y=0.5`. Compare change-point, multistage and
   mixture-of-sigmoids alternatives. Scientific workflows with validity, optimization,
   validation and mechanism bottlenecks are a principled place to expect multiple phases.
4. **Submission efficiency is endogenous.** EdgeBench's effective-submission rate depends on
   when an agent chooses to submit, task score granularity, evaluator noise and a strict-positive
   incumbent rule. Use hash-deduplicated evaluator-only fixed-grid snapshots for the primary
   cross-system improvement-rate comparison, with numerical and domain-material thresholds.
   Treat voluntary submission cadence, bundled edit size and rollback behavior as secondary
   behavioral outcomes rather than interchangeable measures of learning efficiency.
5. **A retrospective model-speed trend needs prospective replication.** EdgeBench forms an
   18-task slice with similar observed first-attempt scores, evaluates different model--scaffold--
   context bundles, and fits rolling top-two frontier systems by release date. That is useful
   exploratory evidence but can inherit task-selection, regression-to-the-mean, frontier-selection
   and harness confounding. Freeze a task panel, weights, scaffold and analysis before evaluating
   future models; retain all scheduled systems; model initial capability as a covariate rather
   than selecting tasks on the same observed baseline; and require prospective replication before
   claiming a temporal doubling rate.
6. **The science case study is closer to reproduction than discovery.** Its milestones include
   digitizing published reference traces and fitting directly to them. That can demonstrate
   persistent engineering progress, but it does not establish recovery of a novel mechanism.
   Every science task therefore needs a target-access audit: determine whether visible papers,
   figures, baselines or repeated diagnostics can reconstruct evaluator targets, and require
   predictions on new observations, interventions or regimes before calling the result discovery.
7. **Protocol release and claim replay are different deliverables.** As rechecked on 2026-07-24,
   the public GitHub/Hugging Face release provides the SForge harness and 51 of 134 task contracts,
   but not the raw 38,000-hour trajectory corpus or figure-analysis code. The headline fits are
   therefore not independently replayable from the public release alone. Frontier-Science should
   publish an immutable analysis table derived from raw event logs plus a one-command figure/table
   rebuild, while separately protecting server-held oracle assets.

## Fourth-pass science and estimand findings

These are further protocol deductions from EdgeBench's theoretical assumptions, full score
tables and long-run operations. They are not additional empirical claims by the EdgeBench
authors.

1. **Scientific claims are reversible, unlike unlocked score units.** EdgeBench's frontier model
   assumes that an unlocked score unit never locks again, matching a monotone best-so-far
   optimization envelope. A scientific mechanism can instead lose support after an intervention,
   regime shift or independent replication. In addition to observer-side best curves, retain a
   time-indexed current claim, confidence, evidence set and explicit `confirm`, `revise`, `retract`
   or `abstain` transition. Inject preregistered contradictory and misspecification evidence and
   measure retraction delay, unsupported-claim exposure, oscillation and recovery of the correct
   mechanism. Never carry an earlier high mechanism score forward after the agent has abandoned
   that mechanism.
2. **A fitted learning speed is not identified when the ceiling is weakly observed.** The three-
   parameter curve jointly estimates `Smax`, `tmid` and `beta`; the paper's 28-hour GPT-5.5 fit,
   for example, has `tmid=14.4h` inside a 28-hour window and a shallow `beta=0.25`. A high level-fit
   `R²` does not show that these parameters, or a frontier-speed reading of `beta`, are stable.
   Require profile-likelihood or trajectory-bootstrap intervals, parameter correlations,
   rolling-window stability, and a minimum amount of post-inflection support. If the ceiling or
   midpoint is not identified, report bounded observed-window gain or time-to-material-event
   rather than a point learning speed.
3. **Task count is not effective sample size.** The suite contains progressive tasks, shared
   domain/data families and related construction templates, so 134 rows need not represent 134
   independent scientific environments. Register a task-lineage graph, cluster near-duplicate
   instances and shared oracle/data ancestry, resample at the lineage/family level, and report an
   effective independent-world count. Hold out complete lineages, not random sibling instances,
   for transfer and scaling forecasts.
4. **Long runs need calendar-time blocking.** Appendix B shows serving reliability changing over
   elapsed time, while SForge's official multi-task launcher staggers starts. Model, feedback and
   scaffold conditions run on different calendar days can therefore inherit service-load or
   endpoint-version effects. Randomize or rotate treatment order within task-instance blocks,
   launch paired conditions concurrently where quotas permit, log endpoint/model snapshots and
   calendar timestamps, and include calendar batch as a design factor. A calendar-imbalanced
   contrast is operational evidence, not a clean algorithmic or feedback effect.
5. **Milestones need counterfactual edit tests.** The gravitational-wave narrative assigns score
   jumps to phases and components, but a chronological trace alone does not establish which edit
   caused a gain, especially when edits are bundled. At selected breakthroughs, replay the parent,
   full child, component-only patches and rollback on the same sealed evaluator panel. Report
   causal-edit retention and interaction effects; label an unablated milestone as an interpreted
   case study rather than a discovered mechanism.
6. **Task admission and confirmatory evaluation must use separate evidence.** EdgeBench selects for
   unsaturated headroom, and this project also uses model runs to calibrate candidate difficulty.
   If the same trajectories set thresholds, choose tasks and support headline curves, the final
   estimate is adaptively selected. Freeze admission on a pilot model/seed/world panel, then use
   fresh confirmatory seeds, procedural worlds and preferably later models; publish excluded and
   saturated tasks in the sampling-frame ledger. Any reused admission data remains exploratory.
7. **Replicate counts should follow the intended claim, not a universal constant.** EdgeBench's
   full tables show large task-specific run variation, including standard deviations near the
   score range on some science tasks, so three runs can be descriptive but severely underpowered
   for feedback, mechanism or model-ranking contrasts. Use pilot variance and a preregistered
   material effect to simulate hierarchical power/precision, then allocate independent runs by
   lineage and task. Keep the broad five-seed screen exploratory when the confirmatory precision
   target is not met.
8. **Adaptive exploration can spend the same evidence twice.** A long-running science agent may
   inspect many hypotheses, experiments and diagnostics before selecting one conclusion. Even if
   the evaluator is hidden from source code, repeatedly using the same sealed worlds for
   snapshots, milestone interpretation or task calibration turns them into an adaptive
   development set. Partition exploratory, commit and one-shot confirmation budgets; after a
   signed claim, evaluate it on a fresh server-held world or high-fidelity replication that was
   never used for search, curve fitting, admission or stopping. Report the number of hypothesis
   and validation looks, and refresh a contaminated confirmation panel rather than calling it
   sealed.

## Fifth-pass task-construction and measurement findings

These findings come from auditing all 39 `Scientific Problems & ML` design notes and their full
score table, rather than only the four publicly released science task contracts.

1. **A scientific workflow can be a linked campaign, not four nominally independent tasks.**
   EdgeBench's Borden/Cape Cod group spans sensor-fault diagnosis, source inversion, monitoring-
   network reconstruction and pump-and-treat dispatch. That decomposition exposes where a
   workflow fails, but the tasks share a scientific system and cannot be counted as independent
   worlds. Frontier-Science should build at least one end-to-end campaign with a typed handoff
   from data-quality diagnosis to inference, experiment design and intervention. Report both
   stage-local scores and final decision regret, propagate upstream uncertainty, and cluster all
   campaign stages under one lineage for confidence intervals and held-out transfer.
2. **The primary discovery artifact should be an executable method, not a fitted answer.** Several
   EdgeBench tasks require a solver, directive, scripts, results and a report, whereas the public
   Borden judge reads only the final `answer.json`. The latter can test one inverse answer but
   cannot show that the method would work on a new aquifer. For discovery and inference tasks,
   replay the submitted workflow from raw observations on unseen procedural worlds, including
   preprocessing, experiment selection, inference, uncertainty and claim generation. Score both
   method replay and the final claim; a correct static answer with a non-replayable or target-
   specific workflow is not a transferable scientific result.
3. **Long-horizon readiness needs a measurement-health gate, not headroom alone.** The full
   science table includes ceiling cells (`100`), an all-model floor (`0` on
   `substrate_interface_simulation`) and task/model standard deviations comparable with most of
   the score range (for example Ocean MT, VSG and motor-clutch cells). These are valid descriptive
   results, but such cells contribute little identifiable information to a three-run learning or
   model contrast. Before 6h/12h admission, measure first-valid probability, baseline--reference
   separation, fixed-artifact repeatability, evaluator resolution, non-saturation, material gain
   after 2h, and shortcut resistance. Use common worlds/seeds and more repeats when scientific
   stochasticity is genuine; quarantine evaluator noise or universal floor failures rather than
   smoothing them into an aggregate curve.
4. **Stage-local improvement and end-to-end scientific utility can disagree.** A better anomaly
   classifier or inverse fit need not improve the downstream monitoring or intervention decision.
   Run counterfactual handoff replays that swap baseline versus agent-produced outputs at each
   campaign stage, then estimate main and interaction effects on final utility, safety and false
   intervention. This gives a scientific analogue of the gravitational-wave component trace, but
   with causal stage ablations rather than a chronological narrative.
5. **The 39-task category is a sampling frame, not a discovery denominator.** Its design notes
   mix prediction, numerical software, prescribed reproduction, inverse problems, active
   learning and decision optimization. Publish track labels before aggregation and report how
   many independent lineages and genuinely active discovery environments support each claim.
   The label `Science / ML`, a real dataset, or a long runtime does not by itself establish an
   autonomous-science task.
6. **Every aggregate needs a versioned cohort manifest.** In the arXiv v1 source,
   `task_by_task_specifications.tex` assigns the 134 tasks to families with counts
   `36/39/19/13/19/8`, while `category_score_tables.tex` assigns the same 134 task IDs with counts
   `35/34/16/13/24/12`. Eleven tasks change family. In particular, five Science/ML design-note
   tasks move to Systems, Optimization or Knowledge Work in the score tables; averaging the 34
   displayed one-decimal Opus row means gives `48.494...`, which rounds to the reported Science
   score `48.5`. Adding the five moved displayed rows gives `47.395`, and their full one-decimal
   rounding intervals still cannot yield `48.5`. This does not invalidate the 134-task total, but
   the public text alone leaves two different family sampling frames. Frontier-Science must bind every curve,
   table and claim to a machine-readable manifest containing task IDs, track labels, lineage
   clusters, weights, score transforms, run inclusion and an immutable hash. A prose category
   count is not sufficient provenance for a family-level result. The source-hash-bound mapping
   and numerical cross-check are retained in
   `.research/edgebench_taxonomy_audit_2026-07-24.json`.

## Sixth-pass contract and runtime findings

These findings come from rechecking all 51 public task contracts and tracing the current SForge
prompt, selector, judge history, snapshot and visualizer paths. The upstream paper, GitHub main and
Hugging Face dataset remain at v1, `a87350a` and `47846a4`; this is therefore an incremental
implementation audit, not a new EdgeBench result.

1. **The objective-selection contract is not uniform across system layers.** The public contracts
   contain 37 `score_first`, four `valid_then_score`, one explicit `pass_rate_first` and nine
   default-`pass_rate_first` tasks. The generic prompt nevertheless says the best score across all
   submissions is final; its local cache advances only on pass-rate gain; the judge executes the
   configured selector; and the visualizer reads selector metadata but recomputes best/ranking via
   score direction or pass rate. Frontier-Science must render one exact, versioned objective and
   selection contract into the prompt and replay it through online state, commit, terminal,
   dashboard and analysis, failing closed on incumbent-hash disagreement.
2. **The convenient run history is a lossy view, not a scientific event ledger.** `EvalReport`
   contains normalized score, runtime, timeout, details, metrics and submission time, but
   judge-server history retains only scalar score/pass rate/counts/valid/summary and explicitly
   drops `score_0_100`. Component trajectories and exact feedback therefore require later joins
   against mutable per-submission files. Use an append-only, schema-versioned ledger containing the
   full raw report, visible-feedback projection, artifact/evaluator/world hashes, all event times,
   costs, failure/retry lineage and selector decisions; generate derived tables only from this
   ledger plus a hashed cohort manifest.
3. **Periodic snapshots omit guaranteed trajectory boundaries.** Auto-evaluation waits one full
   interval before its first tick, stops before terminal archive extraction, and does not judge
   that terminal archive on the same path. A run may therefore lack both `t=0` and terminal points.
   Force immutable, charged sentinels at baseline, first-valid, every explicit submission/commit,
   every fixed checkpoint and the cutoff terminal; reason-code missing captures instead of
   forward-filling historical best.
4. **Agent auto-resume is not exactly-once experimental recovery.** The public judge holds session,
   counters, pending status and run history in process memory. A judge restart can lose budget or
   lineage even if the work container and agent continue. Persist evaluation intent before work,
   key it by artifact + evaluator manifest + seed/world panel, atomically commit outcomes, and
   crash-test that recovery neither loses nor repeats stochastic/costly evidence.

The source hashes, contract census and explicit claim limits are retained in
`.research/edgebench_contract_runtime_audit_2026-07-24.json`.

## Seventh-pass effort-clock and autonomy findings

These are new deductions from the unchanged EdgeBench v1 theory, official Codex configuration
and fixed task contracts. They are proposed Frontier-Science experiments, not EdgeBench results.

1. **Wall time is not automatically a common learning clock.** The theory assumes that raw time
   supplies search effort approximately linearly, yet the official 51-task Codex configuration
   exposes four submission cadences: 44 tasks use a 120-second cooldown, three use 216 seconds,
   D-ABIC uses 2160 seconds and three text adventures use zero; observer auto-evaluation remains
   every 1800 seconds. Judge cost and batch structure differ further by task. A common elapsed-hour
   axis can therefore mix agent search speed with the rate at which the environment releases
   authoritative information. Hold active compute, local calls, total feedback events/bits and
   confirmation budget fixed while randomizing immediate, evenly spaced, batched, jittered and
   end-only release. Compare curve collapse and forecasts on wall, active, experiment-cost,
   feedback-event and revealed-bit clocks before interpreting a wall-time slope.
2. **The frontier graph can be tested by intervention, not only by curve fitting.** Weighted cut
   mixing and self-similar edge difficulty are sufficient assumptions in the paper's mechanism;
   its own limitations predict chains, modules and bottlenecks should produce plateaus or multiple
   phases. Construct matched, answer-disjoint procedural twins with well-mixed, chain,
   modular-single-bridge and hierarchical dependency graphs, where nodes are genuine scientific
   work units rather than rubric atoms. Freeze prospective curve/hazard predictions and intervene
   on bridge availability or one prerequisite observation. A reproducible topology treatment
   effect would support the mechanism; another high-`R²` fit would not.
3. **Fixed objectives omit research-question formation.** Every EdgeBench task specifies the
   objective, deliverable and judge in advance. Even the shared-budget extension chooses among
   author-provided projects. A science benchmark needs one rich procedural laboratory that
   randomizes fixed-question, candidate-menu and open-question contracts. In the open arm, the
   agent preregisters a falsifiable question, hypotheses, identifiability, expected value,
   experiment and stopping rule before seeing new data. Score fresh-world answerability,
   information/decision value, confirmation, triviality and false discovery—not prose style.
4. **Executable starters may anchor the apparent learning path.** A mandatory legal baseline
   lowers first-valid failure, and a prescribed paper/method narrows search, but both can turn a
   long trajectory into local repair around an author prior. Randomize blank schema-only, neutral,
   development-plausible wrong, correct and diverse-choice starters on identical worlds. Measure
   basin escape, exploration diversity, stale-mechanism retraction and sealed/mechanism transfer.
   Keep this separate from text-only workflow-hint ablations.

The configuration census, proposed designs and claim limits are retained in
`.research/edgebench_science_third_order_audit_2026-07-24.json`.

## Eighth-pass horizon-policy and judge findings

These are incremental deductions from the unchanged EdgeBench v1 experiment definition, public
51-task score table and current SForge release. They are not additional EdgeBench empirical claims.

1. **Checkpoint budgets inherit the long-horizon policy.** EdgeBench schedules three independent
   12-hour trials per task--model pair and reads its 2/4/6/8/10/12-hour table from those
   trajectories. This measures the state of a 12-hour-aware policy at each checkpoint, not the
   endpoint of an agent independently told it has two or six hours. Horizon knowledge can change
   exploration, verification, finalization and stopping. In the public 51-task displayed table,
   the best-model sets at 2h and 12h are disjoint on 19 tasks, showing that horizon-conditioned
   rankings are consequential, although it does not identify why they change. Frontier-Science
   should randomize true disclosed horizons and compare independent endpoints with matched
   long-run prefixes; a server-side random-censoring arm can test anytime readiness without
   revealing the exact stop time.
2. **A model-based judge needs its own provenance and reliability experiment.** The public
   `college_english_exam_bank` contract invokes `grade_with_codex.py`, while SForge documentation
   passes the grader model through runtime `SFORGE_JUDGE_MODEL`. The judge image identifies the
   grading program, but `TaskSpec.judge_image_hash` hashes the base/platform/cwd/setup commands and
   the persisted effective `run_config.json` omits `judge_extra_env`; runtime grader identity is
   therefore not naturally bound into the public task/run hash chain. This is an implementation
   provenance finding, not evidence of changed scores. For scientific rubric judgments, pin the
   full judge manifest and measure duplicate/anchor repeatability, inter-judge agreement, style
   sensitivity, drift and rank reversals against executable metrics and expert adjudication.
3. **Effective-submission rate is an endogenous acquisition statistic.** An agent submits after
   inspecting its local state, so the fraction of submissions that improve bundles candidate
   quality with the decision to request feedback, cooldown/latency and task difficulty. Science
   often makes the outer loop an expensive experiment, high-fidelity computation or expert review.
   Compare agent-requested, fixed-grid, random, cost-aware value-of-information and end-only
   policies under the same total feedback/confirmation budget. Require a pre-request prediction of
   what the feedback will distinguish and how it will change action; score predicted-realized
   value calibration, request timing regret, redundant calls and fresh-confirmed utility.
4. **Longer context establishes a level advantage, not automatically faster learning.** The
   reported 1M-versus-200k gap is +5.8 at 2h and +4.4 at 12h. Because the advantage is already
   present at the first displayed checkpoint and slightly narrows, this comparison shows that the
   model--context system performs better over the window; it does not by itself identify a larger
   within-run learning slope. Context studies should add a one-shot/first-valid baseline and test
   baseline-adjusted gain plus the context-by-time interaction before attributing the difference
   to greater accumulation of experience.

The source facts, descriptive 51-task recomputation, proposed designs and claim limits are
retained in `.research/edgebench_science_fifth_order_audit_2026-07-24.json`.

## Ninth-pass continuation and longitudinal-risk-set findings

These are descriptive recomputations from the same unchanged public EdgeBench README table and
protocol deductions for Frontier-Science. They do not establish why any upstream displayed value
has its reported shape and are not additional model-performance claims.

1. **A 2-hour futility screen can delete delayed takeoff.** After applying a cumulative maximum
   solely as a conservative sensitivity to the declared best-so-far semantics, 246 public
   task--model sequences have all six checkpoints and positive 2h-to-12h gain. In 33/246, gain
   from 8h to 12h exceeds gain from 2h to 6h; seven cells improve by at most one point from 2h to
   6h but by at least two points from 6h to 12h. These rounded displayed means are motivation,
   not a continuation-policy treatment effect. Compare fixed, deterministic-headroom,
   randomized-positive-probability and uncertainty-aware continuation under a fixed task-hour
   budget. Force a random audit tranche to 12h regardless of early results and estimate the full
   sampling-frame endpoint; otherwise task selection and long-horizon estimation use the same
   evidence twice.
2. **Best-so-far semantics need an event-level invariant.** Six of the 255 public displayed
   task--model sequences contain a decrease. The public release lacks the raw trajectory corpus
   and figure-analysis code, so this could reflect changing valid-run membership, a different
   checkpoint estimand, aggregation, or another cause; no cause is asserted here. Frontier-Science
   must freeze scheduled run IDs, assert each single-run observer envelope is monotone under one
   selector, publish scheduled/started/captured/judged/valid counts, and distinguish
   failure-inclusive ITT, paired completers and any dynamic risk-set mean. Current artifacts and
   current claims may regress, but they cannot share a column with the historical envelope.

The exact cells, thresholds, source hash and claim boundaries are recorded in
`.research/edgebench_science_sixth_order_audit_2026-07-24.json`.

## Tenth-pass release-cohort, builder and evidence-unit findings

These are protocol deductions from the unchanged EdgeBench v1 paper and public release. They do
not estimate any new EdgeBench treatment effect.

1. **External replay and prospective resistance require different but linked cohorts.** The
   headline study uses 134 tasks, while 51 contracts are public and the raw trajectory corpus plus
   analysis code are not. At 12 hours, the official public-subset aggregate is 5.1--7.1 points
   below the full-benchmark aggregate for every displayed model. This gap does not identify task
   difficulty or the release rule; it shows only that the replayable and headline populations
   differ. Use lineage-matched open, sealed and delayed-release pools, estimate transport between
   them, then publish and independently replay each delayed cohort before rotating an untouched
   reserve into the prospective slot.
2. **Iterative task construction can be a model-specific adaptation channel.** EdgeBench revised
   or excluded tasks after model traces exposed hacking, and Frontier-Science currently uses
   GPT-5.5 calibration to establish headroom and guide rebuilds. Record builder/calibrator model,
   scaffold, triggering trajectory and task edits. Cross-fit procedural families built with
   different systems on common fresh worlds and exclude the evaluated solver from the task's
   final construction round; otherwise builder--solver interaction can masquerade as a model
   capability difference.
3. **Feedback opportunity is not scientific evidence quantity.** Event and bit counts treat an
   exact duplicate, a correlated batch member, a new intervention and independent replication as
   comparable units. Bind evidence to world/sample/batch/instrument/intervention ancestry and
   report nominal calls beside lineage-clustered evidence effective sample size and information
   gain. Repeats may estimate measurement noise but cannot count as independent mechanism or
   confirmation evidence.

The upstream hashes, aggregate-table arithmetic, proposed treatments and claim limits are in
`.research/edgebench_science_seventh_order_audit_2026-07-24.json`.

## Eleventh-pass observation-process findings

These are incremental source-code and public-contract findings from the same unchanged EdgeBench
v1 release. They do not show that the unavailable upstream raw trajectories or headline fit are
wrong or quantify any effect on them.

1. **The public harness does not observe every task on the same clock.** For ordinary artifact
   tasks, `_auto_eval_loop` waits one complete interval, captures the current workspace, submits
   asynchronously and only then begins the next wait. The official 30-minute value is therefore a
   nominal inter-capture delay, not an absolute timestamp grid, and capture/judge latency is not the
   latent edit time. For `game_mode` tasks SForge skips auto-eval entirely. Three of the 51 public
   contracts (`anchorhead_text_adventure`, `trinity_text_adventure` and
   `tryst_text_adventure`) use this path; their score history is generated by agent-created session
   closures, and public step records contain moves/actions/scores but no wall-clock timestamps.
   The other five public Games contracts remain artifact tasks. A common elapsed-time plot can
   therefore combine fixed-delay artifact observation with endogenous event-triggered observation.
2. **Scientific event time is interval-censored unless state is logged at creation.** If a material
   artifact appears between two scored captures, its first-valid or improvement time lies in an
   interval. Assigning the next capture or judge-completion timestamp to the underlying advance can
   shift AUC, takeoff, fitted midpoint and speed. Replay the same immutable event stream under dense,
   5/15/30/60-minute, preregistered seeded-random-phase and agent-event observation kernels and report curve/rank
   sensitivity. For deterministic artifacts, score material commits offline. For consumptive,
   irreversible or interactive laboratories, retain timestamped actions, sensor readings and world
   transitions and analyze a separate live-state stratum; a session-close score cannot be forward-
   filled as though it were a replayable code snapshot.

The source hashes, 51-contract mode census, OBS1/E48 design and claim limits are retained in
`.research/edgebench_science_eighth_order_audit_2026-07-24.json`.

## Minimum next experiments

1. **HartreeFockSCF-v2 calibration:** GPT-5.5 budget 1, normal budget 3 and strict
   selection-blind budget 3. These are single-run calibration only.
2. **Trajectory instrumentation pilot:** record raw/regression curves, effective-submission
   rate, improvement magnitude, rollback latency and active-learning span on Hartree–Fock,
   Distillation, ActiveLaw and Truss.
3. **Stateful versus restart pilot:** one continuous budget-30 run versus six independent
   budget-5 restarts, at least three independent runs per condition. Call this an implementation
   pilot, not a learning estimate, because the Azure endpoint exposes no server-side generation
   seed and token totals may differ.
4. **Feedback-bandwidth pilot:** normal aggregate feedback, scalar-only feedback, delayed block
   feedback and selection-blind open loop under the same visible submission schedule.
5. **Formal Track F/V/M subset:** at least ten independently randomized repetitions on four
   preregistered tasks, with normal, delayed/replayed and strict open-loop conditions; evaluator-
   only science curves; no causal claim unless compute/information balance and run coverage pass.
6. **Population budget curves:** primary long trajectories with preregistered checkpoints at
   30/100/300 proposal units; independent fixed-horizon runs on a smaller subset to test whether
   horizon knowledge changes behavior. Do not fit a scaling law to the present 32 admissible
   tasks or single calibrations.
7. **Endpoint-policy audit:** replay existing trajectories and compare committed, terminal and
   evaluator-only oracle-best artifacts on visible, sealed and mechanism metrics; add atomic
   snapshot hashes before long runs.
8. **Stopping audit:** fixed-horizon forced continuation versus agent-controlled stop/refuse on
   supported, null and misspecified worlds; measure validated utility minus experiment cost and
   whether continued work destroys a previously valid result.
9. **Curve-construction audit:** run the normalization/task-weight/attrition sensitivity suite
   before attempting any log-sigmoid or learning-speed statement.
10. **Knowledge-access and expert pilot:** frozen literature versus no literature on two
    contamination-sensitive tasks, plus matched expert trajectories on one optimization and one
    mechanism/refusal task.
11. **Snapshot observer-effect pilot:** stable committed candidate head plus a separate scratch
    branch; schedule-disclosed fixed snapshots versus jittered schedule-blind snapshots versus
    post-run event replay. Use a separate observer queue and deduplicate identical hashes.
12. **Contract and horizon audit:** machine-check every task's prompt/config budget, evaluator
    timeout, cooldown and submitted paths; then compare genuinely independent short- and
    long-horizon runs rather than interpreting prefixes of a horizon-aware run as counterfactual
    short runs.
13. **Memory/scaffold factorization:** incumbent-only, local-result cache, feedback ledger,
    hypothesis/evidence memory and full state, crossed on a small subset with continuous-context,
    Goal and fresh-context file-backed continuation.
14. **Material-improvement audit:** recompute trajectories under strict-score, numerical-`epsilon`,
    domain-materiality and Pareto/constraint-aware acceptance; quantify acceptance reversals,
    sealed regret and post-commit degradation.
15. **Dual-loop attribution and transfer pilot:** cross local simulator feedback with trusted
    judge feedback, then test whether a provenance-clean evidence ledger transfers to new
    procedural instances or related held-out tasks better than artifact inheritance alone.
16. **Reversible-claim pilot:** on ActiveLaw, SCM and one inverse task, introduce a supported
    world followed by contradictory or model-misspecified evidence; score the current claim,
    confidence, retraction/revision delay and unsupported-claim exposure rather than a monotone
    maximum mechanism score.
17. **Curve-identifiability gate:** before reporting `Smax`, `tmid`, `beta` or a curve-derived speed
    trend, require whole-trajectory parameter intervals, parameter-correlation and rolling-window
    checks plus adequate post-inflection observations; otherwise report observed-window gains.
18. **Lineage-blocked confirmatory design:** freeze task admission on pilot data, assign task-
    lineage clusters, randomize/concurrently pair calendar blocks, and size confirmatory repeats
    from pilot variance and a material-effect target.
19. **MA1/E52 milestone attribution:** preregister the material-event eligibility and milestone
    sample before component outcomes are known. Rebuild parent, full child, component-only,
    leave-one-out and rollback variants on an identical sealed panel; run key `2×2` component
    interactions and, whenever observations changed, `old/new data × old/new method`. Report
    non-separable patches and refusal/validity harms before attributing a gain to a scientific insight.
20. **Fresh-confirmation gate:** reserve a one-shot post-commit world/replication budget that is
    never used by search, periodic snapshots, task admission or stopping; report adaptive looks
    and invalidate/refresh any confirmation panel exposed through repeated analysis.
21. **Linked-campaign pilot:** connect data-quality diagnosis, inference/identification,
    experiment design and intervention on one procedural scientific system; hold out complete
    system lineages and measure stage-local quality, uncertainty propagation and final decision
    regret.
22. **Executable-method replay:** rerun the committed workflow from raw inputs on fresh worlds and
    compare it with scoring only a frozen final answer; record target-specific answer success,
    end-to-end replay success and method-transfer success separately.
23. **Measurement-health audit:** before assigning long horizons, estimate fixed-artifact judge
    noise, first-valid rate, baseline/reference separation, ceiling/floor mass, material 2h
    headroom and required replicate count. Exclude unhealthy cells from scaling-law estimation
    with a reason code, while retaining them in the public sampling-frame ledger.
24. **Campaign-stage counterfactuals:** replay baseline/agent output swaps at each linked stage and
    their combinations on common worlds, so a downstream gain is attributed to the responsible
    scientific stage rather than to temporal co-occurrence.
25. **Cohort-manifest replay:** generate every aggregate figure/table from a hashed manifest and
    fail closed if the declared task count, task set, weights, transforms or run-coverage policy
    differs from the analysis input. Publish taxonomy transitions rather than silently moving a
    task between science, optimization, software and knowledge-work denominators.
26. **Objective-selector replay:** render objective direction, hard gates, materiality, stochastic
    aggregation, tie/Pareto and endpoint policy into the prompt; replay all events and require the
    prompt/online/commit/terminal/dashboard/analysis incumbent hashes to agree.
27. **Lossless durable event ledger:** retain the complete evaluator report and agent-visible
    projection with artifact/evaluator/world hashes, times, costs and retry lineage; regenerate all
    results from this ledger rather than in-memory or summary history.
28. **Boundary-sentinel audit:** score `t=0`, first-valid, every submission/commit, fixed-grid and
    terminal artifacts through one immutable path; quantify missing boundary events without
    best-so-far imputation.
29. **Exactly-once recovery audit:** inject judge/work-container/network failures, duplicate and
    late deliveries; verify idempotent recovery, oracle/sample budget reconciliation and correct
    feedback-descendant lineage.
30. **Score-granularity and task-order audit:** replay identical raw scientific outcomes under
    coarse/canonical/fine score partitions, then refit over random and lineage-blocked task
    permutations/subsamples; treat unstable smoothness, ranking or forecasts as evaluator effects.
31. **Cross-task curriculum transfer:** randomize related, unrelated and misleading source tasks
    before answer-disjoint procedural targets; compare cold, artifact-only, raw-evidence,
    hypothesis/evidence-notebook and full-state target starts.
32. **Shared research portfolio:** allocate one common instrument/oracle/confirmation budget over
    blinded signal, null, misspecified and multifidelity projects; compare equal/random,
    cost-aware VOI and agent allocation on fresh-confirmed portfolio utility and regret.
33. **Stateful laboratory stress test:** inject calibration drift, batch/sample depletion,
    irreversible interventions and out-of-order results; require world/sample/calibration/
    intervention lineage and distinguish physical acts from evaluator retries.
34. **Feedback-clock intervention:** fix total feedback and active/scientific budgets, randomize
    its cadence, and test which time axis yields stable curve collapse and held-out forecasts.
35. **Task-graph topology intervention:** compare matched well-mixed, chain, modular-bottleneck
    and hierarchical procedural twins, including a randomized bridge/prerequisite treatment.
36. **Research-question formation:** compare fixed, menu and open preregistered questions in a
    rich laboratory using fresh-confirmed information/decision value and false discovery.
37. **Starter-prior anchoring:** randomize blank, neutral, plausible-wrong, correct and diverse
    starters and quantify basin escape, mechanism revision, diversity and sealed transfer.
38. **Raw-measurement error propagation:** compare oracle-clean, reference-preprocessed and
    agent-built instrument pipelines on paired calibration, censoring, channel-fault and true-
    anomaly worlds; propagate uncertainty to mechanism, confirmation and decision regret.
39. **Scientific-representation invariance:** run unit, coordinate, channel, grid, spectral and
    symmetry-equivalent metamorphic twins plus non-equivalent physical controls; canonicalize
    only after candidate execution.
40. **Independent-team replication:** compare equal-budget single, shared and isolated investigators
    with blinded evidence synthesis; require one pre-confirmation team claim and report correlated
    error and false consensus rather than oracle-best membership.
41. **Latent-utility robustness:** freeze a domain-valid utility family, reveal constraints but
    draw weights after commit, and compare public-scalar artifacts against reusable Pareto/method
    artifacts on sealed regret, coverage and safety.
42. **Randomized continuation audit:** compare fixed-12h, deterministic headroom,
    positive-probability randomized and uncertainty-aware futility gates; retain an unconditional
    12h audit tranche and report late-bloomer recall, false futility and continuation regret.
43. **Longitudinal risk-set gate:** freeze scheduled run IDs, replay every selector envelope,
    fail on single-run nonmonotonicity and publish ITT, paired-completer and explicitly dynamic
    risk-set summaries separately.
44. **Rotating release-cohort audit:** freeze lineage-matched open, sealed and delayed-release
    pools, publish delayed cohorts after evaluation, and test whether levels, gains, feedback
    effects, ranks and forecasts transport before pooling them.
45. **Builder--solver cross-fit:** record all task-building/calibration systems and cross-evaluate
    A-built, B-built and independent-expert-built procedural families on fresh common worlds.
46. **Evidence-unit audit:** at matched calls, bits and cost compare fresh, correlated, duplicate
    and redundant feedback; report lineage-clustered eESS, information gain and independent
    intervention/replication counts beside science outcomes.
47. **Observation-kernel audit:** replay one sentinel-complete immutable trajectory panel under
    dense, fixed 5/15/30/60-minute, seeded-random-phase and agent-event grids; report interval-censored
    first-valid/material events, AUC/curve/rank sensitivity and snapshot age. Add a separate
    timestamped live-state smoke for an interactive or irreversible laboratory.
48. **Adaptive-design inference audit:** because the agent shapes its own experience stream,
    cross fixed/randomized and agent-adaptive acquisition with naive versus policy-aware analysis.
    Log eligible actions, acquisition probabilities or randomized exploration before outcomes;
    report effect/mechanism bias, coverage, FDR and positivity failures rather than treating
    adaptively selected observations as an i.i.d. design.
49. **Complete-result reporting audit:** outer-loop submissions are not a census of local science.
    Route every simulator/instrument/data action through a trusted append-only result ledger and
    compare it with the agent's claim/evidence package. Report sign-conditional omission of null,
    contradictory, failed and censored outcomes, effect inflation and claim reversal after full
    disclosure; conversation text alone is not a structured all-result manifest.
50. **Conditional checkpoint-fork audit:** freeze one full first-valid or mid-budget research state
    and clone it into independently randomized equal-budget continuations; compare within-parent
    future variance with matched-score states reached through different evidence/hypothesis paths.
    Treat the parent checkpoint as the unit, report every child, wrong-mechanism lock-in and sealed
    escape, and never convert the design into an oracle best-of-`K` endpoint.

## Claim boundary

- Rising nominal best-so-far: scientific **optimization**.
- Lift over equal-budget restarts but not feedback-blind controls: value of retained **state**.
- Repeated lift over strict information controls: **feedback learning**.
- Correct mechanism/intervention transfer plus calibrated null/misspecified refusal:
  **mechanism discovery in the benchmark world**.
- Independent high-fidelity, experimental or formal replication with provenance review:
  evidence eligible for a real-world **scientific discovery** claim.

No single aggregate “science score” should collapse these levels.
