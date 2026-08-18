# Scientist's Last Exam

Scientist's Last Exam (SLE) is a research prototype for **cross-domain, executable,
budget-constrained scientific generative optimization**. An agent edits a runnable program,
a frozen deterministic oracle evaluates each candidate, and the benchmark records both the
best feasible artifact and the cost-aware trajectory used to find it.

The question it is built to answer is not "can a model score well once" but "does giving a model
feedback and more budget make it better **at science**" — the agentic, self-improving regime that
AlphaFold-style and AlphaEvolve-style results live in.

Both halves of that matter, and the concurrent literature splits along exactly this line. SEE
([arXiv:2608.06931](https://arxiv.org/abs/2608.06931)) is science — expert-curated chemistry,
biology and materials questions, 19 multimodal models, best accuracy 48.7% — but it is a static
question set, so it cannot say whether iterating helps. OPT-BENCH
([arXiv:2605.08904](https://arxiv.org/abs/2605.08904)) measures iterative self-optimization with a
memory-less control arm, which is the right instrument, but its thirty environments are twenty
machine-learning tasks and ten NP-hard problems. Neither occupies the intersection: a scientific
problem with a frozen domain oracle, where the thing being measured is whether feedback compounds.

That intersection is what this repository is for. Section
[Does a task measure iteration](#does-a-task-measure-iteration) gives the criterion, and
[Does a task meet the benchmark's own standards](#does-a-task-meet-the-benchmarks-own-standards)
gives the audit of whether the science underneath is real. The honest answer today is a small
number on both.

This repository is inspired by
[Frontier-Engineering](https://github.com/EinsiaLab/Frontier-Engineering). It is unrelated to
the text-question benchmark named *FrontierScience* in
[arXiv:2601.21165](https://arxiv.org/abs/2601.21165).

> A higher simulator or verifier score demonstrates optimization only within the registered
> oracle. It does not by itself establish autonomous scientific discovery, mechanism recovery,
> physical validation, or real-world utility.

## At a glance

- **43 task packages** across **7 broad disciplines** — biology, chemistry, computer science,
  earth science, engineering, mathematics and physics.
- **24 scientific optimization** tasks and **19 scientific discovery** tasks, the two forms this
  benchmark claims to cover. Discovery tasks report mechanism recovery, false-discovery rate and
  calibrated refusal separately, because one maximised scalar cannot say whether a discovery was
  right.
- **5 certified** and **38 candidate** tasks; the quarantine set is empty.
- **8 tasks whose oracles are community-standard scientific tooling** — Stim + PyMatching, RDKit,
  ViennaRNA, nmrsim, networkx, SymPy, QuTiP, Astropy — rather than a bespoke reimplementation,
  each anchored on a value or a routine recomputed at evaluation time.
- **6 tasks** are so far shown to measure iterative improvement, against a criterion the
  repository can apply to any task with paired runs. Three rest on a saturation result that a
  three-seed subset of their own runs would reverse, and are reported as such — one task has
  already left the list when the extra seeds were run.
- **Three models** have been run — one Claude family, two GPT family. They rank the tasks
  consistently (Spearman 0.959 within a family over 50 tasks, 0.811 and 0.559 across families
  over 12) and **disagree on every admission verdict**: see
  [Does a task measure iteration](#does-a-task-measure-iteration).
- Deterministic black-box evaluation through a networkless Bubblewrap sandbox.
- A built-in iterative rewrite baseline plus OpenEvolve, AB-MCTS, and ShinkaEvolve backends.
- Hash-bound experiment reports with Git revision, command, source-tree state, and explicit
  trust decisions.

### Fifteen tasks were retired for having no room left

A task every searcher drives to its cap no longer separates anything, while still consuming a
share of every evaluation budget. Fifteen were retired on that basis: `BroadbandAbsorber`,
`AntennaArraySynthesis`, `LidDrivenCavity`, `GateSynthesis`, `HartreeFockSCF`, `PoissonSolver2D`,
`OptimalPowerFlow`, `RankineCycleOpt`, `SpinGlassGroundState`, `LyapunovControl`,
`OptimalExperimentDesign`, `PhotovoltaicTandemDesign`, `SeismicInversion`, `OceanCurrentInversion`
and `SeismicWaveInversion`.

The rule is *every* model at or above 0.99, not *any*. A task only one model has maxed is still
separating models and stays: `RNAInverseDesign` scores 0.8948 for one and 0.9996 for another.

Scores **above** 1.0 stay too. On an uncapped task, exceeding the anchor is the intended result
rather than saturation — `CirclePacking` is at 1.09 and `RNAEnsembleDesign` at 1.01. Retiring
those would be treating success as a fault.

Two of the fifteen were certified. Certification says the task is sound; it says nothing about
whether the task has any headroom left, and the two need separate accounting.

### How deep the science goes, measured rather than asserted

Claiming a scientific setting is easy; the audit exists because the claim is checkable. Across the
43 packages:

| | |
|---|---:|
| tasks stating their shortcut-resistance argument | 43 / 43 |
| tasks stating scientific invariants | 43 / 43 |
| tasks citing resolvable literature (DOI or arXiv) | 42 / 43 |
| tasks holding a sealed split back from the development score | 35 / 43 |
| tasks whose anchor is recomputed rather than quoted | **10 / 43** |
| tasks whose oracle is community-standard domain tooling | **8 / 43** |
| tasks shipping a runnable reference the anchor is re-derived from | **8 / 43** |
| tasks carrying a difficulty ladder | **8 / 43** |
| tasks reviewed by an external domain expert | **0 / 43** |

The first rows are the framing; the bolded ones are the substance, and they are where this
inventory is thin. Thirty-five of 43 oracles are author-written NumPy reductions of the science
they describe, so a score on them measures agreement with that author's code rather than with the
field. The task narratives cite real work; most of the oracles do not run it.

The eight community-oracle tasks close that gap and are the template for the rest rather than a
finished state.

### Scope

Every remaining task is natural science or its mathematics. Two operations-research entries
(`MultiEchelonStock`, `TrafficSignalTiming`) that had been quarantined for reproduced defects
have since left the inventory, and the quarantine set is now empty.

The default CLI exposes only certified tasks. Candidates remain visible for research and
calibration; neither group beyond the certified core is benchmark-admissible by default.

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

| Discipline | Tasks | Certified | Candidate |
|---|---:|---:|---:|
| Biology | 6 | 0 | 6 |
| Chemistry | 10 | 1 | 9 |
| Computer Science | 4 | 1 | 3 |
| Earth Science | 3 | 0 | 3 |
| Engineering | 10 | 0 | 10 |
| Mathematics | 4 | 2 | 2 |
| Physics | 6 | 1 | 5 |
| **Total** | **43** | **5** | **38** |

The certified core currently consists of:

- `Chemistry/LennardJonesCluster`
- `Algorithm/MatrixMultiplicationRank`
- `Mathematics/CapSet`
- `Optimization/CirclePacking`
- `Photonics/MultilayerThinFilm`

Run `python -m sle list --all` for the authoritative live inventory. The
domain-to-discipline mapping is in
[`sle/benchmark_layout.py`](sle/benchmark_layout.py); admission status
is in [`sle/certification.yaml`](sle/certification.yaml).

## Community-oracle tasks

Most evaluators depend only on NumPy, SciPy and the standard library. Task narratives cite real
science, but those oracles are author-written reduced-order reimplementations, and none has
completed external domain review. A score on them measures agreement with the author's NumPy
code, not with the science.

Eight tasks close that gap. Each puts a community-standard toolkit in the oracle and recomputes
its anchor at evaluation time rather than quoting a number from a paper. `RNAEnsembleDesign` goes
one step further and makes the anchor a routine the community actually uses rather than a value:
it runs ViennaRNA's own designer inside the evaluator, restart-matched so a candidate cannot beat
it by calling it more often.

| Task | Oracle | Form | Anchor |
|---|---|---|---|
| `QuantumErrorCorrection/QuantumErrorDecoder` | **Stim** rotated surface-code circuits, seeded sampling | Opt | **PyMatching 2** minimum-weight perfect matching, recomputed per run; uncapped |
| `RNAEngineering/RNAEnsembleDesign` | **ViennaRNA** partition function over the Turner nearest-neighbour model; ensemble defect | Opt | ViennaRNA's `inverse_pf_fold`, best of three restarts, recomputed per run; uncapped |
| `MedicinalChemistry/MolecularLeadOptimization` | **RDKit** QED, Ertl–Schuffenhauer SA, Lipinski/Veber, PAINS, Morgan/Tanimoto | Opt | mean drug-likeness of structurally distinct approved drugs from a 20-drug panel, each SMILES verified against published molecular weights; uncapped |
| `Spectroscopy/SpinSystemInference` | **nmrsim** full Zeeman-plus-coupling Hamiltonian, diagonalised | Disc | least-squares fit of the nmrsim forward model, run at scoring time |
| `Algorithm/GraphFromDistances` | **networkx** | Disc | truth-blind domain reference strategy, run at scoring time |
| `Mathematics/SequenceLawRecovery` | **SymPy** | Disc | truth-blind reference recoverer; correct-refusal rate 0.50 by construction |
| `QuantumDynamics/HamiltonianLearning` | **QuTiP** | Disc | truth-blind reference identifier |
| `Exoplanets/RadialVelocityPlanets` | **Astropy** | Disc | truth-blind periodogram reference; baseline recovers 0.50 of the mechanism at a false-discovery rate of 0.889 |

The discovery entries all ship their reference under `verification/` and run it at scoring time,
and each reference is deliberately imperfect — a reference that scores 1.0 leaves the task no
headroom. `SpinSystemInference`'s reference recovers 0.5833 of the mechanism at a false-discovery
rate of 0.250.

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
python -m sle list
python -m sle list --all

# Evaluate the bundled baseline for a certified task.
python -m sle eval --task Chemistry/LennardJonesCluster

# Evaluate another candidate implementation.
python -m sle eval \
  --task Chemistry/LennardJonesCluster \
  --candidate /path/to/solution.py
```

Task names are accepted when unambiguous. Candidate and quarantined packages require the
explicit `--allow-uncertified` flag.

### Install the oracle toolkits

Eight tasks put a community toolkit in the oracle, and each pins its version in
`verification/requirements.txt`. On the benchmark host those files cannot be installed the usual
way: the system interpreter's pip fails at import with a pyOpenSSL binding mismatch, so
`pip install -r` never runs. `scripts/setup_oracle_env.sh` documents the way around it — a
virtualenv created *without* `--system-site-packages` has working pip, and `--target` points it at
the oracle interpreter's site-packages.

```bash
bash scripts/setup_oracle_env.sh --check    # report what is present
bash scripts/setup_oracle_env.sh            # install the pinned set
```

The oracle runs in the trusted parent, so installing a toolkit does not touch the isolation model.
A candidate receives one only if its task lists it in `frontier_eval/candidate_packages.txt` **and**
the name appears in the audited allowlist in `sle/secure_eval.py`.

### Configure an LLM

```bash
cp sle/conf/llm/openai_compatible.example.yaml \
   sle/conf/llm/local.yaml
export OPENAI_API_KEY=your_key_here
python -m sle smoke
```

`local.yaml` is git-ignored. Configuration resolution is `--llm-config`, then `FS_LLM_CONFIG`,
then `conf/llm/local.yaml`, then the committed example. Both OpenAI-compatible Chat Completions
and Responses wires are supported. Reasoning models on the chat wire reject `max_tokens`; set
`chat_max_tokens_field: max_completion_tokens` for those. Never commit credentials.

### Run an optimization trajectory

```bash
python -m sle run \
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
| [Admission criterion sweep](.research/task_admission_verification_2026-08-11.md) | 7 tasks shown to measure iteration; 3 of the 7 seed-fragile | Every recorded run, both conditions |
| [Cross-model comparison](.research/cross_model_2026-08-13.md) | ranking consistent, admission verdicts not | Three models, 12 shared tasks |

[`experiments/TRUST.md`](experiments/TRUST.md) is the append-only trust manifest. Study plans and
interpretations live in [`.research/`](.research/). Historical pre-sandbox reports are classified
`UNTRUSTED_PRE_SANDBOX` and must not be used as benchmark evidence.

## Recent findings

Full write-ups are in [`.research/`](.research/); each carries its own claim boundary.

**Every discovery task now emits all three axes.** Five evaluators were measuring mechanism
recovery, false discovery and refusal but publishing some of them as counts, or not at all:
`ActiveLawDiscovery` published false-discovery and abstention counts without the world counts
that make them rates, and `GravityInversion`, `ReactionMechanismFitting`, `SpinSystemInference`,
`NMRSpectrumFitting` and `InterventionalSCM` published no coverage at all, so on those tasks
"was a discovery attempted" could not be read off a run. A sixth, `ForceFieldCalibration`, needed
no change: it publishes mechanism recovery as `supported_correct_model_rate` and
`hypothesis_score`, and the audit had been measuring its own vocabulary rather than the task.

**A task's difficulty is often its submission contract, not its science.** The rank correlation
between hidden-evaluator length and the fraction of proposals that are even valid is **-0.675**
across 39 tasks: the shortest evaluators accept 92-100%, the longest accept 0-5%. The mechanism
is visible rather than inferred. `CalorimeterDesign` rejected 36 of 36 proposals while its own
shipped baseline evaluated fine, and the first rejection retained for diagnosis had read
`problem["light_yield_per_gev"]` when the key is `light_yield_pe_per_active_gev` — the quantity
was real, the name was undocumented, and the prompt named only 15 of the 27 keys the task passes
in.

`scripts/audit_documented_keys.py` found the same defect in **7 of 15** tasks whose baseline reads
an input mapping — 24 undocumented keys, most of them the bounds a candidate must respect and
could only learn by copying the baseline. Documenting them changed no evaluator, no score and no
science:

| task | valid before | valid after | best score before | after |
|---|---:|---:|---:|---:|
| `CalorimeterDesign` | 0% | **77%** | 0.0000 | **1.0000** |
| `HeatExchangerDesign` | 66% | **96%** | 0.7665 | **1.0000** |
| `QuartzCrystalMicrobalanceLab` | 58% | **83%** | 0.0000 | 0.0000 |
| `RoomImpulseResponse` | 69% | 73% | 0.4382 | **0.6824** |
| `DistillationColumnDesign` | 38% | 29% | 0.5822 | **0.9960** |
| `ForceFieldCalibration` | 5% | **17%** | 0.0600 | **0.8288** |

Each row is 48 proposals after the fix against 36-204 before, same model and budget.

`CalorimeterDesign` had been on the list of floor tasks needing recalibration. That diagnosis was
wrong: it was never too hard, it just never said what its inputs were called.
`QuartzCrystalMicrobalanceLab` separates the two failure modes cleanly — its contract problem is
fixed, 58% valid to 83%, and its score is still 0.0000, because what remains is the blanket
abstention below and not the contract. `ForceFieldCalibration` still rejects most proposals, but
the ones that land now score 0.8288 against 0.0600 before, so what was read as a floor task was a
contract that let almost nothing through. One thing about it stays unexplained: the same rejected
candidate raises inside the sandbox and returns cleanly outside it in 0.3s, with scipy importable
in both. Full write-up in
[.research/contract_burden_2026-08-14.md](.research/contract_burden_2026-08-14.md).

Two things made this findable and are worth keeping. Rejected candidates are now retained (five
per run, written to disk only, never fed back to the searcher) — before that, a task rejecting
everything left nothing to look at, since the ledger stores candidates by hash and
`best_program.py` is still the baseline when nothing is accepted. And documenting a task edits its
`Task.md`, which is its prompt, so the rebinding tool **refuses** to re-sign a frozen task whose
evidence could have moved. That refusal is the tool working, and it is the real cost of the fix.

**Runnable references beat blanket abstention on all five tasks that scored zero.** The claim that
declining every world was a failure rather than a correct reading of a hard task rested on prose
in task cards that nothing executed. All five now ship a truth-blind reference — using only what a candidate receives, never the
hidden world:

| task | model proposals | reference | mechanism recovery |
|---|---:|---:|---:|
| `ProspectiveMetaAnalysis` | 0.0000 | **0.9088** | 0.9266 |
| `QuartzCrystalMicrobalanceLab` | 0.0000 | **0.8330** | 0.9585 |
| `RadiativeTransferFit` | 0.0000 | **0.7910** | 0.8606 |
| `ConvectionDiffusionOpt` | 0.0000 | **0.7636** | 0.9724 |
| `GeneNetworkIntervention` | 0.0000 | **0.3926** | 0.8255 |

That is every task that had scored zero on refusal. All five reach coverage 1.0,
false-discovery 0.0 and correct-refusal 1.0 — the same refusal and
false-discovery numbers the abstaining proposals get, since declining cannot misfire, plus the
mechanism recovery those proposals forgo. `QuartzCrystalMicrobalanceLab`'s diagnosis is right on
10 of 10 worlds.

Writing them showed what the tasks measure, and one lesson appeared in three of the five:
**thresholding a fitted model marks far too much active, because the noise lands in every
parameter.** On null worlds it manufactures a mechanism where the truth is that there is none.
Which entries are active is a model-selection question, and answering it as one — BIC over all 32
support patterns in one task, BIC backward elimination over the edges in another — moved the
scores from 0.16 to 0.79 and from 0.16 to 0.39. The same shape appeared twice more in different clothes. On `QuartzCrystalMicrobalanceLab`:
overtone dispersion is a *trend* and not a spread, and judging it by scatter marked a world with
missing samples (0.281) as more dispersing than either genuinely viscoelastic world (0.157, 0.160).
Requiring a monotone trend took that diagnosis from 6 of 10 to 10 of 10. On
`ProspectiveMetaAnalysis` the first out-of-family test asked whether the pooled effect fell
outside the published bounds and never fired once: a curved moderator relationship produces
perfectly ordinary effect sizes, so bounds cannot see it. Testing the quadratic term's
significance instead — linear corpora at 0.17–1.32, nonlinear at 2.40 and 2.86 — took the score
from 0.83 to 0.91 and the refusal rate from 0.0 to 1.0.

A first `RadiativeTransferFit` reference claimed on every world and scored 0.0000 — the exact
mirror of blanket abstention, and evidence that the normalisation demands discrimination rather
than either extreme.

Two harness defects surfaced only because a reference was written. `ConvectionDiffusionOpt`'s
reference abstained everywhere while its PDE solver was **bit-identical** to the evaluator's: the
mismatch was reading the sensors, bilinear against nearest-node, and at a declared noise of 6.5e-4
against field values near 0.27 a one per cent sampling error is a four-sigma residual. A refusal
that comes from the instrument model rather than the science is indistinguishable from the real
thing in the score. And `QuartzCrystalMicrobalanceLab` required four exact calibration key names
that appeared nowhere in its prompt — the submission side of the same undocumented-contract defect
the input-key audit had already found, and now audited too.

**Three explanations for that abstention have been ruled out, and the remaining one is the
models.** Prompt wording does not predict it: the density of abstain/refuse language correlates
with the abstention rate at -0.267, with the sign the wrong way round. Undocumented submission
fields do not explain it: the fields are documented. And the size of the claim contract does not
explain it either — Spearman +0.133 over nine tasks, with `ProspectiveMetaAnalysis` (17 claim
fields, 100% abstention) and `CatalystDeactivationLab` (17 fields, 28%) showing opposite behaviour
at identical contract size.

Meanwhile the five references score 0.39 to 0.91 on the same tasks, so the science is doable. What
is left is a property of the searchers: given a hard inference with a refusal available, these
models refuse rather than attempt, and the scoring correctly pays nothing for it. That is not a
defect in the tasks — it is the kind of thing a discovery benchmark exists to measure.

**The six tasks scoring zero are refusals, not difficulty.** Every valid proposal on them
scores exactly 0.0000 rather than a spread of small values, which is the shape of a gate rather
than of a hard landscape. Reading the evaluator's own components explains it: on
`RadiativeTransferFit` a typical proposal has a correct-refusal rate of 1.0, a false-discovery
rate of 0.0 and a discovery coverage of **0.0** — it declined every world. The score normalises
against the all-abstain baseline, so declining everything earns exactly nothing, which is what
the criterion is for.

Across all discovery tasks the relationship is monotone: 100% blanket abstention on the four
worst, 86% on the fifth, down to 10% on `EnergyBalanceModel` which scores 0.664. The floor is an
abstention ranking, not a difficulty ranking. **Recalibrating those anchors would be treating the
wrong thing** — raising the floor would start paying for declining, which is exactly the strategy
the normalisation exists to refuse.

`scripts/report_discovery_triple.py` now carries a coverage column — not a fourth axis; the
triple says how good a discovery was, coverage says whether one was attempted — and names the
tasks whose best valid proposal attempted nothing. Six further tasks publish no coverage metric
at all, so on those the question cannot be answered from the runs. Full write-up in
[.research/floor_tasks_are_refusals_2026-08-14.md](.research/floor_tasks_are_refusals_2026-08-14.md).

**Three models rank the tasks the same way and disagree on every admission verdict.** Spearman
over the open-loop scores is 0.959 within one model family (50 shared tasks) and 0.811 and 0.559
across families (12 each). On the 12 tasks two families both ran, the admission verdict differs
every time, and one-sidedly: tasks one model qualifies, the other reads as
`control_not_exhausted`, because its best-of-N is still climbing at the same budget — second-half
gains of 0.028, 0.024 and 0.017 against 0.000. Curve length, task version and searcher are all
matched, so this is a model effect rather than an artefact.

The consequence is structural. The crossover budget is a property of the task *and* the searcher,
and the model is part of the searcher, so **a stronger model can disqualify a task**. Admission
has to be stated as a joint claim about a task and a searcher; it cannot be a property of the
task alone. That is a direct cost of the criterion, not a defect in it.

**A hash that decides what is comparable must cover only what can change a score.** Runs record
`task_package_sha256`, and the reports refuse to compare across a difference. Two defects made
that guard reject valid evidence: a one-line `scientific_role` annotation added to every task's
card moved every hash, and the hash covered the task's own `runs/` output, so a task's recorded
identity changed whenever anyone ran it — 35 of the directories accumulate one.

The identity hash now excludes generated output, and
[`scripts/build_task_version_equivalence.py`](scripts/build_task_version_equivalence.py) recovers
the history: it replays each revision's package hash from git objects, and where a recorded hash
cannot be reproduced it asks instead whether anything behavioural has been committed since the
task's first run. Of 20 tasks recorded under more than one hash, **16 are the same task**; three
were genuinely edited and one is unresolved. Without that table, cross-model comparison drops
from 50 shared tasks to 6.

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
cohorts were never paired). Over the 53 tasks with recorded runs:

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

**None of the seven certified tasks is among them.** The certified core is what the default CLI
exposes, and measured against the criterion this benchmark exists to apply:

| certified task | verdict | control settles at |
|---|---|---:|
| `ScientificComputing/PoissonSolver2D` | control exhausted, never paired | 1.000 |
| `Physics/SpinGlassGroundState` | control exhausted, never paired | 1.000 |
| `Optimization/CirclePacking` | control exhausted, never paired | 1.061 |
| `Chemistry/LennardJonesCluster` | control exhausted, never paired | 0.998 |
| `Algorithm/MatrixMultiplicationRank` | control exhausted, never paired | 0.979 |
| `Photonics/MultilayerThinFilm` | control still climbing | 0.936 |
| `Mathematics/CapSet` | control still climbing | 0.705 |

`PoissonSolver2D` and `SpinGlassGroundState` are clipped and sit at exactly 1.000 — best-of-N
reaches the anchor, so there is nothing above it to measure. The three uncapped ones are being
paired now, and are the only certified tasks that could still qualify. Certification in this
repository has always described evidence quality rather than difficulty, and this is what that
distinction costs: a task can be fully certified and still not measure iterative improvement.

**Paired evidence exists for 19 tasks, and seven pass:** `QuantumErrorCorrection/QuantumErrorDecoder`,
`Spectroscopy/NMRSpectrumFitting`, `Astrodynamics/LowThrustTransfer`,
`ProteinEngineering/ProteinStabilityDesign`, `MaterialsScience/AlloyHardnessOptimization`,
`Catalysis/CatalystDeactivationLab` and `ClimateScience/EnergyBalanceModel`.

| task | gap at budget 3 → 12 | last budget | seeds | drop-one-seed |
|---|---|---|---:|---:|
| `QuantumErrorCorrection/QuantumErrorDecoder` | +0.104 → +0.129 | 5/6 | 6 | +0.133 |
| `Spectroscopy/NMRSpectrumFitting` | +0.085 → +0.173 | 3/4 | 4 | +0.097 |
| `Astrodynamics/LowThrustTransfer` | −0.011 → +0.089 | 3/4 | 4 | +0.031 |
| `ProteinEngineering/ProteinStabilityDesign` | +0.032 → +0.035 | 5/5 | 6 | +0.017 |

**Adding seeds shrank the qualifying set, in the direction the fragility flag predicted.** The
three tasks flagged as seed-fragile were re-run with three more seeds each:

| task | seeds | second-half gain | verdict |
|---|---|---|---|
| `ProteinStabilityDesign` | 8 → **11** | 0.0000 → **0.0122** | qualified → **`control_not_exhausted`** |
| `LowThrustTransfer` | 6 → **9** | 0.0053 → **0.0085** | still qualifies, closer to the 0.01 threshold |

`ProteinStabilityDesign` crossed the threshold and left the list, taking the count from seven to
six. Both tasks moved the same way. Two points is weak evidence, but it is the direction the flag
predicted and it means the earlier evidence was optimistic rather than merely thin.

**Three of the seven rest on a saturation their own seeds would reverse.** The necessary
condition is a threshold test on the open-loop control's second-half gain, and the report already
declares three seeds enough to decide it. Enumerating three-seed subsets of the runs that exist
shows `LowThrustTransfer`, `ProteinStabilityDesign` and `QuantumErrorDecoder` flipping:
`LowThrustTransfer` reads 0.0053 over six seeds, which is exhausted, and 0.0193 over the first
three, which is not.

Leave-one-out does not find this — dropping a single seed from six never moves the median across
the threshold, and it reported zero fragile verdicts on an inventory where the seed-matched
comparison had just shown one. The subset has to be as small as the criterion claims to trust.

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

### Is it even the right kind of problem

Two audits check the science and the evidence. A third, `scripts/audit_theme_fit.py`, checks
something they both assume: that the task poses an open-ended problem in the first place. It reads
only the task package, so it applies to every task from the day it is written, unlike the admission
criterion which needs paired runs.

| check | met |
|---|---|
| continuously scored rather than paying out on a threshold | 43 / 43 |
| declares one of the two forms, optimization or discovery | 43 / 43 |
| open-ended — the anchor is not itself a solution a correct implementation reaches | 41 / 43 |
| discovery tasks emitting all three axes | **19 / 19** |
| frontier-anchored — uncapped against a reference the field would want to beat | 7 / 43 |

Two tasks describe an anchor their own card calls a manufactured solution or the optimum:
`ControlTheory/InvertedPendulumSwingUp` and `Optics/DiffractionGratingDesign`. They are not
defective — they ask for a known method and have a unique answer, so iteration stops paying once
it is found. Labelling them is more useful than measuring an evolvability gap on them. Two others
that failed this check, `PoissonSolver2D` and `GateSynthesis`, have since been retired for having
no headroom left, which is the same problem arriving through a different door.

The gap that matters is the last row, but it needs narrowing. Thirty-six of 43 tasks are clipped,
and it is tempting to read that as the structural cause of saturation. Split by role:

| | clipped | uncapped |
|---|---:|---:|
| discovery | 19 | 0 |
| optimization | 17 | 7 |

The 19 clipped discovery tasks are clipped **correctly**. Their `combined_score` is the fraction
of the hidden mechanism recovered, so 1.0 means the truth was recovered, not that a reference was
matched — nobody can recover more than all of it, and uncapping would mean nothing. Uncapping is
a prescription for optimization tasks whose anchor is a human record.

So the real surface is **17 optimization tasks**, not 36. That is still the structural reason the
optimization half saturates, and retiring a maxed task treats the symptom rather than the cause.

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

The inventory was originally swept one open-loop seed per task; 48 of 52 tasks then in it had exactly one
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
properties across all 43 packages and reports them separately, because they are different kinds
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

Several things are deliberately left open rather than papered over.

**The frozen measurement-health cohort passes 7 of 7, and getting there is the interesting part.**
A frozen cohort is a snapshot mechanism for a release point, not a guard for continuous
development: every evaluator improvement moves a task hash and unbinds the evidence attached to
it. The order that works is *finalize the evaluators, measure once, rebind once*.

`scripts/check_evaluator_inert.py` does the measuring. It runs each frozen artifact through the
evaluator as it stood at the freeze revision and as it stands now, and compares the two metric
dictionaries key by key. On this cohort that came out **6 inert, 1 changed** — removing the upper
clip could not move a score that was already under the cap, except on
`DiffractionGratingDesign`, where the artifact's `robustness_score` genuinely crossed 1.0. The six
carried their evidence forward with a number behind the claim; the seventh had all three of its
bindings re-measured on the current runtime instead. Re-measuring the calibration moved 8 of 3004
keys, all at 1e-15.

Two things were worth more than the 7/7. The materiality audit and the preflight were asking the
same question — *could this evaluator edit have moved this evidence* — and answering it
differently, so the same task passed one report and failed the other; they now read the exemption
from the same record. And a test pinned the calibration's filename date, which made it fail the
moment the evidence was legitimately re-measured — exactly backwards. It asserts the recorded
evaluator hash now.

**The trusted runtime changed.** `sle/secure_eval.py` and `benchmark_layout.py`
were modified, and `tests/test_runtime_migration.py` passes at the previous revision and fails
here. The project binds frozen analysis artifacts to a `runtime_source_sha256`, so changing the
runtime unbinds them; the remedy is to register a runtime migration audit, which re-certifies the
trusted runtime and should be a deliberate decision. Note that this guard fires for **any** new
task in a new domain. Nine per-task analysis tests also fail and are explicitly recorded as
unattributed — they read `runs/` paths stored as absolute paths, so they error in a clone or
worktree. See [runtime governance](.research/runtime_change_governance_2026-08-09.md).

**The first measurement against the current contracts is in, and it is thin on purpose.** Every
one of the 43 tasks now has a model run bound to the contract it is scored under — one seed, one
proposal, `greedy_rewrite`, Claude. That is enough to restore the binding and nothing like enough
to rank anything, so read the table below as a single draw rather than as a result.

Two numbers are worth pulling out. `CirclePacking` scores **1.1468** and `CalorimeterDesign`
**1.0121** — above one, which is the whole point of removing the upper clip and the first time the
benchmark has been able to say that a candidate beat its reference witness rather than merely
matched it. At the other end, 17 of 43 score exactly 0.0 from a single proposal, and 6 reach 0.95
or better from that same single proposal, which is a saturation signal rather than a score.

The paired budget-3 sweep that follows — `normal` against `selection_blind`, seed-matched, which is
what the evolvability gap is measured from — is the one that will support a claim.

**Until that campaign landed, no recorded model run was bound to a current task contract, and every
model-derived measurement-health check read zero.** A run binds to the contract it was made against, and the evaluators have
since changed — most of them when the upper clip came off. The runs still exist and still describe
what those models did; they describe it about a previous contract. Concretely: the matched-control
count on the `ActiveLawDiscovery` control and the observed first-valid step on `RNAInverseDesign`
both read 0 where they previously read 48 and 1. Nothing about those measurements was withdrawn —
they were unbound, which is a different and recoverable thing, and the repair is to re-run the
cohort against the current contracts rather than to re-sign the old numbers. Read the model tables
below as measured against pre-uncapping evaluators. For the 17 uncapped optimization tasks a score
can only have moved *up*, and only for candidates that were sitting against the ceiling.

**A candidate could crash three of the evaluators, and a crash costs a cohort rather than a
candidate.** A 129-block paired sweep returned four terminal failures, each reporting only
`trusted evaluator internal failure` — no task, no line, no cause — and those four invalidated the
whole campaign's report. The fixed wording is deliberate: an exception string must not carry
evaluator internals or hidden values back to a candidate. But an infrastructure failure *aborts
the run* rather than scoring anything, so there is no searcher downstream to protect on that path.
The cause now goes to the trusted driver's stderr and is attached only where the run is already
being abandoned, which keeps the separation structural rather than remembered.

With the cause visible it took one run to find: `KeyError: 'abstained'`. The row an evaluator
builds when scoring a world *raises* carried fewer keys than the row it builds when scoring
succeeds, and `discovery_coverage` — added later, as the fourth column of the discovery triple —
read one of the missing ones. A third task had no failure path at all: a controller returning a
dictionary raised out of `float()`.

`scripts/check_evaluator_survives_bad_candidates.py` now asks the question of the whole inventory
by feeding every evaluator three candidates that fail — one that raises, one that returns `{}`,
one that returns a string — and asking whether the evaluator scores them zero or dies. It was 3
tasks crashing; it is now **0 of 43**, across 129 cases.

A structural version of this check was written first and thrown away. It compared the key sets of
the two branches and flagged five tasks the executable check had just cleared, because whether a
missing key matters depends on which list the aggregation walks. An invariant stricter than the
property it stands in for buys nothing and costs a permanently red suite.

**One oracle was not a function, and the headline score hid it.** The 43-task determinism sweep
returned 42 of 43. `RNAEnsembleDesign` failed because ViennaRNA's designers, handed `None` as a
start sequence, draw one from a generator inside the C library that the task's own
`random.Random(seed)` does not reach. The visible symptom was anchor defects wandering by 1e-4.
The damaging one was that a target sitting near the edge of the acceptance band flipped in and out
of the instance set between runs — so *which instances existed* changed, and two scores were not
comparable at all. `combined_score` was 0.0 both times, so the headline number showed nothing.
Seeding is now per call and derived from the call's own inputs, because the candidate is arbitrary
code that may draw from the same generator first; seeding once at import would shift every draw
after it. Three processes now agree to ten decimal places, and
`tests/test_oracle_rng_is_pinned.py` asks the question of the whole inventory rather than of this
one task.

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
python scripts/audit_theme_fit.py --output /tmp/theme.json
python scripts/report_admission_criterion.py --runs runs --output /tmp/admission.json
python scripts/report_cross_model.py --runs runs --output /tmp/cross_model.json \
  --admission /tmp/admission.json
python -m unittest discover -s tests -q
```

New machine-readable reports include their command, Git revision, scoped source-tree state,
changed paths, execution status, and trust decision. A dated artifact is trusted evidence only
when its declared checks pass on a clean, known revision.

## Contributing

The current priority is hardening and independently reviewing the existing inventory. Start with
[`CONTRIBUTING.md`](CONTRIBUTING.md); new tasks enter as candidates and cannot self-certify.
