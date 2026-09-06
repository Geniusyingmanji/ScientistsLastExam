# PermutationFlowShop — close the gap to a frozen makespan witness

## Scientific setting

The permutation flow shop is one of the oldest open problems in production scheduling:
every job visits the same m machines in the same order, the candidate fixes the job
sequence, and the makespan of the sequence is what a factory actually experiences.
Taillard's random instances (processing times uniform on {1..99}) have anchored the
field since 1993, and dozens of them remain unsolved to optimality after thirty years.
Verification is a pure simulation of the machine schedule, so a better sequence is
unambiguously better — no cap applies.

## Your task

```python
def schedule_flow_shop(problem):
    """Return a permutation listing every job index exactly once."""
```

`problem` is a mapping with the keys

```text
instance_id        stable identifier
seed               instance seed
jobs / machines    dimensions
processing_times   jobs-by-machines integer matrix; entry (j, k) is the time job j
                   spends on machine k, which every job visits in machine order
```

The development set is four fresh-seeded instances (20x5, 30x10, 50x5, 50x10); the
held-out set is three more (20x5, 30x5, 50x10). Instances are generated in the
Taillard style by the frozen seeds — no published table, best solution or heuristic
transfers, and memorization cannot help.

## Evaluation

- `combined_score` is the mean over development instances of the gap closed between
  the NEH construction (computed inside the oracle as the zero anchor — the as-given
  order is so weak that any competent construction closes over ninety percent of the
  gap, which would flatten the scale) and the frozen witness search:
  progress = (neh_makespan − achieved) / (neh_makespan − witness_makespan).
- The frozen witness is the shipped truth-blind reference run at 3000 iterations
  (see `references/known_best.md` for the table and the reproduction command) and
  defines score one. The runnable reference performs one full perturb-and-descent
  ILS cycle and scores `0.636364` development / `0.773495` held-out.
- Beating the frozen witness scores above one — the record is open and that is the point.
  A malformed permutation (missing job, repeat, wrong length) scores zero.
- `robustness_score` repeats the audit on the held-out instances.

This is a combinatorial optimization benchmark; nothing here certifies real factory
data.

## Oracle and difficulty

Scoring simulates the schedule exactly in integers (completion-time recursion), so
ties break deterministically and no floating point enters the verification. The
difficulty is entirely in the search: the insertion neighborhood is deceptively
tractable while the global problem is NP-hard and the tail between a good heuristic
and the witness is exactly where thirty years of literature live.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.

References: Taillard (1993), Eur. J. Oper. Res., doi:`10.1016/0377-2217(93)90182-M`;
Gmys et al. (2022), INFORMS J. Comput., doi:`10.1287/ijoc.2022.1193`. These motivate
the instance family and the open-record status; the benchmark uses fresh seeds.

## 关系与区别 / Relationship to nearby tasks

CirclePacking and NonlinearCodeRecords chase published mathematical records; this
task chases a combinatorial scheduling record on fresh-seeded instances, where
verification is an integer schedule simulation rather than a geometric or coding
check, and the anti-memorization design is the instance generator itself. No other
registry task covers production scheduling.

## Admission and reference scope

This package remains **candidate**. The runnable reference is NEH construction plus
seeded iterated local search with accelerated insertion evaluation (prefix/suffix
tables, O(m) per candidate position). Local shortcut and ablation diagnostics are
recorded in `references/known_best.md`; they do not replace clean Linux sandbox
replay, independent operations-research review or a frozen frontier-model calibration
draw.

The former 400-iteration default took 236 seconds on the maintainer's host. The
runnable reference now uses one complete ILS cycle, while the 3000-iteration results
remain frozen numeric record anchors in the trusted evaluator. The package declares
5 seconds expected evaluation time and keeps a 300-second candidate timeout; a local
direct reference evaluation took 0.93 seconds on 2026-09-06. The search budget is
intentional rather than an accidental unlimited run.

## Frontier-Eng overlap comparison (2026-09-06)

同类不同题. Nearest catalog entries: JobShop/abz; JobShop/ft; JobShop/la; JobShop/orb; JobShop/swv; JobShop/ta; JobShop/yn. Submit one common job permutation on all machines with a fixed common route; FE JSSP permits job-specific routes and operation schedules. Fresh seeds prevent table lookup but do not establish novelty. PFSP is a restricted scheduling problem with the same makespan objective: admission is explicitly pending a maintainer decision, not declared clear.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
