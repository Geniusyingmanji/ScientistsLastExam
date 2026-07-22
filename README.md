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
- **16 candidate tasks** pending scientific certification, including intervention-based causal
  and active dynamical-law laboratories whose prediction and mechanism metrics are reported
  separately, a multi-spectrum NMR peak-mechanism/refusal task, and a multi-fidelity
  heat-exchanger Pareto-design task.
- **28 quarantined tasks** with reproduced scientific-oracle, identifiability, provenance or
  shortcut defects; these remain inventory packages but are not admissible benchmark tasks.

The default CLI exposes only the certified core. `--all` explicitly shows the full
inventory. Certification status is not a difficulty claim: the inventory metadata contains
47 `hard` and 2 `flagship` packages, but only certified tasks are benchmark-admissible.

All candidate code runs in a networkless Bubblewrap sandbox with read-only mounts, resource
and process limits, and a typed JSON RPC boundary. The trusted parent alone imports the
oracle and validates metrics. The current audit reports:

- 112/112 unit, security, protocol and scientific-invariant tests passed.
- The latest 51×2 secure-baseline audit reports 51/51 deterministic, 50/51 valid, 51/51
  fail-closed and zero infrastructure failures. The sole invalid baseline is the explicitly
  quarantined `ClimateScience/EnergyBalanceModel`.
- Current manifest: 7 certified / 16 candidate / 28 quarantined. D-optimal design, quantum
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

Machine-readable evidence lives in [`experiments/`](experiments/).
The original five dated P0–P2 reports were regenerated from clean source revision `f48b101`;
the post-repair 50-package audits bind revision `47c3613`; the subsequent wave-2 admission
audit quarantines seven additional defective candidates. The two P2 smokes are baseline-only; the repository does not yet contain
credible multi-seed model-performance evidence. A clean-revision GPT-5.5 budget-one core pilot
is recorded as task calibration, not a benchmark leaderboard.

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
