# PR30 fixed LP-helper replay: baseline/reference valid, LP comparison incomplete

2026-09-11. **The six predeclared sandbox calls completed: four baseline/reference calls were scientifically valid, while both unchanged LP-helper calls failed with `candidate_worker_exit`.** Baseline score was 0.0 and reference score was 0.459105, each with 4/4 valid certificates and identical complete repeated metrics. The LP candidate has **no usable scientific score** in this audit. Its `INVALID_SCORE=-1e18` is a runtime sentinel, not a negative optimization result.

This audit neither confirms nor refutes the LP ceiling result reported in [issue 78](https://github.com/Geniusyingmanji/ScientistsLastExam/issues/78) for this latest task head. It is explicitly a **related current fixed-helper replay**: the original 155-line, pure-standard-library candidate from that issue remains unavailable, and this implementation uses SciPy. No scientific admission status, task card, evaluator, reference, algorithm parameters or runtime implementation was changed.

## Fixed provenance and candidate boundary

- Task head: `90366563a7605e8f6eb6226200b1463615419b4a`.
- Runtime revision: `2660c38a413fb7281d0e7012a6446eb384a934d1`.
- Runtime SHA-256: `8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`.
- Logical ID: `ScientificComputing/AffineLoopRankingCertificate`; physical task package: `benchmarks/ComputerScience/AffineLoopRankingCertificate`. The review driver explicitly adds `ScientificComputing -> ComputerScience` only in its loader process.
- Independent Linux worktree: `sle-pr30-audit-20260911`; Python 3.8.10, NumPy 1.24.4, SciPy 1.10.1; OMP/OpenBLAS/MKL/NumExpr thread environment variables all 1. Timeout: 300 seconds per evaluation.
- Six calls occurred between 2026-09-11 05:15:12 and 05:17:49 UTC. They all used the fixed integrated `sle.evaluate.evaluate_candidate` and real candidate sandbox.

The LP candidate preserves the complete 3,931-byte [tests/affine_ranking_lp.py](https://github.com/Geniusyingmanji/ScientistsLastExam/blob/90366563a7605e8f6eb6226200b1463615419b4a/tests/affine_ranking_lp.py) as an exact prefix. Its original SHA-256 is `6d5a9d2b8550cc84f93aae27935ca02abe2d3c8a1d2175fb75f8ccfbfa4f9207` and Git blob is `d37f67344252969a104a0b24736f60074e754125`. Only a `build_ranking` entrypoint and exact rational decode/encode adapter are appended. The adapter reads `instance.guards`, `instance.A` and `instance.b`; it does not branch on instance names or read hidden optima, certificate tables, evaluator functions or files.

The unchanged helper constructs the Farkas LP from those public coefficients, invokes `scipy.optimize.linprog(..., method="highs")` with its original defaults, selects a numerical basis, reconstructs it using `Fraction` Gaussian elimination and checks exact equalities/nonnegativity. The adapter only converts the returned rationals to the declared `[numerator, denominator]` form. The task oracle remains responsible for exact unit 1-norm, public magnitude caps and both Farkas certificates; no check was weakened. Imports are limited to standard-library fractions, NumPy and SciPy, which are within the task's stated numerical-library contract.

No evaluator or author test driver was imported into the candidate. No model call, parameter sweep, alternative LP method, solver-option change or new strategy was tested within these six calls. In particular, the LP candidate was not modified after its first worker failure.

## Observed outcomes

| Candidate | Calls | Complete repeated metrics | Valid certificates | Combined score | Runtime seconds |
|---|---:|---|---:|---:|---:|
| Baseline | 2 | Identical | 4 / 4 each | 0.0 | 0.660 / 0.654 |
| Reference | 2 | Identical | 4 / 4 each | 0.459105 | 0.936 / 1.029 |
| Fixed LP helper + adapter | 2 | Identical failure payloads | Unavailable | Invalid / unavailable | 0.895 / 0.905 |

The four optimization instances have dimensions 8, 10, 12 and 16. Baseline per-instance scores were all zero. The reference's per-instance score range was 0.366159–0.535373, with mean 0.459105. The oracle rounds its per-instance and combined scores to six decimals; these values are the emitted precision, not reconstructed higher-precision estimates. There is no development/heldout split or discovery/FDR/refusal axis for this task, and none was invented.

Both LP payloads contained `valid=0`, `candidate_failure_kind="candidate_worker_exit"`, and the invalid-score sentinel. They contained no `per_instance` rows or feasibility rate. They were **not marked `infrastructure_failure` by the current runtime**. This is the observed taxonomy, not proof that the algorithm is mathematically wrong or that the environment is compatible: the taxonomy does not preserve a lower-level cause here. A possible interaction between HiGHS thread creation and the sandbox's single-process/thread policy remains an unverified hypothesis in this report. Engineering diagnosis is separate from these six fixed task evaluations.

The initial driver stops on a failed candidate, so it stopped after the fifth call. A separately committed continuation driver verified the pinned runtime, task files, environment, original driver hash, fixed candidate hash, first failure payload and exact 2/2/1 call counts, then performed **only** the missing sixth call. It did not overwrite or rerun the first five. The aggregate records both driver hashes and this continuation. `all_repeats_identical=true` includes two identical failures; `scientifically_valid_evaluations=4` and `all_candidates_scientifically_valid=false` prevent that flag from implying successful scientific replay.

The current PR documentation already acknowledges that a complete LP reaches the normalized ceiling. That remains author-reported evidence; this audit has not independently re-established it through the pinned current sandbox. The scientific comparison is incomplete, and the missing original issue-78 source is a separate provenance gap.

## Evidence and privacy

| Candidate | SHA-256 |
|---|---|
| Baseline | `727ca3e49e35dc16e633ac0919982fee2a0811efea2066785f02df1038c445ec` |
| Reference | `6f92e7ce8680baebf063924022b6664094f29c1e9e0fc0506321b6e32c42f01e` |
| Fixed LP helper + public adapter | `0edd2d00f3d22286e7e33daad4ec1cfb6bc5610f1a1de1e7ceca2521a96f623d` |

All 16 task files were frozen and checked against the PR archive. The original helper Git blob, candidate bytes, appended adapter and both executed drivers are hash-bound in the committed provenance/aggregate. The first driver and continuation driver are preserved as executed, rather than edited to hide the fifth-call failure.

Six raw payloads remain in `/home/azureuser/workspace-gzy/zyf/sle-pr30-private-20260911` (0700 parent, 0600 files). Full per-instance rows and exact proven deltas from successful calls were not exported; the oracle does not include complete ranking vectors in its metric output. Local public evidence contains scalar metrics, instance-count/score aggregates and complete-payload hashes only. Post-run checks verified all raw hashes, equality of each pair, four valid baseline/reference calls and the two LP worker failures. No private raw file was copied into the local checkout.

## Reproduction boundary

In a new independent checkout at the pinned runtime revision, extract only the PR30 task package and overlay the committed audit driver, source manifest and candidate files without changing HEAD. Use a new private evidence directory outside the checkout:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /usr/bin/python3 .research/audit_pr30_shortcuts_2026-09-11.py \
  --private-root /path/outside/checkout/to/new-private-evidence
```

If and only if it reaches the same fifth-call `candidate_worker_exit`, the guarded `complete_pr30_shortcut_repeat_2026-09-11.py PRIVATE_ROOT` completes the sixth predeclared same-source attempt. Both commands require the same pinned thread environment. Any later solver or sandbox compatibility change must receive separate provenance and new evidence; it must not be retroactively substituted for these two failures or presented as the missing original 155-line candidate.
