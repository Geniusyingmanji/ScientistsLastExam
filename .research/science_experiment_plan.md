# Science-specific experiment plan

Date: 2026-07-23 (UTC), updated 2026-07-24 after the EdgeBench theory/configuration re-audit.
This plan complements the Frontier-Eng-style optimization study and the EdgeBench-style
long-horizon trajectory study. It does not assume that optimization, feedback learning,
mechanism recovery, and scientific validation are interchangeable.

## Central experimental distinction

The benchmark should measure three trajectories from the same run:

1. `development_score(b)`: raw submitted and best-feasible score visible to the search system at budget `b`;
2. `sealed_validation_score(b)`: evaluator-only score on hidden shifts, interventions, or a
   higher-fidelity oracle, computed from periodic snapshots and never returned to the agent;
3. `mechanism_score(b)`: correctness of a separately submitted equation, causal graph,
   parameterization, or other scientific claim.

The primary science question is whether these curves improve together. A rising development
curve alone is evidence of optimization, not discovery. A widening development–validation gap
is evidence of proxy overfitting or Goodhart effects. A high predictive/optimization score with
a low mechanism score is evidence that task success did not recover the underlying mechanism.

Do not combine the three curves into one benchmark score.

Periodic evaluator snapshots should follow EdgeBench's auto-eval semantics: snapshot the current
artifact on a fixed host schedule, score it through the trusted evaluator, and never reveal that
snapshot's result to the agent or use it for online selection or stopping. Keep these snapshots
distinct from agent-requested evaluations in both accounting and plots. Unlike SForge's default
final-best policy, the primary science result must not be retrospectively selected by hidden
snapshot scores.

Every curve must therefore retain three artifact-selection policies:

1. `committed`: the artifact and scientific claim explicitly chosen by the agent or online search
   policy using only allowed information;
2. `terminal`: the atomic workspace artifact at the preregistered horizon; and
3. `snapshot_oracle_best`: the post-hoc best among evaluator-only snapshots.

The third policy measures latent trajectory potential. It is not a deployable autonomous result.
Report its visible, sealed and mechanism advantage over `committed` as an
`oracle_selection_gap`, rather than silently using it as the headline endpoint.

## Experiment matrix

| ID | Question | Required comparison | Primary outcomes | Claim enabled |
|---|---|---|---|---|
| O0 | How much performance existed before environmental learning? | Direct one-shot/no-environment artifact vs first valid artifact vs the iterative trajectory, with matched model/tool access | initial score, gain from first valid artifact, time/calls to first valid result and first validated mechanism | Prior task competence separated from within-run improvement |
| O1 | Which model–framework combinations optimize best? | Models × greedy/OpenEvolve/AB-MCTS/ShinkaEvolve × random/quasi-random/BO/CMA-ES or DE/domain heuristics | committed terminal feasible score, observer-side best/AUC, within-task rank, performance profile, oracle calls, tokens/cost/time | Budgeted generative optimization |
| O2 | How does performance scale with budget? | Budgets 30/100/300; a deeper subset beyond 300 if justified | raw and best-so-far task curves, improvement frequency/magnitude, regression/rollback rate, plateau and active-learning span, marginal gain per call | Empirical budget-response, not yet a universal scaling law |
| O3 | Is depth better than width? | Equal total budget split across 1/2/4/8 restarts or branches | best score, AUC, diversity, time to last improvement | Search-allocation result |
| O4 | Can artifact bootstrapping be separated from scientific improvement? | Preregister valid/feasible states and analyze time to first valid artifact separately from gain after the one-shot or first-valid baseline | cause-specific first-valid time, validity probability by budget, conditional quality gain and joint sealed-plus-mechanism success | Protocol competence separated from scientific optimization and validation |
| F1 | Is the system using experimental feedback causally? | Normal feedback vs shuffled feedback vs delayed feedback vs strict selection-blind/no-feedback, using paired seeds and identical budgets | paired AUC lift, terminal lift, proposal divergence after feedback, validated discoveries per call | Feedback learning |
| F2 | Does persistent experience help beyond repeated sampling? | One continuous run vs equal-budget independent restarts; full memory vs summarized/frozen/no memory; identical submission/feedback schedules | score/AUC, effective submissions and sealed-validation lift | Value of accumulated scientific state |
| F3 | Does gain come from more evaluator information rather than better learning? | Matched submission budget/cooldown with scalar-only, aggregated, diagnostic and evaluator-silent periodic snapshots | terminal/AUC lift per revealed bit, oracle call and visible judge event | Value and risk of feedback bandwidth |
| F4 | Does a diagnostic teach scientific structure or merely reveal the score decomposition? | Equal-length/equal-bit meaningful component labels vs label-permuted components vs unlabeled values vs scalar feedback | sealed/mechanism lift, proposal targeting, causal attribution and hidden-target reconstruction risk | Value of semantic scientific feedback beyond numeric bandwidth |
| F5 | Which retained state actually carries scientific learning? | Factor incumbent artifact, local-result cache, judge-feedback ledger, hypothesis/evidence memory, conversational context and full workspace | sealed/mechanism lift, evidence-use accuracy, contradiction/failed-branch retention, transfer to a new instance | Mechanism of stateful improvement rather than a bundled continuous-run effect |
| F6 | Which loop causes improvement? | 2×2 local simulator/test feedback × agent-visible trusted-judge feedback, with matched calls and information accounting | visible/sealed/mechanism gain per local tool call, trusted call and revealed bit | Local experimentation separated from authoritative-judge learning |
| F7 | Does retained experience transfer, or anchor a stale hypothesis? | Same-regime continuation vs related-instance transfer or a preregistered regime change; artifact-only, evidence-memory, full-state and clean-restart conditions | positive/negative transfer, adaptation delay, stale-claim persistence, calibrated revision and false discovery | Scientific memory quality rather than same-task score persistence |
| F9 | Can the agent decide when costly external feedback is worth requesting? | Equal total trusted-feedback budget under agent-requested, fixed-grid, random, cost-aware VOI and end-only policies; every on-demand request preregisters its question, expected information/decision value and action threshold | predicted-versus-realized feedback value, gain/information per cost, request timing regret, redundant/escalatory calls, confirmation reserve, false discovery and committed utility | Autonomous feedback acquisition rather than an endogenous effective-submission rate |
| V1 | Does optimization generalize beyond the visible oracle? | Visible development oracle vs evaluator-only hidden instances/shifts | sealed score, development–validation gap, rank correlation, replication rate | Generalizable result |
| V2 | Does a cheap proxy survive higher-fidelity evaluation? | Proxy-only search; scheduled promotion; adaptive multifidelity; exact-only reference where affordable | proxy/exact rank correlation, false-promotion rate, exact-call efficiency, high-fidelity regret | Multifidelity validation |
| V3 | Does an adaptively selected claim survive genuinely fresh confirmation? | Exploration/development worlds and periodic sealed monitoring vs a single post-commit server-held world or independent high-fidelity replication never used for search, admission, fitting or stopping | confirmation success, replication effect/interval, adaptive-look count and confirmation regret | Confirmatory evidence separated from adaptive discovery |
| M1 | Did the system recover a mechanism rather than a predictor? | Observational-only vs intervention access; prediction-only vs explicit mechanism submission | graph F1, equation/term recovery, parameter error, intervention and shift prediction | Mechanism recovery |
| R1 | Can the system detect when no supported discovery exists? | Well-specified worlds vs null, noisy, confounded, biased-oracle and model-misspecified worlds | false-discovery rate, calibration, correct abstention, detection delay, unnecessary experiments | Calibrated refusal and reliability |
| R2 | Is the claimed result reproducible and traceable? | Original evaluator vs independent implementation/reviewer; replay from immutable artifact | replay success, independent replication rate, claim–evidence consistency, failed-branch coverage | Research integrity |
| R3 | Can the system select and stop on a deployable scientific conclusion? | Agent-controlled stop/commit vs forced fixed-horizon continuation; compare committed, terminal and hidden oracle-best artifacts | stopping utility net of experiment cost, commitment regret, oracle-selection gap, post-commit degradation | Autonomous selection/stopping rather than retrospective oracle selection |
| R4 | Does the system revise or retract a scientific claim when later evidence contradicts it? | Supported evidence followed by preregistered intervention, regime-shift, misspecification or replication evidence; current-claim ledger vs score-only memory | unsupported-claim exposure, retraction/revision delay, confidence calibration, oscillation and correct-mechanism recovery | Self-correction rather than monotone claim accumulation |
| K1 | Is an apparent discovery retrieval, reproduction or task-local inference? | Frozen dated corpus vs no literature vs open Web, crossed with public, time-held-out and family-held-out tasks | citation provenance, novelty/reproduction label, sealed transfer and contamination sensitivity | Knowledge-use attribution, not discovery by retrieval |
| K2 | Did the system discover a method or execute one supplied by the task? | Method-prescriptive vs method-neutral contracts and workflow-hint ablations on matched procedural worlds | algorithm-family novelty, mechanism/validation lift, literature overlap and independent transfer | Prescribed reproduction separated from task-local method discovery |
| B1 | How does the trajectory compare with domain experts under the same interface? | Expert one-shot and iterative runs on a stratified subset with matched feedback, experiment and wall/compute budgets | validated utility, sample efficiency, mechanism/refusal calibration, stopping and failed-hypothesis coverage | Human-calibrated capability and task difficulty |
| I1 | Does hidden trajectory measurement alter the trajectory? | Stable committed head plus scratch workspace; fixed disclosed snapshots vs jittered undisclosed snapshots vs post-run event replay | branching/edit cadence, transient invalidity, throughput, visible-feedback latency and final science outcomes | Observer effect of evaluator-only measurement |
| I2 | How much performance comes from continuation scaffolding? | Fixed model/context/tools crossed with continuous session, goal state and fresh-context file-backed loop; separately vary context capacity with a preregistered one-shot/first-valid baseline | active duty cycle, state-loss incidents, evidence retention, baseline-adjusted gain, context-by-time interaction and committed/sealed outcomes | Model capability and initial level separated from continuation or accumulated-experience effects |
| S1 | Is an aggregate scaling curve predictively and mechanistically supported? | Preregistered log-sigmoid and alternatives, whole-trajectory validation across held-out suffixes/runs/tasks/families, and fixed-grid material-improvement events | held-out error/log score, interval coverage, parameter stability and improvement hazard versus normalized progress | A bounded empirical regularity; never feedback learning or discovery by itself |
| S2 | Are the fitted ceiling, midpoint and speed actually identifiable in the observed horizon? | Profile/trajectory-bootstrap fits across rolling windows and longer horizons, with constrained or nonparametric alternatives | parameter intervals/correlation, post-inflection support, window stability and coverage | Curve-parameter interpretation only when identified; otherwise observed-window gain |
| I3 | Is a narrated breakthrough caused by the attributed edit? | Parent, full child, component-only patch and rollback replay on one frozen sealed evaluator panel | retained effect, interaction, regression and component-specific science metrics | Causal edit attribution for selected milestones, not from chronology alone |
| I4 | Do all system layers agree on which artifact is incumbent and why? | Replay every event through one versioned objective-selection contract and compare prompt, agent cache, online selector, signed commit, terminal endpoint, dashboard and analysis; include score-first, valid-then-score, safety-lexicographic and material-Pareto sensitivity | incumbent-hash agreement, selector reversals, sealed/mechanism/false-discovery reversal rate and protocol failures | Trustworthy artifact selection rather than an ambiguous scalar leaderboard |
| I5 | Can a day-long scientific run survive failures without losing or double-spending evidence? | Durable append-only ledger with judge/work-container/network crash injection, duplicate/late delivery, restart and idempotent replay | exactly-once oracle/sample budget reconciliation, lost/duplicate events, stale-feedback attribution, recovery time and byte-replay of derived tables | Crash-consistent long-horizon evidence rather than best-effort execution logs |
| S3 | Is the apparent scaling shape invariant to evaluator granularity and task ordering? | Replay identical raw outcomes under preregistered coarse/canonical/fine score partitions; random and lineage-blocked task accumulation orders/subsamples | curve/forecast/parameter/ranking dispersion, maximum score atom and material-event stability | A curve tied to scientific outcomes rather than rubric atomization or one task ordering |
| F8 | Does scientific experience transfer across tasks rather than only persist within one task? | Randomized source→target curricula with related, unrelated and misleading sources; cold, artifact-only, evidence-notebook and full-state transfer | target early AUC/time-to-valid, sealed/mechanism lift, false discovery, adaptation/retraction delay and transfer half-life | Cross-task scientific meta-learning or negative transfer |
| P1 | Can the agent allocate a shared research budget across competing projects? | Equal/random/independent allocations vs cost-aware VOI/knowledge-gradient and agent allocation over blinded signal/null/misspecified projects | validated portfolio utility and discoveries per cost, allocation regret, starvation/drop decisions and unsafe/false-discovery exposure | Scientific portfolio decision quality rather than per-task optimization in isolation |
| D1 | Can the agent reason under nonstationary, irreversible and asynchronously observed science? | Stationary/reversible control vs drift, batch changes, sample depletion, irreversible interventions and randomized result latency | drift/recalibration delay, sample efficiency, stale-result misuse, duplicate physical acts, unsafe interventions and fresh-batch confirmation | Laboratory-state reasoning rather than replayable software search |
| S4 | Is elapsed time the relevant scaling coordinate, or merely a proxy for feedback opportunity? | Hold active compute, local calls, total authoritative feedback events/bits and confirmation budget fixed; randomize immediate/even/batched/jittered/end-only feedback release | cross-cadence curve collapse and forecast/rank stability on wall, active, experiment-cost, feedback-event and revealed-bit axes; gain per feedback; false discovery | A named feedback/effort clock, rather than an uninterpretable hour-based curve |
| S5 | Does intervening on the task dependency graph change learning as the frontier mechanism predicts? | Answer-disjoint procedural twins with matched marginal node difficulty, score mass, feedback and cost but well-mixed, chain, modular-bottleneck and hierarchical dependency graphs; bridge/prerequisite intervention | material-event hazard, plateau/inflection count, module transfer, bridge treatment effect, sealed/mechanism outcome and prospective curve-family prediction | Empirical support or falsification of the latent frontier-expansion mechanism rather than fit alone |
| Q1 | Can the agent formulate a worthwhile, falsifiable scientific question before solving it? | Fixed question vs candidate menu vs open question formation in one rich procedural laboratory; signed preregistration before new data | answerability/identifiability, predicted and realized information or decision value, fresh confirmation, trivial-question rate, false discovery and preregistration deviation | Research-question/agenda formation, distinct from solving an author-specified objective |
| K3 | How strongly do executable starters and embedded scientific priors anchor the search? | Blank schema-only scaffold vs quality-matched neutral, development-plausible wrong, correct and diverse-choice starters on identical procedural worlds | time-to-valid and basin escape, exploration diversity, stale-hypothesis/retraction delay, sealed/mechanism/false-discovery outcome and structural distance from starter | Scaffold-conditioned adaptation separated from independent method discovery |
| I6 | Can the system carry raw instrument observations into a valid conclusion without hiding measurement error? | Oracle-clean features vs frozen reference preprocessing vs agent-built raw-data pipeline, paired across calibration drift, missing/censoring, channel/unit faults and true anomalies | extraction/calibration error, uncertainty propagation, mechanism/confirmation, false alarm/miss and downstream decision regret | Instrument-facing science separated from reasoning over clean structured observations |
| V4 | Is the scientific method invariant to equivalent representations while remaining sensitive to real physical changes? | Unit, coordinate, channel, grid, spectral and symmetry-equivalent metamorphic twins plus visually similar non-equivalent negative controls | physical-claim consistency, performance drop, equivariance violations, contradictions and negative-control sensitivity | Representation-robust scientific transfer rather than template or schema matching |
| T1 | Does independent scientific review reduce correlated error under a fixed total budget? | Single continuous agent vs shared branches vs isolated investigators vs blinded evidence synthesis vs shared-context critic; team signs one claim before fresh confirmation | hypothesis diversity, pairwise error correlation, false consensus, minority correctness, synthesis calibration, confirmation and utility per cost | Multi-agent/team benefit without post-hoc oracle winner selection |
| U1 | Does the artifact remain useful when a reasonable downstream utility is not known during search? | Public fixed scalar vs public utility family with sealed post-commit weights vs reusable Pareto/response-surface/method artifact; announced objective-shift control | sealed utility regret, worst-case/CVaR regret, Pareto coverage, safety violations and adaptation cost | Reusable scientific knowledge separated from evaluator-targeted scalar optimization |
| HZ1 | Does the disclosed research horizon change the scientific policy, not merely its cutoff? | Independent runs with the true horizon disclosed as 2/6/12 h, matched prefixes from a 12 h-aware run, and a preregistered random-censoring arm; hold task/world, feedback policy and per-unit resources fixed | exploration-to-confirmation allocation, early committed/sealed/mechanism utility, confirmation-budget reserve, stopping/abstention, horizon-conditioned rank and prefix regret | Budget-response and model rankings that are valid for the policy actually deployed at each horizon |
| J1 | Are rubric- or model-mediated scientific judgments stable enough to support trajectory and ranking claims? | Pin a complete judge manifest and evaluate blinded anchor artifacts, exact duplicates and adversarial style/verbosity twins with repeated independent judges, deterministic executable metrics and expert adjudication where needed | repeatability, inter-judge agreement, anchor drift, style sensitivity, rank reversals, calibration to executable outcomes and adjudication rate | Judge-mediated evidence only when evaluator identity, uncertainty and construct validity are demonstrated |
| CA1 | Can early evidence allocate continuation budget without systematically deleting late scientific progress? | Under one fixed total task-hour budget compare fixed-12h, deterministic 2h-headroom, randomized-positive-probability and uncertainty-aware futility policies; force a randomly selected audit tranche to 12h regardless of its early result | task-hour savings, late-bloomer recall, false-futility rate, continuation regret, 12h committed sealed/mechanism utility and selection-induced curve/rank bias | Research-budget allocation with an estimable full-cohort endpoint, distinct from an agent's own stopping decision |
| M2 | Does the longitudinal analysis preserve one risk set and the declared best-so-far semantics? | Replay scheduled run IDs and selector events at every checkpoint; assert each single-run observer envelope is monotone and compare failure-inclusive ITT with fixed paired-completer and explicitly named changing-risk-set summaries | scheduled/started/captured/judged/valid flow, monotonicity violations, risk-set drift, attrition sensitivity and replay status | A trustworthy longitudinal curve; this is a protocol gate, not an agent capability score |
| G1 | Can an externally replayable result transport to a contamination-resistant prospective cohort? | Pre-registered lineage-stratified open-replay, sealed-prospective and delayed-release pools; freeze one system, evaluate open and sealed pools concurrently, then release and independently replay the delayed pool before rotating in an untouched reserve | open-to-sealed gaps in level, baseline-adjusted gain and feedback effect; rank/curve/forecast transport; delayed-release replay; exposure age and contamination sensitivity | Reproducibility and prospective validity as separate, jointly measured properties |
| G2 | Did benchmark construction adapt to the model used to build and calibrate the task? | Record builder/calibrator model and scaffold lineage; cross-evaluate A-built, B-built and independent-expert-built procedural families on common fresh worlds while excluding each evaluated solver from the corresponding final construction round | builder×solver interaction, first-valid/invalidity, shortcut and exclusion rates, sealed/mechanism gain, feedback interpretability and ranking reversals | Builder-balanced capability rather than performance on a benchmark tuned through the tested system |
| EVI1 | Does another feedback event add independent scientific evidence? | Match nominal calls, payload and scientific cost while varying fresh-independent, correlated-batch, exact-duplicate and adversarially redundant observations; bind all events to world/sample/batch/instrument/intervention lineage | lineage-clustered evidence effective sample size, information/entropy gain, independent interventions/replications, sealed/mechanism/refusal gain per eESS and confidence calibration | Evidence accumulation and identifiability rather than repeated evaluator contact |
| OBS1 | Is the reported learning trajectory robust to how and when latent scientific state is observed? | Replay identical immutable artifact/event trajectories under dense-event, fixed 5/15/30/60-minute, preregistered seeded-random-phase and agent-event-only observation kernels; separately stratify replayable artifacts and path-dependent live-state laboratories | interval-censored first-valid/material-event time, AUC and curve/rank/forecast sensitivity, observation delay/age, missed transient states and live-state replay coverage | A trajectory attributable to agent progress rather than observation cadence or task-interface mode |
| AD1 | Does an adaptively chosen experiment stream still support calibrated scientific inference? | In answer-disjoint procedural worlds compare fixed randomized/balanced designs, agent-adaptive acquisition, the same adaptive data analyzed naively, and policy-aware analysis using logged action probabilities or randomized exploration; require positivity or mark unsupported regions | bias/RMSE and interval coverage for effects/mechanisms, FDR, propensity calibration, support violations, information/decision value, fresh-world confirmation and policy regret | Valid inference after endogenous experiment selection, distinct from merely choosing informative experiments |
| NR1 | Does the system preserve and report unfavorable local evidence rather than only the best artifact or selected milestones? | Route every simulator/instrument action through a trusted event server, then compare the objective ledger with the submitted claim/evidence package under a preregistered result-reporting schema; inject positive, null, contradictory, failed and censored outcomes | result-capture completeness, sign-conditional reporting odds, failed/null/contradictory omission, effect-size inflation, claim reversals after full-ledger disclosure, reproducibility and fresh confirmation | Auditable scientific reporting without a file-drawer or selective-reporting advantage |
| CF1 | Given the same accumulated scientific history, how variable and path-dependent is the remaining research outcome? | At preregistered first-valid and mid-budget times, clone one content-addressed full checkpoint into independently randomized equal-budget continuations; add matched-score/different-history parents and incumbent-only or audited-notebook descendants | within-checkpoint continuation variance, between-history variance at matched score, conditional value of remaining budget, wrong-mechanism lock-in/escape, descendant diversity, sealed/mechanism confirmation and state-sufficiency prediction | Conditional reproducibility and research-history lock-in rather than unconditional seed variance or best-of-K search |

## Controls that must be strict

The current `none` and `shuffled` modes only alter metrics shown in proposal prompts while
selection still sees real scores. They cannot identify the causal effect of feedback. At least
one control must make selection blind as well, for example:

- freeze or randomize parent selection;
- generate an open-loop batch before any results are revealed;
- delay all outcomes until the end of a fixed proposal block; or
- replay feedback from a different paired run while keeping timing and message shape fixed.

The built-in greedy runner now implements the first strict control as `selection_blind`.
Every proposal uses the same frozen baseline parent and public baseline metrics; scores are
retained only for offline best-of-batch analysis. The control isolates the value of iterative
incumbent/score feedback from repeated open-loop sampling. It does not isolate score text from
parent-program adaptation, and the current Azure endpoint exposes no server-side random seed;
both limitations must be stated in paired-result reports.

Normal and control runs should use paired task instances, seeds, call budgets, tool access, and
feedback-message lengths. The treatment contrast is the information content of feedback, not
extra compute.

Cross-system submission efficiency should be computed primarily on a common evaluator-only time
or charged-budget grid. Agent-chosen submissions are an endogenous behavioral outcome: systems
that submit at different thresholds or bundle edits differently do not expose comparable
Bernoulli trials. Retain their cadence and success rate, but do not use them as the sole learning-
efficiency denominator.

The evaluator interface must also constrain adaptive information leakage. Predeclare an
agent-visible submission budget and cooldown, log the feedback payload class/size, and run a
feedback-resolution audit: repeated scalar or component feedback must not identify hidden
targets more easily than the scientific inverse problem itself. Evaluator-only snapshots are
exempt from the agent submission limit because their outputs are never returned, but remain
charged as trusted evaluation calls.

All evaluator-only snapshots must be atomic, content-addressed bundles rather than live directory
copies. For asynchronous judging, log `submitted_at`, `feedback_ready_at`, `feedback_read_at`, the
submitted artifact hash and the first descendant proposal hash. A score can be credited as
feedback used only by descendants produced after it was actually read.

For stateful scientific environments, artifact lineage is insufficient. Every observation must
also bind a `world_state_id`, `sample_id`, `calibration_id`, intervention parent and whether the
physical act is reversible or consumptive. Retrying an evaluator process may be idempotent;
repeating a destructive assay is a new intervention and must consume a new sample/budget entry.
Out-of-order results can update only hypotheses and descendants whose world-state assumptions
remain compatible.

Auto-evaluation is score-hidden but can still change behavior when its schedule and requirement
to keep files runnable are disclosed. Keep the stable committed candidate in a separate path from
scratch work. Prefer a resource-isolated observer queue or post-run scoring of content-addressed
event snapshots. Deduplicate identical hashes for deterministic judges; for stochastic judges,
combine preregistered seed replicates into an expectation and uncertainty interval rather than
letting repeated unchanged snapshots enter best-of-N selection.

Every task must pass a contract-consistency lint: the time horizon and checkpoint schedule stated
in its prompt must match the harness timeout; evaluator timeout must fit the submission/queue
policy; submitted paths and exclusion rules must match the claimed deliverable; and cooldown plus
maximum submissions must leave the advertised workflow possible. Time-budget comparisons require
independent runs told their true horizon. A prefix of a long-horizon-aware run is descriptive, not
a counterfactual short-horizon policy.

Every longitudinal curve must also pass a risk-set and envelope lint. Bind every checkpoint to
the preregistered scheduled run IDs, publish scheduled/started/captured/judged/valid counts, and
assert monotonicity for each single-run observer-side best-so-far envelope under one selector.
Current artifacts, terminal artifacts and current scientific claims may regress, but must live in
separate named columns. A changing-valid-run mean is a different estimand and cannot be relabeled
as one fixed-cohort best-so-far trajectory. Do not repair violations with an analysis-time
cumulative maximum; fail closed and trace them to source events.

The objective and selection rule are also part of that contract. Render the exact raw objective
direction, validity/safety/confirmation gates, materiality `epsilon`, constraint ordering,
tie/Pareto rule, stochastic expectation or quantile policy and eligible endpoint policy into the
agent prompt. The agent-visible incumbent cache, authoritative online selector, signed commit,
terminal evaluation, dashboard and analysis must execute the same versioned selector. Replay all
events and fail closed if any layer names a different incumbent artifact hash, even when two
artifacts happen to share the same scalar score.

Score changes smaller than numerical noise or scientific materiality must not automatically
replace an incumbent. Predeclare an evaluator-resolution `epsilon`, hard scientific constraints,
domain-material effect thresholds and tie/Pareto policy. Retain both strict-score and material-
improvement trajectories so near-ceiling floating-point changes cannot silently reverse a
robustness or mechanism conclusion.

Forced continuation and autonomous stopping answer different questions. Fixed horizons remain
useful for comparable capability curves, but discovery/reliability experiments must also permit
a signed `commit`, `abstain` or `continue` decision. Continuing after a warranted stop consumes
scientific budget and can introduce false discoveries; that cost is part of the outcome.

Scientific claim state must not be reduced to a monotone best-ever mechanism score. Each
claim-bearing event should record a stable `claim_id`, current mechanism/equation, confidence,
supporting and contradicting evidence hashes, and one of `propose`, `confirm`, `revise`,
`retract` or `abstain`. The score at budget `b` is the claim the system would defend at `b`, not
the best historical claim selected with future evidence. On contradictory-evidence trials,
measure both how quickly a false claim is withdrawn and whether the agent recovers a supported
replacement rather than merely refusing forever.

Evaluator-only monitoring is still adaptive evidence for the research team even when the agent
cannot see it. Do not reuse a repeatedly inspected sealed panel as the final confirmation set.
Log every hypothesis/evaluator look and reserve a post-commit confirmation world, seed panel or
higher-fidelity replication that influences neither search, task admission, curve-model choice,
stopping nor milestone selection. If analysts inspect or tune against that panel, mark it
contaminated and refresh it before a confirmatory claim.

The authoritative trajectory must be an append-only, schema-versioned, durable event ledger, not
an in-memory judge history, a container-local display cache or a mutable summary. Before judging,
persist an evaluation intent keyed by artifact hash, evaluator manifest and world/seed panel;
atomically commit the complete raw report, agent-visible feedback projection, event times, costs,
failure/retry lineage and selector decision. Recovery must query or resume this idempotency key
rather than silently rerun a costly or stochastic experiment. Crash-injection tests must show
that evidence and budget are neither lost nor counted twice and that every headline table can be
reconstructed from the ledger plus its hashed cohort manifest.

Fixed-grid monitoring must include boundary sentinels. Capture and charge the immutable artifact
at `t=0`, first-valid, every agent submission, every signed commit/abstention, every scheduled
checkpoint and the terminal cutoff. A terminal evaluation may finish after the cutoff, but its
feedback cannot cause an in-horizon descendant. Missing boundary captures remain reason-coded
missing outcomes; never forward-fill them with a historical best.

Science tasks often need literature access, so blanket network isolation is not a sufficient
contamination protocol. Build a dated, frozen and logged literature corpus for the primary
condition, keep open-Web access as a separate treatment, and label recovered public results as
reproduction unless novelty survives the preregistered cutoff and independent search.

## Science-specific task extensions

| Current task | Useful sealed or shifted evaluation | Best role |
|---|---|---|
| Lennard-Jones clusters | unseen cluster sizes and seeds; perturbed interaction parameters; finite-temperature stability; an independently implemented energy oracle | optimization transfer and proxy-to-physics validation |
| SK spin glass | procedurally generated hidden couplings, larger sizes, and held-out coupling distributions | instance/distribution generalization |
| Poisson solver | hidden spectra, resolutions, boundary conditions and coefficient fields; measured convergence order | numerical-law and solver generalization |
| Multilayer thin film | hidden angles, polarization, dispersion tables, material tolerances and fabrication noise; later high-fidelity/physical replication | strongest current multifidelity/robustness case |
| Truss sizing | held-out topology/material families; load, stiffness, strength and manufacturing shifts; later nonlinear FEM replication | structural optimization versus physical robustness |
| Antenna synthesis | held-out scanned/nonuniform arrays; frequency, position, calibration and exhaustive single-element failures; later full-wave/measured replication | nominal pattern synthesis versus hardware robustness |
| Distillation design | server-held mixtures and cost regimes; volatility/feed/reflux shifts; rate-based simulator replication | nominal economics versus operating robustness and mechanism responsiveness |
| Hartree--Fock SCF | server-held molecules/geometries/bases; AO transformations; internal/external stability; higher-basis and correlated-method comparison | self-consistency/objective value versus variational stability and model fidelity |
| Matrix multiplication | held-out dimensions/fields, exact tensor identity and independent proof/checker | machine-verifiable mathematical discovery |
| Cap Set | held-out dimensions or fields and exact construction verification; contamination audit against known constructions | machine-verifiable mathematical discovery |
| Circle packing | unseen `N`, interval/independent geometric verification and perturbation robustness | machine-verifiable construction |

The seven certified tasks do not currently contain a clean mechanism-identification benchmark.
Do not force a mechanism claim onto them. Two candidate families now provide the intended
starting point and should be hardened rather than duplicated:

1. a hidden structural-causal-model laboratory with observation and intervention actions,
   separately scored prediction, graph, equations, and intervention transfer; and
2. a hidden dynamical-law laboratory with noisy trajectories, experiment/control selection,
   symbolic equation and parameter recovery, plus extrapolation to sealed regimes.

Include null and misspecified instances in both families so that always producing a mechanism
is penalized. `InterventionalSCM` and `ActiveLawDiscovery` implement the basic versions, but both
still require harder latent/nonlinear/partial-observation or model-mismatch regimes,
server-held procedural worlds, multi-seed feedback controls and independent review before M1.

## Recommended figures and tables

1. Benchmark/task taxonomy and the O/F/M/V/R capability ladder.
2. Model × framework within-task ranks and Dolan–Moré performance profiles.
3. Best-so-far score and AUC against proposal budget, actual oracle calls, wall time, and cost.
4. Equal-budget depth–width heatmap and continuous-run versus restart curves.
5. Paired normal/shuffled/delayed/selection-blind feedback curves, plus scalar/aggregated versus
   diagnostic feedback at a matched submission schedule.
6. The main science figure: development, sealed-validation, and mechanism curves against the
   same budget, with their generalization gaps.
7. Proxy-versus-high-fidelity scatter/calibration curve and false-promotion rate.
8. Risk–coverage or calibration plot on null/misspecified cases, including false discoveries.
9. One successful and one failed hypothesis–experiment–evidence DAG with replayable artifacts.
10. Raw submission/regression plot with effective-submission rate, improvement magnitude,
    rollback latency and active-learning span; mark evaluator-only snapshots distinctly.
11. For stochastic tasks, expected/median performance and uncertainty beside best-of-N, with
    hidden-seed reuse and seed-overfitting diagnostics.
12. Initial/first-valid-to-final improvement curves, so high pretrained one-shot competence is
    not plotted as learning from feedback.
13. Committed versus terminal versus hidden-snapshot oracle-best small multiples, including the
    sealed/mechanism `oracle_selection_gap`.
14. Wall-time decomposition into active model time, local tool/simulator time, judge/queue wait,
    resume/idle time and charged scientific experiment cost.
15. Stopping risk–utility curves and post-commit degradation under forced continuation.
16. Curve/leaderboard sensitivity under alternative task weights, score transforms, anchor
    perturbations and leave-one-task/family-out aggregation.
17. Snapshot observer-effect plot: stable-head versus scratch edits, transient-invalid intervals,
    snapshot queue load and visible-feedback latency under fixed/jittered/post-run measurement.
18. State-channel and continuation-scaffold factorial: artifact, local results, feedback ledger,
    hypothesis/evidence memory and context, with evidence-use and held-out transfer outcomes.
19. Material-improvement curves under strict `>`, numerical-`epsilon`, domain-threshold and
    Pareto/constraint-aware acceptance, including selection reversals and sealed regret.
20. Two-loop attribution table crossing local simulator/test feedback with trusted-judge feedback;
    report calls, information and scientific experiment cost for both channels.
21. A hurdle/multistate panel: cumulative incidence of first valid/feasible artifacts, conditional
    post-valid quality, and jointly validated mechanism success, with reason-coded invalid states.
22. Prospective curve forecast audit with last-value, monotone, per-task plateau and repeated-
    sampling baselines; report held-out interval coverage and whole-trajectory bootstrap error.
23. Scientific-memory transfer and regime-change panel showing beneficial transfer, adaptation
    latency and stale-hypothesis/negative-transfer failures.
24. Current-claim state plot showing proposal, confirmation, revision/retraction and abstention
    events, with confidence and unsupported-claim exposure under contradictory evidence.
25. Curve-parameter identifiability panel with joint/profile intervals for `Smax`, `tmid` and
    `beta`, rolling-window estimates and the observed fraction of the post-inflection regime.
26. Task-lineage and calendar-block table: shared data/oracle/template ancestry, independent-
    world count, admission versus confirmation split, treatment order and endpoint snapshot.
27. Selected milestone edit-ablation table comparing parent, full child, component-only patches
    and rollback on the same sealed panel.
28. Exploration-to-confirmation flow showing hypothesis/evaluator look counts, signed commit,
    fresh post-commit world/replication and any confirmation-set refresh after contamination.
29. Linked-campaign error propagation from data QC through inference/design to intervention,
    including baseline/agent stage swaps and final decision regret.
30. Measurement-health and cohort-provenance panel: first-valid rate, baseline/reference gap,
    fixed-artifact judge noise, floor/ceiling mass, post-2h material headroom, manifest hash and
    nominal versus effective lineage count.
31. Objective-selection agreement panel: prompt/online/commit/terminal/dashboard/analysis
    incumbent hashes plus selector-sensitivity reversals on sealed, mechanism and safety axes.
32. Durable event and recovery panel: scheduled, durably accepted, judged, delivered and used
    events with duplicate/retry/crash/late-result accounting and exactly-once budget reconciliation.
33. Sentinel-complete trajectory marking `t=0`, first-valid, submissions, signed commits,
    fixed-grid snapshots and terminal without best-so-far imputation at missing boundaries.
34. Equivalent-score-partition and task-order audit: curve/rank/forecast distributions under
    coarse/canonical/fine rubric atoms plus random and lineage-blocked accumulation orders.
35. Cross-task curriculum transfer matrix: related/unrelated/misleading source tasks crossed with
    cold/artifact/evidence-notebook/full-state target starts.
36. Shared-budget research portfolio: validated utility and false-discovery/safety against total
    instrument/oracle cost, with allocation regret and dropped/starved projects visible.
37. Stateful laboratory timeline: calibration/sample/intervention lineage, drift/batch changes,
    asynchronous results, irreversible acts and fresh-batch confirmation.
38. Feedback-clock collapse panel: the same total feedback under different release schedules,
    aligned by wall time, active time, scientific cost, feedback-event count and revealed bits.
39. Task-graph intervention panel: well-mixed, chain, modular-bottleneck and hierarchical twins,
    including prospective curve predictions and the bridge/prerequisite treatment effect.
40. Question-formulation frontier: fixed/menu/open contracts with identifiability, realized
    information/decision value, triviality, false discovery and fresh confirmation.
41. Starter-prior anchoring matrix: blank/neutral/wrong/correct/diverse starters with basin
    escape, exploration diversity, mechanism retraction and sealed transfer.
42. Raw-measurement error cascade from calibration/extraction/QC through mechanism, confidence,
    confirmation and final decision, with oracle-clean-feature rescue.
43. Scientific-representation metamorphic matrix over unit/coordinate/channel/grid/spectral
    twins and non-equivalent negative controls.
44. Independent-team panel comparing single, shared and isolated investigators plus blinded
    synthesis on diversity, correlated error, false consensus, fresh confirmation and cost.
45. Latent-utility robustness frontier comparing public scalar optimization with reusable
    Pareto/method artifacts under post-commit sealed utility weights.
46. Horizon-policy matrix: independently disclosed 2/6/12-hour runs versus matched prefixes of
    a 12-hour-aware run, including exploration/confirmation allocation, rank reversals and prefix regret.
47. Judge-reliability panel: blinded anchors/duplicates/style twins across pinned judge manifests,
    with repeatability, inter-judge agreement, executable-metric concordance and adjudication rates.
48. Feedback-acquisition calibration: predicted versus realized information/decision value for
    each external request, costed request-timing regret and unused confirmation reserve.
49. Continuation-policy audit: fixed/headroom/randomized/uncertainty-aware allocation against
    task-hour cost, late-bloomer recall, false futility, 12-hour scientific utility and curve bias.
50. Longitudinal risk-set audit: checkpoint scheduled-to-valid flow, single-run envelope
    monotonicity, ITT versus paired-completer sensitivity and all changing-risk-set warnings.
51. Open/sealed/delayed-release transport: level, gain, feedback effect, model rank and curve/
    forecast gaps, plus delayed-release replay and exposure age.
52. Builder×solver cross-fit: A-built/B-built/expert-built task families by evaluated system,
    with shortcut, invalidity, sealed/mechanism and rank-reversal outcomes.
53. Evidence-efficiency panel: nominal calls/bits beside lineage-clustered eESS, information gain,
    independent interventions/replications and science gain per eESS.
54. Observation-kernel sensitivity: dense-event versus fixed/random-phase/event-triggered grids,
    with interval-censored event times, AUC/curve/rank shifts, snapshot age and separate coverage for
    replayable artifacts versus path-dependent laboratory state.
55. Adaptive-design inference panel: fixed/randomized acquisition versus agent-adaptive acquisition,
    crossed with naive and policy-aware estimators; show overlap/positivity, effect/mechanism bias,
    interval coverage, false discovery and fresh-world confirmation.
56. Local-result reporting audit: objective trusted action/result ledger versus the agent's submitted
    evidence package, stratified by positive/null/contradictory/failed/censored result and linked to
    effect-size inflation, claim revision and reproducibility after full-ledger disclosure.
57. Conditional checkpoint-fork tree: one frozen parent history to all randomized continuations,
    showing within-parent versus matched-score between-history variance, wrong-mechanism lock-in,
    escape probability and sealed-confirmed child outcomes without post-hoc best-child selection.

Avoid presenting a radar chart or a single “science score”; small multiples preserve the
important capability dissociations.

## Statistical protocol

- Use at least five seeds for the broad O1/O2 matrix. Use at least ten paired seeds on a smaller
  preregistered F1/M1/V1 subset when making causal or reliability claims.
- Treat those counts as screening floors, not automatic adequacy. Before the confirmatory run,
  use pilot task/seed variance and a preregistered scientifically material effect to simulate
  hierarchical precision or power; increase independent lineages/runs or weaken the claim when
  the target interval width or power cannot be met.
- Treat task/instance and seed as the experimental units, not every trajectory checkpoint.
- Register task lineage—shared source data, simulator/oracle, procedural generator, starter code
  and construction template—and cluster or resample at the highest shared ancestry relevant to
  the claim. Report both nominal task count and effective independent-world/lineage count.
- Bootstrap or hierarchically resample complete task-instance/run trajectories; the dense,
  serially dependent points of a best-so-far curve are not independent experimental units.
- Treat independently randomized restart pools as experimental units; subset combinations from
  one fixed pool are dependent summaries, not extra replicates.
- Report task-level results and hierarchical/bootstrap uncertainty across tasks and seeds;
  use paired contrasts for controls.
- Preregister primary outcomes, budgets, exclusions, and stopping rules. Correct for multiple
  model/framework comparisons where inferential claims are made.
- Report missing token/cost data as missing, never zero. Report proposal budget and real trusted
  oracle calls separately; additionally report agent-visible submissions, evaluator-only
  snapshots, cooldown, feedback payload class and infrastructure incidents.
- Keep development feedback sealed from validation results. Periodic hidden auto-evaluation may
  measure the validation curve but must not influence search or stopping.
- Release all valid and failed trajectories, source/environment hashes, candidate lineage,
  feedback messages, evaluator versions and replay instructions.
- Report scheduled, started, completed, recovered and valid run counts with reason-coded
  exclusions. Give both a scientific estimand over preregistered valid executions and an
  operational estimand that retains model/infrastructure failures; never silently analyze only
  long-horizon survivors.
- Freeze the scheduled run-ID risk set before the first checkpoint. Validate observer-envelope
  monotonicity at the single-run/event level, then report failure-inclusive ITT and a fixed
  paired-completer sensitivity. If valid membership changes with time, name and plot that dynamic
  risk set separately; it cannot replace the fixed-cohort curve.
- When early outcomes allocate later task-hours, retain a randomized audit tranche with strictly
  positive continuation probability for every eligible cell. Estimate the full sampling-frame
  12-hour endpoint with prespecified inverse-probability or doubly robust sensitivity, and keep
  the pilot/allocation sample separate from confirmatory headline estimation.
- Report end-to-end wall time for deployment and active model/tool/oracle time for algorithmic
  efficiency. Queueing, rate limits, serving incidents and resume count are outcomes, not tokens.
- Block and randomize treatment order over calendar time. Prefer concurrently paired conditions
  on the same task instance when endpoint quotas permit; otherwise rotate order, log UTC start,
  endpoint/model snapshot and service incidents, and include calendar batch in the analysis.
- Predeclare task weights, normalization anchors and endpoint-selection policy. Repeat aggregate
  claims under rank/family-balanced aggregation, raw within-task gain, plausible anchor
  perturbations and leave-one-task/family-out analyses.
- Generate each aggregate from a frozen machine-readable manifest containing task IDs, evidence
  tracks, lineage clusters, weights, score transforms, run/failure policy and source revision;
  fail closed on any count or input mismatch and publish taxonomy changes as manifest diffs.
- Treat the task sampling frame as part of the estimand. Headroom-screened headline tasks measure
  improvement conditional on improvability; retain saturated on-ramps, null/misspecified and
  unsolvable cases for refusal, calibration and unconditional reliability analyses.
- Report model, scaffold, context limit, compaction, stop/resume policy and disclosed horizon as
  factors of the evaluated system. Do not attribute a cross-model difference to the base model
  when these factors differ.
- Distinguish artifact creation/submission before the cutoff from judge completion after it.
  Post-cutoff scores may enter a preregistered observer-side endpoint, but their feedback cannot
  be credited with causing an in-horizon descendant.
- Require every trajectory used for AUC, first-valid, terminal or commitment estimands to contain
  the preregistered boundary sentinels or an explicit reason-coded missing event; do not infer a
  start/end artifact from the nearest periodic snapshot or forward-filled historical maximum.
- Reconcile every oracle/sample call against a durable idempotency key and event ledger. Retry,
  recovery and duplicate delivery are operational events, not additional scientific evidence or
  free independent replicates.
- Bind every scientific observation to world, sample, batch, instrument and intervention lineage.
  Report nominal calls/bits beside an explicitly defined lineage-clustered evidence effective
  sample size; exact repeats may estimate measurement noise but never count as independent
  mechanism or replication evidence. Define eESS per estimand and show the independent top-lineage
  cluster count plus design-effect/weight sensitivity; do not collapse interventions, samples and
  independent laboratories into one universal evidence score.
- Treat the observation process as part of the measurement contract. Record scheduled capture,
  actual capture, artifact/state creation, judge start/completion and feedback-read times. For a
  deterministic replayable artifact, evaluate every immutable material commit offline or analyze
  first-valid/improvement times as interval-censored between scored captures; never assign the
  capture or judge-completion time to the underlying edit without qualification. Replay headline
  analyses under multiple fixed cadences and preregistered seeded-random phases. For consumptive, irreversible or
  interactive worlds, retain timestamped state transitions and sensor observations and report
  them in a separate live-state stratum rather than imputing an artifact-style snapshot curve.
- Replay the versioned selection contract over the raw event stream and assert that the declared
  incumbent hashes in online state, endpoint files, dashboards and analysis inputs are identical.
  Treat any divergence as a protocol failure before comparing systems.
- Analyze protocol/runtime validity as a separate transition before conditional optimization.
  Never let a high rate of first-valid artifacts silently substitute for post-valid sealed or
  mechanism improvement, and never discard invalid attempts from the operational estimand.
- Separate task admission/calibration data from confirmatory evaluation. Freeze thresholds,
  task weights and inclusion using a declared pilot model/seed/world panel; headline estimates
  use fresh seeds and procedural worlds, with reused pilot data labeled exploratory.
- Record every model/scaffold used to author, calibrate, red-team or revise a task and every task
  edit triggered by its trajectory. Use builder-blocked or leave-builder-out sensitivity for
  headline model comparisons rather than treating model-assisted task construction as neutral.
- Keep lineage-matched open-replay, sealed-prospective and delayed-release pools. Release the
  delayed pool and its privacy-reviewed ledger after the frozen cycle, independently replay it,
  and replenish only from a pre-generated untouched reserve; never report open and sealed pools
  as if they were the same reproducibility estimand.
- Within each claim-bearing run, separate exploratory/development evaluations, evaluator-only
  monitoring and a one-shot fresh post-commit confirmation panel. Count adaptive looks; a panel
  used to choose a claim, curve, milestone or stopping point is validation, not confirmation.
- For checkpoint-fork experiments, freeze the parent artifact, model/conversation or explicit
  context state, hypothesis/evidence ledger, local-result cache, outstanding jobs, environment,
  budget and random-state metadata before cloning. Treat the parent checkpoint as the top-level
  experimental unit, retain every descendant and report the conditional distribution; selecting
  the best child converts the design into best-of-`K` search and does not measure reproducibility.
- For interpreted breakthrough milestones, archive the parent and patch decomposition and replay
  parent/full-child/component-only/rollback artifacts on one frozen sealed panel. Chronological
  score coincidence without this edit ablation is descriptive, not causal attribution.
- Treat a scoring rubric as an analysis choice, not extra evidence. Recompute headline curves
  under preregistered coarsenings/refinements that preserve raw physical outcomes and total
  weights; also randomize task accumulation order. A curve whose smoothness, rank or forecast
  changes materially is evaluator-dependent and cannot support a universal scaling claim.
- Randomize source→target curriculum order and keep target worlds/confirmation panels disjoint
  from source tasks. Analyze transfer on target outcomes only; pooled source+target score gains
  cannot identify cross-task learning.
- For portfolio experiments, the experimental unit is a complete shared-budget episode. Retain
  abandoned/null projects in the denominator and compare allocation against information- and
  cost-constrained baselines, not an oracle that knew hidden truth before spending budget.
- For nonstationary or consumptive tasks, model world/sample state as part of treatment history.
  Bootstrap complete episodes or batches; do not shuffle observations across calibration eras,
  count repeated destructive acts as software retries, or reuse a post-intervention baseline.
- For feedback-clock studies, randomize release schedule at the run level and hold total feedback
  payload, active budget and scientific calls fixed. Do not call delayed bits independent
  observations, and do not compare cadence arms only at unequal event counts. Predeclare the
  candidate time coordinate and evaluate curve collapse/forecast on held-out runs and tasks.
- For task-graph interventions, the experimental unit is a generated graph/world lineage, not a
  graph node. Match or adjust for marginal node difficulty and score mass, randomize surface names,
  and freeze curve-family predictions before opening outcomes. Rubric repartition alone is S3,
  not evidence for S5.
- For question-formation studies, sign the question, hypothesis set, identifiability rationale,
  value forecast, falsification and stopping criteria before revealing outcome-bearing data.
  Evaluate with fresh procedural worlds and decision consequences, never prose style or similarity
  to an author-written question.
- For starter-prior studies, randomize starter arm within the same task/world block and hash the
  complete starter lineage. A wrong starter must be truth-blind, plausible on development evidence
  and falsifiable on preregistered interventions; do not count hidden-answer leakage as a helpful
  prior.
- For raw-measurement studies, pair every preprocessing arm on the same latent world and common
  noise draw. Preserve raw observations and typed uncertainty; never score downstream inference
  only on features produced by the same hidden generator used as ground truth.
- For metamorphic studies, canonicalize outputs only after candidate execution and freeze the
  transformation group before runs. Include non-equivalent negative controls so ignoring the
  transformed input cannot masquerade as invariance.
- For team studies, the experimental unit is a complete budget-matched team episode. Independent
  investigators cannot share scratch state or judge feedback, and the team must sign one claim or
  abstention before confirmation; member-wise oracle-best is a diagnostic, not the endpoint.
- For latent-utility studies, freeze and hash the utility family before search, reveal only
  scientifically legitimate constraints, and draw final weights after signed commit. Report the
  full regret distribution rather than selecting the most favorable stakeholder weight.

## Scaling-law caution

Seven heterogeneous tasks are enough for initial budget-response curves but not for a strong
cross-domain scaling-law claim. A scaling-law analysis should require substantially more
independent tasks or procedurally generated task instances, compare log-sigmoid, power-law,
log-linear and alternative saturating curves, and test forecasts on held-out time windows and
held-out tasks. Include Weibull/extreme-value repeated-sampling baselines and continuous-versus-
restart controls. Report bootstrap uncertainty for curve parameters. High in-sample `R²` on an
aggregate best-so-far curve is not, by itself, evidence of learning or mechanism discovery.
The fit must also survive alternative score transforms, family-balanced weights, task/family
deletion, missing-run policies and active-time rather than wall-time axes. Do not estimate a
universal curve only from tasks admitted because current agents had visible headroom.

Because absolute scientific-task scores often have a nonzero one-shot baseline and a separate
invalid-to-valid transition, also compare gain curves with an explicit baseline and a
hurdle/multistate model. Evaluate prospective forecasts against last-value-carried-forward,
monotone interpolation and empirical plateau baselines, with uncertainty coverage. Test the
logistic frontier account through its material-event prediction—improvement intensity near
`y(1-y)` with an inflection near `y=0.5`—and allow multiple phases or moving attainable support.
Any model-generation speed trend must use a panel and analysis frozen before the evaluated model
releases, or be labeled retrospective/exploratory.

The EdgeBench frontier derivation also requires vanishing score granularity and treats benchmark
tasks as non-interacting. Before interpreting smoother fits at larger task count, repeat the fit
under equivalent rubric partitions and randomized/lineage-blocked task orders. Cross-task
curricula, shared portfolio budgets, drifting instruments and irreversible interventions violate
the independent stationary task abstraction by design; analyze them with transfer, decision or
state-space estimands rather than forcing them into the same scalar log-sigmoid.

Elapsed time also cannot be assumed to be the causal learning coordinate. The current public
EdgeBench Codex configuration uses four different submission-cooldown values across 51 tasks
(`44×120 s`, `3×216 s`, `1×2160 s`, `3×0 s`) while auto-evaluation remains on a 30-minute observer
schedule. Frontier-Science should require an S4 cadence intervention before interpreting a
wall-time slope as an agent-intrinsic rate. Likewise, a good S-curve fit does not validate the
frontier graph: S5 must prospectively distinguish matched well-mixed, chained and bottlenecked
procedural worlds and recover the predicted bridge effect.

Do not interpret fitted `Smax`, `tmid` or `beta` merely because the aggregate level curve has a
high `R²`. The parameters trade off when the plateau or post-inflection region is weakly observed.
Require joint/profile or whole-trajectory bootstrap intervals, parameter-correlation and rolling-
window stability checks, plus a preregistered minimum of post-inflection observations. When this
gate fails, report observed-window gain, AUC and time-to-material-event without a point ceiling,
midpoint, speed or doubling-time claim.

## Minimum publishable sequence

### Stage A — optimization paper core

- Seven certified tasks × at least five seeds × budgets 30/100/300.
- Greedy, the three official search backends, and applicable classical/domain baselines.
- O1–O3 figures, raw trajectories, paired uncertainty and cost/oracle accounting.
- O0 one-shot/first-valid baselines; committed, terminal and evaluator-only endpoints reported
  separately; complete run-coverage and time-decomposition tables.
- Sentinel-complete, durable trajectory ledger with objective-selector replay and crash/recovery
  budget reconciliation on the pilot slice.
- Claim only cross-domain executable scientific generative optimization.

### Stage B — science-distinctive evidence

- F1 on at least four tasks with strict selection-blind controls.
- V1 on Lennard-Jones, spin glass, Poisson, thin film, Truss-v2 and Antenna-v2 using evaluator-only hidden shifts.
- V2 on at least thin film and one additional proxy/exact task.
- V3 fresh post-commit confirmation on at least one mechanism family and one optimization/
  multifidelity family; the confirmation worlds cannot have contributed snapshots or admission.
- M1 on the hardened SCM and ActiveLaw mechanism families.
- R1 null/misspecification cases and R2 independent replay.
- R3 autonomous commit/stop decisions; F4 semantic-feedback control; K1 frozen-corpus audit.
- R4 reversible-claim trials with contradictory/misspecified evidence; the mechanism curve must
  represent the current defended claim rather than a historical maximum.
- A small B1 expert-trajectory calibration before making claims relative to scientific work.
- One linked campaign with raw-input executable-method replay, typed stage handoffs,
  uncertainty propagation and stage-swap attribution of final decision utility.
- A measurement-health screen and hashed cohort manifest for every long-horizon and headline
  aggregate cell.
- S3 score-partition/task-order replay on the headline aggregate; F8 source→target transfer on at
  least one procedural lineage; one small P1 portfolio and one D1 stateful-laboratory stress test.
- S4 feedback-clock intervention on at least two heterogeneous tasks and an S5 matched task-graph
  twin pilot before giving a mechanistic interpretation to any scaling curve.
- One exploratory Q1 question-formulation laboratory and one K3 wrong-prior starter ablation before
  using the phrases autonomous research agenda or independent method discovery.
- One I6 raw-instrument pipeline and V4 metamorphic-invariance audit before claiming scope beyond
  structured observations; one T1 independent-team and U1 sealed-utility pilot before claiming
  collaborative autonomous science or stakeholder-robust scientific knowledge.
- One HZ1 disclosed-horizon/random-censoring pilot before interpreting long-run prefixes as
  short-budget policies; J1 judge calibration before any rubric/model-judge result is primary.
- One CA1 continuation-policy pilot with a randomized forced-12h audit tranche; M2 risk-set and
  single-run envelope replay must pass before any long-horizon aggregate curve is primary.
- One G1 open/sealed/delayed-release transport audit, a two-family G2 builder--solver cross-fit,
  and one EVI1 fresh/correlated/duplicate evidence-unit pilot before claiming that a public
  long-horizon curve generalizes to prospective science or measures independent evidence growth.
- One OBS1 offline observation-kernel replay on sentinel-complete trajectories, plus one
  path-dependent laboratory smoke with timestamped state transitions, before comparing curve
  speed, AUC or takeoff time across artifact and live-state task families.
- One AD1 adaptive-acquisition inference pilot crossed with naive versus policy-aware analysis,
  and one NR1 trusted local-result ledger audit, before claiming that an agent's endogenously
  collected evidence supports calibrated inference or complete scientific reporting.
- One CF1 checkpoint-fork pilot on two checkpointable procedural tasks before treating a single
  long trajectory as a stable estimate of future scientific progress or claiming that equal
  current scores represent equivalent research states.

Only Stage B can support claims about feedback-driven scientific discovery. A real-world
discovery claim additionally requires independent high-fidelity or physical confirmation and
domain-expert review.

## Preregistered hypotheses, not assumed conclusions

- H1: structured feedback improves paired AUC and sealed validation over shuffled and strict
  no-feedback controls.
- H2: persistent experience improves sealed validation over equal-budget restarts.
- H3: development and sealed-validation curves separate under proxy shift, and multifidelity
  promotion reduces this gap.
- H4: optimization/prediction performance can exceed mechanism recovery, especially without
  interventions.
- H5: calibrated stopping/refusal reduces false discoveries on null or misspecified instances
  without an unacceptable loss of validated discoveries.
- H6: meaningful diagnostic labels improve sealed mechanism recovery beyond equal-bit
  label-permuted feedback, rather than merely accelerating optimization of known score weights.
- H7: agent-committed scientific artifacts underperform hidden-snapshot oracle selection, and
  explicit commit/stop training reduces this deployability gap without increasing false discovery.
- H8: some apparent gains on public tasks disappear under frozen-corpus time/family-held-out
  evaluation, distinguishing retrieval/reproduction from task-local discovery.
- H9: a structured claim/evidence ledger reduces unsupported-claim exposure and revision delay
  after contradictory evidence relative to score-only or artifact-only memory.
- H10: a genuine aggregate learning result retains its qualitative curve, model ranking and
  held-out forecast under scientifically equivalent score partitions and task orders.
- H11: provenance-clean evidence memory improves target-task early efficiency on related worlds
  without increasing false discovery after misleading or regime-shift sources.
- H12: cost-aware allocation improves fresh-confirmed portfolio utility over equal allocation,
  while drift/state lineage reduces stale-result and irreversible-intervention errors.
- H13: after equalizing feedback payload and active scientific work, trajectories align more
  consistently on feedback-event or experiment-cost time than on raw wall time when cadence varies.
- H14: matched well-mixed task graphs exhibit a single frontier-like material-event hazard, while
  chain or bridge-bottleneck twins show preregistered plateaus/multiple phases that shrink when the
  bridge prerequisite is supplied.
- H15: open question formation can improve fresh-confirmed information or decision value over a
  candidate menu without increasing trivial questions or false discoveries.
- H16: a development-plausible wrong starter delays mechanism correction and reduces exploration
  diversity relative to blank/neutral starters; a successful system detects and escapes this prior.
- H17: agent-built preprocessing preserves calibrated downstream mechanism and decision quality
  under realistic instrument faults relative to oracle-clean features, rather than converting
  measurement error into confident false discovery.
- H18: physical claims and selected interventions remain equivalent under valid unit/coordinate/
  channel transformations while responding to non-equivalent physical controls.
- H19: blinded synthesis of genuinely independent investigators lowers correlated false discovery
  over an equal-budget single agent or shared-context critic without relying on oracle winner selection.
- H20: executable Pareto/method artifacts have lower post-commit sealed-utility regret than artifacts
  optimized for one public scalar, at comparable scientific cost and safety.
- H21: an independently disclosed short-horizon policy differs materially from the matched prefix
  of a long-horizon-aware policy in exploration/confirmation allocation or committed science utility.
- H22: a pinned rubric/model judge meets preregistered repeatability, agreement and style-invariance
  thresholds and preserves conclusions against executable outcomes or expert adjudication.
- H23: an agent-requested external-feedback policy predicts realized information or decision value
  better than fixed/random schedules and improves fresh-confirmed utility per cost without spending
  the one-shot confirmation reserve or increasing false discovery.
- H24: a deterministic 2h-headroom continuation gate saves task-hours but misses more materially
  useful 12h outcomes than a positive-probability uncertainty-aware gate at matched total cost;
  any retained advantage survives full-sampling-frame weighting and fresh confirmation.
- H25: baseline-adjusted learning and feedback-control effects measured on open-replay tasks
  attenuate on sealed prospective tasks as public exposure grows, while delayed-release replay
  recovers the original sealed estimate within preregistered uncertainty.
- H26: a solver performs differently on tasks whose final construction used that same solver;
  builder-balanced or leave-builder-out aggregation reduces the interaction and any induced rank reversal.
- H27: fresh independent evidence improves sealed mechanism/refusal outcomes and calibration more
  per nominal call than correlated or duplicate feedback; raw-call gains without eESS or fresh-
  confirmation gain do not constitute evidence accumulation.
- H28: first-valid time, AUC, fitted midpoint/speed and system ranking remain materially stable
  across preregistered observation cadences and seeded-random phases after interval-censoring is respected;
  event-triggered or live-state tasks that fail this test are analyzed separately rather than
  pooled into a common wall-time scaling curve.
- H29: policy-aware inference using logged acquisition propensities or randomized exploration
  restores effect/mechanism coverage after adaptive experiment selection relative to a naive
  analysis of the same observations; unsupported regions are refused rather than extrapolated.
- H30: a trusted all-action ledger reveals more null, contradictory and failed local results than
  the agent's submitted evidence package unless complete-result reporting is required; mandatory
  disclosure reduces effect-size inflation and unsupported confirmation without erasing true findings.
- H31: continuations cloned from one complete research checkpoint show lower outcome variance than
  matched-score checkpoints reached through different histories; histories carrying a wrong but
  development-plausible mechanism have lower sealed-confirmed escape probability even at equal
  current score, demonstrating that scalar progress is not a sufficient scientific state.

These are hypotheses to test. The paper should report failed hypotheses and negative results
rather than selecting only curves that resemble Frontier-Eng or EdgeBench.
