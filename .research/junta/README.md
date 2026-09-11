# JuntaVariableDiscovery: construction scripts

Every number in the task's `Task.md`, `TASK_CARD.yaml`, `references/known_best.md` and its
certification entry comes from these scripts, run against the package's own evaluator
(`benchmarks/ComputerScience/JuntaVariableDiscovery/verification/evaluator.py`). `summary.py`
recomputes all of them from a fresh evaluation.

| script | what it does |
|---|---|
| `summary.py` | recomputes every quoted number: reference and baseline, the margin-and-budget ladder, the shortcut probe, the worlds' kappa*, all over twelve run-seed shifts |
| `pkg_eval.py` | evaluates the reference, the baseline and named variants against the delivered evaluator, with each world's run seed shifted by 7919 per shift |
| `probe.py` | the shortcut strategies and the fixed-margin ladder solvers, importable by `summary.py` |
| `ladder.jsonl`, `probe.jsonl`, `reference_robust.jsonl` | the recorded outputs |

The second group is the prototype the task was designed on, with its own campaign seeding. Its
numbers are superseded by the delivered evaluator and are not quoted anywhere.

| script | what it was |
|---|---|
| `eng.py` | prototype world, campaign and influence oracle |
| `solve.py` | prototype reference, correlation baseline and their variants |
