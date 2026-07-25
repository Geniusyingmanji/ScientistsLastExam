# Frontier-Science

Frontier-Science is a research prototype for **cross-domain, executable,
budget-constrained scientific generative optimization**. An agent edits one runnable
program; a frozen deterministic oracle scores each candidate, and the benchmark measures
both the best feasible artifact and its cost-aware discovery trajectory.

This repository is inspired by
[Frontier-Engineering](https://github.com/EinsiaLab/Frontier-Engineering). It is not the
text-question benchmark named *FrontierScience* in
[arXiv:2601.21165](https://arxiv.org/abs/2601.21165).

> Scope: an improved simulator/verifier score demonstrates scientific optimization. It is
> not, by itself, autonomous scientific discovery. Mechanism recovery, hidden-shift or
> physical validation, and claim–evidence provenance are separate future gates.

## Current status

The repository contains **59 task packages in 55 metadata domains**:

- **7 certified core tasks**: Lennard–Jones clusters, spin glass, Poisson solver,
  matrix-multiplication rank, Cap Set, circle packing, and multilayer thin films.
- **40 candidate tasks** pending scientific certification, including intervention-based causal
  and active dynamical-law laboratories whose prediction and mechanism metrics are reported
  separately, a multi-spectrum NMR peak-mechanism/refusal task, and a multi-fidelity
  heat-exchanger Pareto-design task, a full-field lid-driven-cavity solver, active
  climate-response identification with explicit model-mismatch refusal, and a robust
  broadband acoustic-absorber design task, and a robust mixed-integer equilibrium-stage
  distillation design task, a multi-system stable finite-basis Hartree–Fock task, an IAPWS-IF97
  single-reheat Pareto-cycle task, robust room
  acoustics design, active convection--diffusion identification/design, active layered
  reflection acquisition/inversion with explicit model-inadequacy refusal, constrained RNA
  inverse design with exact ensemble scoring and proxy-false-promotion diagnostics, and a
  real-data protein-stability assay-allocation replay, and a real-data electrolyte-conductivity
  assay-allocation replay with discovery and untouched-repeat confirmation reported separately,
  active demographic-SFS inference with finite-information and model-refusal diagnostics, and
  cost-conditioned sampling-calorimeter design with sealed fabrication margins, and prospective
  evidence synthesis with registry screening, participant-lineage de-duplication, selective-report
  detection, heterogeneous inference, pre-result commitment and fresh simulated confirmation,
  budget-conditioned finite-absorption tandem-photovoltaic design with held-out spectra and
  sealed thermal, process and optical perturbations, and a stateful catalyst-deactivation
  laboratory with instrument drift, finite coupons, irreversible reactions, out-of-order batch
  completion, retry lineage, model refusal and a sealed fresh-batch operating decision, and a
  raw-I/Q quartz-crystal-microbalance pipeline that separates complex calibration, BVD resonance
  extraction, rigid-film inference, physical-model mismatch, instrument faults and a sealed stop
  decision.
- **12 quarantined tasks** retain reproduced scientific-oracle, identifiability, provenance or
  shortcut defects.
  Quarantined packages remain inventory artifacts but are not admissible benchmark tasks.

The default CLI exposes only the certified core. `--all` explicitly shows the full
inventory. Certification status is not a difficulty claim: the inventory metadata contains
50 `hard` and 9 `flagship` packages, but only certified tasks are benchmark-admissible.

All candidate code runs in a networkless Bubblewrap sandbox with read-only mounts, resource
and process limits, and a typed JSON RPC boundary. The trusted parent alone imports the
oracle and validates metrics. Multi-world evaluators can explicitly reset the candidate
session at scientific-world boundaries; the active multi-world inverse tasks do so to prevent
module, imported-package or private-tmpfs state from revealing hidden world order. Candidate-
controlled exception text is reduced to a fixed label-blind failure taxonomy before it can enter
search feedback, preventing observations from being carried between worlds through exceptions.
The current audit reports:

- Trusted certification v53 and security v37 bind clean revision `e516d56`. Certification covers
  `7/40/12` over 59 packages with no missing manifest records, orphaned records or task-level
  admission issues; it retains one known duplicate-oracle group containing five quarantined
  packages. Security passes 18/18 adversarial tests. The 59×2 baseline v42 reports 59/59
  deterministic, valid and fail-closed tasks with zero infrastructure failures. The latest
  full-suite v10 binds clean revision `e516d56` and passes 438/438 tests in 1272.433 seconds.
  Cross-task summary v28 (SHA-256
  `940495a9cb64e717e6395b3cb7e4ec1d8d5b8d13232618a05c43e20f68edded4`) binds clean
  revision `577e66a` and contains 69 normal single-run conditions over 35 tasks.
- Current source manifest: 7 certified / 40 candidate / 12 quarantined. ProteinStabilityDesign
  rebuilds 2,756 reliable double-mutant records across five
  development and three held-out domains from hash-bound ProteinGym v1.3/Tsuboyama sources.
  It separates additive proxy, charged assay, diversity, top-decile, trypsin, chymotrypsin,
  uncertainty and held-out metrics. Source reconstruction, secure baseline and shortcut audits
  pass, and all seven GPT-5.5 proposals are executable. It was counted among 44 internally
  admissible tasks but remains an offline public-data candidate, not prospective protein
  discovery. D-optimal design, quantum
  gate synthesis, DC optimal power flow, truss sizing, antenna synthesis and NMR peak fitting have been rebuilt with separate sealed
  validation or robustness metrics and re-admitted as candidates. HeatExchanger-v2 additionally
  separates a public constant-property proxy from a sealed segmented temperature-dependent
  oracle and scores cost-versus-duty Pareto archives, held-out fluids, false promotion and
  fouling/manufacturing/blockage shifts. It remains a correlation-based optimization task, not
  experimental validation. A proxy-only classical archive reaches 0.997 development exact
  hypervolume but has only 0.948 exact feasibility, 0.094 false-promotion rate and 0.942 sealed
  robustness. An independent GPT-5.5 budget-three trajectory improves 0.000→0.008→0.126 while
  its final proxy score is 0.173 and two of four development regimes remain at zero; a strict
  open-loop diagnostic reaches 0.294 but has 0.174 false promotion and is not token- or
  model-randomness-matched. ReactionMechanismFitting-v2 adds active partial-species assays, twelve possible
  reactions, null/model-mismatch refusal and held-out topologies: its truth-blind classical fit
  reaches 0.482/0.404 development/held-out mechanism quality and 0.860 development interpolation,
  but falsely reports an in-library mechanism in half of unsupported worlds. Independent GPT-5.5
  budget-one and normal budget-three runs remain at zero because every proposal performs only one
  or two under-informative assays and abstains. A same-local-identifier strict open-loop batch
  contains a 0.343 development/0.363 held-out mechanism solution, but still falsely claims a
  mechanism in half of unsupported worlds. The single-run, non-token-matched conditions have no
  server-side random seed and support no causal feedback conclusion.
  GravityInversion-v2 replaces two duplicate noise-dominated grids with active multi-height
  surveys and seven procedural signed-body topologies. Its truth-blind BIC fit reaches
  0.786/0.775 development/held-out mechanism and approximately 0.99 sealed field prediction;
  the gap on one topology illustrates that external-field fit does not uniquely establish an
  internal geological mechanism. GPT-5.5 budget one fails the callback dictionary protocol;
  an independent budget-three run instead reaches 0.994 development and 0.767 held-out
  mechanism, with one topology at 0.975 field prediction but only 0.346 body mechanism. It is
  therefore a valid algorithm-synthesis on-ramp, not a long-horizon headline task.
  OceanCurrentInversion-v2 replaces a sub-metre-signal fixed raster with charged active
  drifter deployment over thirty public divergence-free, time-dependent streamfunction modes,
  plus null and out-of-library refusal. Its truth-blind two-release sparse fit scores
  0.707/0.406 on development/held-out mechanism quality with zero false discovery; all seven
  in-library trajectory Jacobians are full rank, and the weakest best-of-four-start bounded
  nonlinear public-library fit to an out-of-library world has reduced chi-square 10.53 versus
  the refusal threshold 3.0; all four starts converge to the same score within `4e-10`.
  Field/drifter prediction and mechanism remain separate. GPT-5.5 budget one and normal budget
  three both remain at zero. The only valid non-baseline proposal spends the full 12-unit budget
  but refuses every in-library world, giving zero in-library discovery coverage and mechanism
  recovery; the other normal proposals fail the public experiment/callback protocol. A
  same-seed-label selection-blind batch also remains at zero, with all proposals failing the
  callback schema. These single runs diagnose protocol following and sparse credit assignment,
  not a causal feedback effect or field-oceanography capability.
  RankineCycleOpt-v2 uses a self-contained IAPWS-IF97 single-reheat cycle over four development
  and two held-out regimes. GPT-5.5 budget one reaches nominal development/held-out
  `0.9636/0.9574`; normal and strict selection-blind budget three both reach `1.0/1.0`, yet all
  selected artifacts retain robustness `0.0/0.0` and shift feasibility `0.6/0.6`. This is strong
  nominal algorithm synthesis with a sealed material/combined-shift failure. Single, token/wall-
  time-mismatched runs with no server-side generation seed support neither a feedback-effect nor
  plant-validation claim.
  RadiativeTransferFit-v2 replaces an underdetermined fixed-profile retrieval with charged
  channel/view selection over a public five-parameter thermal-emission family. All seven
  supported worlds have full-rank sounding sensitivities with worst condition number 28; a
  truth-blind two-view fit reaches 0.614/0.491 development/held-out mechanism and 0.855/0.812
  radiance prediction while correctly refusing null, extra-absorber and cloud worlds. Across
  budget-one, normal budget-three and strict open-loop budget-three calibrations, all seven
  GPT-5.5 proposals are protocol-valid, but every proposal refuses every supported atmosphere.
  Their perfect unsupported-world refusal and zero false-discovery rate therefore coexist with
  zero discovery coverage and zero supported-world mechanism recovery. These single runs are
  synthetic task calibration, not a causal feedback, satellite-retrieval or discovery claim.
  LowThrustTransfer-v2 replaces a single unstable 30-day Euler trajectory and unsupported fuel
  anchors with six raising, lowering, eccentricity and plane-change MEE+J2 transfers. A compact
  28-parameter harmonic guidance artifact is checked against a continuous thrust bound,
  rocket-equation mass depletion, terminal feasibility, held-out missions and sealed execution
  shifts. A public-input-only Gauss--Newton calibration reaches `0.711/0.719`
  development/held-out utility and `0.682/0.660` shifted robustness with full nominal terminal
  feasibility. The production propagator agrees with an independent Cartesian DOP853 path
  within `0.00288` of a public terminal tolerance. Across budget-one, normal budget-three and
  strict open-loop budget-three GPT-5.5 calibrations, all seven generated artifacts are valid,
  but none reaches nominal or shifted terminal feasibility. Their development scores span
  `2.1e-6–0.00774`, and the maximum held-out score is only `5.8e-9`, versus `0.711/0.719` for
  the public Gauss--Newton policy. The normal and open-loop best scores are `0.00508/0.00549`;
  this one-run, non-token-matched contrast is not a feedback effect. Server-held missions and
  independent review remain pending.
  LidDrivenCavity-v2 replaces sparse Re=100 centerline matching with six Reynolds/grid cases,
  two refinement calls, full streamfunction-vorticity fields and hard Poisson, transport and
  wall-residual gates. Its trusted continuation reference agrees with Ghia Re=100 profiles at
  velocity RMSE `0.00979/0.01207`; a near-reference field with 0.857 ungated similarity utility
  scores zero when it violates transport feasibility. GPT-5.5 reaches `0.99999999` at budget
  one. An independent normal budget-three trajectory rises `0.8699→0.8949→0.8981`, while a
  strict open-loop batch produces another `0.99999999` solver. The budget-one and
  open-loop programs remain above `0.99999995` full-field similarity on three post-hoc Re/grid
  probes; the normal program is feasible on all three but has minimum similarity 0.845. These
  runs support general numerical solver synthesis within the same discrete model and also expose
  an on-ramp with a ceiling risk. They do not support a feedback, continuum CFD or discovery claim.
  EnergyBalanceModel-v2 replaces an unstable explicit-diffusion toy with a charged active
  two-layer climate-response laboratory. Candidates choose at most eight budget units of forcing
  experiments and infer five response parameters or refuse a null, state-dependent-feedback or
  three-layer-ocean world. A truth-blind long multiscale design reaches `0.809/0.942`
  development/held-out mechanism quality, approximately `0.999/0.999` response prediction,
  full supported-world coverage and zero false discovery. A short under-informative design still
  predicts at `0.968/0.990` but has only `0.0039/0.0` mechanism quality and makes false model
  claims. GPT-5.5 budget one and normal budget three stay at zero because all four proposals are
  invalid return artifacts. A strict open-loop batch contains a valid `0.618/0.282`
  development/held-out mechanism solution with `0.977/0.994` prediction, but false-discovery
  rates are `0.20/0.25`; on twelve post-hoc procedural worlds it predicts supported responses at
  0.995 while mechanism quality falls to 0.370 and it falsely claims the public model in four of
  six unsupported worlds. Those post-hoc worlds are neither preregistered hidden tests nor
  independent Earth-system validation, and the one-run conditions support no feedback claim.
  BroadbandAbsorber-v2 replaces a fail-open single-resonator proxy with six variable-band,
  variable-cell-count panel instances, a Stinson dynamic-density/finite-cavity distributed
  model, a separately reported low-order public proxy, and sealed angle, air-property and
  manufacturing shifts. The budget-one GPT-5.5 proposal times out and leaves score zero. In an
  independent normal budget-three run, the first proposal reaches development/held-out nominal
  scores `0.9148/0.8588` and sealed robustness `0.9118/0.8583`; two later rewrites time out. A
  same-local-seed-label strict open-loop batch reaches nominal `0.9173/0.9574` but robustness
  only `0.4519/0.4491`, because manufacturing perturbations leave the hard panel envelope in
  three split-instance cases. Normal/open-loop use 24,179/15,152 tokens and Azure exposes no
  server-side generation seed, so this one-run contrast is descriptive, not a feedback effect.
  DistillationColumnDesign-v2 replaces fixed 0.99 product purity and missing material balances
  with six varying binary separations, exact tray/feed-stage decisions and closed
  total-condenser/feed-stage/partial-reboiler light-component balances. Fixed-seed nominal
  witnesses cost 35--47% of the conservative baseline but usually fail sealed operation;
  robust witnesses cost 37--52%, retain all five volatility/feed/quality/reflux shifts and score
  0.963/0.903 nominal development/held-out plus 1.0/1.0 robustness. Independent bounded
  least-squares MESH solves agree below `1.1e-11` on product composition. This validates the
  reduced-order task, not a rate-based process model or plant design. GPT-5.5 budget one times
  out. In the normal budget-three run, its only valid proposal reaches nominal
  development/held-out `0.6131/0.5407`, yet only the richer-feed shift remains feasible:
  shift feasibility is `0.20/0.20` and robustness is zero. The other six proposals across all
  three conditions time out. A post-hoc public-cost probe reverses the ordering between the
  selected 8-stage/high-reflux design and a feasible 13-stage/low-reflux witness, but the
  selected program returns the same design because it does not read the public tray/vapour cost
  fields. Thus the observed success is nominal feasibility/cost reduction, not demonstrated
  mastery of the capital--energy tradeoff or robust process design.
  HartreeFockSCF-v2 replaces an inconsistent two-coefficient H2 toy with seven reproducible
  STO-3G/6-31G finite-basis Hamiltonians, a valid zero-score single-start DIIS policy, stable
  fixed-seed multistart witnesses, a different-size held-out symmetry-breaking ring, freshly
  generated 3% geometry shifts, AO-representation invariance and occupied--virtual stability.
  The conventional policy is self-consistent but internally unstable on development H8 and
  held-out H4 rings, lying 0.0375 and 0.0619 Ha above stable witnesses. Independent NumPy/SciPy
  equations reproduce all frozen energies within `4.3e-14` Ha, and the data archive is
  byte-reproducible. GPT-5.5 reaches approximately unit nominal and sealed scores in one proposal
  through deterministic multistart/stability search. In a normal budget-three trajectory, a
  `9.1e-15` selection-score increase changes development/held-out robustness from
  `1.000/0.902` to `0.707/1.000`; a `1e-12` materiality replay keeps the earlier non-dominated
  artifact. A strict open-loop batch also reaches approximately unit score, so these single,
  token-mismatched runs do not show feedback necessity. The weak single-start baseline's held-out
  geometry score is BLAS-thread sensitive (`0.667` in the authoritative secure one-thread path
  versus approximately `1.0` at 2/4/8 threads), while secure and explicit one-thread execution
  agree across all scalar/sealed axes. Independent quantum-chemistry review remains pending.
  GPT-5.5 reaches nominal OPF score 1.0
  at budget one while sealed N-1 robustness is only 0.031 on development and approximately
  zero on held-out networks. On Truss-v2, a separate budget-three run improves development
  `0.000 -> 0.416 -> 0.548 -> 0.611`, while its final accepted step increases held-out nominal
  transfer and decreases sealed held-out robustness; these are calibration trajectories, not
  multi-seed feedback claims. On Antenna-v2, budget one nearly saturates nominal pattern quality,
  while a budget-three nominal curve `0.845 -> 0.993 -> 1.000` coincides with decreasing sealed
  hardware robustness `0.705 -> 0.636 -> 0.576`. NMR-v2 separates peak-mechanism recovery from
  reconstruction and refusal: a truth-blind classical fit reconstructs clean signals at
  `0.887/0.851` on development/held-out spectra, but scores only `0.271/0.146` on normalized
  mechanism/refusal quality and falsely fits the development phase-distorted spectrum. GPT-5.5
  reaches `0.428/0.176` development/held-out mechanism/refusal at budget one; at budget three,
  the two later rewrites score lower and falsely fit every unsupported spectrum.
  ConvectionDiffusionOpt-v2 adds a charged anisotropic transport laboratory: a truth-blind
  complementary two-experiment policy reaches development/held-out joint quality
  `0.896/0.892` and shifted robustness `0.894/0.890`, whereas one nearly singular symmetric
  experiment scores approximately zero. Across budget-one, normal budget-three and strict
  open-loop GPT-5.5 calibration, four proposals fail the executable contract and all three valid
  proposals abstain on every supported world—even one that spends all 12 units on two
  experiments. This separates experiment spend, identifiability, mechanism recovery and
  conservative refusal; the single-run normal/open-loop contrast is not causal evidence.
  SeismicWaveInversion-v2 replaces an evidence-free fixed velocity guess with charged active
  CMP/offset/frequency acquisition over three-layer, null and resolvable four-layer worlds. A
  truth-blind NMO/Dix plus waveform policy reaches development/held-out joint quality
  `0.9977/0.9944`, full supported-world coverage and zero false discovery. Its complementary
  reference acquisition has rank nine with worst condition number 246, while one centered
  narrow-offset experiment has rank five and zero information score. This is a controlled
  ray-theoretical acquisition/model-checking on-ramp, not field FWI or geological discovery.
  Under the now-explicit acquisition return contract, three formal GPT-5.5 conditions yield
  six executable proposals and one timeout. Five executable proposals abstain on every
  supported world even though their experiment-information score is `0.974–1.0`; the remaining
  budget-one proposal claims only one of three held-out supported worlds and none in development.
  Thus high-information acquisition is not mechanism recovery, while the shared scalar zero
  conflates timeout, over-refusal and weak transfer. Three earlier runs are retained only as
  superseded contract diagnostics because `acquire()` returned an undocumented dictionary at
  that revision; they are excluded from formal model-performance counts.

Machine-readable evidence lives in [`experiments/`](experiments/).
The original five dated P0–P2 reports were regenerated from clean source revision `f48b101`;
the post-repair 50-package audits bind revision `47c3613`; the subsequent wave-2 admission
audit quarantines seven additional defective candidates. The two P2 smokes are baseline-only; the repository does not yet contain
credible multi-seed model-performance evidence. A clean-revision GPT-5.5 budget-one core pilot
is recorded as task calibration, not a benchmark leaderboard.
The latest closeout certification/security/baseline audits are v53/v37/v42 and bind clean
source revision `e516d56`; full-suite v10 binds the same revision and passes 438/438 tests.
CalorimeterDesign-v2's task calibration and wave-4 admission
audit also bind `f6a7b73`. After the internally admitted QuartzCrystalMicrobalanceLab addition,
the current source manifest is 7/40/12 and contains 47 internally admissible tasks, leaving an
approximate gap of 3 to the roughly 50-task target. The preceding photovoltaic calibration reproduces
ideal one-through-four-junction efficiencies `0.33695/0.45735/0.51291/0.55329`, with nominal
reference score `1.000/1.000` and minimax-reference nominal/robust score
`0.963/0.965` and `1.000/1.000`; these are reduced-order task anchors, not device records.
Three same-model GPT-5.5 calibrations bind clean revision `e57bb68`. Budget one reaches
development/held-out nominal `0.994571/0.993728` but development/held-out robustness
`0.862800/0.806769`. Normal budget three accepts `0.974838→0.993821`, while its selected
held-out robustness is `0.814356`; a frozen-parent batch selects nominal `0.999926` with held-out
robustness `0.824565`. Across seven proposals, five are valid and two have sanitized candidate
runtime errors, with no infrastructure failure. These one-run conditions are not token- or
wall-time-matched and the endpoint has no generation seed, so their ordering is not a feedback-
effect estimate. The selected programs optimize a known public detailed-balance model; they are
not photovoltaic device records, new materials or autonomous discovery.
The budget-one, normal budget-three and frozen-parent reports have SHA-256
`6402d412916e5d4b252a1d5b7a4a483cfe2c6b0a070f5b8e6c1dac34f5b607c5`,
`581a668727b27a4d621ebf3bb6b2f057595098b98478d706f709183a22428aaa` and
`07d3a6d37afa04791eac0dc38b17cf9857be70f77e561a3cf131fb08438538f2`; the derived
analysis has SHA-256 `e938f0bc635ec1569a2276a9041995ee957eeb89248db008dc5a48a5e8658607`.
GeneNetworkIntervention adds an active nonlinear signed-network, protected-readout intervention,
sealed-transfer and null/latent-regulator refusal candidate. Its truth-blind nonlinear reference
scores `0.9053/0.8932` development/held-out joint quality with zero false discovery. Across the
budget-one, normal budget-three and selection-blind budget-three GPT-5.5 calibrations, six of
seven proposals are invalid and the only valid proposal refuses every supported world; no valid
nonzero scientific proposal is observed. RNAInverseDesign adds five development and three held-out
secondary-structure families under a transparent exact pair-stack-loop ensemble. Normal budget
three improves development exact utility `0.239→0.507→0.720`, with held-out utility `0.500`, but
retains proxy false promotions; a pair-compatible counterexample has target probability `3e-9`.
This is simplified computational ensemble design, not full Turner thermodynamics, a synthesized
RNA or biological discovery. ProteinStabilityDesign adds two normal runs and one strict
selection-blind diagnostic over a public DMS replay. Budget one reaches development/held-out
`0.614/0.412`; normal budget three reaches `0.535/0.559`; the frozen-parent batch selects
`0.546/0.519`, while a rejected candidate reaches held-out policy/robustness `0.652/0.753`.
These single runs are calibration evidence, not a leaderboard, feedback-effect estimate,
pretraining-contamination audit, prospective experiment or biological discovery.
ElectrolyteConductivityDesign adds two normal runs and one strict selection-blind diagnostic over public EIS
measurements. Its normal budget-three selected artifact reaches development/held-out visible
scores `0.878/0.926` and discovery-repeat robustness `0.826/0.896`, while untouched-repeat
confirmation and confirmation robustness are `0/0` on both splits. This is offline optimization
and repeatability-gap evidence, not a prospective formulation or complete-cell result.
DemographicSFS-v2 adds two normal runs and a strict selection-blind diagnostic. Its normal
budget-three selected policy reaches development/held-out mechanism `0.640/0.397` and
sample-size prediction `0.883/0.939`, with full supported coverage, full resolvable-mismatch
refusal and zero false discovery. A rejected proposal reaches higher held-out mechanism `0.603`
at lower development mechanism `0.521`. Budget one and all three frozen-parent proposals fail
the executable protocol; the normal/open-loop contrast is unseeded and non-causal.
CalorimeterDesign-v2 adds three cost-conditioned detector curves per regime. Its nominal
reference reaches `1.0/1.0` development/held-out score but only `0.483/0.467` shifted-geometry
feasibility; leaving 1.913 percentage points of development cost headroom yields unit robustness
and shift feasibility at nominal score `0.798/0.754`. All seven GPT-5.5 proposals are runtime-
invalid, so this is a task/reference calibration, not model success or detector validation. The
prospective evidence-synthesis task adds ten registered-study worlds with duplicated participant
lineages, selectively highlighted outcomes, heterogeneous linear effects, resolvable nonlinear
misspecification, an immutable forecast/design commit and one fresh simulated study. Its truth-
blind reference scores `0.934/0.886` development/held-out with zero false discovery and complete
unsupported-world refusal. Across budget-one, normal budget-three and selection-blind budget-
three GPT-5.5 runs, four proposals are schema-invalid and three are valid empty abstentions; none
screens evidence or requests confirmation. Normal iteration repairs executable validity after its
first proposal but does not cross the scientific-workflow hurdle. The single-run normal/open-loop
contrast remains non-causal. CatalystDeactivationLab-v1 then adds a deterministic reduced-order
state machine with gain/offset drift, four finite coupons, irreversible deactivation, out-of-order
batch completion and exact-retry idempotency. Its truth-blind reference reaches
`0.958034/0.951263` development/held-out nominal score and `0.883174/0.942773` robustness while
covering all supported worlds, refusing every unsupported world and producing no false discovery.
Across the three GPT-5.5 calibration conditions, six of seven proposals are valid and four obtain
nonzero scores. Budget one conservatively refuses every world. Normal and frozen-parent budget
three cover all supported worlds but refuse none of the unsupported worlds, with false-discovery
rates `0.40/0.333` and zero development decision score. The frozen-parent selected artifact uses
out-of-order batches; no model proposal exercises exact retry. These single synthetic runs do not
support feedback-causal, reactor, catalyst, instrument or autonomous-discovery claims. Cross-task
summary v27 contains 67 normal conditions over 34 tasks and adds CatalystDeactivationLab-v1
budgets one and three without averaging task-specific science axes into a common score.
QuartzCrystalMicrobalanceLab-v1 then adds nine raw I/Q sweeps per world, two complex calibration
blocks, three harmonics, missing samples, viscoelastic/rate anomalies, I/Q conjugation and ADC
clipping. Its truth-blind reference reaches development/held-out nominal
`0.995228/0.996343` and sealed robustness `0.940278/0.949282`, with full supported coverage,
unsupported refusal and fault diagnosis and zero false discovery. Across budget one, normal
budget three and selection-blind budget three, all seven GPT-5.5 proposals are valid but score
zero: five refuse every supported world, one claims every world with false-discovery rate
`0.5/0.5`, and one obtains partial development coverage without held-out transfer. All three
conditions retain the weak baseline. This is a synthetic raw-instrument task calibration, not a
QCM, thin-film, material or autonomous-discovery result. Cross-task summary v28 contains 69
normal conditions over 35 tasks; the selection-blind run remains in the task-specific analysis.

The latest EdgeBench re-audit keeps its upstream facts at arXiv `2607.05155v1`, SForge
`a87350a` and public dataset `47846a4`. In addition to E1--E36, the science plan now preregisters
nineteen scope/protocol tests. I6/E37 has a synthetic QCM implementation smoke, while its paired
repeated treatment and real-instrument stratum remain unrun; the other tests include unit/coordinate/
representation metamorphic invariance (V4/E38), independent investigators with blinded synthesis
(T1/E39), post-commit sealed downstream utilities (U1/E40), independently disclosed research
horizons rather than long-run prefixes (HZ1/E41), and pinned/calibrated rubric or model judges
(J1/E42), calibrated acquisition of costly authoritative feedback (F9/E43), plus randomized
continuation auditing to retain delayed scientific takeoff (CA1/E44), rotating open/sealed/delayed-
release cohorts (G1/E45), builder--solver cross-fitting (G2/E46), evidence-effective-sample-size
accounting (EVI1/E47), observation-kernel/interval-censoring sensitivity with a separate
live-state stratum (OBS1/E48), policy-aware inference after endogenous experiment selection
(AD1/E49), complete reporting of null/contradictory/failed local experiments (NR1/E50), and
conditional checkpoint forks that separate same-history continuation randomness from matched-score
research-history lock-in (CF1/E51), plus preregistered single-factor/factorial replay that separates
new evidence, method edits and their interactions at narrated breakthroughs (MA1/E52), explicit
retention and falsification of competing hypotheses rather than only one incumbent (HP1/E53), and
calibration of biased, drifting or conflicting feedback sources (FR1/E54), and preregistered
performance–cost–constraint-margin sweeps for scientific instruments (CM1/E55). A separate M2
protocol gate freezes the checkpoint risk set and replays single-run best-so-far monotonicity.
These are proposed experiments, not new EdgeBench or Frontier-
Science performance results. The expansion plan also prioritizes one prospective evidence-synthesis task over another
near-duplicate clean-simulator scalar task.

An implementation-level OBS1 micro-pilot now replays the three trusted MOSFET trajectories on a
common 120-second horizon. Dense AUC ordering survives 15/30/60-second fixed grids, while the
120-second fixed grid collapses all three trajectories to a zero-AUC tie and its seeded-random-phase
variant produces one pairwise reversal. This is a trusted short-run measurement-sensitivity report,
not the planned multi-hour OBS1 experiment and not evidence for a feedback or model effect.

## Quickstart

```bash
python -m frontier_science list
python -m frontier_science list --all
python -m frontier_science eval --task LennardJonesCluster
python -m frontier_science run --task LennardJonesCluster \
  --algorithm greedy_rewrite --budget 10 --seed 0 --workdir runs/lj/seed-0
```

Resume the exact work directory with `--resume`. Available algorithm names are:

- `greedy_rewrite`: the built-in single-incumbent full-file baseline.
- `openevolve`: official OpenEvolve 0.2.26 population/MAP-Elites backend (optional,
  Python ≥3.10).
- `abmcts`: official TreeQuest AB-MCTS-A backend (optional, Python ≥3.11).
- `shinkaevolve`: official ShinkaEvolve backend (optional, Python ≥3.10).

Named optional backends fail explicitly when their upstream package or supported wire is
unavailable; they never silently substitute the greedy baseline. Every backend routes
candidate scoring through the same secure evaluator and writes the unified
trajectory-schema-v2 `trajectory.jsonl`/`summary.json`, plus `checkpoint` and
`best_program.py` artifacts. Pinned optional dependencies are listed in
[`requirements-upstream.txt`](requirements-upstream.txt); TreeQuest needs a Python 3.11
environment, so it cannot share this host's Python 3.8 runtime.

`greedy_rewrite` additionally supports `--feedback-mode selection_blind`. In this open-loop
control, every proposal sees the frozen baseline program and baseline public metrics; evaluation
results are retained only for offline best-of-batch analysis and never alter a later prompt or
parent. Local run seeds label paired replicates and control local sampling, but the current Azure
Responses endpoint does not expose a server-side random seed.

Run a preregistered multi-seed experiment with:

```bash
python scripts/batch_evolve.py \
  --algorithms greedy_rewrite \
  --feedback-modes normal,selection_blind \
  --seeds 0,1,2,3,4 --budget 30
```

The runner reports terminal best score, best-so-far AUC over charged proposal/benchmark
`budget_units`, actual `oracle_calls` as a separate count, wall time, token/cost fields, and
Student-t 95% confidence intervals. Thus, for example, an unparsable proposal consumes a
budget unit without fabricating an oracle call. Here `none`/`shuffled` control only the metrics
shown in the proposal prompt; incumbent/parent selection still uses true oracle scores, and each
summary records that scope. They are diagnostic prompt-feedback ablations; `selection_blind` is
the strict open-loop control for the whole iterative-feedback package. Unsupported combinations
fail rather than changing semantics.

## LLM configuration

Copy the public example and provide an OpenAI-compatible endpoint:

```bash
cp frontier_science/conf/llm/openai_compatible.example.yaml \
   frontier_science/conf/llm/local.yaml
# edit base_url / api_key / model, or export OPENAI_API_KEY
python -m frontier_science smoke
```

`local.yaml` is git-ignored. Resolution order is `--llm-config` / `FS_LLM_CONFIG`, then
`conf/llm/local.yaml`, then the committed example. The built-in client supports Chat
Completions and Responses; optional upstream frameworks currently require Chat Completions.

## Task contract and certification

A task package has `Task.md`, an editable baseline, a hidden
`verification/evaluator.py`, and a `frontier_eval/` contract containing `metadata.yaml`,
`initial_program.txt`, `candidate_destination.txt`, `entrypoint.txt`, and
`constraints.txt`. Adding a directory makes it discoverable, but does **not** make it
certified.

Certification additionally requires a task card, stable citation identifiers, a trusted
sandbox entrypoint, deterministic baseline, scientific invariants, defensible normalization
anchors, and reviewer evidence. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the admission
process and [`frontier_science/certification.yaml`](frontier_science/certification.yaml) for
current status.

## Reproduce audits

```bash
python scripts/run_security_audit.py --output /tmp/security.json
python scripts/audit_tasks.py --output /tmp/certification.json
python scripts/audit_inverse_candidates.py --output /tmp/inverse-admission.json
python scripts/audit_candidate_wave3.py --output /tmp/candidate-wave3.json
python scripts/audit_candidate_wave4.py --output /tmp/candidate-wave4.json
python scripts/run_secure_baseline.py --repeats 2 --output /tmp/baselines.json
python -m unittest discover -v -s tests
# From each compatible optional-backend venv:
python scripts/smoke_upstream_backends.py --backend openevolve --output /tmp/openevolve.json
# Repeat for abmcts and shinkaevolve, then validate/merge all three:
python scripts/merge_upstream_smokes.py \
  --input /tmp/openevolve.json --input /tmp/abmcts.json --input /tmp/shinkaevolve.json \
  --output /tmp/upstream-smokes.json
```

Every new machine-readable report includes its command, Git revision, scoped source-dirty state,
and changed source paths. Trusted dated evidence must report a clean source tree.

Historical results produced before sandboxing are retained unchanged for provenance and are
classified `UNTRUSTED_PRE_SANDBOX` in [`experiments/TRUST.md`](experiments/TRUST.md); they must
not be used as benchmark evidence.
