# Cross-task science calibration findings

Date: 2026-07-22 (UTC). These findings use trusted GPT-5.5 `greedy_rewrite` calibrations on
OED-v2, Pendulum-v2, GateSynthesis-v2, ActiveLawDiscovery, OPF-v2, Truss-v2, Antenna-v2,
NMR-v2, HeatExchanger-v2, ReactionMechanismFitting-v2 and GravityInversion-v2. The 21 normal-feedback model
conditions each contain one seed and proposal budget one
or three. They calibrate tasks and motivate experiments; they are not a model leaderboard, a causal
feedback study or population evidence.

The portable machine record is `experiments/science_calibration_summary_2026-07-22_v4.json`. It
retains every top-level scalar metric, candidate lineage hash and raw trajectory SHA-256 for all
21 normal conditions. Strict selection-blind diagnostics remain in task-specific
analysis because it is not a normal-feedback calibration. The underlying reports bind the
task-specific source revision. Pendulum's initial budget-one run on revision `57c0e1b` is
excluded because the public task omitted the exact plant equations and was explicitly superseded
by the corrected-contract run on `2557adb`.

## Direct observations

| Task and condition | Visible result | Sealed result | What this run supports |
|---|---:|---:|---|
| OED-v2, budget 1 | development 0.990615 | shifted validation 0.993697 | A general textbook design algorithm transfers to the shifted families and nearly saturates the task in one proposal. |
| Pendulum-v2, corrected contract, budget 1 | development 0.796874 | shifted robustness 0.630753 | A valid nominal controller retains a 0.166122 robustness gap. |
| Pendulum-v2, budget 3 | development 0.690588 to 0.854016 | robustness 0.640591 to 0.639041 | Within this trajectory, accepted visible improvement did not improve shifted control and widened the gap from 0.049997 to 0.214975. |
| GateSynthesis-v2, budget 1 | nominal development 0.999872; held-out nominal 0.999992 | hardware robustness 0.956894; held-out robustness 0.983037 | Nominal and target-transfer scores can saturate while hardware-shift performance remains lower. |
| GateSynthesis-v2, budget 3 | nominal 0.9999996 to numerical 1.0 | development robustness 0.966531 to 0.974567; held-out robustness 0.984628 to 0.984472 | Sealed development robustness rose incidentally, but held-out robustness did not; one seed cannot attribute this change to feedback. |
| ActiveLawDiscovery, budget 1 | selected score 0.796281; rollout prediction 0.997392 | validation mechanism 0.744607; validation prediction 0.995864 | Near-perfect prediction coexists with one high-confidence false discovery in each split's misspecified world. |
| ActiveLawDiscovery, budget 3 | selected score 0.711322 then lower | every proposal retains one false discovery in each split | More nominal score feedback did not repair model-inadequacy detection in this trajectory. |
| OPF-v2, budget 1 | development and held-out nominal scores approximately 1.0 | N-1 robustness 0.031378 and 0.0000007 | The generated program implements nominal DC-OPF only. Mean development outage feasibility is 0.113997 despite exact nominal optimization. |
| OPF-v2, budget 3 | two valid nominal proposals score approximately 1.0 | both retain N-1 robustness 0.031378 and outage feasibility 0.113997 | Additional nominal feedback leaves the economy-security failure unchanged. |
| Truss-v2, budget 1 | development and held-out nominal 0.0 | development and held-out robustness 0.0 | A robustness-aware optimizer returns the safe all-maximum design, showing that valid code generation need not improve normalized scientific utility. |
| Truss-v2, budget 3 | development 0.000000 → 0.415579 → 0.548497 → 0.611494 | final held-out robustness 0.206438 → 0.077881 while held-out nominal rises 0.251321 → 0.422348 | The task retains optimization headroom, but the final nominally accepted update worsens sealed transfer robustness. |
| Antenna-v2, budget 1 | development 0.999263; held-out nominal 0.995115 | hardware/failure robustness 0.624204/0.394718 | A general window/null-synthesis policy nearly saturates nominal pattern quality in one proposal but not shifted hardware performance. |
| Antenna-v2, budget 3 | development 0.845170 → 0.993267 → 1.0 | development robustness 0.704823 → 0.635511 → 0.576348 | Every accepted nominal improvement lowers sealed robustness and mean worst-shift quality within this trajectory. |
| NMR-v2, budget 1 | development mechanism/refusal 0.427998; reconstruction 0.874116 | held-out mechanism/refusal 0.176186; reconstruction 0.878353; false-discovery 0.5/0.5 | GPT-5.5 beats the classical mechanism baseline without saturating, but high reconstruction coexists with false discovery and weak shifted mechanism validity. |
| NMR-v2, budget 3 | development proposals 0.375440 → 0.212692 → 0.161475; only step 1 accepted | held-out mechanism/refusal remains 0.0; rejected steps retain development reconstruction 0.819/0.783 while false-discovery is 1.0 on both splits | Aggregate score feedback does not repair model-inadequacy detection in this trajectory; residual quality alone remains misleading. |
| HeatExchanger-v2, budget 1 | the only proposal is invalid; development remains 0.0 | no validated improvement | Valid code generation and scientific feasibility remain separate gates. |
| HeatExchanger-v2, budget 3 | development exact 0.000 → 0.008 → 0.126; final proxy 0.173 | held-out exact 0.280; robustness 0.130; two of four development regimes remain zero | Aggregate improvement can be concentrated in one regime and need not transfer to physical shifts. |
| ReactionMechanism-v2, budget 1 | valid proposal remains at normalized mechanism 0.0 | held-out normalized mechanism 0.0 | A complex fitter spends the assay budget on an under-informative design and abstains everywhere. |
| ReactionMechanism-v2, budget 3 | all three proposals remain at 0.0 and are rejected | each performs one assay and abstains everywhere | More rewrite budget does not help when scalar zero feedback cannot localize whether experiment design, inference or refusal caused failure. |
| GravityInversion-v2, budget 1 | invalid callback unpacking; development remains 0.0 | no validated improvement | A physically sophisticated implementation can still fail the executable laboratory protocol. |
| GravityInversion-v2, budget 3 | development mechanism 0.000 → 0.994; field prediction 0.992 | held-out mechanism 0.767; held-out field prediction 0.988 | Known parametric inversion nearly saturates development, but field transfer does not establish the same internal geology. |

OPF's `robustness_score` combines security-constrained economic quality with overload penalties.
It is not a pure safety probability. The proportional baseline is feasible for every tested
outage but has robustness score zero because it provides no economic improvement above itself.
Accordingly, OPF results must report contingency feasibility, overload and security-constrained
cost separately.

## Repeated patterns and their current evidence limits

### 1. One-step success often measures algorithm synthesis, not scientific learning

GPT-5.5 writes recognizable multiplicative/Fedorov design, GRAPE, convex DC-OPF and window/null-
synthesis procedures
in one proposal. These results directly measure whether a model can instantiate a known method
inside a new executable contract. They do not establish that score feedback produced a new
scientific strategy. Budget-one saturation is therefore useful as an on-ramp calibration but
weak evidence for long-horizon autonomous research.

### 2. Visible optimization and scientific validity are different trajectories

Pendulum, gate synthesis, OPF, Truss, Antenna and NMR all separate a visible development
objective from an evaluator-only shift, contingency or held-out mechanism metric. OPF has the
largest numeric gap among the nominal-design calibrations, while NMR budget one falls from
0.428 development to 0.176 held-out mechanism/refusal despite similar reconstruction. In OPF,
nominal optimization reaches its reference while most complete line-outage scenarios fail. The
current observations indicate
that terminal best-score curves alone can hide a task-relevant validation loss. A general claim
requires repeated paired runs and hidden server-side instances.

### 3. Held-out nominal transfer does not imply robustness

Gate synthesis, OPF and Antenna reach near-perfect nominal scores on interleaved held-out instances.
Their sealed perturbation or contingency scores remain lower. Procedural held-out networks or
targets test policy transfer, whereas altered physics, hardware error and component failure test
robustness. Future task cards must specify both axes instead of using one generic validation
field.

### 4. Prediction does not imply mechanism recovery or warranted belief

ActiveLawDiscovery predicts in-library trajectories with approximately 0.99 accuracy while
assigning high confidence to unsupported polynomial mechanisms in misspecified worlds. NMR-v2
shows the same distinction in an inverse problem: the truth-blind classical policy reconstructs
clean spectra at 0.887/0.851 but scores only 0.271/0.146 on normalized mechanism/refusal, while
GPT-5.5 budget one reconstructs at 0.874/0.878 but retains false discoveries on both splits.
The error is not primarily prediction or residual fit. It is failure to recover the right
artifact and detect when the candidate model class is inadequate. Discovery tasks therefore
need explicit mechanism artifacts, null and misspecified worlds, confidence, abstention and
false-discovery metrics.

ReactionMechanism-v2 provides a second dynamical inverse example. Its truth-blind classical
fit reaches 0.860 development interpolation but only 0.482 normalized mechanism/refusal and
falsely claims a mechanism in half of unsupported worlds. In a strict open-loop diagnostic,
one proposal reaches 0.711 interpolation and 0.747 extrapolation but only 0.259 normalized
mechanism, again with a 0.5 false-discovery rate. This strengthens the cross-domain conclusion
without turning two synthetic tasks into evidence about wet-lab discovery.

### 5. Feedback cannot optimize information that selection never receives

In the OPF budget-three run, later proposals receive only nominal score and reproduce the same
N-1 failure. Pendulum's visible improvement is accompanied by flat shifted robustness, while
ActiveLawDiscovery retains its misspecification errors. NMR selection does include a normalized
mechanism/refusal aggregate, but does not expose its decomposition: after the first accepted
proposal, both rewrites make false discoveries on every unsupported development and held-out
spectrum and score lower despite retaining substantial reconstruction. Gate synthesis provides
a counterpoint: sealed robustness changes slightly even without being exposed, showing that
correlated movement can occur by chance or through shared structure. These runs motivate, but do not prove, the
hypothesis that objective-aligned structured feedback is required for reliable improvement on a
sealed scientific property.

ReactionMechanism-v2 exposes an additional feedback bottleneck: all three normal proposals
score exactly zero and are rejected, so the parent and visible feedback remain unchanged. The
agent cannot tell from the scalar whether it chose uninformative assays, estimated poor rate
curves or set an overly conservative refusal threshold. A same-identifier open-loop batch finds
a nonzero candidate by proposal diversity alone. Because the endpoint has no server-side seed
and the runs are not token-matched, this is evidence of sparse credit assignment and high
proposal variance—not evidence that removing feedback helps.

### 6. Contract completeness must precede headroom claims

The superseded Pendulum diagnostic failed because the public contract omitted the evaluator's
exact equations. Disclosing the equations changed budget-one performance from no improvement to
0.796874. A benchmark should hide instances, perturbations and validation outcomes, but not
equations or observations required to define the stated problem. Apparent difficulty caused by
an underspecified contract is evaluator error, not scientific headroom.

### 7. A single science score would erase the observed failure modes

The calibrated tasks expose different quantities: nominal utility, held-out transfer, physical
robustness, constraint feasibility, prediction, mechanism recovery and refusal. Averaging them
would allow nominal gains to compensate for unsafe dispatch or false discovery. The benchmark
should retain an O/F/M/V/R capability vector and use Pareto or risk-coverage analysis where a
single ordering is not scientifically justified.

## Preregistered next tests

The observations above define hypotheses rather than assumed conclusions:

1. Normal structured feedback will improve sealed validation more than shuffled, delayed and
   strict selection-blind feedback under paired seeds.
2. Robustness-aware selection will move the Pendulum, Gate and OPF Pareto frontier, whereas
   nominal-only selection will primarily improve the visible objective.
3. Explicit model-checking and abstention feedback will reduce ActiveLawDiscovery and NMR-v2
   false discoveries without an unacceptable loss of correct in-library mechanisms.
4. Continuous scientific memory will outperform equal-budget restarts only when it stores
   falsified hypotheses and experiment evidence, not merely the incumbent program.
5. One-step saturation will predict limited long-horizon headroom on tasks whose solution is a
   standard algorithm, but not on tasks requiring model discrimination, multifidelity promotion
   or calibrated refusal.
6. Factorized but label-blind feedback about experiment coverage, feasibility and residual
   diagnostics will escape zero-score plateaus more reliably than an aggregate scalar alone,
   without leaking held-out mechanisms or evaluator-only world types.

Tests 1--3 require at least ten paired seeds on the focused science subset. All comparisons must
hold proposal budget, actual oracle calls, tool access and feedback-message shape fixed. Hidden
metrics may be evaluated periodically for curves but cannot affect search or stopping in the
nominal-only condition.

### Strict-control pilot update

A preregistered three-replicate implementation pilot has now compared normal iteration with a
strict open-loop `selection_blind` control on Pendulum, GateSynthesis, ActiveLawDiscovery and
OPF. All 24 conditions completed with trusted provenance and correct blind lineage. No task shows
a direction-stable visible or sealed feedback advantage; every preregistered performance or
science-outcome paired interval spans zero. ActiveLawDiscovery retains one development and one validation false discovery in every
selected condition, while OPF retains identical N-1 feasibility under normal and blind search.
Normal runs use more tokens on all four tasks, so the pilot is not compute-matched. These results
leave hypotheses 1--3 open for a larger, token-matched study and prohibit a positive Track F
claim from the current evidence. Exact paired estimates and limitations are recorded in
`feedback_pilot_results.md` and `experiments/feedback_pilot_analysis_2026-07-21.json`.

### Truss-v2 headroom diagnostic

Truss-v2 adds a qualitatively different structural-design case. An independent budget-one
GPT-5.5 proposal attempts a robustness-aware optimizer but falls back to the all-maximum baseline
on every structure, leaving development and sealed scores at zero. In a separate budget-three
normal run, all three proposals are accepted and development score rises
`0.0000 -> 0.4156 -> 0.5485 -> 0.6115`; held-out nominal transfer also reaches 0.4223. The task
therefore has genuine iterative optimization headroom rather than the one-step saturation seen
in OED, gate synthesis and nominal OPF.

The science trajectory does not improve monotonically with the visible curve. From the second
to the third accepted proposal, held-out nominal score rises from 0.2513 to 0.4223 while sealed
held-out robustness falls from 0.2064 to 0.0779; development shifted-case feasibility remains
0.75. The final policy is nominally feasible on all six structures, but its steel Pratt
development structure and titanium held-out structure fail every shifted case. Thus policy
transfer to a new nominal topology/material does not imply physical-shift transfer, consistent
with the gate and OPF findings.

A same-identifier budget-three strict open-loop diagnostic selects only 0.0846 development,
compared with 0.6115 for normal iteration. This is a useful feedback-headroom signal, not a
causal estimate: each condition has one run, the endpoint has no server-side seed, and normal
uses 19,659 tokens versus 12,637. Notably, the blind selected candidate has higher held-out
robustness (0.4164) than the normal selected candidate (0.0779), reinforcing that a visible
feedback advantage and scientific validation advantage are separate hypotheses. Exact hashes,
lineage and contrasts are retained by `analyze_truss_v2_calibrations.py`.

### Antenna-v2 nominal-versus-hardware diagnostic

Antenna-v2 is another one-step algorithm-synthesis on-ramp. At budget one, GPT-5.5 generates a
general taper/null-projection policy that reaches development/held-out nominal
`0.999263/0.995115`, while exhaustive frequency, position, calibration and single-element-
failure robustness is only `0.624204/0.394718`. The target-gain feasibility rate remains one,
so the gap is due to degraded sidelobe/null suppression rather than loss of the main beam.

An independent budget-three trajectory starts from a weaker first proposal and accepts all
three nominal improvements: `0.845170 -> 0.993267 -> 1.000000`. Across the same accepted steps,
development robustness decreases `0.704823 -> 0.635511 -> 0.576348`, and mean worst-shift
quality falls `10.9824 -> 10.6213 -> 10.3506 dB`. Held-out nominal reaches 0.998717, while
held-out robustness is nonmonotone and ends at 0.534775. This within-run dissociation is direct
evidence that nominal selection did not optimize hardware robustness. It is not a causal
feedback comparison or population result: there is one run, robustness stayed sealed, and no
robustness-aware treatment was tested. Report and trajectory hashes plus accepted parent lineage
are validated by `analyze_antenna_v2_calibrations.py`.

## Consequences for expansion to approximately 50 tasks

Every new or rebuilt task must pass the following gate before it counts toward the target:

- a scientifically recognizable artifact and cited workflow;
- a complete public problem contract and a valid weak baseline;
- an independent numerical, analytic or exact reference plus invariant tests;
- procedural development and server-held instances rather than a fixed public truth;
- separate nominal, held-out and shifted/high-fidelity metrics where applicable;
- explicit mechanism and refusal outputs for discovery tasks;
- finite-output rejection, secure isolation, deterministic replay and metric sealing;
- classical and domain baselines, followed by GPT-5.5 budget-one headroom screening; and
- retention as an on-ramp, not a headline task, if a standard method reliably saturates it.

The present inventory contains 23 internally admissible certified or candidate packages. The
remaining gap is approximately 27 tasks. Expansion should use procedural families spanning
design, inverse problems, control, multifidelity validation, mechanism discovery and exact
mathematical construction rather than cloning one scalar optimization template across domains.
