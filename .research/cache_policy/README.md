# CacheReplacementPolicyID: construction scripts

Every number in the task's `Task.md`, `TASK_CARD.yaml`, `references/known_best.md` and its
certification entry comes from the scripts in the first group, run against the package's own
evaluator (`benchmarks/ComputerScience/CacheReplacementPolicyID/verification/evaluator.py`).
`summary.py` recomputes all of them from the recorded runs and a fresh evaluation.

| script | what it does | output |
|---|---|---|
| `pkg_eval.py reference\|original\|baseline [shift ...]` | evaluates the reference (`verification/reference_permutation_augmented.py`), the original builder reference (`verification/reference_lstar_family.py`, now an omission probe) or the baseline, with every world's run seed shifted by 7919 per shift | `pkg_reference_robust.jsonl` (shifts 0 to 15), `pkg_original_robust.jsonl`, `pkg_baseline_robust.jsonl` (shifts 0 to 7) |
| `ladder.py NAME [shift ...]` | the ablation ladder, one choice of the reference changed at a time, and blind claims; `NAME@key=value,...` overrides a configuration | `ladder.jsonl` (shifts 0 to 7) |
| `grid.py list\|run PART OF\|best K [shift ...]` | the fixed 343-cell shortcut grid: every cell leaves out at least one of the reference's learners or replaces it with a textbook-template fit; declared in full before any cell runs | `grid.jsonl` (every cell on shift 0, the best cells on shifts 1 to 7) |
| `det_diag.py FIRST LAST` | both determinism statistics in every world over a range of shifts, the pooled one after 24, 32, 40 and 48 traces | `det_diag.jsonl` (shifts 0 to 23) |
| `summary.py` | recomputes every quoted number | stdout |

The second group is the prototype the task was designed on, with its own cache simulator whose
run seeding differs from the evaluator's. Its numbers are superseded by the first group and are not
quoted anywhere.

| script | what it was |
|---|---|
| `engine.py` | policies, machines, minimisation, equivalence and a noisy cache |
| `learn.py` | victim queries, L* with Maler-Pnueli and Rivest-Schapire counterexamples, random-trace checks |
| `ref.py` | the prototype reference: determinism tests, the age-table library, targeted checks |
| `permfit.py` | the prototype of the permutation-policy fit that is now part of the reference |
| `worlds_proto.py` | the prototype world set, from which the evaluator's worlds were written out |
| `probe.py` | the prototype ladder and probe |
