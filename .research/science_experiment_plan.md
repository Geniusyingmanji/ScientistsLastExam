# Science-specific experiment plan

Date: 2026-07-21 (UTC). This plan complements the Frontier-Eng-style optimization study and
the EdgeBench-style long-horizon trajectory study. It does not assume that optimization,
feedback learning, mechanism recovery, and scientific validation are interchangeable.

## Central experimental distinction

The benchmark should measure three trajectories from the same run:

1. `development_score(b)`: best feasible score visible to the search system at budget `b`;
2. `sealed_validation_score(b)`: evaluator-only score on hidden shifts, interventions, or a
   higher-fidelity oracle, computed from periodic snapshots and never returned to the agent;
3. `mechanism_score(b)`: correctness of a separately submitted equation, causal graph,
   parameterization, or other scientific claim.

The primary science question is whether these curves improve together. A rising development
curve alone is evidence of optimization, not discovery. A widening development–validation gap
is evidence of proxy overfitting or Goodhart effects. A high predictive/optimization score with
a low mechanism score is evidence that task success did not recover the underlying mechanism.

Do not combine the three curves into one benchmark score.

## Experiment matrix

| ID | Question | Required comparison | Primary outcomes | Claim enabled |
|---|---|---|---|---|
| O1 | Which model–framework combinations optimize best? | Models × greedy/OpenEvolve/AB-MCTS/ShinkaEvolve × random/quasi-random/BO/CMA-ES or DE/domain heuristics | terminal best feasible score, best-so-far AUC, within-task rank, performance profile, oracle calls, tokens/cost/time | Budgeted generative optimization |
| O2 | How does performance scale with budget? | Budgets 30/100/300; a deeper subset beyond 300 if justified | task-level and aggregate trajectories, improvement frequency/magnitude, plateau length, marginal gain per call | Empirical budget-response, not yet a universal scaling law |
| O3 | Is depth better than width? | Equal total budget split across 1/2/4/8 restarts or branches | best score, AUC, diversity, time to last improvement | Search-allocation result |
| F1 | Is the system using experimental feedback causally? | Normal feedback vs shuffled feedback vs delayed feedback vs strict selection-blind/no-feedback, using paired seeds and identical budgets | paired AUC lift, terminal lift, proposal divergence after feedback, validated discoveries per call | Feedback learning |
| F2 | Does persistent experience help beyond repeated sampling? | One continuous run vs equal-budget independent restarts; full memory vs summarized/frozen/no memory | score/AUC and sealed-validation lift | Value of accumulated scientific state |
| V1 | Does optimization generalize beyond the visible oracle? | Visible development oracle vs evaluator-only hidden instances/shifts | sealed score, development–validation gap, rank correlation, replication rate | Generalizable result |
| V2 | Does a cheap proxy survive higher-fidelity evaluation? | Proxy-only search; scheduled promotion; adaptive multifidelity; exact-only reference where affordable | proxy/exact rank correlation, false-promotion rate, exact-call efficiency, high-fidelity regret | Multifidelity validation |
| M1 | Did the system recover a mechanism rather than a predictor? | Observational-only vs intervention access; prediction-only vs explicit mechanism submission | graph F1, equation/term recovery, parameter error, intervention and shift prediction | Mechanism recovery |
| R1 | Can the system detect when no supported discovery exists? | Well-specified worlds vs null, noisy, confounded, biased-oracle and model-misspecified worlds | false-discovery rate, calibration, correct abstention, detection delay, unnecessary experiments | Calibrated refusal and reliability |
| R2 | Is the claimed result reproducible and traceable? | Original evaluator vs independent implementation/reviewer; replay from immutable artifact | replay success, independent replication rate, claim–evidence consistency, failed-branch coverage | Research integrity |

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

## Science-specific task extensions

| Current task | Useful sealed or shifted evaluation | Best role |
|---|---|---|
| Lennard-Jones clusters | unseen cluster sizes and seeds; perturbed interaction parameters; finite-temperature stability; an independently implemented energy oracle | optimization transfer and proxy-to-physics validation |
| SK spin glass | procedurally generated hidden couplings, larger sizes, and held-out coupling distributions | instance/distribution generalization |
| Poisson solver | hidden spectra, resolutions, boundary conditions and coefficient fields; measured convergence order | numerical-law and solver generalization |
| Multilayer thin film | hidden angles, polarization, dispersion tables, material tolerances and fabrication noise; later high-fidelity/physical replication | strongest current multifidelity/robustness case |
| Matrix multiplication | held-out dimensions/fields, exact tensor identity and independent proof/checker | machine-verifiable mathematical discovery |
| Cap Set | held-out dimensions or fields and exact construction verification; contamination audit against known constructions | machine-verifiable mathematical discovery |
| Circle packing | unseen `N`, interval/independent geometric verification and perturbation robustness | machine-verifiable construction |

The seven certified tasks do not currently contain a clean mechanism-identification benchmark.
Do not force a mechanism claim onto them. Add at least two procedurally generated task families:

1. a hidden structural-causal-model laboratory with observation and intervention actions,
   separately scored prediction, graph, equations, and intervention transfer; and
2. a hidden dynamical-law laboratory with noisy trajectories, experiment/control selection,
   symbolic equation and parameter recovery, plus extrapolation to sealed regimes.

Include null and misspecified instances in both families so that always producing a mechanism
is penalized.

## Recommended figures and tables

1. Benchmark/task taxonomy and the O/F/M/V/R capability ladder.
2. Model × framework within-task ranks and Dolan–Moré performance profiles.
3. Best-so-far score and AUC against proposal budget, actual oracle calls, wall time, and cost.
4. Equal-budget depth–width heatmap and continuous-run versus restart curves.
5. Paired normal/shuffled/delayed/selection-blind feedback curves.
6. The main science figure: development, sealed-validation, and mechanism curves against the
   same budget, with their generalization gaps.
7. Proxy-versus-high-fidelity scatter/calibration curve and false-promotion rate.
8. Risk–coverage or calibration plot on null/misspecified cases, including false discoveries.
9. One successful and one failed hypothesis–experiment–evidence DAG with replayable artifacts.

Avoid presenting a radar chart or a single “science score”; small multiples preserve the
important capability dissociations.

## Statistical protocol

- Use at least five seeds for the broad O1/O2 matrix. Use at least ten paired seeds on a smaller
  preregistered F1/M1/V1 subset when making causal or reliability claims.
- Treat task/instance and seed as the experimental units, not every trajectory checkpoint.
- Report task-level results and hierarchical/bootstrap uncertainty across tasks and seeds;
  use paired contrasts for controls.
- Preregister primary outcomes, budgets, exclusions, and stopping rules. Correct for multiple
  model/framework comparisons where inferential claims are made.
- Report missing token/cost data as missing, never zero. Report proposal budget and real trusted
  oracle calls separately.
- Keep development feedback sealed from validation results. Periodic hidden auto-evaluation may
  measure the validation curve but must not influence search or stopping.
- Release all valid and failed trajectories, source/environment hashes, candidate lineage,
  feedback messages, evaluator versions and replay instructions.

## Scaling-law caution

Seven heterogeneous tasks are enough for initial budget-response curves but not for a strong
cross-domain scaling-law claim. A scaling-law analysis should require substantially more
independent tasks or procedurally generated task instances, compare log-sigmoid, power-law,
log-linear and alternative saturating curves, and test forecasts on held-out time windows and
held-out tasks. Report bootstrap uncertainty for curve parameters. High in-sample `R²` on an
aggregate best-so-far curve is not, by itself, evidence of learning or mechanism discovery.

## Minimum publishable sequence

### Stage A — optimization paper core

- Seven certified tasks × at least five seeds × budgets 30/100/300.
- Greedy, the three official search backends, and applicable classical/domain baselines.
- O1–O3 figures, raw trajectories, paired uncertainty and cost/oracle accounting.
- Claim only cross-domain executable scientific generative optimization.

### Stage B — science-distinctive evidence

- F1 on at least four tasks with strict selection-blind controls.
- V1 on Lennard-Jones, spin glass, Poisson and thin film using evaluator-only hidden shifts.
- V2 on at least thin film and one additional proxy/exact task.
- M1 on the two new mechanism families.
- R1 null/misspecification cases and R2 independent replay.

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

These are hypotheses to test. The paper should report failed hypotheses and negative results
rather than selecting only curves that resemble Frontier-Eng or EdgeBench.
