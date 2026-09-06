# ScalingLawIdentification — identify the asymptotic law of a black-box program

## Scientific setting

Empirical algorithm analysis profiles a program at chosen input sizes and infers its
asymptotic complexity class from noisy run times. Two worlds make a confident class
claim a false discovery: a runtime that branches on the input size (no single law
exists), and a noise floor so large the law is unrecoverable from any affordable
ladder.

## Your task

```python
def identify_scaling_law(problem, time_run, budget_units):
    """Return {"class_probabilities": mapping over the six classes summing to one,
               "scale": positive constant, "abstain": bool, "confidence": [0,1]}."""
```

`problem` is a mapping with the keys

```text
classes / class_shapes   the six public forms c, c*log2(m), c*m, c*m*log2(m),
                          c*m^2, c*2^(m/8)
size_bounds              [8, 384]
cost_tiers               size <= 64 costs 1, <= 192 costs 2, otherwise 3
budget_units             9
noise_note               multiplicative noise; repeats draw fresh noise
refusal_note             branching runtimes and jitter floors must be refused
```

`time_run(size)` charges by tier and returns `{size, runtime_ms, budget_cost}`.
Repeated sizes are allowed and draw fresh noise. Overspending or malformed calls
invalidate the world even when caught.

## Evaluation

- `combined_score` is development mechanism recovery above the always-abstain
  baseline: geometric mean of the true class probability, a log-scale score for the
  constant, and a sealed extrapolation of the runtime at size 700 under seven
  percent multiplicative noise.
- Branch and jitter worlds score refusal only; abstaining scores one and any class
  claim scores zero.
- Class probability, false discovery rate, correct refusal rate and discovery
  coverage are reported with denominators; a full abstention scores exactly zero.
- `robustness_score` repeats the audit on held-out classes, scales and failures.

This is a deterministic synthetic profiler, not a claim about any real program.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Profiler errors and overspending invalidate the world even when caught.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

Reference: Cormen, Leiserson, Rivest & Stein, *Introduction to Algorithms*, ISBN
`9780262033848`, for the asymptotic-class family.

## 关系与区别 / Relationship to nearby tasks

SequenceLawRecovery recovers exact integer recurrences; ChronoamperometryLawID
identifies electrochemical law families from functional transients. This task infers
an asymptotic complexity class from budgeted noisy timings, with branching-runtime
and jitter refusal worlds and a sealed out-of-ladder extrapolation that separates the
polynomial classes from the exponential tail.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only: a
seven-size ladder covering both mod-3 residue classes and a repeated size, per-class
log-space regression with an exponent penalty, a split-fit branch test and a
repeat-estimated jitter gate. Local shortcut and ablation diagnostics are recorded in
`references/known_best.md`; they do not replace clean Linux sandbox replay,
independent review or a frozen frontier-model calibration draw.

## Frontier-Eng overlap comparison (2026-09-06)

无. Nearest catalog entries: MallocLab; MLA; FlashAttention; TriMul. Pay to observe a black-box size ladder, classify asymptotic runtime and refuse branching/noise floors. FE implements faster kernels/allocators rather than inferring a law from budgeted timings.

See `.research/pr9_frontier_eng_overlap_2026-09-06.md` for the pinned 47-task paper and complete available repository catalog. The requested 95-entry source could not be reconciled with the available 78 rows (84 expanded tasks); source reconciliation and maintainer acceptance remain pending.
