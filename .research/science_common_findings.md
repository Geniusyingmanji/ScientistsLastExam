# Cross-task science calibration findings

Date: 2026-07-23 (UTC), updated 2026-07-24. These findings use trusted GPT-5.5 `greedy_rewrite` calibrations on
OED-v2, Pendulum-v2, GateSynthesis-v2, ActiveLawDiscovery, OPF-v2, Truss-v2, Antenna-v2,
NMR-v2, HeatExchanger-v2, ReactionMechanismFitting-v2, GravityInversion-v2,
OceanCurrentInversion-v2, RadiativeTransferFit-v2, LowThrustTransfer-v2,
LidDrivenCavity-v2, EnergyBalanceModel-v2, BroadbandAbsorber-v2,
DistillationColumnDesign-v2, HartreeFockSCF-v2, RoomImpulseResponse-v2,
ConvectionDiffusionOpt-v2, SeismicWaveInversion-v2, RankineCycleOpt-v2 and MOSFETDoping-v2. The
list now also includes RANSCalibration-v2, GeneNetworkIntervention-v1 and RNAInverseDesign-v1. The
53 normal-feedback model conditions across these 27 tasks each
contain one seed and proposal budget one or three. They calibrate tasks and motivate experiments;
they are not a model leaderboard, a causal feedback study or population evidence.

The portable machine record
`experiments/science_calibration_summary_2026-07-24_v20.json` retains every top-level scalar metric,
candidate lineage hash and raw trajectory SHA-256 for all 53 normal conditions.
Additional strict diagnostics for Distillation-v2, Hartree--Fock and room acoustics are bound
separately by `experiments/distillation_v2_calibration_analysis_2026-07-23.json`,
`experiments/hartree_fock_v2_calibration_analysis_2026-07-23.json` and
`experiments/room_acoustics_v2_calibration_analysis_2026-07-23.json` and
`experiments/convection_diffusion_v2_calibration_analysis_2026-07-23.json`,
`experiments/seismic_wave_v2_calibration_analysis_2026-07-24.json` and
`experiments/rankine_v2_calibration_analysis_2026-07-24.json` and
`experiments/mosfet_v2_calibration_analysis_2026-07-24.json`,
`experiments/rans_v2_calibration_analysis_2026-07-24.json`,
`experiments/gene_network_intervention_calibration_analysis_2026-07-24.json` and
`experiments/rna_inverse_design_calibration_analysis_2026-07-24.json`. Strict selection-blind
diagnostics remain in task-specific analysis because they are not normal-feedback calibrations.
The underlying reports bind the task-specific source revision. Pendulum's initial budget-one
run on revision `57c0e1b` is
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
| MOSFETDoping-v2, budget 1 | nominal development/held-out `0.780/0.746` | robustness `0.707/0.718`; shift feasibility `0.586/0.536` | One proposal finds a useful compact-model Pareto archive, but many process/operating-shift archive members are infeasible. This is reduced-order design optimization, not TCAD or device validation. |
| MOSFETDoping-v2, budget 3 | normal nominal development/held-out `0.457/0.445`; selection-blind `0.770/0.738` | normal robustness `0.298/0.402`; selection-blind `0.723/0.712` | The frozen-parent batch happens to outperform the normal run on every main score axis. Oracle calls match, but tokens differ by 5,507 and model randomness is unseeded, so the contrast is proposal-variance evidence, not a negative feedback effect. |
| HeatExchanger-v2, budget 1 | the only proposal is invalid; development remains 0.0 | no validated improvement | Valid code generation and scientific feasibility remain separate gates. |
| HeatExchanger-v2, budget 3 | development exact 0.000 → 0.008 → 0.126; final proxy 0.173 | held-out exact 0.280; robustness 0.130; two of four development regimes remain zero | Aggregate improvement can be concentrated in one regime and need not transfer to physical shifts. |
| LowThrustTransfer-v2, public Gauss--Newton | development/held-out utility 0.711/0.719; nominal feasibility 1.0/1.0 | shifted robustness 0.682/0.660; held-out shifted feasibility 0.833; production/refinement discrepancy 0.0423 tolerance | Long-horizon optimization must separate numerical error, terminal feasibility, nominal utility, held-out transfer and execution robustness. |
| LowThrustTransfer-v2, budget 1 | development 0.007736; valid artifact; mean development delta-v 737 m/s | held-out `5.8e-9`; nominal and shifted terminal feasibility 0 on both splits | A plausible finite guidance law and nonzero graded score do not establish arrival in the terminal tolerance set. |
| LowThrustTransfer-v2, budget 3 | proposal scores 0.005079 → 0.004750 → `2.1e-6`; only step 1 accepted | selected held-out `1.3e-11`; all three proposals nominally and shift infeasible | More scalar feedback did not localize the long-horizon boundary-value error in this trajectory. |
| LidDrivenCavity-v2, budget 1 | development `0.999999990`; PDE feasibility 1.0 | held-out `0.999999957`; both grid-refinement scores above `0.99999998` | One proposal synthesizes a numerical solver that nearly matches the same discrete reference on development, held-out and refinement cases. This is solver synthesis, not a new flow result. |
| LidDrivenCavity-v2, budget 3 | normal accepted `0.869915 → 0.894913 → 0.898062` | selected held-out `0.843732`; all nominal and grid physics gates pass | Iterative rewrites improve this normal trajectory but remain below independent one-shot and open-loop near-ceiling solvers. One run cannot assign the difference to feedback. |
| EnergyBalanceModel-v2, long versus short classical design | long/short development mechanism `0.809/0.0039` | held-out mechanism `0.942/0.0`; held-out prediction `0.999/0.990`; short false discovery `0.20/0.25` | Accurate response prediction can survive an under-informative experiment even when parameter recovery and model-class discrimination collapse. |
| EnergyBalanceModel-v2, budget 1 and normal budget 3 | all four proposals are invalid return artifacts and remain at 0.0 | no supported mechanism, prediction or refusal claim is validated | Scientific sophistication in generated code does not compensate for failure to return the documented artifact. |
| EnergyBalanceModel-v2, strict open-loop budget 3 | offline best development mechanism `0.618`; prediction `0.977` | held-out mechanism `0.282`; prediction `0.994`; false discovery `0.20/0.25` | Near-unit prediction coexists with weak held-out mechanism and high-confidence feedback-drift/three-layer false claims. The one-run contrast is not a feedback estimate. |
| BroadbandAbsorber-v2, budget 1 | the only proposal times out; development remains 0.0 | no validated improvement | Candidate compute boundedness is a separate gate from acoustic design quality. |
| BroadbandAbsorber-v2, normal budget 3 | selected development/held-out nominal `0.9148/0.8588`; exact utility `0.4678/0.4476` | sealed robustness `0.9118/0.8583`; manufacturing geometry feasibility `1.0/1.0` | One valid log-spaced design transfers across bands and physical shifts; two later rewrites time out, so more rewrite budget is not monotone progress. |
| BroadbandAbsorber-v2, strict open-loop budget 3 | offline-best development/held-out nominal `0.9173/0.9574` | sealed robustness `0.4519/0.4491`; manufacturing geometry feasibility `0.75/0.75` | Nearly equal development score and higher held-out nominal transfer coexist with roughly half the robustness retention because manufacturing errors cross the panel envelope. The one-run contrast is not a feedback estimate. |
| Distillation-v2, budget 1 | the only proposal times out; development remains at the valid zero-score baseline | no validated improvement | Process-equation sophistication is irrelevant if the candidate cannot finish within the evaluator budget. |
| Distillation-v2, normal budget 3 | one of three proposals is valid; selected development/held-out nominal `0.613/0.541` | robustness `0.0/0.0`; only `0.20/0.20` of shifted cases remain feasible | Nominal MESH feasibility and cost improvement do not transfer to operating shifts; two later rewrites time out. A post-hoc public-cost probe also finds that the selected design is unchanged when the capital/energy ranking reverses. |
| HartreeFockSCF-v2, budget 1 | development score approximately 1.0 from one valid proposal | development/held-out robustness approximately 1.0; geometry, representation and stability axes pass | One proposal synthesizes deterministic multistart/stability search for public finite-basis systems. This is known-algorithm synthesis, not feedback learning or new chemistry. |
| HartreeFockSCF-v2, normal budget 3 | step two/three selection scores differ by only `9.1e-15` | development robustness `1.000→0.707`, held-out robustness `0.902→1.000`; representation axes trade off | Strict positive-score incumbent replacement selects a scientifically different, non-dominating artifact below numerical materiality. Science search needs epsilon/tie and Pareto commit policies. |
| HartreeFockSCF-v2, strict open-loop budget 3 | every proposal uses the frozen baseline parent; offline best is approximately 1.0 | selected development/held-out robustness `0.707/0.902` | Open-loop near-ceiling success shows feedback was not necessary in this one calibration, but normal/blind are single-run, token/wall-time mismatched and Azure lacks a server-side seed. |
| RoomImpulseResponse-v2, budget 1 | selected development remains 0.0; valid rejected proposal lowers development utility `0.608→0.581` | the same proposal reaches held-out nominal score 0.419 and utility `0.669→0.699` | Development selection can reject a policy that transfers better to held-out rooms; one proposal does not establish a general tradeoff. |
| RoomImpulseResponse-v2, normal budget 3 | all three proposals fail at runtime by reading undocumented absorption keys | no validated improvement | Contract adherence remains a distinct bottleneck from scientific sophistication; repeated aggregate zero/failure feedback does not localize the wrong key. |
| RoomImpulseResponse-v2, strict open-loop budget 3 | frozen-parent offline best reaches development 0.754 | held-out nominal 0.742; development/held-out robustness `0.639/0.803`; all shifts remain geometry-feasible | The task retains graded headroom and transfer. The normal/open-loop contrast is single-run, Azure-random and slightly token/wall-time mismatched, so it is not evidence that removing feedback helps. |
| ReactionMechanism-v2, budget 1 | valid proposal remains at normalized mechanism 0.0 | held-out normalized mechanism 0.0 | A complex fitter spends the assay budget on an under-informative design and abstains everywhere. |
| ReactionMechanism-v2, budget 3 | all three proposals remain at 0.0 and are rejected | each performs one assay and abstains everywhere | More rewrite budget does not help when scalar zero feedback cannot localize whether experiment design, inference or refusal caused failure. |
| GravityInversion-v2, budget 1 | invalid callback unpacking; development remains 0.0 | no validated improvement | A physically sophisticated implementation can still fail the executable laboratory protocol. |
| GravityInversion-v2, budget 3 | development mechanism 0.000 → 0.994; field prediction 0.992 | held-out mechanism 0.767; held-out field prediction 0.988 | Known parametric inversion nearly saturates development, but field transfer does not establish the same internal geology. |
| OceanCurrentInversion-v2, budget 1 | invalid release geometry; development remains 0.0 | no validated improvement | The proposal places at least one initial drifter outside the documented public interior and fails closed. |
| OceanCurrentInversion-v2, budget 3 | one valid proposal uses two releases and the full 12-unit budget but scores 0.0; two later proposals misread the callback schema | zero in-library mechanism recovery and discovery coverage; correct refusal on all four unsupported worlds | Correct refusal does not compensate for refusing all seven supported worlds. The aggregate mechanism field alone would obscure this zero discovery coverage. |
| RadiativeTransferFit-v2, budget 1 | the valid proposal uses two views and all 18 measurement units but scores 0.0 | zero supported-world coverage/mechanism; correct refusal on all four unsupported worlds | A physically plausible full-budget policy can still be an always-refuse policy rather than a discovery policy. |
| RadiativeTransferFit-v2, budget 3 | all three proposals are valid and remain at 0.0; two use the full budget and one performs no experiment | every proposal has zero supported-world coverage/mechanism and zero false discovery | Protocol validity and conservative refusal do not establish scientific discovery; active measurement use must be reported alongside risk–coverage. |
| ConvectionDiffusionOpt-v2, truth-blind designs | one symmetric experiment scores 0.0; complementary two-experiment design scores 0.895605 | held-out joint 0.891509; held-out mechanism 0.659574; shifted robustness 0.890417; zero false discovery | Numerical rank alone is insufficient: a nearly singular midline experiment cannot identify the five coefficients, while a second off-axis intervention resolves the ambiguity. |
| ConvectionDiffusionOpt-v2, GPT-5.5 three conditions | all seven proposals fail to improve the zero baseline; four are invalid and three are valid | every valid proposal abstains on all seven supported worlds and all four unsupported worlds; supported discovery coverage is zero | Spending up to the full 12-unit experimental budget does not imply informative experiment design or mechanism recovery. The normal/open-loop contrast is single-run and non-causal. |
| SeismicWaveInversion-v2, truth-blind reference | development/held-out joint `0.997697/0.994382`; information near 1.0 | full supported coverage, zero false discovery; centered narrow acquisition has rank 5/9 and zero information | Active acquisition can make the layered mechanism identifiable, but this ray-theoretical laboratory remains a controlled on-ramp rather than field FWI. |
| SeismicWaveInversion-v2, GPT-5.5 formal runs | six valid proposals and one timeout; five valid proposals have information `0.974–1.0` | five valid proposals abstain on every supported world; the remaining budget-one proposal claims only one held-out supported world | High-information experiment geometry and full budget spend do not imply mechanism recovery or supported discovery coverage. |
| RankineCycleOpt-v2, budget 1 | development/held-out nominal `0.963561/0.957382`; nominal feasibility `1/1` | robustness `0/0`; shift feasibility `0.6/0.6` | One proposal synthesizes a strong nominal IF97 cycle archive but misses material-derating and combined-shift feasibility. |
| RankineCycleOpt-v2, normal budget 3 | first proposal reaches development/held-out nominal `1/1`; all three proposals valid | robustness `0/0`; shift feasibility `0.6/0.6` | The nominal ceiling is reached at step one and later scalar feedback does not expose or repair the sealed robustness failure in this trajectory. |
| RankineCycleOpt-v2, selection-blind budget 3 | frozen-baseline open-loop batch reaches offline-best development/held-out nominal `1/1` | robustness `0/0`; shift feasibility `0.6/0.6` | Nominal success does not require iterative score/parent feedback in this single run; unequal tokens/wall time and uncontrolled generation randomness preclude a feedback-effect claim. |
| RANSCalibration-v2, normal budget 3 | selected development/held-out nominal `0.356/0.428` | development/held-out robustness `0.127/0.299`; later proposal regresses to zero | A four-parameter channel-flow closure improves the nominal score, but coordinate shifts reduce both split scores. The matched-oracle-call selection-blind run remains at zero, but unequal tokens and unseeded generation preclude a feedback-effect claim. |
| GeneNetworkIntervention-v1, truth-blind reference | development/held-out joint `0.905/0.893`; supported coverage `1/1` | mechanism `0.862/0.800`; prediction `0.916/0.898`; unsupported refusal `1/1`; false discovery `0/0` | The synthetic task has recoverable mechanism, prediction and intervention headroom without requiring truth access. It is not real Perturb-seq or biological-discovery evidence. |
| GeneNetworkIntervention-v1, three GPT-5.5 conditions | all seven proposals remain at zero; six are invalid | four invalid experiments, two callback-schema failures and one valid proposal that refuses every supported world | The same score can represent protocol failure or scientifically empty over-refusal. Validity, supported-world coverage and conditional scientific quality must be reported as separate hurdles. |
| RNAInverseDesign-v1, proxy counterexample | target-pair compatibility `1.0` | target probability `3e-9`; normalized exact and shifted quality `0`; ensemble defect `0.335` | Satisfying every requested pair is necessary but not sufficient for a target to dominate the complete declared ensemble. |
| RNAInverseDesign-v1, normal budget 3 | development exact utility `0.239→0.507→0.720`; proxy compatibility remains `1.0` | held-out utility `0.500`; development/held-out robustness `0.712/0.487`; proxy false promotion `0.40/0.667` | Exact ensemble optimization can improve monotonically while a saturated pair proxy continues to over-promote sequences. |
| RNAInverseDesign-v1, selection-blind budget 3 | frozen-parent offline best development/held-out `0.894/0.986` | robustness `0.888/0.982`; target probability `0.432/0.806`; zero proxy false promotion | A strong open-loop sample exists, but four matched oracle calls do not make the contrast causal: the conditions differ by 12,169 tokens, 37 seconds and uncontrolled endpoint randomness. |

OPF's `robustness_score` combines security-constrained economic quality with overload penalties.
It is not a pure safety probability. The proportional baseline is feasible for every tested
outage but has robustness score zero because it provides no economic improvement above itself.
Accordingly, OPF results must report contingency feasibility, overload and security-constrained
cost separately.

## Repeated patterns and their current evidence limits

### 1. One-step success often measures algorithm synthesis, not scientific learning

GPT-5.5 writes recognizable multiplicative/Fedorov design, GRAPE, convex DC-OPF, window/null-
synthesis, deterministic multistart SCF and Sobol/Pareto cycle-design procedures
in one proposal. These results directly measure whether a model can instantiate a known method
inside a new executable contract. They do not establish that score feedback produced a new
scientific strategy. Budget-one saturation is therefore useful as an on-ramp calibration but
weak evidence for long-horizon autonomous research.

### 2. Visible optimization and scientific validity are different trajectories

Pendulum, gate synthesis, OPF, Truss, Antenna, NMR, BroadbandAbsorber and Rankine all separate a visible
development objective from an evaluator-only shift, contingency or held-out mechanism metric. OPF has the
largest numeric gap among the nominal-design calibrations, while NMR budget one falls from
0.428 development to 0.176 held-out mechanism/refusal despite similar reconstruction. In OPF,
nominal optimization reaches its reference while most complete line-outage scenarios fail. The
current observations indicate
that terminal best-score curves alone can hide a task-relevant validation loss. A general claim
requires repeated paired runs and hidden server-side instances.

### 3. Held-out nominal transfer does not imply robustness

Gate synthesis, OPF, Antenna, the absorber and Rankine calibrations reach strong nominal scores on
interleaved held-out instances.
Their sealed perturbation or contingency scores remain lower. Procedural held-out networks or
targets test policy transfer, whereas altered physics, hardware error and component failure test
robustness. Future task cards must specify both axes instead of using one generic validation
field.

Rankine makes the logical separation exact: budget one transfers nominally at `0.9636/0.9574`,
and both normal and selection-blind budget-three conditions reach `1.0/1.0` nominally, yet every
selected artifact has `0.0/0.0` robustness and only `0.6/0.6` shift feasibility. The same policy
works on unseen nominal operating regimes but fails material-derating and combined-shift envelopes.
Nominal world transfer is therefore not robustness transfer.

BroadbandAbsorber-v2 makes this distinction especially concrete. The strict open-loop selected
artifact has higher held-out nominal score than the normal selected artifact (`0.957/0.859`),
yet only `0.449` held-out robustness versus `0.858`. Its nominal geometry is valid, but one
manufacturing pattern leaves the hard panel envelope on two development instances and one
held-out instance. A transfer curve over nominal bands would therefore reverse the engineering
conclusion supplied by the manufacturing-shift curve.

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

OceanCurrentInversion-v2 exposes the complementary over-refusal failure. Its truth-blind
classical fit claims a mechanism in all seven in-library worlds, with mean in-library mechanism
quality 0.578, and correctly refuses all four unsupported worlds. GPT-5.5's only valid
non-baseline proposal instead spends the full observation budget and refuses every world. It
therefore has perfect unsupported-world refusal but zero in-library mechanism recovery and zero
discovery coverage. Because the aggregate `mechanism_score` includes credit for correct refusal,
discovery tasks must report in-library recovery and risk–coverage alongside the aggregate score.

HartreeFockSCF-v2 adds a complementary distinction even before model calibration: satisfying
the RHF equations is not enough if the stationary determinant is internally unstable. Its valid
single-start DIIS baseline has development/held-out stability rates `0.75/0.667`; on the hard H8
and held-out H4 rings, stable multistart witnesses lower the energy by `0.0375/0.0619 Ha` and
change the minimum occupied--virtual curvature from `-0.294/-0.511` to `+0.299/+0.095`.
Scientific optimization curves must therefore retain validity, objective value, physical or
variational stability and representation/geometry transfer as separate axes.

RNAInverseDesign adds an ensemble analogue. A sequence can make all target pairs canonical and
still assign the complete target only `3e-9` Boltzmann probability because competing structures
dominate. In the normal budget-three trajectory, pair compatibility is saturated at every
accepted step while exact utility rises from `0.239` to `0.720` and held-out target probability
from `0.0010` to `0.187`. Pair compatibility is therefore a useful construction constraint, not
an adequate success metric; target probability, ensemble defect, MFE agreement and shifted
transfer remain separate. This result is exact only for the declared simplified pair-stack-loop
model and is not evidence about full Turner thermodynamics or experimental RNA function.

The model calibration sharpens this point. A budget-one proposal reaches approximately unit
nominal and sealed scores by synthesizing a known deterministic multistart method. In the normal
budget-three trajectory, the accepted step-two and step-three selection scores differ by only
`9.10e-15`, but development robustness falls by 0.293 while held-out robustness rises by 0.098;
development representation invariance falls by 0.125 while held-out invariance rises by 0.167.
Neither artifact dominates the other. Replaying endpoint selection with `epsilon=1e-12` keeps
step two instead of step three. This replay does not reconstruct the counterfactual proposal
trajectory, but it proves that strict floating-point `>` is an inadequate commit rule for this
science vector.

The conventional single-start baseline also exposes an execution-environment issue. Under the
authoritative secure one-thread BLAS environment its held-out shifted score is about 0.667;
under explicit 2/4/8-thread direct execution it is approximately 1.0 because the hard shifted H4
case enters a different SCF basin. Secure and explicit one-thread direct execution agree across
all scalar/sealed axes within the registered tolerances. The secure path remains authoritative,
while thread sensitivity must be retained as a numerical-stability diagnostic rather than hidden
by checking nominal raw score alone.

RadiativeTransferFit-v2 reproduces this failure without a protocol confound. Its truth-blind
two-view nonlinear fit claims all seven supported atmospheres, reaches mean supported mechanism
quality 0.561 and held-out radiance prediction 0.812, and correctly refuses all four unsupported
worlds. By contrast, every one of seven GPT-5.5 proposals across budget-one, normal budget-three
and strict open-loop budget-three is executable and schema-valid, yet all seven refuse every
supported atmosphere. Five proposals use the full 18-unit measurement budget and two perform no
experiment, but both strategies yield zero discovery coverage and zero supported-world mechanism
recovery. Thus protocol validity, experiment-budget use, refusal specificity and discovery
coverage are four distinct quantities; none can stand in for the others.

ConvectionDiffusionOpt-v2 adds a controlled identifiability counterexample. A symmetric midline
experiment is numerically rank five, yet its Jacobian condition number ranges from `1.0e5` to
`4.0e8` and the truth-blind one-experiment mechanism score is effectively zero. Adding one
off-axis experiment raises development/held-out joint quality to `0.896/0.892`, with
held-out mechanism `0.660`, shifted robustness `0.890`, full supported coverage and zero false
discovery. By contrast, the three valid GPT-5.5 proposals across the budget-one, normal
budget-three and strict open-loop conditions abstain on all eleven worlds. One of them spends the
full 12-unit budget on two experiments. Thus experiment count, spend, numerical rank,
conditioning, supported-world coverage and recovered mechanism must all be reported separately.

EnergyBalanceModel-v2 supplies the sharpest prediction-versus-mechanism counterexample so far.
The under-informative short classical design reaches development/held-out prediction
`0.968/0.990` while mechanism quality is only `0.0039/0.0` and false-discovery rates are
`0.20/0.25`. The selected strict open-loop model program improves fixed-world prediction to
`0.977/0.994`, but held-out mechanism remains 0.282 and it confidently assigns the public
two-layer model to state-dependent-feedback and three-layer-ocean worlds. On twelve post-hoc
procedural worlds it predicts supported responses at 0.995 while supported mechanism quality is
0.370 and unsupported false discovery is 2/3. Those probes were selected after the runs and are
not preregistered hidden validation, but they show why response fit, parameter recovery,
model-class adequacy and refusal must be separate curves.

### 5. Protocol validity, scientific coverage and conditional quality are sequential hurdles

GeneNetworkIntervention makes the hurdle structure explicit. Across budget one, normal budget
three and selection-blind budget three, six of seven proposals fail before scientific quality can
be interpreted: four request invalid experiments and two violate the callback schema. The only
valid proposal refuses every supported world. It therefore passes the executable protocol and
avoids false discoveries, but has zero supported-world coverage and no mechanism, prediction or
intervention result to assess. A zero endpoint score alone cannot distinguish these states.

The same separation appears in RadiativeTransferFit-v2 and ConvectionDiffusionOpt-v2, where valid
full-budget programs can still refuse all supported worlds. Scientific-agent curves should first
report protocol validity and first-valid incidence, then supported coverage and calibrated
refusal, and finally mechanism, prediction, decision utility and transfer conditional on making a
warranted claim. A joint success curve may be reported after these components, but it cannot
replace them. The current evidence is task calibration from single runs and does not estimate a
population success probability.

### 6. Feedback cannot optimize information that selection never receives

In the OPF budget-three run, later proposals receive only nominal score and reproduce the same
N-1 failure. Pendulum's visible improvement is accompanied by flat shifted robustness, while
ActiveLawDiscovery retains its misspecification errors. Rankine reaches the nominal ceiling in
the first budget-three proposal in both normal and frozen-parent open-loop conditions, while the
sealed robustness axis remains zero throughout. NMR selection does include a normalized
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

OceanCurrentInversion-v2 adds an interface-level bottleneck. Five of six model proposals fail
the public experiment or callback contract, and the only valid proposal receives the same zero
selection score as always abstaining. Normal and selection-blind budget-three conditions both
select the baseline, so their zero score contrast contains no information about a feedback
effect. The useful next treatment is factorized, label-blind feedback that distinguishes invalid
experiment geometry, callback parsing, in-library coverage and model-check residuals without
revealing held-out mechanisms or world labels.

RadiativeTransferFit-v2 provides the cleaner zero-plateau control: all seven proposals satisfy
the executable protocol, but each returns the canonical refusal on all supported worlds. Normal
and strict open-loop budget-three conditions use the same oracle-call budget and both stay at
zero; normal uses 1,122 more tokens, neither condition changes its parent, and the endpoint has
no server-side seed. The result therefore contains no feedback-effect estimate. It does show
that factorized label-blind feedback must distinguish experiment coverage, supported-world claim
coverage, residual/model-check evidence and false-discovery risk. A single zero cannot tell the
agent whether to measure more, fit differently, or lower an over-conservative abstention threshold.

ConvectionDiffusionOpt-v2 combines both failure types. Four of seven proposals fail the callback
or runtime contract. The other three are valid, including a full-budget two-experiment policy,
but all retain the always-abstain scientific outcome. Normal and strict open-loop budget-three
conditions use four oracle calls and `16,833/16,982` tokens, neither changes its parent, and Azure
has no server-side generation seed. Their equal zero score therefore contains no feedback-effect
information. A useful feedback treatment must distinguish experiment validity, conditioning or
information content, supported-world claim coverage and model-inadequacy evidence without
revealing hidden parameters or world labels.

EnergyBalanceModel-v2 adds both an interface plateau and an experiment-design bottleneck. All
four normal proposals fail the return-artifact contract, whereas a strict open-loop batch happens
to contain two valid programs and one nonzero selection. Normal uses 14,181 tokens and open-loop
15,297, both use four oracle calls, and the endpoint exposes no server-side generation seed. The
`0.000` versus `0.618` contrast therefore cannot identify a feedback effect. The scientifically
useful observation is that the nonzero program still combines high predictive fit with false
model claims, while a truth-blind long multiscale forcing design avoids those errors. Future
treatments must factor protocol repair, temporal experiment design, parameter estimation and
model checking instead of interpreting one aggregate score as the source of failure.

### 7. Contract completeness must precede headroom claims

The superseded Pendulum diagnostic failed because the public contract omitted the evaluator's
exact equations. Disclosing the equations changed budget-one performance from no improvement to
0.796874. A benchmark should hide instances, perturbations and validation outcomes, but not
equations or observations required to define the stated problem. Apparent difficulty caused by
an underspecified contract is evaluator error, not scientific headroom.

### 8. A single science score would erase the observed failure modes

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
7. At equal charged budget, temporally multiscale or adaptive experiments will improve mechanism
   recovery and model-mismatch refusal more than short experiments even when their response-
   prediction scores are similar.
8. At equal experiment count and cost, complementary off-axis or intervention-rich designs will
   improve mechanism recovery over merely full-rank but ill-conditioned designs; budget use and
   numerical rank alone will not predict discovery success.

Tests 1--3, 7 and 8 require at least ten paired seeds on the focused science subset. All comparisons must
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

### LowThrustTransfer-v2 numerical-versus-scientific diagnostic

LowThrustTransfer-v2 makes numerical fidelity an explicit axis rather than silently folding it
into an optimization score. Its six missions cover orbit raising, lowering, eccentricity,
plane-change and combined transfers. A public-input-only 28-parameter Gauss--Newton guidance
policy reaches development/held-out utility `0.711433/0.719404`, shifted robustness
`0.681712/0.659987`, and full nominal terminal feasibility. One of six held-out shifted cases
misses the terminal-feasibility gate, even though aggregate held-out utility remains high.

The 1800 s production RK4 trajectory differs from a 900 s refinement by at most `0.042274` of a
public terminal tolerance. The refined MEE+J2 propagation differs from an independently coded
Cartesian DOP853 path by at most `0.002876` terminal tolerances and `0.000223 kg`. These checks
bound two different threats: discretization error inside the production model and disagreement
between coordinate/formulation implementations. Neither proves real mission fidelity; third
bodies, drag, eclipse, power, thermal and attitude constraints remain absent.

Across the three GPT-5.5 conditions, all seven proposed programs are valid artifacts and spend
mean development delta-v between 737 and 958 m/s, but no proposal makes any nominal or shifted
mission terminal-feasible. Development utility ranges from `2.1e-6` to `0.007736`, while the
largest held-out utility is `5.8e-9`. Budget-one happens to match the Gauss--Newton policy's tiny
sealed phase diagnostic (`8.49e-7` versus `8.55e-7`) while missing every first-five-MEE terminal
tolerance; phase is not part of that scored terminal state and cannot substitute for it.

The normal budget-three run accepts only its first proposal and selects 0.005079. The same-local-
seed-label strict open-loop batch has offline best 0.005491, with every parent frozen at the
baseline. Normal uses 18,491 tokens versus 13,366, and the endpoint supplies no server-side seed,
so the difference is not a feedback-effect estimate. It instead confirms that proposal diversity
alone can exceed one short iterative trajectory while both remain scientifically infeasible.

The resulting reporting rule is five-way: integration/model-consistency error, nominal utility,
terminal feasibility, held-out mission transfer and physical execution robustness must remain
separate. Otherwise an apparent optimization frontier can be an integrator frontier, and a high
fuel/accuracy aggregate can conceal an infeasible shifted mission. These are single-run
controlled-task calibrations, not population performance, causal feedback, global optimality,
flight validation or autonomous discovery.

### LidDrivenCavity-v2 solver synthesis and ceiling diagnostic

LidDrivenCavity-v2 replaces a single sparse profile score with full streamfunction and vorticity
fields over six Reynolds/grid cases and two refinement calls. Public feasibility requires
relative Poisson, transport and wall residuals below `0.03`, `0.05` and `0.05`. The trusted
continuation fields score above 0.99999999 on development and held-out cases. Their Ghia Re=100
centerline RMSE is `0.009789` for horizontal velocity and `0.012070` for vertical velocity. An
attenuated reference has ungated development utility 0.857026 but scores zero because its
transport residual violates the public gate. This shortcut test is why field similarity alone
cannot determine CFD validity.

The budget-one proposal implements a DST Poisson solver, continuation and Krylov correction and
scores 0.999999990. Its held-out and two grid-refinement scores exceed 0.99999995. The independent
normal budget-three run accepts all three proposals and rises from 0.869915 to 0.898062. A strict
open-loop batch with every parent fixed at the weak baseline produces a
0.999999990 solver at step two. Normal and open-loop use the same four oracle calls, while normal
uses 19,483 tokens and open-loop 14,288. The endpoint has no server-side seed, so the
`-0.101938` normal-minus-open-loop score difference is not a feedback-effect estimate.

Three post-hoc probes at `(Re,N)=(137,27),(245,39),(375,45)` test combinations absent from the
eight benchmark calls. The budget-one and open-loop programs are physics-feasible on all three
and retain minimum full-field similarity 0.999999951 to the same discrete reference. The normal
selected program also passes all three public physics gates, with minimum similarity 0.844965.
These probes were selected after the model runs and use the same second-order model, so they
support general solver behavior within that model but are not preregistered hidden, higher-order
or experimental validation.

The scientific implication is about benchmark placement. A model that reaches the numerical
ceiling from the public equations in one proposal leaves little room to measure iterative
optimization. Cavity-v2 is useful as a CFD algorithm synthesis on-ramp and as a test of full-field
physics gates. A headline task requires procedurally held-out geometries or boundary conditions,
higher Reynolds regimes, independent high-order references, solver-cost tradeoffs or
multifidelity validation. None of these runs supports a new fluid mechanism or autonomous
scientific discovery.

### EnergyBalanceModel-v2 experiment-design and mechanism diagnostic

EnergyBalanceModel-v2 replaces the quarantined unstable diffusion implementation with a public
five-parameter two-layer energy-balance model, charged forcing experiments and surface-
temperature plus top-of-atmosphere observations. The eleven fixed worlds contain seven
in-library climates, two null responses, state-dependent feedback and a third ocean reservoir.
A fixed eight-unit, 160-year multiscale forcing design has rank-five sensitivity in every
supported world, with condition numbers 11.5--17.7. Independent RK4 and matrix-exponential
checks agree, and all four unsupported worlds are resolvably outside the public family under the
benchmark noise model.

The truth-blind long-design fit reaches development/held-out mechanism `0.808913/0.941773`,
prediction `0.998981/0.999242`, full supported coverage and zero false discovery. A short-design
fit reaches prediction `0.9676/0.9897` but mechanism only `0.003909/0.0` and falsely promotes one
misspecified world in each split. This is a task-calibration result: it shows that the benchmark
can distinguish informative experiment design from mere response interpolation, not that the
particular long forcing is optimal or realistic for an Earth-system experiment.

The GPT-5.5 budget-one proposal and all three normal budget-three proposals fail the return-
artifact contract and remain at zero. In the same-local-seed-label strict open-loop diagnostic,
the third proposal reaches development/held-out mechanism `0.617931/0.282383` and prediction
`0.976686/0.994285`, with full supported coverage but unsupported refusal only 0.5 in each split.
It makes high-confidence public-model claims for both feedback drift and the third ocean layer.
Normal and open-loop use 14,181/15,297 tokens; Azure supplies no server-side seed, so the result
supports no claim that removing feedback helps.

Twelve new procedural worlds were evaluated only after the model runs. On six supported worlds,
the open-loop program retains mean prediction 0.994882 but mean mechanism quality falls to
0.370445, with a minimum of 0.075278. It refuses both nulls but falsely claims mechanisms in all
four feedback-drift and three-layer worlds, for unsupported false discovery 2/3. These are useful
post-hoc transfer probes, not preregistered hidden tests or independent climate validation.

The reporting consequence is explicit: a climate-response discovery plot needs separate
experiment cost/horizon, prediction, parameter/mechanism, supported coverage, model-check
residual, confidence and false-discovery/refusal curves. A response curve alone would rate the
short design and the misspecified model claims as successful. This synthetic global-mean task
does not estimate Earth's climate sensitivity or establish autonomous scientific discovery.

## Consequences for expansion to approximately 50 tasks

Every new or rebuilt task must pass the following gate before it counts toward the target:

- a scientifically recognizable artifact and cited workflow;
- a complete public problem contract and a valid weak baseline;
- an independent numerical, analytic or exact reference plus invariant tests;
- procedural development and server-held instances rather than a fixed public truth;
- separate nominal, held-out and shifted/high-fidelity metrics where applicable;
- explicit mechanism and refusal outputs for discovery tasks;
- finite-output rejection, secure isolation, deterministic replay and metric sealing;
- a fixed label-blind failure taxonomy so candidate exception text cannot carry observations
  between hidden worlds or into later proposal prompts;
- classical and domain baselines, followed by GPT-5.5 budget-one headroom screening; and
- retention as an on-ramp, not a headline task, if a standard method reliably saturates it.

SeismicWaveInversion-v2 adds the same distinction in a wave-propagation setting. Its truth-blind
NMO/Dix plus public-waveform fit reaches development/held-out joint quality `0.997697/0.994382`,
but this near-ceiling classical result follows only after a complementary two-acquisition design.
The centered narrow-offset experiment has numerical rank five for nine parameters and zero
information score, whereas the reference design is rank nine with worst condition number
`246.34`. Null and resolvable four-layer worlds are correctly refused; the minimum misspecified
reduced chi-square is `33.10`. Thus good acquired-waveform fit, parameter identifiability,
far-offset prediction, model-class adequacy and geological interpretation remain separate axes.
The current synthetic primary-reflection laboratory is an active-acquisition/model-checking
on-ramp, not field FWI or autonomous geological discovery.

The present inventory contains 39 internally admissible certified or candidate packages: seven
certified and 32 candidate, with 14 quarantined. The remaining gap is approximately 11 tasks.
Expansion should use procedural families spanning
design, inverse problems, control, multifidelity validation, mechanism discovery and exact
mathematical construction rather than cloning one scalar optimization template across domains.
