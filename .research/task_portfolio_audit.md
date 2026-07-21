# Scientific task portfolio audit

Audit date: 2026-07-21 (UTC). The repository now contains 50 discoverable task packages. This
count is an inventory fact, not evidence that all 50 are benchmark-admissible.

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
  sparse solvers and needs hidden sensing/noise/sparsity shifts. SeismicInversion is currently
  non-identifiable. LyapunovControl's omitted feedback derivative has since been repaired with
  a two-trajectory closed-loop estimator; replaying the candidate gives MLE -1.413 and clipped
  score 1.0, so it is an on-ramp rather than a headline task. NeutronDiffusionCriticality still
  uses an unverified fixed score anchor.
- **11 earlier candidates with complete metadata fields.** These are the fastest next review
  tranche: RoomImpulseResponse, LowThrustTransfer, InvertedPendulumSwingUp, LyapunovControl,
  LidDrivenCavity, SeismicInversion, AlloyHardnessOptimization, NeutronDiffusionCriticality,
  DiffractionGratingDesign, SparseRecovery and HeatExchangerDesign.
- **26 candidates with incomplete scientific metadata.** These require citation, baseline and
  best-known anchors before detailed admission review.
- **5 quarantined generic-objective clones.** They must be replaced with real domain oracles;
  metadata completion alone cannot rehabilitate them.
- **1 known invalid candidate.** `ClimateScience/EnergyBalanceModel` returns non-finite metrics
  and must be repaired or quarantined.

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

## Expansion rule

The target is approximately 50 **admissible** open scientific optimization tasks, not merely
50 folders. Expansion proceeds in waves:

1. harden and recalibrate the seven core tasks;
2. certify only the strongest procedural/physics-backed candidates;
3. replace pseudo-scientific or narrow proxies;
4. add missing mechanism, multifidelity, experimental-design and null/misspecification families;
5. run frontier-model budget-one screening before expensive budget 30/100/300 studies.

A candidate that saturates across seeds at budget one is a calibration/on-ramp task, not an
open-optimization headline task. A candidate that improves development score without sealed
validation improvement remains optimization-only.
