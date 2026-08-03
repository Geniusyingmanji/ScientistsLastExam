# Frontier-Science

Frontier-Science is a research prototype for **cross-domain, executable,
budget-constrained scientific generative optimization**. An agent edits a runnable program,
a frozen deterministic oracle evaluates each candidate, and the benchmark records both the
best feasible artifact and the cost-aware trajectory used to find it.

This repository is inspired by
[Frontier-Engineering](https://github.com/EinsiaLab/Frontier-Engineering). It is unrelated to
the text-question benchmark named *FrontierScience* in
[arXiv:2601.21165](https://arxiv.org/abs/2601.21165).

> A higher simulator or verifier score demonstrates optimization only within the registered
> oracle. It does not by itself establish autonomous scientific discovery, mechanism recovery,
> physical validation, or real-world utility.

## At a glance

- **59 task packages** across **55 logical domains** and **7 broad disciplines**.
- **7 certified**, **43 candidate**, and **9 quarantined** tasks.
- Deterministic black-box evaluation through a networkless Bubblewrap sandbox.
- A built-in iterative rewrite baseline plus optional OpenEvolve, AB-MCTS, and
  ShinkaEvolve backends.
- Hash-bound experiment reports with Git revision, command, source-tree state, and explicit
  trust decisions.

The default CLI exposes only certified tasks. Candidates remain visible for research and
calibration, while quarantined packages preserve known defects for auditability; neither group
is benchmark-admissible by default.

## Benchmark organization

Tasks are grouped on disk by broad discipline, while their stable public IDs retain the more
specific metadata domain:

```text
benchmarks/<Discipline>/<Task>/
task id: <Domain>/<Task>
```

For example, `benchmarks/Physics/DiffractionGratingDesign/` has the stable task ID
`Optics/DiffractionGratingDesign`. Code and reports should use the task ID; filesystem tooling
should use the discipline path.

| Discipline | Tasks | Certified | Candidate | Quarantined |
|---|---:|---:|---:|---:|
| Biology | 6 | 0 | 5 | 1 |
| Chemistry | 12 | 1 | 9 | 2 |
| Computer Science | 4 | 2 | 2 | 0 |
| Earth Science | 6 | 0 | 6 | 0 |
| Engineering | 18 | 0 | 14 | 4 |
| Mathematics | 5 | 2 | 3 | 0 |
| Physics | 8 | 2 | 4 | 2 |
| **Total** | **59** | **7** | **43** | **9** |

The certified core currently consists of:

- `Chemistry/LennardJonesCluster`
- `Algorithm/MatrixMultiplicationRank`
- `ScientificComputing/PoissonSolver2D`
- `Mathematics/CapSet`
- `Optimization/CirclePacking`
- `Photonics/MultilayerThinFilm`
- `Physics/SpinGlassGroundState`

Run `python -m frontier_science list --all` for the authoritative live inventory, including
discipline, logical domain, certification status, difficulty, and oracle type. The domain-to-
discipline mapping is defined in
[`frontier_science/benchmark_layout.py`](frontier_science/benchmark_layout.py), and admission
status is defined in
[`frontier_science/certification.yaml`](frontier_science/certification.yaml).

## Quickstart

Run commands from the repository root. Core evaluation requires Python, PyYAML, NumPy, SciPy,
and Linux Bubblewrap (`bwrap`). The checked-in environment used for the latest trusted reports
is Python 3.8; optional search backends have newer Python requirements.

```bash
# Show certified tasks, then the complete inventory.
python -m frontier_science list
python -m frontier_science list --all

# Evaluate the bundled baseline for a certified task.
python -m frontier_science eval --task Chemistry/LennardJonesCluster

# Evaluate another candidate implementation.
python -m frontier_science eval \
  --task Chemistry/LennardJonesCluster \
  --candidate /path/to/solution.py
```

Task names are accepted when unambiguous, so `--task LennardJonesCluster` also works. Candidate
and quarantined packages require the explicit `--allow-uncertified` flag.

### Configure an LLM

Copy the public OpenAI-compatible example and provide credentials through the environment:

```bash
cp frontier_science/conf/llm/openai_compatible.example.yaml \
   frontier_science/conf/llm/local.yaml
export OPENAI_API_KEY=your_key_here
# Edit local.yaml for the endpoint, wire protocol, and model.
python -m frontier_science smoke
```

`local.yaml` is git-ignored. Configuration resolution is:

1. `--llm-config <path>`
2. `FS_LLM_CONFIG`
3. `frontier_science/conf/llm/local.yaml`
4. the committed example

The built-in client supports OpenAI-compatible Chat Completions and Responses endpoints.
Never commit credentials.

### Run an optimization trajectory

```bash
python -m frontier_science run \
  --task Chemistry/LennardJonesCluster \
  --algorithm greedy_rewrite \
  --budget 10 \
  --seed 0 \
  --workdir runs/lj/seed-0
```

Use `--resume` with the same work directory to continue an interrupted run. Every backend
routes candidate scoring through the same trusted evaluator and writes unified trajectory,
summary, checkpoint, and best-program artifacts.

Available algorithms are:

- `greedy_rewrite`: built-in single-incumbent full-file rewriting.
- `openevolve`: OpenEvolve 0.2.26; optional, Python 3.10 or newer.
- `abmcts`: TreeQuest AB-MCTS-A; optional, Python 3.11 or newer.
- `shinkaevolve`: ShinkaEvolve; optional, Python 3.10 or newer.

Pinned optional dependencies are in
[`requirements-upstream.txt`](requirements-upstream.txt). A named backend fails explicitly if
its dependency or supported interface is unavailable; it never silently falls back to
`greedy_rewrite`.

### Run a multi-seed study

```bash
python scripts/batch_evolve.py \
  --algorithms greedy_rewrite \
  --feedback-modes normal,selection_blind \
  --seeds 0,1,2,3,4 \
  --budget 30
```

The batch runner records best score, best-so-far AUC over charged budget units, actual oracle
calls, wall time, token usage, configured cost, and confidence intervals. `selection_blind` is
the strict open-loop control: proposals always see the frozen baseline and its public metrics,
while evaluation results are retained only for offline selection. Other feedback modes are
diagnostic prompt ablations and do not imply the same causal control.

Local seeds control local sampling and identify replicates. They are not server-side model
seeds unless the provider explicitly exposes and honors such a control.

## Evaluation and security model

The trusted parent process imports each hidden oracle. Candidate code runs separately through a
typed JSON-RPC boundary inside Bubblewrap with:

- no network namespace access;
- read-only runtime and candidate mounts;
- a private temporary filesystem;
- CPU, memory, file, descriptor, and process limits;
- seccomp blocking process and thread creation;
- fixed numerical thread counts; and
- a label-blind failure taxonomy that removes candidate-controlled exception text from search
  feedback.

Multi-world evaluators can reset the candidate process and private temporary filesystem at world
boundaries, preventing state from revealing hidden execution order. The trusted runtime alone
validates metric shape and finiteness.

This design reduces common leakage and host-access risks; it does not prove absence of training-
data contamination, semantic shortcuts, simulator error, or hidden scientific confounding.

## Task package contract

Each package is auto-discovered at `benchmarks/<Discipline>/<Task>/` and normally contains:

```text
<Task>/
├── Task.md                       # agent-visible task description
├── TASK_CARD.yaml                # scientific evidence and review record
├── solution.py                   # weak but valid baseline
├── frontier_eval/
│   ├── metadata.yaml             # logical domain and task metadata
│   ├── initial_program.txt
│   ├── candidate_destination.txt
│   ├── entrypoint.txt
│   ├── constraints.txt
│   ├── agent_files.txt
│   └── readonly_files.txt
└── verification/
    └── evaluator.py              # hidden frozen oracle
```

The evaluator returns at least finite numeric `combined_score` and `valid` fields. Adding a
package makes it discoverable, not certified. Certification also requires deterministic
behavior, sandbox compatibility, scientific invariants, defensible normalization, stable
citations, a task card, and independent review evidence.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the complete contract, task generator workflow,
review checklist, and certification requirements.

## Certification and evidence

Certification status describes evidence quality, not task difficulty:

- `certified`: admitted to the default benchmark after all required gates pass.
- `candidate`: retained for calibration or research but still missing one or more external,
  scientific, robustness, contamination, or review gates.
- `quarantined`: a reproduced material defect makes the package inadmissible until repaired and
  re-audited.

The inventory contains 50 `hard` and 9 `flagship` packages, but those labels do not override
certification.

Key trusted artifacts include:

| Evidence | Result | Scope |
|---|---|---|
| [Certification audit v65](experiments/task_certification_audit_2026-07-26_v65.json) | 7 certified / 43 candidate / 9 quarantined | Inventory and admission gates at clean revision `c98e28c` |
| [Secure baseline v46](experiments/secure_baseline_determinism_2026-07-26_v46.json) | 59/59 deterministic, valid, and fail-closed | Two baseline evaluations per task at clean revision `1565e22` |
| [Security audit v49](experiments/security_audit_2026-07-27_v49.json) | 23/23 tests passed | Sandbox and protocol regressions at clean revision `ab0c393` |
| [Full suite v28](experiments/full_test_suite_2026-07-30_v28.json) | 653/653 tests passed | Hash-bound historical test report at clean revision `549d588` |
| [Science summary v28](experiments/science_calibration_summary_2026-07-25_v28.json) | 69 normal single-run conditions across 35 tasks | Calibration only; heterogeneous science axes are not averaged |
| [Two-hour exploratory analysis](experiments/exploratory_2h_analysis_2026-07-30_v1.json) | 7/7 declared cells completed | Result-selected exploratory screen, not confirmatory or population evidence |

The current discipline-layout branch additionally passes 662/662 local tests. Because those
tests ran on a source-dirty pre-commit tree, they are implementation verification rather than a
new trusted dated evidence artifact.

[`experiments/TRUST.md`](experiments/TRUST.md) is the append-only trust manifest and the primary
index for dated reports. Detailed study plans and interpretations live in [`.research/`](.research/),
including the [two-hour result note](.research/exploratory_2h_results_2026-07-30_v1.md) and
[task maturity ledger](.research/task_maturity_ledger_2026-07-27_v4.md).

Historical pre-sandbox reports are retained for provenance but classified
`UNTRUSTED_PRE_SANDBOX`; they must not be used as benchmark evidence.

## Reproduce checks

Fast structural and security checks:

```bash
python -m unittest -v tests.test_benchmark_layout tests.test_runtime_migration
python scripts/run_security_audit.py --output /tmp/security.json
python scripts/audit_tasks.py --output /tmp/certification.json
python scripts/audit_quarantined_tasks.py --output /tmp/quarantined.json
```

Longer inventory and full-suite checks:

```bash
python scripts/run_secure_baseline.py \
  --repeats 2 \
  --output /tmp/baselines.json
python -m unittest discover -s tests -q
```

Task-family admission audits and analysis scripts are kept in [`scripts/`](scripts/). New
machine-readable reports include their command, Git revision, scoped source-tree state, changed
paths, execution status, and trust decision. A dated artifact is trusted evidence only when its
declared checks pass on a clean, known revision.

## Contributing

The current priority is hardening and independently reviewing the existing inventory. Fixes,
scientific tests, task cards, and carefully justified new tasks are welcome. Start with
[`CONTRIBUTING.md`](CONTRIBUTING.md); new tasks enter as candidates and cannot self-certify.
