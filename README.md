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

The repository contains **51 task packages in 47 metadata domains**:

- **7 certified core tasks**: Lennard–Jones clusters, spin glass, Poisson solver,
  matrix-multiplication rank, Cap Set, circle packing, and multilayer thin films.
- **28 candidate tasks** pending scientific certification, including intervention-based causal
  and active dynamical-law laboratories whose prediction and mechanism metrics are reported
  separately, a multi-spectrum NMR peak-mechanism/refusal task, and a multi-fidelity
  heat-exchanger Pareto-design task, a full-field lid-driven-cavity solver, active
  climate-response identification with explicit model-mismatch refusal, and a robust
  broadband acoustic-absorber design task, and a robust mixed-integer equilibrium-stage
  distillation design task, a multi-system stable finite-basis Hartree–Fock task, an IAPWS-IF97
  single-reheat Pareto-cycle task, robust room
  acoustics design, active convection--diffusion identification/design and active layered
  reflection acquisition/inversion with explicit model-inadequacy refusal.
- **16 quarantined tasks** with reproduced scientific-oracle, identifiability, provenance or
  shortcut defects; these remain inventory packages but are not admissible benchmark tasks.

The default CLI exposes only the certified core. `--all` explicitly shows the full
inventory. Certification status is not a difficulty claim: the inventory metadata contains
46 `hard` and 5 `flagship` packages, but only certified tasks are benchmark-admissible.

All candidate code runs in a networkless Bubblewrap sandbox with read-only mounts, resource
and process limits, and a typed JSON RPC boundary. The trusted parent alone imports the
oracle and validates metrics. Multi-world evaluators can explicitly reset the candidate
session at scientific-world boundaries; the active multi-world inverse tasks do so to prevent
module, imported-package or private-tmpfs state from revealing hidden world order. Candidate-
controlled exception text is reduced to a fixed label-blind failure taxonomy before it can enter
search feedback, preventing observations from being carried between worlds through exceptions.
The current audit reports:

- 244/244 unit, security, protocol, analysis and scientific-invariant tests passed after the
  RankineCycleOpt-v2 rebuild. The latest trusted task/security/baseline reports bind clean source
  revision `ec14510`; the trusted Rankine model analysis and 45-condition cross-task summary bind
  later clean evidence revisions.
- The latest 51×2 secure-baseline audit reports 51/51 deterministic, 51/51 valid, 51/51
  fail-closed and zero infrastructure failures.
- Current source manifest: 7 certified / 28 candidate / 16 quarantined. D-optimal design, quantum
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
The latest trusted clean-revision certification/security/baseline audits are v34/v18/v24. The
current source manifest is 7/28/16 and contains 35 internally admissible tasks, leaving an
approximate gap of 15 to the roughly 50-task target. The hash-bound cross-task summary v16
contains 45 normal single-run conditions over 23 tasks; it is calibration
evidence, not a leaderboard or population result.

The latest EdgeBench re-audit keeps its upstream facts at arXiv `2607.05155v1`, SForge
`a87350a` and public dataset `47846a4`. In addition to E1--E36, the science plan now preregisters
four unrun scope tests: raw instrument-to-claim error propagation (I6/E37), unit/coordinate/
representation metamorphic invariance (V4/E38), independent investigators with blinded synthesis
(T1/E39), and post-commit sealed downstream utilities (U1/E40). These are proposed experiments,
not new EdgeBench or Frontier-Science performance results. The expansion plan also prioritizes one
prospective evidence-synthesis task over another near-duplicate clean-simulator scalar task.

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
