# PR30 revised-simplex follow-up: two fixed calls, comparison still incomplete

2026-09-11. **Both independently planned revised-simplex candidate calls failed with `candidate_runtime_error`; neither produced a usable scientific score.** Their complete returned payloads are identical. This report preserves those failures and makes no task-ceiling, difficulty or admission claim. The prior six-call evidence and its two HiGHS worker failures remain unchanged.

The follow-up was authorized after the separate [zero-task-data LP compatibility diagnosis](https://github.com/Geniusyingmanji/ScientistsLastExam/blob/e0a7c129b2e4dd88637e52526afcd160dee901eb/.research/pr30_lp_compatibility_2026-09-11.md) found that its fixed two-variable `revised simplex` micro candidate worked in this environment, while the HiGHS variants exited. That engineering result motivated this one preselected backend substitution; it did not establish that this task's full LP helper or exact reconstruction would succeed. No further method or parameter was tried after these two failures.

## One frozen change

Task head: `90366563a7605e8f6eb6226200b1463615419b4a`. Runtime: `2660c38a413fb7281d0e7012a6446eb384a934d1`, source SHA-256 `8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`. The independent `sle-pr30-simplex-audit-20260911` Linux worktree uses Python 3.8.10, NumPy 1.24.4 and SciPy 1.10.1, with OMP/OpenBLAS/MKL/NumExpr variables set to 1 and a 300-second per-call timeout.

Starting with the candidate frozen in prior evidence commit `967be15528a95613defc2bd2af5fb5022c616184`, exactly one line changed:

```diff
-    result = linprog(-cf, A_eq=af, b_eq=bf, bounds=[(0, None)] * nvars, method="highs")
+    result = linprog(-cf, A_eq=af, b_eq=bf, bounds=[(0, None)] * nvars, method="revised simplex")
```

Prior candidate SHA-256: `0edd2d00f3d22286e7e33daad4ec1cfb6bc5610f1a1de1e7ceca2521a96f623d`.
New candidate SHA-256: `e64e17faa29645ddd656b3c134a76096c98b6191b0e87e0ff11dd5dda02f3342`.

The Farkas LP formulation, basis-selection code, Fraction reconstruction, exact checks and public rational input/output adapter are otherwise byte-for-byte unchanged. No solver option, tolerance or iteration budget was changed. The new driver reverses the one method-string replacement and checks the previous complete candidate hash before allowing evaluation.

The candidate still reads only public guards/A/b and imports fractions, NumPy and SciPy. It does not read hidden optima, labels, answer tables, oracle/reference functions or files. It remains a related current helper implementation, **not** the missing original [issue-78](https://github.com/Geniusyingmanji/ScientistsLastExam/issues/78) 155-line pure-standard-library probe.

## Observed results and comparison boundary

| Plan / candidate | Calls | Scientific status | Combined score | Runtime seconds |
|---|---:|---|---:|---:|
| Prior six-call plan / baseline | 2 | 4/4 certificates valid each | 0.0 | 0.660 / 0.654 |
| Prior six-call plan / reference | 2 | 4/4 certificates valid each | 0.459105 | 0.936 / 1.029 |
| Prior six-call plan / HiGHS helper | 2 | `candidate_worker_exit` | Unavailable | 0.895 / 0.905 |
| This independent plan / revised-simplex helper | 2 | `candidate_runtime_error` | Unavailable | 0.981 / 0.958 |

**No baseline or reference was rerun in this follow-up.** The aggregate records the prior report hash, evidence commit, reference candidate hash, task package hash, runtime hash and environment versions. This is a comparison across two independent plans with the same task/runtime/environment, not one eight-call experiment retroactively changing its candidate policy.

Both new results have `valid=0`, `candidate_failure_kind="candidate_runtime_error"`, and no feasibility rate or per-instance rows. The current runtime did not mark them as `infrastructure_failure`. `INVALID_SCORE=-1e18` is retained in the aggregate solely as the raw runtime sentinel; it is not an optimization score and cannot be used to rank the LP below the reference.

The changed failure category does not identify the precise failing line or establish a mathematical cause. The returned taxonomy contains no underlying exception detail. This plan did not instrument the candidate, change its source again, run more task evaluations or try another solver. The micro LP's success and the full candidate's failure therefore remain separate facts.

PR30 is an optimization task with four public instances (dimensions 8, 10, 12 and 16), not a development/heldout discovery benchmark. No discovery/FDR/refusal values or missing per-instance objectives were fabricated. The task-level LP comparison remains **invalid/incomplete**. These two runs neither confirm nor refute the claimed ceiling and do not overwrite the prior two worker-exit records.

## Evidence preservation

The private directory `/home/azureuser/workspace-gzy/zyf/sle-pr30-simplex-private-20260911` is separate from the original six-call directory. It contains exactly two 0600 raw JSON payloads under a 0700 parent. Their complete metric hashes were checked against the aggregate and match each other. No raw payload was copied to the local checkout; public evidence includes scalar outcomes, complete-payload hashes and empty instance aggregates only.

All 16 task files were frozen against the original task archive, and the driver checked task/runtime hashes before and after the two calls. The public candidate, original-hash-reversibility check, single-line patch and executed driver are committed. The original six-call reports, candidates and private files were not edited or replaced.

For reproduction, use a new independent checkout at the pinned runtime revision, extract the same task package, and overlay this follow-up's driver, manifest and candidate files while keeping HEAD at that runtime revision. Choose an empty private directory outside the checkout:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /usr/bin/python3 .research/audit_pr30_simplex_2026-09-11.py \
  --private-root /path/outside/checkout/to/new-simplex-private-evidence
```

The driver executes exactly two calls even when a candidate outcome is invalid and preserves both outcomes. Any future change requires a separately authorized plan and distinct provenance; these results remain part of the audit history.
