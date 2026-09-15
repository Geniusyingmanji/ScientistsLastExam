# EllipticCurveRecovery — evidence-supported coefficient recovery

A hidden arithmetic object provides exact point counts at selected finite-field
primes. Recover the bounded integer coefficients of `y² = x³ + ax + b` when the
measurements determine a unique nonsingular pair. Refuse singular-only or empty
compatibility sets, and indistinguishable nonsingular coefficient pairs.

```python
def recover_curve(problem, count_points, budget_units):
    return {"a": 0, "b": 1, "abstain": False, "confidence": 0.8}
```

`problem` contains:

```text
curve_family      y^2 = x^3 + a*x + b, |a|,|b| <= 1200, nonzero discriminant
coefficient_bound 1200 (integer bound on each coefficient)
prime_list        all queryable primes
cost_tiers        prime <= 100 costs 1, <= 1000 costs 2, otherwise 3
budget_units      5
answer_semantics  exact projective point counts, including the point at infinity
refusal_note      singular-only, empty and indistinguishable nonsingular cases
```

`count_points(prime)` charges by tier and returns `{prime, point_count, budget_cost}`.
Both budget fields equal five. Repeated calls are charged and return the same exact
count, so they do not add information. Unknown primes, noninteger inputs (including
`11.0`, strings and booleans), and overspending invalidate that world even if caught.

Return integer coefficients in the public window, boolean `abstain`, and finite
`confidence` in [0,1]. With abstention, omit both coefficients or set them to `None`.
A **singular integer claim is syntactically valid but scientifically wrong**. On a
refusal world it is a false discovery and scores zero; it does not invalidate the
whole evaluation. Floats, strings and booleans are not coefficient integers.

## Evaluation

Recovery earns one on a supported world only if the returned pair is correct
**and all the actual purchased counts together isolate it as the unique
nonsingular pair in the entire public window**. The evaluator independently
recomputes this compatibility set. No queries, one prime, or a transcript that
still admits competing nonsingular pairs gives zero recovery credit, even if a
memorized answer happens to equal the hidden pair. There is no reward for unspent
budget. Uncertainty must be reduced by scientifically informative measurements.

Supported abstention earns zero. Unsupported worlds earn one for refusal and zero
for a claim. The mean is normalized above the always-abstain baseline and clipped
to [0,1], making complete abstention exactly zero. The development cohort has
24 supported worlds and four worlds of each refusal kind; heldout has 18 supported
and four of each refusal kind. Aggregation yields a graded recovery rate across
worlds; individual recovery certificates are exact. `combined_score` uses
development and `robustness_score` uses heldout.

The three refusal causes differ: a singular cubic leaves only discriminant-zero
lifts; a smooth genus-two quintic can leave no bounded cubic lift; Q-isomorphic
curves `(a,b)` and `(16a,64b)` have identical counts at every listed prime and
cannot be distinguished as coefficient pairs. A genus-two curve need not violate
the elliptic Hasse interval at any single queried prime: joint bounded consistency
is the decisive test. These are finite-window statements, not a theorem that
arbitrary genus-two counts always exclude every elliptic curve.

`development_evidence_support_score` and `heldout_evidence_support_score` report
supported certificate coverage. Per-world diagnostics include
`compatible_curve_count`, `queried_prime_count`, `budget_used`,
`intrinsic_mechanism_score` and `evidence_support_score`. Compatibility counts
are computed for claims; zero in an unexamined row is not proof of an empty set.
Mechanism recovery, false discovery, refusal and discovery coverage are reported
separately with denominators. Confidence predicts response quality and is scored
as one minus squared error. Invalid rows earn zero and are not discovery attempts.
`valid=1` means at least one valid development world; `feasibility_rate` gives the
fraction. One malformed world does not erase other valid recovery. All-invalid returned
artifacts return `valid=0, combined_score=0`.

Use `sle.contract_lint` for free local submission-shape checks.
Only edit `solution.py`. Use deterministic Python/NumPy/SciPy/stdlib, with no
network or process creation. Do not read `verification/` or `frontier_eval/`.

## Sources and relationship to nearby tasks

Silverman, *The Arithmetic of Elliptic Curves*, ISBN `9780387094939`, supplies the
elliptic-curve model; [MIT hyperelliptic definitions](https://math.mit.edu/~drew/Definitions.html)
support the odd-degree genus-two point-count model.
SequenceLawRecovery infers integer recurrences; ExactIdentityEvidence certifies
identities from digits; BlackBoxGroupIdentification classifies group structure.
This task instead acquires finite-field counts to identify a bounded coefficient
pair, with exact evidence and family/isomorphism refusal.

The Frontier-Eng comparison is in
`.research/elliptic_curve_recovery_frontier_eng_overlap_2026-09-07.md`.
The package remains **candidate**. Reference, shortcuts, capability ablations and
review history are in `references/known_best.md`. Repository-visible frozen worlds
remain enumerable; evidence checks block unqueried answers but cannot establish
that a candidate did not memorize an informative query policy. Fresh server-held
worlds, independent review and frontier-model calibration remain pending.

Each sandbox world starts a fresh candidate session. Module globals and temporary
files cannot carry a world index or previous answers across worlds.

The per-world validity rule applies to decoded artifacts and caught oracle-call
errors. Worker crashes, uncaught runtime errors, sandbox violations and the overall
timeout fail the run through the trusted harness.

Measured capability comparisons (development / heldout):

| Variant | Scores |
|---|---|
| Full witness | 0.875000 / 0.944444 |
| Fixed prime order | 0.875000 / 0.777778 |
| Without singularity filtering | 0.791667 / 0.833333 |
| Three-query limit | 0.000000 / 0.000000 |
| Four-query limit | 0.166667 / 0.111111 |

These are diagnostic capability comparisons, not model calibration.

The external `frontier_eval/run_eval.py` writes only search-visible metrics. Full
diagnostics can be saved with `--full-metrics-dir` to an explicitly private
directory outside both the candidate and public output directories. Infrastructure
failures exit 2 with no public score file, following the shared trusted entrypoint.
