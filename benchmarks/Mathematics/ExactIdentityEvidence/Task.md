# ExactIdentityEvidence — audit claimed identities against purchasable precision

## Scientific setting

Experimental mathematics certifies identities by evaluating them to high precision
and applying an integer-relation search (PSLQ-class methods). The honest discipline
has three parts: recover the integer row behind a near-vanishing combination, certify
exactness only when the purchasable precision outruns the scale at which a deviation
could hide, and refuse when a value's precision cap makes the residual forever
unobservable. A claimed identity that merely looks exact at twelve digits is exactly
how numerical coincidences become false discoveries.

## Your task

```python
def audit_identity_claims(problem, purchase, budget_units):
    """Return a mapping with exactly:
      verdicts: mapping claim id -> "exact" | "false" | "undecidable"
      coefficients: claim id -> [a, b, c] for exact verdicts only
      confidence: finite scalar in [0,1]
    """
```

`problem` is a mapping with the keys

```text
values            list of {name, digits, precision_cap}; twelve significant digits are
                  free, and precision_cap is the finest tier the value can ever reach
base_precision   12
precision_tiers   [40, 80, 150]
purchase_budget   10
claims            list of {id, values, coefficient_bound}; each claim asserts that its
                  three values satisfy a*x + b*y + c*z = 0 with the common factor
                  removed and |a|,|b|,|c| within the bound
epsilon_floor     any deviation in a value is either zero or at least 1e-70 in magnitude
claim_note        verdict semantics, including the false-rejection penalty below
```

`purchase(name, precision)` charges one unit, accepts a published tier, and returns
`{name, precision, digits, budget_cost}` — the value's digits truncated at that
precision (never beyond its public cap). Overspending, an unknown tier or malformed
calls invalidate the world even when caught.

## Evaluation

- Per claim: an exactly true relation scores 1.0 for `exact` with the recovered row
  (0.5 for the right verdict with the wrong row), 0.0 for `undecidable`, and **−0.5**
  for `false` — a certified rejection of a true relation is an error below abstention.
  A false relation scores 1.0 for `false`, 0.0 otherwise (an `exact` verdict is also
  counted as a false discovery). A claim whose values include a cap below the
  epsilon-floor exponent scores 1.0 for `undecidable` — no purchasable precision can
  separate a zero residual from a hidden deviation — and 0.0 otherwise.
- `combined_score` is the development mean above the all-undecided auditor (the
  passive floor), which scores exactly zero after normalization.
- False discovery rate and discovery coverage are reported with their denominators.
- `robustness_score` repeats the audit on held-out values, epsilons and caps.

This is a synthetic exact-arithmetic world, not a claim about any published constant.

## Oracle and difficulty

Values are integer combinations of six hidden exact bases (pi, ln 2, ln 3, sqrt 2,
e, phi) computed by pure-integer series (Machin, atanh, Newton, factorial) to any
precision. A few values carry one planted decimal epsilon: hard-false epsilons
(1e-25..1e-54) need purchased digits to see; capped epsilons sit below their value's
public cap forever. Twelve claims per world mix five exact, three grossly false,
two hard-false and two undecidable.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy/stdlib code only (the `decimal` and `fractions`
  modules are stdlib); no network or process creation. Use exact or
  sufficiently-precise arithmetic — default floating point cannot certify anything
  here.
- Do not read `verification/` or `frontier_eval/`.
- Use `sle.contract_lint` for free local shape checks before returning an inference.

References: Ferguson, Bailey & Arno (1999), Math. Comp., doi:`10.1090/S0025-5718-99-01081-3`.
This motivates integer-relation certification; the benchmark uses the synthetic world
stated above.

## 关系与区别 / Relationship to nearby tasks

SequenceLawRecovery recovers recurrences from integer terms (no precision economics);
DiscrepantMeasurements reconciles noisy physical measurements. This task's evidence
is exact digit strings whose residual structure is deterministic: the difficulty is
precision economics (which values to buy at which tier), calibrated refusal at a
public precision cap, and the asymmetry between an uncertified guess and a certified
verdict.

## Admission and reference scope

This package remains **candidate**. The runnable reference uses public inputs only:
base-precision brute-force row fits, cap-driven refusal without spending, and
fewest-missing-first purchases at the 80-digit tier until the budget runs out. Local
shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do
not replace clean Linux sandbox replay, independent review or a frozen frontier-model
calibration draw.
