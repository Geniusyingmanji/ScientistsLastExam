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

- **61 task packages** across **57 logical domains** and **7 broad disciplines**.
- **7 certified**, **45 candidate**, and **9 quarantined** tasks.
- Two tasks whose oracles are **community-standard scientific tooling** (Stim + PyMatching,
  RDKit) rather than a bespoke reimplementation, both scored **uncapped** against anchors
  recomputed at evaluation time.
- Deterministic black-box evaluation through a networkless Bubblewrap sandbox.
- A built-in iterative rewrite baseline plus OpenEvolve, AB-MCTS, and ShinkaEvolve backends.
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
| Chemistry | 13 | 1 | 10 | 2 |
| Computer Science | 4 | 2 | 2 | 0 |
| Earth Science | 6 | 0 | 6 | 0 |
| Engineering | 18 | 0 | 14 | 4 |
| Mathematics | 5 | 2 | 3 | 0 |
| Physics | 9 | 2 | 5 | 2 |
| **Total** | **61** | **7** | **45** | **9** |

The certified core currently consists of:

- `Chemistry/LennardJonesCluster`
- `Algorithm/MatrixMultiplicationRank`
- `ScientificComputing/PoissonSolver2D`
- `Mathematics/CapSet`
- `Optimization/CirclePacking`
- `Photonics/MultilayerThinFilm`
- `Physics/SpinGlassGroundState`

Run `python -m frontier_science list --all` for the authoritative live inventory. The
domain-to-discipline mapping is in
[`frontier_science/benchmark_layout.py`](frontier_science/benchmark_layout.py); admission status
is in [`frontier_science/certification.yaml`](frontier_science/certification.yaml).

## Community-oracle tasks

Every one of the original 59 evaluators depends only on NumPy, SciPy and the standard library —
a dependency scan over all 29,087 lines of oracle code finds no RDKit, ViennaRNA, Stim, PySCF,
ASE or BioPython. Task narratives cite real science, but the oracles are author-written
reduced-order reimplementations, and none has completed external domain review. A score
therefore measures agreement with the author's NumPy code, not with the science.

Two tasks were added to close that gap. Both put a community-standard toolkit in the oracle and
recompute their anchor at evaluation time rather than quoting a number from a paper.

| Task | Oracle | Anchor | Scoring |
|---|---|---|---|
| `QuantumErrorCorrection/QuantumErrorDecoder` | **Stim** rotated surface-code circuits, seeded sampling | **PyMatching 2** minimum-weight perfect matching, recomputed per run | uncapped; matching MWPM = 1.0 |
| `MedicinalChemistry/MolecularLeadOptimization` | **RDKit** QED, Ertl–Schuffenhauer SA score, Lipinski/Veber descriptors, PAINS catalogue, Morgan/Tanimoto | mean drug-likeness of structurally distinct approved drugs from a 20-drug panel whose SMILES were each verified against published molecular weights | uncapped; approved-drug quality = 1.0 |

Calibration ladders are in each task's `references/known_best.md`. On the decoder task:
baseline 0.0, two NumPy/SciPy reference decoders at 0.2395 and 0.3832, GPT-5.6 budget-one best
of five draws 0.7391, OpenEvolve at budget 40 **0.9932**, PyMatching anchor 1.0.

The oracle runs in the trusted parent, not the sandbox, so adding a scientific library to an
evaluator does not touch the isolation model. A task may additionally expose a toolkit to its
*candidate* through `frontier_eval/candidate_packages.txt`, expanded via a fixed allowlist in
trusted code; verification-side anchors such as PyMatching are deliberately excluded from that
allowlist.

## Quickstart

Run commands from the repository root. Core evaluation requires Python, PyYAML, NumPy, SciPy,
and Linux Bubblewrap (`bwrap`). The checked-in environment is Python 3.8; optional search
backends have newer Python requirements. Per-task oracle dependencies are pinned in each
`verification/requirements.txt`.

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

Task names are accepted when unambiguous. Candidate and quarantined packages require the
explicit `--allow-uncertified` flag.

### Configure an LLM

```bash
cp frontier_science/conf/llm/openai_compatible.example.yaml \
   frontier_science/conf/llm/local.yaml
export OPENAI_API_KEY=your_key_here
python -m frontier_science smoke
```

`local.yaml` is git-ignored. Configuration resolution is `--llm-config`, then `FS_LLM_CONFIG`,
then `conf/llm/local.yaml`, then the committed example. Both OpenAI-compatible Chat Completions
and Responses wires are supported. Reasoning models on the chat wire reject `max_tokens`; set
`chat_max_tokens_field: max_completion_tokens` for those. Never commit credentials.

### Run an optimization trajectory

```bash
python -m frontier_science run \
  --task Chemistry/LennardJonesCluster \
  --algorithm greedy_rewrite \
  --budget 10 \
  --seed 0 \
  --workdir runs/lj/seed-0
```

Available algorithms are `greedy_rewrite` (built-in single-incumbent full-file rewriting),
`openevolve` (0.2.26, Python ≥3.10), `abmcts` (TreeQuest AB-MCTS-A, Python ≥3.11) and
`shinkaevolve`. A named backend fails explicitly if unavailable; it never silently falls back.

`selection_blind` is the strict open-loop control: proposals always see the frozen baseline and
its public metrics, while evaluation results are retained only for offline selection.

## Evaluation and security model

The trusted parent process imports each hidden oracle. Candidate code runs separately through a
typed JSON-RPC boundary inside Bubblewrap with no network namespace, read-only mounts, a private
temporary filesystem, CPU/memory/file/descriptor/process limits, seccomp blocking process and
thread creation, fixed numerical thread counts, and a label-blind failure taxonomy that removes
candidate-controlled exception text from search feedback.

Site-packages are resolved for the interpreter that will actually import them, not for the
parent process — these differ whenever a search backend runs the harness inside its own
virtualenv.

This design reduces common leakage and host-access risks; it does not prove absence of
training-data contamination, semantic shortcuts, simulator error, or hidden scientific
confounding.

## Task package contract

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
│   ├── readonly_files.txt
│   └── candidate_packages.txt    # optional; domain toolkits exposed to the candidate
├── verification/
│   ├── evaluator.py              # hidden frozen oracle
│   └── requirements.txt          # optional; pinned oracle dependencies
└── references/
    └── known_best.md             # required for uncapped tasks
```

The evaluator returns at least finite numeric `combined_score` and `valid` fields. Adding a
package makes it discoverable, not certified. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the
complete contract and certification requirements.

## Certification and evidence

Certification status describes evidence quality, not task difficulty: `certified` is admitted to
the default benchmark, `candidate` is retained for calibration but missing one or more gates, and
`quarantined` marks a reproduced material defect.

| Evidence | Result | Scope |
|---|---|---|
| [Certification audit v65](experiments/task_certification_audit_2026-07-26_v65.json) | 7 certified / 43 candidate / 9 quarantined | Inventory and admission gates at the 59-package revision |
| [Secure baseline v46](experiments/secure_baseline_determinism_2026-07-26_v46.json) | 59/59 deterministic, valid, fail-closed | Two baseline evaluations per task |
| [Security audit v49](experiments/security_audit_2026-07-27_v49.json) | 23/23 tests passed | Sandbox and protocol regressions |
| [GPT-5.6 50-task census](experiments/gpt56_science_census_analysis_2026-08-06_v1.json) | 50/50 cells; 36/50 valid proposals | Budget-one screen; challenge gate fails |
| [Track F confirmatory analysis](experiments/track_f_analysis_2026-07-26_v1.json) | no identified feedback advantage | Preregistered, n=48/arm, on ActiveLawDiscovery |

[`experiments/TRUST.md`](experiments/TRUST.md) is the append-only trust manifest. Study plans and
interpretations live in [`.research/`](.research/). Historical pre-sandbox reports are classified
`UNTRUSTED_PRE_SANDBOX` and must not be used as benchmark evidence.

## Recent findings

Full write-ups are in [`.research/`](.research/); each carries its own claim boundary.

**The evolvability gap, and its budget dependence.** Paired `normal` versus `selection_blind`
runs measure whether an oracle budget is better spent on a feedback loop or on independent
draws. At budget 3 both community-oracle tasks show a positive gap whose 95% CI excludes zero at
both the full-horizon and token-matched endpoints — the first positive feedback result in this
project, and the opposite sign to the Track F null. **At budget 10 the gap shrinks 41% on the
decoder task and reverses on the molecular task**, where the open-loop control wins five of six
paired seeds. Best-of-N strengthens as N grows while a single incumbent locks into a basin, and
feedback's token overhead compounds (1.26× → 1.52×). A `Δ > 0` admission rule is therefore
underspecified without naming the budget and the searcher.
See [evolvability_gap](.research/evolvability_gap_2026-08-09.md) and
[budget dependence](.research/evolvability_gap_budget_dependence_2026-08-09.md).

**The search backends had never produced a data point, for mechanical reasons.** Across 2822
recorded algorithm invocations the only search algorithm ever run was `greedy_rewrite`. Six
independent blockers were found and four fixed: the sandbox mounted no packages under any
backend virtualenv; the chat wire hardcoded `max_tokens`; OpenEvolve silently discarded
candidates over 10,000 characters (29 of 40 iterations on the decoder task, which moved its
reported score by 0.054); and upstream evaluator timeouts aborted whole runs. ShinkaEvolve's own
request body and an AB-MCTS bandit key error remain open.
See [E0 unblocking](.research/e0_backend_unblocking_2026-08-08.md).

**A certified task turned out to have no measurable difficulty.** With the backends working,
`Optimization/CirclePacking` is solved in three oracle calls by OpenEvolve and reaches 0.999989
under plain greedy — the two searchers are indistinguishable because the task is easy at
`N = 7, 10, 13`, where the Packomania values are long settled. No certified task has ever been
exposed to a population search, so every difficulty claim on record was calibrated against
`greedy_rewrite` at budget one to three.

**Population search does not reproduce greedy's reversal — directionally.** On the molecular task
at budget 10 against the same open-loop control, greedy scores −0.093 (1 of 6 paired wins) while
OpenEvolve scores +0.153 (8 of 10). Both confidence intervals span zero and the sign tests give
p = 0.22 and p = 0.11, so this is consistent with the lock-in explanation but does not establish
it. See [population search](.research/population_search_results_2026-08-09.md).

## Known state before relying on this branch

Two things are deliberately left open rather than papered over.

**The trusted runtime changed.** `frontier_science/secure_eval.py` and `benchmark_layout.py`
were modified, and `tests/test_runtime_migration.py` passes at the previous revision and fails
here. The project binds frozen analysis artifacts to a `runtime_source_sha256`, so changing the
runtime unbinds them; the remedy is to register a runtime migration audit, which re-certifies the
trusted runtime and should be a deliberate decision. Note that this guard fires for **any** new
task in a new domain. Nine per-task analysis tests also fail and are explicitly recorded as
unattributed — they read `runs/` paths stored as absolute paths, so they error in a clone or
worktree. See [runtime governance](.research/runtime_change_governance_2026-08-09.md).

**The new tasks are not registered as maturity evidence.** They pass `scripts/audit_tasks.py`
with zero task-card issues, but their GPT-5.6 measurements are not yet trusted artifacts under
`experiments/`, so the maturity ledger still counts 50 internally admitted tasks rather than 52.
Both task contracts have had zero contract-path commits since their runs began and each run
records its own `task_contract_sha256`, so the groundwork is done.

The sandbox itself is verified intact: `tests.test_secure_eval` passes and
`scripts/run_security_audit.py` passes 23/23 with `trusted_evidence: true`.

## Reproduce checks

```bash
python -m unittest -v tests.test_benchmark_layout tests.test_secure_eval
python scripts/run_security_audit.py --output /tmp/security.json
python scripts/audit_tasks.py --output /tmp/certification.json
python -m unittest discover -s tests -q
```

New machine-readable reports include their command, Git revision, scoped source-tree state,
changed paths, execution status, and trust decision. A dated artifact is trusted evidence only
when its declared checks pass on a clean, known revision.

## Contributing

The current priority is hardening and independently reviewing the existing inventory. Start with
[`CONTRIBUTING.md`](CONTRIBUTING.md); new tasks enter as candidates and cannot self-certify.
