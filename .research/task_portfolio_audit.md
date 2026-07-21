# Scientific task portfolio audit

Audit date: 2026-07-21 (UTC). The original inventory contained 50 discoverable task packages;
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
  other six remain quarantined after reproducible adversarial review: RIR
  length failure, unstable low-thrust propagation, centerline-spoofable cavity scoring,
  pseudo-data alloy hardness, scalar-FFT pseudo-RCWA and a degenerate heat-exchanger objective.
- **No original unscreened candidates remain after wave 4; eight candidates remain in total.** They are
  SCM, Lyapunov control, neutron criticality, seismic refraction, pendulum control, sparse
  recovery, OED-v2 and the new ActiveLawDiscovery laboratory. All are currently on-ramps or
  repair/calibration candidates rather than externally reviewed open-frontier tasks.
- **ActiveLawDiscovery preserves science-specific headroom.** GPT-5.5 budget one attains 0.796
  development and 0.745 sealed validation mechanism score with approximately 0.996 rollout
  prediction, but makes a high-confidence false discovery in both misspecified worlds. In an
  independent budget-three run, all three proposals retain the same two false discoveries;
  score feedback does not fix model-inadequacy detection and later proposals reduce mechanism
  recovery. This is a reliability/refusal frontier rather than an ordinary prediction frontier.
- **36 quarantined packages.** Five generic-objective clones must be replaced with real domain
  oracles; metadata completion alone cannot rehabilitate them. The sixth,
  `ClimateScience/EnergyBalanceModel`, uses an unstable explicit diffusion iteration, an
  unverified ERA5 attribution and a structurally underdetermined seven-parameter fit to one
  steady profile. It requires replacement with documented multi-regime data, not a numerical
  patch. Six wave-2 and seven inverse-track tasks remain blocked by concrete oracle failures;
  none may contribute model-performance evidence until rebuilt and re-admitted. The inverse
  failures include rank-deficient hidden-truth retrieval, saturated reaction data, gravity and
  ocean signal/noise inversions, a rank-two demographic surrogate, underidentified pseudo-DNS
  RANS fitting and an FWI interface with no observations.
  Wave 3 additionally isolates six scientifically promising topics whose current evaluators are
  unusable: fail-open NMR/OED/gate/OPF/antenna scores and a non-canonical duplicated-member
  truss topology. OED-v2 has since been substantively rebuilt and re-admitted; the other five
  task families should be rebuilt rather than cosmetically patched.
  Wave 4 quarantines the final 12 unscreened packages after reproducing fail-open paths,
  unreachable anchors, missing observations, uncoupled systems, degenerate corners and models
  that do not implement the claimed science.

## Priority review findings

The first review tranche contains real scientific topics but several narrow evaluators:

- Room acoustics uses two fixed scenarios and a simplified image-source implementation; add
  procedural room/source/microphone configurations and independent acoustic invariants.
- Low-thrust transfer has one scenario and a low-order propagation scheme; add multiple orbital
  regimes and a higher-fidelity integrator before scientific claims.
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
- Neutron diffusion has a substantive PDE/eigenvalue oracle but only one geometry/loading
  regime and an unsupported fixed normalization increment; validate anchors and add shifts.
- Gate synthesis, OPF, truss sizing, antenna synthesis and NMR fitting are valuable task
  families, but their current packages cannot support model evidence. Re-admission requires
  procedural instances, finite-output checks, independent anchors, and sealed shifted or
  mechanism metrics where applicable.
- OED-v2 now meets those internal evaluator criteria: six development and four shifted model
  families, finite integer allocations, numerically whitened Fisher sensitivities, and
  Kiefer-Wolfowitz-certified references. GPT-5.5 then reaches 0.991 development and 0.994
  sealed validation in one proposal by implementing whitening, multiplicative design and
  determinant/exchange optimization. It is therefore a useful, scientifically valid on-ramp,
  not a long-horizon headline task; harder sequential model-discrimination regimes,
  server-held instances and independent review remain necessary.

## Expansion rule

The target is approximately 50 **admissible** open scientific optimization tasks, not merely
50 folders. Expansion proceeds in waves:

1. harden and recalibrate the seven core tasks;
2. certify only the strongest procedural/physics-backed candidates;
3. replace pseudo-scientific or narrow proxies;
4. add missing mechanism, multifidelity, experimental-design and null/misspecification families;
5. run frontier-model budget-one screening before expensive budget 30/100/300 studies.

After complete original-inventory triage and adding ActiveLawDiscovery, the net expansion gap
is approximately 42 admissible tasks, not zero: 51 folders minus 36 quarantines leaves only 15
internally admissible certified or candidate packages. New work should emphasize procedural task families and independent regimes,
not one-off fixed instances or scientific names around hand-written scalar objectives.

A candidate that saturates across seeds at budget one is a calibration/on-ramp task, not an
open-optimization headline task. A candidate that improves development score without sealed
validation improvement remains optimization-only.
