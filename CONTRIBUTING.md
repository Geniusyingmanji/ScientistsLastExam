# Contributing to Frontier-Science

The current priority is certifying and hardening the existing inventory, not increasing its
size. We welcome fixes, task cards, scientific tests, and carefully reviewed new optimization
tasks via Pull Requests. Discovery makes a package visible with `--all`; admission to the
default benchmark requires the separate certification gate below.

> **AI-assisted contributions are welcome.** However, please verify all oracle code and
> reference values yourself — do not leave scientific correctness entirely to AI.

---

## Task requirements

Every certified Frontier-Science task must satisfy **all seven** of these:

1. **PhD/expert difficulty floor.** The task must require doctoral-level domain knowledge,
   advanced numerical optimization, or current research heuristics. Do not submit educational
   prompts, textbook exercises, toy demos, or easy/medium on-ramp tasks as benchmark items.
2. **Continuous, improvable metric.** The oracle returns a numeric `combined_score` that can be
   meaningfully improved — not a binary pass/fail.
3. **Deterministic, frozen oracle.** Same candidate program → same score. No LLM judge, no
   network, no randomness without a fixed seed.
4. **Locally runnable.** CPU-only hard tasks should finish within a few minutes; flagship tasks
   may use GPU or heavier assets if the dependency and budget are documented.
5. **Black-box safety.** The agent must not be able to read the oracle code, the test-split
   answers, or the verification internals. The candidate runs in a restricted sandbox and the
   trusted parent process alone imports the oracle and produces metrics.
6. **Scientific significance.** Improvement corresponds to real scientific value (a better
   algorithm, a better molecular design, a lower energy, ...). Provide a citable reference for
   the baseline and the best-known result.
7. **Auditable task card and review.** Add `TASK_CARD.yaml` with the scientific question,
   artifact semantics, equations/oracle, normalization, stable DOI/arXiv/URL identifiers,
   invariants, known shortcuts, licensing/contamination notes, and both domain and evaluator
   review status. A directory without this evidence remains `candidate`.

---

## Task directory layout

Each task lives at `benchmarks/<Discipline>/<Task>/` and is **auto-discovered** by the harness.
The broad physical discipline is intentionally separate from the finer-grained `domain` in
`metadata.yaml`: the latter preserves the stable public task id `<Domain>/<Task>`. New metadata
domains must first be assigned in `frontier_science/benchmark_layout.py`.

```
benchmarks/
└── <Discipline>/                     # one of the seven broad categories below
    └── <Task>/                       # e.g. LennardJonesCluster, CapSet
        ├── Task.md                   # [Required] Agent-visible task description
        ├── TASK_CARD.yaml            # [Required for certification] evidence + reviews
        ├── solution.py               # [Required] Weak-but-valid baseline program
        ├── frontier_eval/            # [Required] Black-box evaluation contract
        │   ├── metadata.yaml         # Task metadata (see below)
        │   ├── initial_program.txt   # Points to the baseline file (e.g. "solution.py")
        │   ├── candidate_destination.txt  # File the agent edits (e.g. "solution.py")
        │   ├── entrypoint.txt        # Required callable exported by solution.py
        │   ├── constraints.txt       # Natural-language constraints shown to the agent
        │   ├── agent_files.txt       # Files the agent is allowed to see
        │   ├── readonly_files.txt    # Files the agent must not modify
        │   └── run_eval.py           # Legacy compatibility; never trusted for metrics
        ├── verification/             # [Required] Hidden oracle — agent CANNOT see this
        │   └── evaluator.py          # The frozen scoring function
        └── references/               # [Optional] Data, configs, known-best records
            └── known_best.md         # Best-known values + sources (for flagship tasks)
```

The seven top-level disciplines are `Biology`, `Chemistry`, `ComputerScience`,
`EarthScience`, `Engineering`, `Mathematics`, and `Physics`.

### `frontier_eval/metadata.yaml`

```yaml
domain: Chemistry                    # stable logical domain (not the top-level directory)
task: LennardJonesCluster            # task directory name
difficulty: hard                     # hard | flagship
tier: T2                             # T2 (expert) | T3 (flagship)
oracle_type: analytical              # analytical | physical_sim | dataset_oracle | neural_surrogate
score_mode: clipped                  # clipped (cap at [0,1]) | uncapped (SoTA-relative, >1 = beat SoTA)
gpu_required: false
eval_time_seconds: 5                 # approx wall-clock for one evaluation
science_metric: <name>               # human-readable name of the primary metric
reference_baseline: <description>    # what the initial program does
reference_sota: <description>        # best-known result and its source
citation: "Author, Journal, Year"    # citable reference(s)
```

### `frontier_eval/entrypoint.txt`

This file contains one callable name, such as `build_cluster`, `solve`, or `build_capset`.
The trusted evaluator imports `verification/evaluator.py`; it invokes this candidate callable
only through the sandboxed JSON RPC worker. Benchmark-local `run_eval.py` and
`eval_command.txt` remain for legacy tooling, but their metrics are never trusted by the runner.

### `verification/evaluator.py` contract

Your oracle must define an `evaluate(candidate_callable)` function that returns a dict with
**at least**:

```python
{
    "combined_score": float,   # the primary metric (higher is better; -1e18 on failure)
    "valid": float,            # 1.0 if the candidate produced a legal result, else 0.0
}
```

Optional fields: `feasibility_rate`, `constraint_violations`, `beat_sota`, `per_size`,
`raw_score`, etc.

---

## Scoring modes

| Mode | When to use | Score range |
|---|---|---|
| `clipped` | A hard task has a strong known reference value | `[0, 1]` |
| `uncapped` | The best-known value is a live research frontier (flagship tasks) | `[0, ∞)` — reaching SoTA = 1.0, beating it > 1.0 |

For `uncapped` tasks, also provide `references/known_best.md` documenting the current
best-known value, its source, and the date.

---

## Baseline program (`solution.py`)

- Must be **weak but valid**: it runs, the oracle accepts it, and it scores near 0.
- Keep the function signature and output contract that the oracle expects.
- Use only `numpy` and `scipy` (for CPU tasks). Document any extra dependencies in a
  `verification/requirements.txt`.

---

## Checklist before submitting a PR

- [ ] Add the new task to `frontier_science/certification.yaml` as `candidate` first; do not
      self-certify an unreviewed task.
- [ ] `python -m frontier_science eval --allow-uncertified --task <Domain>/<Task>` runs and returns a valid
      `metrics.json` with `combined_score` near 0 for the baseline.
- [ ] `python -m frontier_science list --all` shows the new package with correct metadata.
- [ ] The oracle is deterministic (run twice, get the same score).
- [ ] The agent files (`Task.md`, `solution.py`, `constraints.txt`) do not leak the oracle
      implementation or the answer.
- [ ] No absolute paths, no `.env` files, no API keys, no `__pycache__`, no large data files.
- [ ] `metadata.yaml` is complete (all fields filled in).
- [ ] For flagship (`uncapped`) tasks: `references/known_best.md` exists with sourced values.
- [ ] `python scripts/audit_tasks.py` reports no admission issues and all invariant tests pass.

---

## Contribution process

1. **Fork** this repository and **clone** your fork.
2. **Create a branch**: `feat/<Domain>/<Task>` (e.g. `feat/Biology/RNAInverseFolding`).
3. **Add your task** following the directory layout above. Use an existing task (e.g.
   `Chemistry/LennardJonesCluster` for clipped, `Mathematics/CapSet` for uncapped) as a
   template.
4. **Test locally** (new packages are uncertified by default):
   ```bash
   python -m frontier_science eval --allow-uncertified --task <Domain>/<Task>
   python -m frontier_science run --allow-uncertified --task <Domain>/<Task> --budget 3
   ```
5. **Submit a Pull Request** to `main`. In the PR description, include:
   - Scientific background (1–2 sentences).
   - Oracle details (what it computes, dependencies, compute cost).
   - Baseline score and reference SoTA.
6. **Review**: maintainers will check oracle correctness, black-box safety, and scoring
   calibration before merging.

---

## LLM configuration (for testing)

The harness uses any OpenAI-compatible endpoint. Copy the example config and fill in your own:

```bash
cp frontier_science/conf/llm/openai_compatible.example.yaml frontier_science/conf/llm/local.yaml
# edit base_url / api_key / model
```

`local.yaml` is git-ignored. Never commit API keys.

---

> Questions? Open an Issue to discuss your task idea before writing code.
