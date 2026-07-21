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

The repository contains **50 task packages in 47 metadata domains**:

- **7 certified core tasks**: Lennard–Jones clusters, spin glass, Poisson solver,
  matrix-multiplication rank, Cap Set, circle packing, and multilayer thin films.
- **18 candidate tasks** pending scientific certification, including an intervention-based
  causal-mechanism laboratory whose prediction and mechanism metrics are reported separately.
- **25 quarantined tasks** with reproduced scientific-oracle, identifiability, provenance or
  shortcut defects; these remain inventory packages but are not admissible benchmark tasks.

The default CLI exposes only the certified core. `--all` explicitly shows the full
inventory. Certification status is not a difficulty claim: the inventory metadata contains
47 `hard` and 2 `flagship` packages, but only certified tasks are benchmark-admissible.

All candidate code runs in a networkless Bubblewrap sandbox with read-only mounts, resource
and process limits, and a typed JSON RPC boundary. The trusted parent alone imports the
oracle and validates metrics. The current audit reports:

- 66/66 unit, security, protocol and scientific-invariant tests passed.
- The current clean-revision audit covers all 50 packages: 50/50 baselines were deterministic
  across two secure runs.
- 49/50 baselines were valid; `ClimateScience/EnergyBalanceModel` returned a non-finite
  oracle metric and was correctly rejected fail-closed.
- All 50 packages failed closed and there were no infrastructure failures. The newly added
  mechanism task passed invariant, callback-budget and deterministic secure-baseline tests.
- Current manifest: 7 certified / 18 candidate / 25 quarantined.

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
`best_program.py` artifacts.
Pinned optional dependencies are listed in
[`requirements-upstream.txt`](requirements-upstream.txt); TreeQuest needs a Python 3.11
environment, so it cannot share this host's Python 3.8 runtime.

Run a preregistered multi-seed experiment with:

```bash
python scripts/batch_evolve.py \
  --algorithms greedy_rewrite \
  --feedback-modes normal,none,shuffled \
  --seeds 0,1,2,3,4 --budget 30
```

The runner reports terminal best score, best-so-far AUC over charged proposal/benchmark
`budget_units`, actual `oracle_calls` as a separate count, wall time, token/cost fields, and
Student-t 95% confidence intervals. Thus, for example, an unparsable proposal consumes a
budget unit without fabricating an oracle call. Here `none`/`shuffled` control only the metrics
shown in the proposal prompt; incumbent/parent selection still uses true oracle scores, and each
summary records that scope. They are diagnostic prompt-feedback ablations, not yet strict causal
no-feedback controls. Unsupported combinations fail rather than changing semantics.

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
