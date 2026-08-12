# Sequence law recovery

Given the first terms of an integer sequence, state the linear recurrence that produced it.

## Two things make this more than linear algebra

**A finite prefix never determines an infinite object.** A prefix of length L is consistent with
every recurrence of order above L/2. Some sequences here are shown with just too few terms to pin
a unique minimal rule: two different rules of the same order fit everything you can see and
disagree afterwards. Declining is the only correct answer there.

**Some terms are wrong.** Real sequence tables carry transcription errors, and a rule that must
reproduce every term you were shown is the wrong target. What matters is the continuation.

## Your function

```python
def recover_law(observation) -> dict:
    ...
```

`observation` gives `terms`, the `horizon` your rule will be checked over, and `max_order`. Return

```python
{"coefficients": [c0, c1, ...]}    # a[n] = c0*a[n-1] + c1*a[n-2] + ...
{"abstain": True}                   # when the terms do not pin a rule
```

## Oracle

Recurrences are verified exactly over the integers with **SymPy**, and the evaluator uses SymPy's
exact rank computations to decide whether a prefix pins a unique minimal rule. Exact arithmetic is
the point: a floating-point fit accepts coefficients that are merely close, and a rule with nearly
right coefficients diverges from the continuation immediately.

## Three axes, reported separately

- **mechanism** — the rule reproduces the held-out continuation exactly. Fitting the visible terms
  is not enough and is not what is scored.
- **false discovery rate** — of the rules claimed, how many fit everything shown and still get the
  continuation wrong. That is a rule the prefix allowed rather than one the sequence has.
- **calibrated refusal** — the under-determined sequences. Abstaining is correct there and wrong
  elsewhere; abstaining on a determined sequence scores zero for it.

## Rules

- Only edit `solution.py`; keep `recover_law(observation)`.
- Integer coefficients, order at most 6.
- Deterministic CPU code. The standard library, NumPy, SciPy and SymPy are available.
- `frontier_science.contract_lint` is importable and free to call for shape checks.
- Do not read `verification/` or `frontier_eval/`.

## Difficulty

Sequences are generated from a seeded draw over order, coefficients and seed terms. Harder levels
raise the order, widen the coefficients and corrupt more terms. Roughly a third of each set is
under-determined and a third carries corrupted terms; the rest are clean, so a method that assumes
corruption everywhere is not free either.
