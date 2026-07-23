# EdgeBench → Frontier-Science protocol delta

Date: 2026-07-23 UTC. Sources: EdgeBench arXiv:2607.05155v1 full text; public SForge
repository revision `a87350ab80eeb320b13cb71d1b0c3ffcc20a670f`; official Codex experiment
configuration; and the public 51-task Hugging Face dataset at revision
`47846a4c3669ad447e0ea984833b0d352460c5f9`. The arXiv API and upstream `main` were
rechecked on 2026-07-23 and still resolve to v1 and this repository revision. EdgeBench results
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
7. **Protocol release and claim replay are different deliverables.** As rechecked on 2026-07-23,
   the public GitHub/Hugging Face release provides the SForge harness and 51 of 134 task contracts,
   but not the raw 38,000-hour trajectory corpus or figure-analysis code. The headline fits are
   therefore not independently replayable from the public release alone. Frontier-Science should
   publish an immutable analysis table derived from raw event logs plus a one-command figure/table
   rebuild, while separately protecting server-held oracle assets.

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

## Claim boundary

- Rising nominal best-so-far: scientific **optimization**.
- Lift over equal-budget restarts but not feedback-blind controls: value of retained **state**.
- Repeated lift over strict information controls: **feedback learning**.
- Correct mechanism/intervention transfer plus calibrated null/misspecified refusal:
  **mechanism discovery in the benchmark world**.
- Independent high-fidelity, experimental or formal replication with provenance review:
  evidence eligible for a real-world **scientific discovery** claim.

No single aggregate “science score” should collapse these levels.
