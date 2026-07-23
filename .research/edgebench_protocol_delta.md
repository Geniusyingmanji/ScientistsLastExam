# EdgeBench → Frontier-Science protocol delta

Date: 2026-07-23 UTC. Sources: EdgeBench arXiv:2607.05155v1 full text; public SForge
repository revision `a87350ab80eeb320b13cb71d1b0c3ffcc20a670f`; official Codex experiment
configuration; public 51-task manifest. The arXiv API and upstream `main` were rechecked on
2026-07-23 and still resolve to v1 and this revision. EdgeBench results below are author-reported.

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
   horizon knowledge changes behavior. Do not fit a scaling law to the present 31 admissible
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

## Claim boundary

- Rising nominal best-so-far: scientific **optimization**.
- Lift over equal-budget restarts but not feedback-blind controls: value of retained **state**.
- Repeated lift over strict information controls: **feedback learning**.
- Correct mechanism/intervention transfer plus calibrated null/misspecified refusal:
  **mechanism discovery in the benchmark world**.
- Independent high-fidelity, experimental or formal replication with provenance review:
  evidence eligible for a real-world **scientific discovery** claim.

No single aggregate “science score” should collapse these levels.
