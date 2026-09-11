# LDMismatchFineMapping construction scripts

The historical builder scripts below produced the original construction numbers. Their
runtime estimates describe the builder's environment, and `probe.py` can resume previous
temporary output; neither is the final admission record.

The post-builder fixed screen is `admission_audit.py`: it requires a new output directory,
records the complete 1,120-cell plan, runs all 29 reference/ablation/control rungs and checks
all equal-size joint-swap alternatives. It never resumes or reads prior strategy scores.
Its Linux result and artifact hashes are in `admission_2026-09-11.json`; the final review,
Linux sandbox validation and limits are in `review_2026-09-11.md`.

Run construction scripts from the repository root with the project interpreter. They import
the task's oracle directly, so their results must remain separate from real sandbox gate and
model-calibration evidence.

| script | what it produces | runtime |
|---|---|---|
| `run_both.py` | reference and baseline metrics with one row per world | about 5 s |
| `trace.py` | for every graded world, the reference's configuration, swap margin and rows next to the truth | about 3 s |
| `worlds.py` | the construction statistics of every graded world: mismatch, the single-world trap proxy, the masked partner's rank and sign, the weakest multi signal's rank, the near-duplicate's correlation in the cohort and in the panel, the resolvability gap | about 3 s |
| `checks.py` | Python 3.8 syntax, determinism, blanket abstention in both forms, the top-|z| and fixed-variant candidates, twenty-three malformed candidate shapes, repeat rows and the budget | about 1 min |
| `ablation.py` | the difficulty ladder, one reference choice changed at a time (`FM_ONLY=<substring>` restricts to matching rungs) | about 40 s |
| `probe.py` | the low-dimensional shortcut probe over purchase rule, model, refusal and effects; appends one JSON line per strategy to the system temporary directory and resumes if interrupted | about 40 min |
| `robust.py` | the reference on `FM_N` extra worlds of every kind outside the graded seeds (default 25): mechanism, false discoveries, margins, gaps and construction attempts | about 1 min |

JSON side outputs go to the system temporary directory.
