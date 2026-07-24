# Scientific task portfolio audit

Audit date: 2026-07-24 (UTC). The original inventory contained 50 discoverable task packages;
the new ActiveLawDiscovery candidate brings the current inventory to 51. This count is an
inventory fact, not evidence that all packages are benchmark-admissible.

## Admission dimensions

Every task must be assessed on distinct axes before certification:

| Axis | Required evidence | Common failure |
|---|---|---|
| Scientific semantics | Artifact and objective correspond to a cited research workflow | Scientific name wrapped around a generic function |
| Oracle fidelity | Equations/data/simulator and invariants independently reviewed | Simplified proxy mislabeled as a physical simulator |
| Openness/headroom | Frontier model does not reliably saturate at tiny budget; meaningful improvement remains | Textbook algorithm reaches a clipped ceiling in one proposal |
| Generalization | Hidden procedural instances, shifts or time-held-out cases | Fixed public instances reward memorization and tuning |
| Optimization continuity | Valid weak baseline and graded feasible improvements | Binary validity or mostly-invalid search space |
| Evidence separation | Development score separated from sealed validation and mechanism where applicable | One scalar hides proxy overfitting or wrong mechanisms |
| Integrity | Trusted isolation, determinism, citations, task card, replay and reviewer state | Directory exists but evidence package is absent |

Certification requires all axes. A task may be scientifically meaningful but still need a
better evaluator; conversely, a deterministic numerical objective can still lack scientific
meaning.

## Current inventory triage

- **7 certified core tasks.** Secure and documented, but the 2026-07-21 GPT-5.5 pilot shows
  that Poisson and Spin Glass saturate in one proposal and Lennard-Jones nearly saturates.
  Their certification establishes oracle integrity, not sufficient long-horizon headroom.
- **1 new mechanism candidate.** `CausalDiscovery/InterventionalSCM` supplies budgeted
  interventions, a null world, separate mechanism/prediction metrics and deterministic hidden
  worlds. GPT-5.5 nevertheless reaches 0.983 in one proposal through textbook total-effect
  inversion, so it needs latent/partial/nonlinear/misspecified regimes in addition to external
  review and a server-held split.
- **4 candidates screened at budget one.** SparseRecovery reaches 0.958 through standard
  sparse solvers and needs hidden sensing/noise/sparsity shifts. SeismicInversion's mean-only
  forward model has since been replaced with identifiable 4–6 layer direct/head-wave surveys
  and separate velocity/holdout diagnostics; GPT-5.5 then reaches 0.994 in one proposal, so it
  is a scientifically valid on-ramp rather than a long-horizon headline task.
  LyapunovControl's omitted feedback derivative has since been repaired with
  a two-trajectory closed-loop estimator; replaying the candidate gives MLE -1.413 and clipped
  score 1.0, so it is an on-ramp rather than a headline task. NeutronDiffusionCriticality's
  asymmetric diffusion stencil and fixed anchor have since been replaced by a conservative
  symmetric operator and a reproducible optimization/eigenvalue witness; its old GPT-5.5 score
  is superseded.
- **The 11 metadata-complete candidates have now been screened.** Lyapunov and seismic are
  repaired on-ramps; neutron has a repaired oracle and verified anchor but still needs hidden
  regimes; sparse recovery is a near-saturated on-ramp. Pendulum-v2 has been rebuilt and
  restored as a candidate: GPT-5.5 reaches 0.797 development and 0.631 shifted robustness at
  budget one. At budget three, visible development rises from 0.691 to 0.854 while shifted
  robustness stays near 0.64, making it the first useful development–validation gap task. The
  original five failed reproducible adversarial review: RIR length failure, unstable
  low-thrust propagation, centerline-spoofable cavity scoring, pseudo-data alloy hardness and
  scalar-FFT pseudo-RCWA. HeatExchanger-v2 and LowThrustTransfer-v2 were subsequently rebuilt
  as multifidelity Pareto and long-horizon trajectory-optimization candidates, respectively;
  RoomImpulseResponse-v2 has now also been substantively rebuilt; the remaining three stay
  quarantined.
- **No original unscreened candidates remain after wave 4; 28 candidates remain in total.** They include
  SCM, Lyapunov control, neutron criticality, seismic refraction, pendulum control, sparse
  recovery, OED-v2, GateSynthesis-v2, OPF-v2, Truss-v2, Antenna-v2, NMR-v2,
  HeatExchanger-v2, ReactionMechanismFitting-v2, GravityInversion-v2,
  OceanCurrentInversion-v2, RadiativeTransferFit-v2, LowThrustTransfer-v2,
  LidDrivenCavity-v2, EnergyBalanceModel-v2, BroadbandAbsorber-v2,
  DistillationColumnDesign-v2, HartreeFockSCF-v2, RoomImpulseResponse-v2,
  ConvectionDiffusionOpt-v2, SeismicWaveInversion-v2, RankineCycleOpt-v2 and the
  ActiveLawDiscovery laboratory. All are
  currently on-ramps or repair/calibration candidates rather than externally reviewed
  open-frontier tasks.
- **ActiveLawDiscovery preserves science-specific headroom.** GPT-5.5 budget one attains 0.796
  development and 0.745 sealed validation mechanism score with approximately 0.996 rollout
  prediction, but makes a high-confidence false discovery in both misspecified worlds. In an
  independent budget-three run, all three proposals retain the same two false discoveries;
  score feedback does not fix model-inadequacy detection and later proposals reduce mechanism
  recovery. This is a reliability/refusal frontier rather than an ordinary prediction frontier.
- **16 quarantined packages.** Five generic-objective clones must be replaced with real domain
  oracles; metadata completion alone cannot rehabilitate them. The former Climate, cavity and
  broadband-absorber defects have been resolved by substantive v2 rebuilds rather than local
  numerical patches. The remaining wave-2 and inverse-track tasks are still blocked by concrete oracle failures;
  none may contribute model-performance evidence until rebuilt and re-admitted. The inverse
  failures include rank-deficient hidden-truth retrieval, a rank-two demographic surrogate,
  underidentified pseudo-DNS
  RANS fitting. The former evidence-free FWI interface has been replaced by
  SeismicWaveInversion-v2 and re-admitted as a candidate.
  Wave 3 additionally isolates six scientifically promising topics whose current evaluators are
  unusable: fail-open NMR/OED/gate/OPF/antenna scores and a non-canonical duplicated-member
  truss topology. All six have since been substantively rebuilt and re-admitted; their candidate
  status records internal scientific validity, not external validation or headline difficulty.
  Wave 4 initially quarantined the final 12 unscreened packages after reproducing fail-open paths,
  unreachable anchors, missing observations, uncoupled systems, degenerate corners and models
  that do not implement the claimed science. BroadbandAbsorber-v2, Distillation-v2 and
  HartreeFockSCF-v2, ConvectionDiffusionOpt-v2 and RankineCycleOpt-v2 now resolve five of those
  twelve; the other seven retain their reproduced
  defects.

## Priority review findings

The first review tranche contains real scientific topics but several narrow evaluators:

- RoomImpulseResponse-v2 now replaces two fixed reconstruction scenes with source placement and
  six-surface treatment over four development and two held-out rooms. Independent wall-hit,
  path-energy, absorption and Eyring checks reproduce the order-10 oracle; first-order proxy,
  order-14 horizon, installation, audience, material and geometry axes remain separate. GPT-5.5
  budget one stays at development zero while a valid rejected proposal reaches held-out 0.419.
  Normal budget three makes three contract-key runtime errors; a frozen-parent open-loop batch
  finds 0.754 development, 0.742 held-out nominal and 0.803 held-out robustness. This preserves
  headroom and transfer, but the single token-mismatched runs support no feedback claim. Retain
  pending server-held rooms, hybrid wave/ray and measured-RIR replication and independent review.
- LowThrustTransfer-v2 now spans six raising, lowering, eccentricity, plane-change and combined
  transfers with MEE+J2 propagation, rocket-equation mass loss, continuous harmonic-control
  bounds, two held-out missions and three sealed execution shifts. A public-input Gauss--Newton
  policy is nominally feasible on all missions and reaches 0.711/0.719 development/held-out
  utility and 0.682/0.660 shifted robustness. Its 1800 s production propagation differs from a
  900 s refinement by at most 0.0423 terminal tolerances; the refined MEE path differs from an
  independent Cartesian DOP853 path by at most 0.00288 tolerances and 0.000223 kg. GPT-5.5
  preserves substantial headroom: all seven proposals across budget-one, normal budget-three
  and strict open-loop budget-three are executable but terminal-infeasible, development scores
  never exceed 0.00774 and held-out utility never exceeds `5.8e-9`. The normal/open-loop
  selected scores are 0.00508/0.00549, but the single-run conditions are not randomness- or
  token-matched and support no feedback claim. The candidate still needs server-held missions,
  paired repetitions, higher-fidelity mission-tool replication and independent astrodynamics
  review.
- Pendulum, Lorenz control and heat-exchanger tasks are likely to admit short analytic/template
  solutions; retain only if hidden parameter regimes and robustness/cost tradeoffs preserve
  headroom.
- Lid-driven cavity exposes one Reynolds number/grid and published centerline targets; add
  held-out Reynolds/grid convergence and conservation diagnostics.
- Seismic inversion and sparse recovery naturally support procedural hidden instances and are
  strong candidates after task cards, invariants and multi-regime calibration.
- The alloy task currently uses a pseudo-physical polynomial surrogate rather than experimental
  material data. It should be replaced with a documented dataset/model split or quarantined.
- Diffraction grating uses a scalar FFT phase model, not the claimed rigorous coupled-wave
  analysis. Rename the fidelity or replace it with a validated RCWA oracle.
- Neutron diffusion now has a conservative symmetric PDE/eigenvalue oracle and a reproducible
  optimization/eigenvalue witness, but still exposes only one geometry/loading regime; add
  hidden material/geometry shifts before treating it as more than an on-ramp.
- Truss-v2 now supplies six procedural structures, finite-output checks, independently reproduced
  nominal/robust local witnesses and sealed topology/physical-shift metrics. Its non-saturated
  GPT-5.5 trajectory makes it a useful optimization/validation candidate, pending server-held
  structures, paired controls and independent review. Antenna-v2 now likewise supplies six
  scanned uniform/nonuniform arrays, measured normalization, finite-grid nominal/robust domain
  witnesses, and sealed frequency/calibration/position/exhaustive element-failure metrics;
  it still needs model calibration, server-held arrays, full-wave replication and independent
  review. NMR-v2 now has ten procedural spectra, order-invariant peak-mechanism matching,
  held-out line-shape/noise/baseline shifts and explicit null/model-inadequacy refusal; it still
  requires independent spectroscopist review and server-held spectra. GPT-5.5 preserves
  headroom at budget one (0.428 development versus 0.176 held-out mechanism/refusal), while
  high 0.874/0.878 reconstruction coexists with false discovery. Two later budget-three
  rewrites score lower and falsely fit every unsupported spectrum.
- OED-v2 now meets those internal evaluator criteria: six development and four shifted model
  families, finite integer allocations, numerically whitened Fisher sensitivities, and
  Kiefer-Wolfowitz-certified references. GPT-5.5 then reaches 0.991 development and 0.994
  sealed validation in one proposal by implementing whitening, multiplicative design and
  determinant/exchange optimization. It is therefore a useful, scientifically valid on-ramp,
  not a long-horizon headline task; harder sequential model-discrimination regimes,
  server-held instances and independent review remain necessary.
- OPF-v2 supplies six complete 5--9 bus meshed DC networks, finite dispatch validation, safe
  baselines, independent nominal and security-constrained QP witnesses, and exhaustive
  non-islanding N-1 evaluation. The nominal witness reaches development score 1.0 but only
  0.031 sealed robustness, whereas the security-constrained witness reaches approximately
  unit robustness at nominal score 0.144. GPT-5.5 reproduces the nominal witness at budget one,
  reaching development/held-out nominal score 1.0 but N-1 robustness 0.031/0.000001. An
  independent budget-three run leaves the same security failure unchanged. This candidate still
  needs paired controls, server-held networks, AC replication and independent review.
- OceanCurrentInversion-v2 supplies charged active drifter releases, thirty public
  divergence-free modes, seven identifiable in-library worlds, null and resolvable
  misspecification cases, and separate mechanism, field and trajectory metrics. A truth-blind
  sparse fit scores 0.707/0.406 development/held-out mechanism with zero false discovery.
  GPT-5.5 budget one and normal budget three remain at zero; its only valid non-baseline
  proposal spends the full budget but refuses every in-library world, while the other proposals
  fail the public release/callback protocol. It remains a useful active-inference and
  protocol-following candidate pending paired runs, server-held currents and independent review.
- RadiativeTransferFit-v2 replaces a fixed 10-observation/20-unknown profile score with charged
  selection over 24 thermal channels and view angles, a public five-parameter temperature and
  optical-depth family, seven full-rank supported worlds, and null/absorber/cloud refusal. Its
  truth-blind two-view fit reaches 0.614/0.491 development/held-out mechanism and 0.855/0.812
  radiance prediction with zero false discovery. All seven GPT-5.5 proposals across budget-one,
  normal budget-three and strict open-loop budget-three are protocol-valid but refuse every
  supported atmosphere. It is therefore useful for active sounding, calibrated refusal and
  risk–coverage studies, pending factorized paired controls, server-held atmospheres,
  line-by-line or real-data replication and independent atmospheric-science review.
- BroadbandAbsorber-v2 replaces a fail-open single-resonator proxy with six variable-band,
  6--10-cell panels, a Stinson circular-tube dynamic-density model, finite rigid cavities,
  parallel surface admittance and five sealed angle/air/manufacturing shifts. Independent
  complex-valued equations agree to approximately `1e-14`, references retain nominal and robust
  headroom, and the public proxy differs from the distributed model by `0.34--0.59` utility on
  the reference family. GPT-5.5 normal budget three reaches nominal `0.915/0.859` and robust
  `0.912/0.858` development/held-out scores; a one-run strict open-loop artifact has similar or
  higher nominal scores but robust `0.452/0.449` because manufacturing errors exceed the hard
  panel envelope. The contrast is not randomness- or token-matched and supports no feedback
  claim. The candidate still needs server-held geometries, thermoviscous/full-wave replication,
  impedance-tube data and independent acoustics review.
- Distillation-v2 replaces a fixed-purity tray toy with six varying binary separations, exact
  tray/feed-stage artifacts, closed equilibrium-stage material balances, product purity and
  recovery gates, interleaved held-out mixtures and five sealed operating shifts. Independent
  least-squares MESH solves agree below `2e-8`; nominal and robust references expose a real
  cost-versus-shift tradeoff. GPT-5.5 normal budget three produces one valid nominally feasible
  improvement at development/held-out `0.613/0.541`, but only `0.20/0.20` shifted feasibility
  and zero robustness; six of seven proposals across the three calibration conditions time out.
  A post-hoc public-cost probe also shows the selected design does not respond when the
  capital-versus-energy ranking reverses. Retain pending repeated calibration, server-held
  mixtures, rate-based process-simulator replication and independent chemical-engineering review.
- HartreeFockSCF-v2 replaces an inconsistent two-coefficient H2 toy with seven reproducible
  closed-shell finite-basis Hamiltonians, finite occupied-orbital artifacts, independently
  recomputed RHF equations, physical geometry shifts, AO representation checks and internal
  occupied--virtual stability. The valid single-start DIIS baseline has development/held-out
  stability `0.75/0.667`; stable multistart witnesses lower the hard H8/H4 energies by
  `0.0375/0.0619 Ha` and reverse their minimum stability curvatures from negative to positive.
  The reference reaches approximately `0.99997` development and `0.99813` held-out nominal
  score with approximately unit robustness. GPT-5.5 then reaches approximately unit nominal and
  sealed scores in one proposal by synthesizing deterministic multistart/stability search, so the
  current fixed task is an algorithm-synthesis on-ramp. In the normal budget-three trajectory, a
  `9.1e-15` selection-score increase trades development robustness `1.000→0.707` for held-out
  robustness `0.902→1.000`; a `1e-12` acceptance epsilon retains the earlier artifact. A strict
  open-loop batch also reaches approximately unit nominal score, so feedback is not shown
  necessary by these single, token-mismatched runs. The public single-start baseline is BLAS-
  thread sensitive on the held-out geometry shift (`0.667` at the authoritative secure one-
  thread setting versus approximately `1.0` at 2/4/8 threads). It remains a candidate pending
  server-held procedural molecules/basis families, external-instability and correlated-method
  checks, repeated controls and independent quantum-chemistry review.
- ConvectionDiffusionOpt-v2 replaces a fixed hidden target and unusable three-argument interface
  with an active anisotropic convection--diffusion laboratory. Across six development and five
  held-out worlds, candidates may spend 12 units on chosen calibration heaters and sensors,
  infer five homogeneous transport/loss coefficients, design four target-matching heaters and
  refuse zero-response or spatially heterogeneous apparatuses. A truth-blind two-experiment
  policy reaches `0.896/0.892` development/held-out joint quality and approximately `0.894/0.890`
  shifted robustness with zero false discovery; its first symmetric midline experiment alone is
  numerically rank five but has condition numbers above `7.8e4` and scores approximately zero,
  while the off-axis second experiment resolves the ambiguity. This validates active experiment
  design inside the finite-difference benchmark, not continuum heat transfer or a physical
  device. GPT-5.5 calibration finds four invalid proposals and three valid all-world abstention
  policies, including one full-budget two-experiment design, so the task retains experiment-design
  and supported-discovery headroom. Retain pending repeated paired controls, server-held
  apparatuses and independent review.
- SeismicWaveInversion-v2 replaces a fixed hidden velocity guess with charged CMP, offset and
  frequency acquisition over procedural three-layer, null and four-layer low-velocity-zone
  worlds. The public forward model uses exact Snell-ray primary travel times, Gardner-style
  impedance and Ricker waveforms; waveform fit, nine-parameter mechanism recovery, acquisition
  information, far-offset prediction, confidence and refusal remain separate. A truth-blind
  NMO/Dix plus waveform policy reaches `0.998/0.994` development/held-out joint quality with
  zero false discovery. The complementary design is rank nine with worst condition number 246,
  while one centered narrow design is rank five and scores zero information. Retain as an
  active-acquisition/model-checking on-ramp pending GPT-5.5 calibration, server-held worlds,
  elastic/wave-equation replication, field evidence and independent geophysics review.

## Expansion rule

The target is approximately 50 **admissible** open scientific optimization tasks, not merely
50 folders. Expansion proceeds in waves:

1. harden and recalibrate the seven core tasks;
2. certify only the strongest procedural/physics-backed candidates;
3. replace pseudo-scientific or narrow proxies;
4. add missing mechanism, multifidelity, experimental-design and null/misspecification families;
5. run frontier-model budget-one screening before expensive budget 30/100/300 studies.

After complete original-inventory triage, adding ActiveLawDiscovery and rebuilding Gate-v2,
OPF-v2, Truss-v2, Antenna-v2, NMR-v2, HeatExchanger-v2, ReactionMechanismFitting-v2 and
GravityInversion-v2, OceanCurrentInversion-v2, RadiativeTransferFit-v2, LowThrustTransfer-v2,
LidDrivenCavity-v2, EnergyBalanceModel-v2, BroadbandAbsorber-v2, Distillation-v2,
HartreeFockSCF-v2, RoomImpulseResponse-v2, ConvectionDiffusionOpt-v2 and
SeismicWaveInversion-v2 and RankineCycleOpt-v2, the net expansion gap is approximately 15
admissible tasks: 51 folders minus 16 quarantines leaves 35 internally admissible certified or
candidate packages, while the target
is about 50. New
work should emphasize procedural task families and independent regimes,
not one-off fixed instances or scientific names around hand-written scalar objectives.

A candidate that saturates across seeds at budget one is a calibration/on-ramp task, not an
open-optimization headline task. A candidate that improves development score without sealed
validation improvement remains optimization-only.
