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

- **63 task packages** across **58 logical domains** and **7 broad disciplines**.
- **7 certified**, **47 candidate**, and **9 quarantined** tasks.
- Four tasks whose oracles are **community-standard scientific tooling** (Stim + PyMatching,
  RDKit, ViennaRNA, nmrsim) rather than a bespoke reimplementation, each anchored on a value or a
  routine recomputed at evaluation time, and each carrying a measured **difficulty ladder**.
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
| Biology | 7 | 0 | 6 | 1 |
| Chemistry | 14 | 1 | 11 | 2 |
| Computer Science | 4 | 2 | 2 | 0 |
| Earth Science | 6 | 0 | 6 | 0 |
| Engineering | 18 | 0 | 14 | 4 |
| Mathematics | 5 | 2 | 3 | 0 |
| Physics | 9 | 2 | 5 | 2 |
| **Total** | **63** | **7** | **47** | **9** |

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

Three tasks were added to close that gap. Each puts a community-standard toolkit in the oracle and
recomputes its anchor at evaluation time rather than quoting a number from a paper. The third also
answers a question the first two leave open: whether the anchor can be a routine the community
actually uses rather than a value. `RNAEnsembleDesign` runs ViennaRNA's own designer inside the
evaluator, restart-matched so a candidate cannot beat it by calling it more often — a single call
scores 0.576, measured through the harness.

| Task | Oracle | Anchor | Scoring |
|---|---|---|---|
| `QuantumErrorCorrection/QuantumErrorDecoder` | **Stim** rotated surface-code circuits, seeded sampling | **PyMatching 2** minimum-weight perfect matching, recomputed per run | uncapped; matching MWPM = 1.0 |
| `RNAEngineering/RNAEnsembleDesign` | **ViennaRNA** partition function over the Turner nearest-neighbour model; ensemble defect | ViennaRNA's own `inverse_pf_fold`, best of three restarts by ensemble defect, recomputed per run | uncapped; matching the reference designer = 1.0 |
| `Spectroscopy/SpinSystemInference` | **nmrsim** full Zeeman-plus-coupling Hamiltonian, diagonalised | least-squares fit of the nmrsim forward model, shipped under `verification/` and run at scoring time | clipped; mechanism recovery reported apart from false-discovery rate and refusal |
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

1. **necessary** — the open-loop control must *saturate* with budget. A control that keeps
   climbing means best-of-N is not exhausted, so independent sampling will eventually overtake
   any searcher and whatever gap you measured was an artefact of the budget you picked.
2. **sufficient** — with best-of-N exhausted, the feedback arm must still beat it, and the gap
   must widen with budget rather than close.

The sign of condition 1 reads backwards at first glance, and an earlier version of this section
had it inverted — it asked for a control that keeps climbing, which disqualified every task that
actually passes. The evidence sits in this repository: the decoder's control is flat from budget 5
onward and its feedback arm pulls further ahead the longer it runs, while the molecular task's
control climbs 0.404 → 0.970 and its gap crosses zero near budget 7.8. Refining beats redrawing
precisely where redrawing has stopped paying. A saturated control is not a solved task — `floor`,
where the control never leaves zero, is reported separately because nothing is measurable there
either.

`scripts/report_admission_criterion.py` applies both conditions to every run in `runs/`, reading
each run's task and arm from its manifest rather than its directory name, pooling open-loop seeds
across cohorts (saturation is one-armed) while keeping gaps within a cohort (arms from different
cohorts were never paired). Over 52 tasks:

| verdict | tasks |
|---|---:|
| measures iteration | 5 |
| measures iteration, but one paired seed carries it | 1 |
| feedback actively harmful | 3 |
| feedback harmful, but one paired seed carries it | 3 |
| arms indistinguishable — gap too small to matter | 1 |
| control exhausted, feedback arm never run | 25 |
| control still climbing — best-of-N not exhausted | 7 |
| judged on fewer than three seeds | 2 |
| floor — control never leaves zero | 6 |

A gap counts as a difference only when it is large next to the scores being compared — at least 2%
of the open-loop mean. Sign alone was not enough: `RNAEngineering/RNAEnsembleDesign` trailed by
0.0021 against scores near 1.0, two parts in a thousand, and the criterion was calling that
"harmful" with the same word it gave a task trailing by 0.37 against scores near 0.5.

**Paired evidence exists for 15 of 53 tasks, and five pass:** `QuantumErrorCorrection/QuantumErrorDecoder`,
`Spectroscopy/NMRSpectrumFitting`, `Astrodynamics/LowThrustTransfer`,
`ProteinEngineering/ProteinStabilityDesign` and `MaterialsScience/AlloyHardnessOptimization`.

| task | gap at budget 3 → 12 | last budget | seeds | drop-one-seed |
|---|---|---|---:|---:|
| `QuantumErrorCorrection/QuantumErrorDecoder` | +0.104 → +0.129 | 5/6 | 6 | +0.133 |
| `Spectroscopy/NMRSpectrumFitting` | +0.085 → +0.173 | 3/4 | 4 | +0.097 |
| `Astrodynamics/LowThrustTransfer` | −0.011 → +0.089 | 3/4 | 4 | +0.031 |
| `ProteinEngineering/ProteinStabilityDesign` | +0.032 → +0.035 | 5/5 | 6 | +0.017 |

A sixth was on this list two seeds ago and is not now.
`ChemicalKinetics/ReactionMechanismFitting` showed the largest gap in the inventory, +0.423 with
two paired seeds and no losses; at four seeds it reversed sign and now reads as harmful, carried by
one seed in that direction too. Nothing about the task changed — the evidence did.

**Feedback is actively harmful on nearly as many tasks as it clearly helps.** Three tasks —
`StructuralEngineering/TrussWeightMinimization`, `Turbulence/RANSCalibration` and
`Thermodynamics/HeatExchangerDesign` — score materially worse with feedback than their own
open-loop controls, and two more read that way on a single seed. This is not a
harness fault: pass rates are comparable between the arms, and on the decoder task the mechanism is
visible — independent draws find a long right tail that an incumbent-anchored search never
explores. A benchmark for iterative improvement has to be able to report that iteration sometimes
costs you, and this one does.

The last column is the mean after dropping whichever single seed helps the conclusion most. With
four to six seeds a verdict can be one seed deep, so the report computes it and labels any gap it
flips; all four survive at their final budget. `LowThrustTransfer` does flip at budget 5, which is
visible in its curve and is why the trend across budgets is what the verdict rests on.

The decoder is the strongest, passing in two independent cohorts. `ProteinStabilityDesign` has the
smallest effect but the tightest: four of four paired seeds at budgets 8, 10 and 12 with a
standard error near 0.013, so its gap sits about three standard errors from zero. The other two
carry wider intervals on four seeds and are provisional. Effect size and evidence strength are
different things here — `NMRSpectrumFitting` has a gap four times larger than
`ProteinStabilityDesign` and a weaker case for it.

**The drop-one-seed guard changes two verdicts.** `MolecularDynamics/ForceFieldCalibration` reads
a gap of +0.0367 at budget 12 that becomes +0.0000 when one seed is removed — one of its four
paired seeds had any gap at all — and `Catalysis/CatalystDeactivationLab` reads −0.022 that flips
positive under the same test. Both are reported as one-seed-deep rather than as findings. The
guard cuts in both directions on purpose: a harmful verdict can rest on one seed exactly as easily
as a favourable one.

The clearest case: `StructuralEngineering/TrussWeightMinimization`
trails its own open-loop control by 0.37 and loses every paired seed from budget 8 onward
(−0.30 after dropping the most favourable seed). Both arms pass roughly half their submissions —
0.50 open-loop against 0.40 with feedback — so this is not the contract rejecting the feedback
arm's work. The open-loop arm reached 0.9979 on one seed while the feedback arm's best across all
four was 0.4143: independent draws find the tail, and anchoring on an incumbent does not.

**31 tasks have an exhausted control and have never been paired.** That is the pool that can add
qualifying tasks, and it is where paired runs are going next, ordered by how much room the
control leaves: a control that has run out at 0.998 gives a searcher almost nothing to
demonstrate, while `Catalysis/CatalystDeactivationLab` and `MolecularDynamics/ForceFieldCalibration`
run out near 0.12.

### A rejected proposal is not always a contract failure

`scripts/report_protocol_vs_science.py` used to report one pass rate, valid proposals over total,
and that number answered no clean question. It counted a candidate that crashed together with a
candidate that ran to completion and was then ruled infeasible — the first never reached the
science, the second reached it and failed there, and several of the second group carry a real
score the oracle computed before rejecting them. Across the paired and screening cohorts the
split is 162 that never executed against 101 that executed and were infeasible, so roughly two
fifths of rejections are scientific rather than contractual. The report now gives
`execution_rate` and `feasible_given_executed` separately.

### How much of this is measurement, and how much is a screen

The inventory was originally swept one open-loop seed per task; 48 of 52 tasks had exactly one
seed anywhere in the repository. A seeding pass has since raised 50 of 52 to three or more, and it
changed verdicts: 17 of 52 tasks moved category. That pass also exposed a defect in the criterion
itself. Saturation was judged on the *mean* second-half gain across seeds, and because a
best-so-far curve is monotone, that gain is never negative — so the mean can only rise as seeds
are added, and one climbing seed drags a set of flat controls over the threshold. The tell was
that every one of the first 17 flips went the same way. Judging the *median* seed removes it, and
the flips then go both directions. Rows below three seeds are labelled `thin_screen` rather than
given a verdict.

## Does a task meet the benchmark's own standards

Measuring iteration is one question; whether a task's science is solid is another, and the two
are independent. `scripts/audit_benchmark_standards.py` checks nine mechanically verifiable
properties across all 63 packages and reports them separately, because they are different kinds
of defect and an average would hide whichever one matters.

| standard | met |
|---|---:|
| declares specific known shortcuts | 53 / 62 |
| states oracle invariants | 53 / 62 |
| cites resolvable literature | 50 / 62 |
| holds a sealed split back from the development score | 41 / 62 |
| ships a runnable reference implementation the evaluator can re-derive its anchor from | 6 / 62 |
| card claims the anchor is recomputed, without shipping one | 6 / 62 |
| ships a reference record | 7 / 62 |
| oracle is community-standard tooling, not a reimplementation | 3 / 62 |
| exposes a difficulty level | 3 / 62 |
| externally domain reviewed | 0 / 62 |

The distribution is lopsided in a specific way: the documentation standards are largely met while
the standards that decide scientific credibility are largely not. The anchor row is split on
purpose. A reference implementation under `verification/` is something the evaluator can run; a
sentence in the card saying the anchor is "recomputed" is a claim, and spot-checking found that
claim on a task whose same sentence also cites a literature value. Counting them together gave 9
of 62 where the runnable evidence is 6. Only three tasks reach eight of
nine, and those are the three built to these standards; nothing else exceeds five.

An independent check that the standards are measuring something: the nine tasks scoring zero are
exactly the nine the repository has quarantined, and this audit never reads `certification.yaml`.

Crossing the two audits gives the honest position. `QuantumErrorCorrection/QuantumErrorDecoder` is
the only task that both measures iteration and rests on community tooling with a recomputed
anchor. `ProteinStabilityDesign`, `NMRSpectrumFitting` and `LowThrustTransfer` measure iteration
but score against author-written NumPy reimplementations, so what they measure is agreement with
that code rather than with the science. `MolecularLeadOptimization` is the reverse: solid
grounding, but its control has not been exhausted.

See [standards audit](.research/benchmark_standards_audit_2026-08-11.md).

### What the newest task shows about the criterion

`RNAEngineering/RNAEnsembleDesign` was built to close the community-oracle gap and then run
through the admission criterion like anything else. Over four paired seeds its gap is +0.0135 at
budget 3 and −0.0005 by budget 12, against an open-loop mean of 1.0062 — the searcher sits right
at ViennaRNA's own partition-function designer and feedback neither helps nor hurts. The verdict
is `no measurable difference`, which is the honest reading and not one the criterion could produce
until the materiality rule was added.

That is a useful negative for the benchmark: a task can have a community oracle, a recomputed
anchor, a sealed split and a difficulty ladder — eight of nine standards — and still not measure
iterative improvement. Scientific grounding and RSI fit are separate properties, and this task now
demonstrates the separation from the other direction.

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
python scripts/audit_benchmark_standards.py --output /tmp/standards.json
python scripts/report_admission_criterion.py --runs runs --output /tmp/admission.json
python -m unittest discover -s tests -q
```

New machine-readable reports include their command, Git revision, scoped source-tree state,
changed paths, execution status, and trust decision. A dated artifact is trusted evidence only
when its declared checks pass on a clean, known revision.

## Contributing

The current priority is hardening and independently reviewing the existing inventory. Start with
[`CONTRIBUTING.md`](CONTRIBUTING.md); new tasks enter as candidates and cannot self-certify.
