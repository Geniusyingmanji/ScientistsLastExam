# PR74 fixed paired-grid replay under the integrated trusted runtime

2026-09-11. **All six sandbox evaluations passed and each candidate's complete metrics dictionary repeated identically.** The published `paired62208_refined` candidate scored **0.7751364580347875 development / 0.8142296791715209 heldout**. The unchanged current reference scored **0.7854573533368907 / 0.7967725500580608**. The fixed probe therefore retains 98.6860% of reference development score and exceeds heldout reference by 0.01745712911346009 (102.1910% of reference).

This supports the unresolved PR74 shortcut-separation finding in [issue 78](https://github.com/Geniusyingmanji/ScientistsLastExam/issues/78) at the task head pinned below. It does not measure frontier-model difficulty, certify the task, or prove an upper bound over other algorithms. The task remains outside the integrated task collection; no task card, oracle, reference, score normalization or admission policy was changed.

## Frozen source and method

- Task PR head: `8193c5aa6abff91ff8cbbce9f617518ff3bb9b61`.
- Integrated runtime: `2660c38a413fb7281d0e7012a6446eb384a934d1`.
- Runtime source SHA-256: `8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86`.
- Logical task: `Geophysics/FocalMechanismStressInversion`; physical package: `benchmarks/EarthScience/FocalMechanismStressInversion`. The driver explicitly sets `Geophysics -> EarthScience` in memory before `load_task_spec`; no PR layout/runtime file is imported.
- Linux Python 3.8.10, NumPy 1.24.4, SciPy 1.10.1. OMP, OpenBLAS, MKL and NumExpr thread counts are all 1. Each evaluation uses the declared 300-second timeout.
- Execution: 2026-09-11 05:07:15–05:08:49 UTC, independent `sle-pr74-audit-20260911` worktree. The baseline, reference and fixed probe were each evaluated twice through the integrated `sle.evaluate.evaluate_candidate`, which places candidate callbacks behind the real Linux sandbox boundary.

The probe is the complete, unchanged [published grid source](https://github.com/Geniusyingmanji/ScientistsLastExam/blob/8193c5aa6abff91ff8cbbce9f617518ff3bb9b61/.research/pr74_grid_probe.py), followed by only these fixed module constants:

```python
GRID_SHAPE = (24, 12, 24, 9)
PAIRED = True
QUERY_POLICY = "ambiguous"
SIGNED = True
LOCAL_ROUNDS = 3
THRESHOLD_DEG = 25.0
```

The tuple is the existing `paired62208_refined` row in [.research/pr74_diagnostics.py:99](https://github.com/Geniusyingmanji/ScientistsLastExam/blob/8193c5aa6abff91ff8cbbce9f617518ff3bb9b61/.research/pr74_diagnostics.py#L99). Its 25° refusal gate is the probe's own default retained in [known_best.md](https://github.com/Geniusyingmanji/ScientistsLastExam/blob/8193c5aa6abff91ff8cbbce9f617518ff3bb9b61/benchmarks/EarthScience/FocalMechanismStressInversion/references/known_best.md#L59). The author's diagnostic driver temporarily changes that gate to infinity for threshold postprocessing; this audit never executes that driver or adopts its instrumentation. No threshold sweep, new grid, parameter selection, fresh seed selection or model call was performed. The candidate's already-defined 62,208-point internal search and three local refinement rounds are part of the fixed algorithm being tested.

Static review confirmed that the probe imports only `itertools` and NumPy, uses public event IDs and both observed nodal planes, reads the public coarse/fine noise scales and budget, and calls the charged `reanalyze(event_id)` interface. It imports neither evaluator nor reference and accesses no files or network. All mathematical helpers are preserved byte-for-byte in the original source prefix. The baseline and reference also use public observations and permitted numerical libraries only. The derived source, original prefix length/hash, appended configuration and exact source URLs are committed together.

This is an exact replay of the *published author implementation and configuration* associated with the 0.814230 table row. The earlier maintainer's original four-dimensional implementation remains unavailable; the author describes this code as an independent member of that family. Those two provenance claims must not be conflated.

## Results and denominators

Every run had `valid=1`, development feasibility 1 and heldout feasibility 1. Development contains 5 supported and 3 unsupported catalogs; heldout contains 3 supported and 2 unsupported catalogs. Each catalog has 96 events.

| Candidate | Development normalized mechanism | Heldout normalized mechanism | Runtime seconds, two runs |
|---|---:|---:|---:|
| Baseline | 0.0 | 0.0 | 0.877 / 0.890 |
| Reference | 0.7854573533368907 | 0.7967725500580608 | 11.706 / 11.558 |
| Fixed paired62208_refined | 0.7751364580347875 | 0.8142296791715209 | 34.553 / 34.540 |

The mechanism metric is continuous reconstruction quality, not a binary correct-count ratio. `combined_score` and `robustness_score` are normalized above always-abstain. The oracle's unnormalized development `mechanism_score`, which also includes refusal credit, was 0.12319619278493557 / 0.8659108458355567 / 0.8594602862717422 for baseline / reference / probe respectively. Full unrounded scalar metrics are in the aggregate JSON.

| Candidate / split | False discovery count / denominator | Correct refusal count / denominator | Discovery coverage count / denominator | Paid units per catalog |
|---|---:|---:|---:|---:|
| Baseline / development | 3 / 3 | 0 / 3 | 5 / 5 | 0 |
| Baseline / heldout | 2 / 2 | 0 / 2 | 3 / 3 | 0 |
| Reference / development | 0 / 3 | 3 / 3 | 5 / 5 | 16 |
| Reference / heldout | 0 / 2 | 2 / 2 | 3 / 3 | 16 |
| Fixed probe / development | 0 / 3 | 3 / 3 | 5 / 5 | 16 |
| Fixed probe / heldout | 0 / 2 | 2 / 2 | 3 / 3 | 16 |

These are the oracle's emitted denominators: its `false_discovery_rate` divides false claims by **unsupported catalogs**, not by all positive claims. The correct-refusal denominator is the same unsupported set; coverage divides valid, non-abstaining supported submissions by supported catalogs. They should not be silently compared with tasks that define false discovery over all discoveries. Reference and probe each spent 128 units over the 8 development catalogs and 80 units over the 5 heldout catalogs. The probe's advantage did not arise from spending more paid credits; it did consume more CPU time.

The current probe score reproduces the published 0.775136 / 0.814230 after rounding. The reference differs slightly from the author's 0.783503 / 0.796709 measured under NumPy 1.26.4 / SciPy 1.13.1. This audit establishes within-environment repeatability; it does not isolate the cause of cross-environment differences. No constants were adjusted in response.

Even this single fixed probe fails the task author's disclosed separation requirement (reference advantage greater than 0.15 **and** probe below 75% of reference): development advantage is only 0.010320895302103228; heldout advantage is negative. This is an arithmetic check of the already-published task-specific rule, not a new global admission threshold or execution of the author's sweeping audit.

## Source hashes and evidence privacy

| Candidate | SHA-256 |
|---|---|
| Baseline | `1aee41922acfaa8bfdc23f7e2c88ad5187318df2965c4915b6b435044e262a83` |
| Reference | `3d2f071b414fe5a8e41e11d3140d10f72a76d9456236c2e2742934732b7f80e5` |
| Fixed paired62208_refined | `ce6a820bd33afa90be919d408622deabcb8269fcf769408f4e892d70a4719160` |

The original 6,801-byte grid source has SHA-256 `44d5e5395802141d762c8150e26b5e0a5ea6159f8f794807a03d652305621ddc` and Git blob `64ff3d2bf0ac706483d10e48b9de82bffde180f9`. All 20 task-package files were frozen before evaluation and rechecked afterward. The driver's own hash and task package hash are stored in the aggregate.

Complete metrics, including all 13 per-world rows per run, remain in `/home/azureuser/workspace-gzy/zyf/sle-pr74-private-20260911`: parent directory 0700, six JSON files 0600. Post-run validation checked each complete metrics hash, all 13 worlds valid, and full dictionary equality between repeats. Only scalar metrics and budget aggregates are exported; per-world records, artifacts and inferred parameters are not committed. The private raw files were not copied to the local checkout.

An initial transport preflight found macOS AppleDouble `._*` metadata before any sandbox evaluation. Only that audit's transport metadata was removed; original source hashes were unchanged. The six scientific evaluations then ran once as planned, with no infrastructure failures and no repeated or discarded scientific runs.

## Reproduction

Use a fresh independent checkout at the pinned integration revision, extract only the task package from the pinned PR74 head, and add the committed audit driver, source hashes and fixed candidate files. Keep Git HEAD at the pinned integration revision while executing, as enforced by the driver. Do not substitute the PR's old wrapper/runtime or an author oracle-import driver.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /usr/bin/python3 .research/audit_pr74_shortcuts_2026-09-11.py \
  --private-root /path/outside/checkout/to/new-private-evidence
```

The driver verifies the task archive, exact original probe prefix and appended constants, environment, runtime source hash and logical ID before running. It refuses to overwrite previous private evidence. This report and aggregate are independent review evidence; they do not request merging PR74 or altering scientific admission.
