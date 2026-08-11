# Scientist's Last Exam

Scientist's Last Exam (SLE) is a research prototype for **cross-domain, executable,
budget-constrained scientific generative optimization**. An agent edits a runnable program,
a frozen deterministic oracle evaluates each candidate, and the benchmark records both the
best feasible artifact and the cost-aware trajectory used to find it.

The question it is built to answer is not "can a model score well once" but "does giving a model
feedback and more budget make it better" — the agentic, self-improving regime that AlphaFold-style
and AlphaEvolve-style results live in. Section [Does a task measure iteration](#does-a-task-measure-iteration)
gives the criterion, and the answer for the current inventory is a small number.

This repository is inspired by
[Frontier-Engineering](https://github.com/EinsiaLab/Frontier-Engineering). It is unrelated to
the text-question benchmark named *FrontierScience* in
[arXiv:2601.21165](https://arxiv.org/abs/2601.21165).

The Python package is still importable as `frontier_science`, which was this project's working
name; the CLI examples below reflect that. Renaming the module is a separate mechanical change.

> A higher simulator or verifier score demonstrates optimization only within the registered
> oracle. It does not by itself establish autonomous scientific discovery, mechanism recovery,
> physical validation, or real-world utility.

## At a glance

- **61 task packages** across **57 logical domains** and **7 broad disciplines**.
- **7 certified**, **45 candidate**, and **9 quarantined** tasks.
- Two tasks whose oracles are **community-standard scientific tooling** (Stim + PyMatching,
  RDKit) rather than a bespoke reimplementation, both scored **uncapped** against anchors
  recomputed at evaluation time, and both carrying a measured **difficulty ladder**.
- **2 of 52** tasks are so far shown to measure iterative improvement, against a criterion the
  repository can now apply to any task with paired runs.
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
| [Admission criterion sweep](.research/task_admission_verification_2026-08-11.md) | 2 of 52 tasks shown to measure iteration | Every recorded run, both conditions |

[`experiments/TRUST.md`](experiments/TRUST.md) is the append-only trust manifest. Study plans and
interpretations live in [`.research/`](.research/). Historical pre-sandbox reports are classified
`UNTRUSTED_PRE_SANDBOX` and must not be used as benchmark evidence.

## Recent findings

Full write-ups are in [`.research/`](.research/); each carries its own claim boundary.

**The evolvability gap depends on the task, not just on the budget.** Paired `normal` versus
`selection_blind` runs measure whether an oracle budget is better spent on a feedback loop or on
independent draws. Sweeping the budget on both community-oracle tasks, seed-paired:

| budget | 3 | 5 | 7 | 10 | 15 | 20 |
|---|---:|---:|---:|---:|---:|---:|
| Molecular | +0.311 | **+0.371** | +0.036 | −0.093 | — | — |
| decoder | +0.135 | +0.061 | — | +0.080 | **+0.172** | +0.111 |

On the molecular task the gap is **not monotone**: it peaks at budget 5 — the strongest result in
this project, eight paired wins out of eight, sign test p=0.0078 — then collapses, reaches parity
at 7, and crosses zero near **budget 7.8**. On the decoder task the gap is **positive at every
budget through 20**, three of five intervals excluding zero, and largest at 15.

Same searcher, same model, same protocol. **The crossover is a task property, not a searcher
property**, and the control arms say why: the decoder's open loop is flat from budget 5
(0.824, 0.869, 0.824, 0.845) while the molecular one climbs 0.404 → 0.970. A molecular draw can
land in a long right tail, so more draws keep helping; a decoder's per-draw quality is bounded by
what one generation can write, so refining beats redrawing and the feedback arm climbs to 0.995
against the matching anchor.

That implied a sharper admission rule than `Δ > 0`, measurable from the control arm alone: a task
measures iterative improvement to the extent that its open-loop control saturates with budget.
**That rule turned out to be necessary but not sufficient**, and the counterexample is in this
repository — see [Does a task measure iteration](#does-a-task-measure-iteration).
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
at budget 10 against the same open-loop control, greedy scores −0.093 and loses five of six
paired seeds, while OpenEvolve scores **+0.074** and wins eight of twelve. Both confidence
intervals span zero and the sign tests give p = 0.22 and p = 0.39, so this is consistent with the
lock-in explanation but does not establish it — the arms differ by 0.167 against a per-seed
spread near 1.1.

An interim read of the same comparison at n=10 gave +0.153, twice the final value. The two
missing cells were missing because of a crash, not a result, but they were still not missing at
random: OpenEvolve scored 0.990 and 1.034 on them while the control happened to draw 1.325 and
1.336. Disappearing cells have to be recovered, not analysed around.
See [population search](.research/population_search_results_2026-08-09.md).

## Does a task measure iteration

A task earns its place here by measuring iterative improvement. That takes two conditions, and
the order matters:

1. **necessary** — the open-loop control must not saturate with budget. If best-of-N stops paying
   after a few draws, there is nothing left for a searcher to add.
2. **sufficient** — the feedback arm must beat the open-loop arm, and the gap must widen with
   budget rather than close.

Condition 1 alone was the earlier rule and it is not enough. `MedicinalChemistry/MolecularLeadOptimization`
at portfolio size 320 with a Tanimoto ceiling of 0.20 has a strictly climbing open-loop curve and
an evolvability gap flat at zero from budget 3 through 12, because every proposal sits on a low
plateau with no exploitable gradient. Passing 1 and failing 2 means a task is too hard to measure
with, not that it is a good task.

`scripts/report_admission_criterion.py` applies both conditions to every run in `runs/`, reading
each run's task and arm from its manifest rather than its directory name. Over 52 distinct tasks:

| verdict | (task, cohort) pairs |
|---|---:|
| measures iteration | 3 |
| gap closes within the budget range | 1 |
| headroom exists but feedback cannot climb it | 1 |
| apparent headroom on a single seed, never paired | 11 |
| headroom below the 0.01 materiality floor | 4 |
| no headroom — control flat over its second half | 31 |
| floor — control never leaves zero | 7 |
| insufficient evidence to judge | 11 |

**Ninety percent of those verdicts rest on a single open-loop seed.** Fifty-two of the 58 rows
with a saturation verdict — including all 31 `no headroom` and all 7 `floor` rows — come from a
screen that ran one seed per task. The one candidate later paired at four seeds moved from
"+0.4098 and climbing" to "+0.0000, flat", so a single seed can overstate headroom; by the same
token the `no headroom` and `floor` rows may understate it. Every row now prints its seed count
and a `measured` / `single_seed_screen` confidence label.

**Paired evidence exists for 3 of 52 tasks, and two pass.** The decoder passes in two independent
cohorts, with the gap growing from +0.052 at budget 3 to +0.080 at budget 10 (six of six paired
seeds) in one and +0.104 to +0.129 in the other. The molecular task's verdict is split by cohort,
which is the crossover at budget 7.8 showing up as disagreement — for that task a single gap
number is not reportable, only the curve is.

The 11 tasks with apparent headroom and no feedback arm are the only pool that can add qualifying
tasks, and they are where paired runs are being added next — but every one of those verdicts rests
on a **single** open-loop seed, and the first candidate actually paired inverted. `TrussWeightMinimization`
was ranked strongest on a one-seed second-half gain of +0.4098; four seeds put that gain at
+0.0000, and its feedback arm lost every seed from budget 8 onward, trailing by 0.37. Feedback
does not merely fail to help there, it hurts. Treat that ranking as a queue, not a finding.
Everything else is a statement about evidence rather than about the task. See
[task admission verification](.research/task_admission_verification_2026-08-11.md).

## Difficulty ladders

Both community-oracle tasks carry a `DIFFICULTY` level so that saturating one does not retire the
task. Level 1 reproduces the shipped instances and their recorded anchors exactly; a level with no
measured entry raises rather than being extrapolated.

Each ladder is a measured table rather than a formula, because both tasks punish the obvious
formula:

- On the decoder, difficulty cannot be raised by code distance. Below threshold a larger code
  drives the logical error rate down exponentially, so the anchor stops failing often enough to
  measure — a first attempt left a level-3 regime with 9 anchor failures. Each level instead
  pushes the physical error rate toward the circuit-level threshold near 1%. Shot counts then hold
  the *decoding workload* fixed, not the shot count: detectors grow as `d²`, so keeping the shots
  high silently made level 2 a 1.68× throughput test, and 24 of 29 feedback-arm failures there
  were timeouts.
- On the molecular task the two knobs interact through the reference panel. Tightening the
  diversity ceiling shrinks the retained portfolio *and* raises the anchor, because the panel is
  selected highest-QED-first and the survivors of a stricter ceiling are the better drugs. Past a
  point it breaks the panel outright.

Rungs are placed by the shape of the evolvability gap against budget, not by score. Level 1 of the
molecular task is effectively solved — the strongest submission this benchmark has produced scores
1.3363 against a QED ceiling near 1.35 — and its gap turns negative by budget 10. The level-2 rung
was chosen because its gap instead grows monotonically, −0.011 at budget 3 to +0.062 at budget 12
over eight paired seeds. That endpoint's interval includes zero; the evidence is the monotone
trend across five budget points, not the endpoint.

All ladder measurements use `greedy_rewrite` with searcher `gpt-5.5` at `reasoning_effort: low`.
The calibration ladders in each task's `references/known_best.md` were measured with GPT-5.6, so
the two are not comparable, and because the crossover is a task-and-searcher property the rung
placement is specific to this condition. Run manifests now record the model condition in readable
form, alongside the hash that binds it, so this cannot be ambiguous again.

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
with zero task-card issues and appear in the live inventory, but their measurements are not yet
trusted artifacts under `experiments/`, so the maturity ledger does not count them as internally
admitted. Each run records its own `task_contract_sha256`, so the groundwork is done. The
inventory guard itself was internally inconsistent — it asserted 61 packages while its status
counts summed to 59 — and now agrees with the live inventory.

**Four discovery tasks cannot report a false-discovery rate.** Their evaluators do measure it,
but publish the numerator as a count without the world count that would make it a rate, so the
discovery triple cannot be completed for them. `scripts/report_discovery_triple.py` now separates
this case from an axis that was never measured, because the two need different fixes. Publishing
the denominator edits the task package and therefore rebinds that task's analysis artifacts —
including the Track F negative result — so it is a governance step rather than a cleanup, and has
been left for a deliberate decision.

The sandbox itself is verified intact: `tests.test_secure_eval` passes and
`scripts/run_security_audit.py` passes 23/23 with `trusted_evidence: true`.

## Reproduce checks

```bash
python -m unittest -v tests.test_benchmark_layout tests.test_secure_eval
python scripts/run_security_audit.py --output /tmp/security.json
python scripts/audit_tasks.py --output /tmp/certification.json
python scripts/report_admission_criterion.py --runs runs --output /tmp/admission.json
python -m unittest discover -s tests -q
```

New machine-readable reports include their command, Git revision, scoped source-tree state,
changed paths, execution status, and trust decision. A dated artifact is trusted evidence only
when its declared checks pass on a clean, known revision.

## Contributing

The current priority is hardening and independently reviewing the existing inventory. Start with
[`CONTRIBUTING.md`](CONTRIBUTING.md); new tasks enter as candidates and cannot self-certify.
