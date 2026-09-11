# ClockSyncInversion: construction scripts

Every number in the task's `Task.md`, `TASK_CARD.yaml`, `references/known_best.md` and its
certification entry comes from the scripts in the first group, run against the package's own
evaluator (`benchmarks/ComputerScience/ClockSyncInversion/verification/evaluator.py`).
`summary.py` recomputes all of them from the recorded runs and a fresh evaluation.

| script | what it does | output |
|---|---|---|
| `pkg_eval.py reference\|baseline\|reference@key=value,... [shift ...]` | evaluates the reference, the baseline or a reference variant, with every world's run seed shifted by 7919 per shift | `pkg_reference_robust.jsonl` (shifts 0 to 15), `pkg_baseline_robust.jsonl` (shifts 0 to 7) |
| `ladder.py NAME\|ladder\|probe\|all [shift ...]` | the ablation ladder, the headroom (`headroom_z3`) and the 29-strategy shortcut probe | `ladder.jsonl`, `probe.jsonl` (shifts 0 to 7) |
| `summary.py` | recomputes every quoted number, including the worlds' identifiable widths and kappa* | stdout |

The second group is the prototype the task was designed on, with its own campaign seeding. Its
numbers are superseded by the first group and are not quoted anywhere. The package's worlds are
drawn by the same code from the same seeds, and `summary.py`'s widths and kappa* match it.

| script | what it was |
|---|---|
| `engine.py` | clocks, delays, the campaign, the identifiable widths and both detectability measures |
| `ref.py` | the prototype reference and its variants |
| `run.py` | the prototype runner, with NTP strategies |
| `worlds.py` | the prototype world set, from which the evaluator's worlds were written out |
