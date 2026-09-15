# Reference and admission record: EllipticCurveRecovery

Maintainer-facing. `review_evidence.json` binds the current diagnostic to source
hashes and a clean Linux revision. Its direct-evaluator scope is distinct from the
sandbox contribution gate. Task.md, solution.py and constraints.txt are the only
agent files; reference methods and literal attack fixtures are withheld.

## 1. Reference method and scientific headroom

The standalone witness builds exact per-prime residue-count tables, expands their
classes into the complete public integer window, filters on every purchased count,
and selects affordable cost-one primes by the entropy of predicted counts over the
remaining pairs. It retains singular models during query planning and filters the
discriminant at decision time. It claims only a unique nonsingular lift.

Headroom is **budgeted experimental design**, specifically a multistep rather than
one-step discrimination policy and joint comparison of more expensive primes.
The reference covers the full bounded coefficient family and performs standard
counting, lifting, consistency, singularity and ambiguity checks. Quadratic-form
acceleration and Hasse reasoning are no longer advertised as score headroom:
review correctly showed that they had no benefit under the former score.

## 2. Baseline, evidence and normalization

The single-query fixed guess scores zero. The five-unit budget restricts
information acquisition; unused budget does not increase the score. The trusted
`verification/arithmetic.py` independently reconstructs every bounded pair
compatible with the actual purchased transcript. A supported claim earns recovery
credit only if it is correct and that nonsingular set is its singleton. Knowing an
answer without distinguishing measurements earns zero. Repeated queries add no
information. World-level exact certificates aggregate into a graded cohort rate.

Development has 24 supported curves plus four singular, four smooth genus-two and
four Q-isomorphic worlds; heldout has 18+4+4+4. Refusal earns one on unsupported
worlds, supported abstention zero, followed by normalization above full abstention.
A singular bounded integer claim is valid but wrong and contributes to false
discovery on refusal worlds. Invalid artifacts/calls lose only their world;
valid_count > 0 determines aggregate validity.

## 3. Capability ablations

`review_evidence.json` records the complete metrics. The initial revised reference
measures 0.875 development / 0.944444 heldout. Removing adaptive selection leaves
**development unchanged** but reduces heldout to 0.777778; this component's measured
benefit is heldout discrimination. Removing discriminant filtering reduces scores
to 0.791667 / 0.833333 and produces false discoveries. Limiting the same method to
four queries gives 0.166667 / 0.111111; three queries gives zero. These are observed
capability comparisons, not frontier-model calibration or a proof of expert difficulty.

## 4. Source-bound shortcut probes

The [0310ab2 review](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/52#issuecomment-5594780907)
found the old reference at 0.750, adaptive stopping at 0.8063, descending cheap primes
at 0.8187, literal answers plus 1–2-prime fingerprints at 0.9438, and a zero-query
call-counter literal program at **1.000 through the sandbox**. The old threshold
grid (25 points) and four-prime ablation scored zero; six primes gave 0.4875.
These are historical reviewer measurements, superseded by the revised score.

The new audit exports literal answers for **every current world**, using the
stronger call-order side channel, and checks them with zero, one and two real
queries. All three score **0 development / 0 heldout** even in the direct evaluator
where the counter persists. Their sources and hashes are recorded; the exact
fixtures live in `verification/shortcut_memo_*.py` and run twice in the contribution
gate. Fresh candidate processes at every world also remove the call-order channel
in the real sandbox. A regression explicitly tests that reset.

A newly specified 25-point heuristic sweep uses n=1..5 small primes and
k in {0.5,1,1.5,2,2.5} to turn the mean/absolute point-count deviations into a and b.
Its best score is zero. This is a reproducible representative low-dimensional
probe; the review did not provide its original threshold-candidate source, so this
is not asserted to be the identical historical candidate.

## 5. Frontier-model calibration and lineage

Current-revision clean frontier calibration remains missing. Builder lineage
remains complete and empty calibration lists remain explicitly disclosed; the
maintainer withdrew the objection to that combination. The old macOS proxy draws
and the draw on scientifically incorrect refusal worlds are archived in
`history_before_2026-09-12.md`; they are not current admission evidence.

## 6. Construction corrections and refusal invariants

The previous quartic/genus confusion, missing affine roots, wrong infinity count,
exploding Cartesian CRT, small coefficient window and mismatched contract are
preserved in the archived history. This revision additionally removes the
unused-budget multiplier, adds transcript support and fresh sessions, publishes
per-world validity, separates singular claims from malformed artifacts, expands
the cohorts and introduces Q-isomorphic coefficient ambiguity.

Singular worlds use a=-3t², b=2t³ from positive t square classes in development and
negative t classes in heldout; their complete published-prime count signatures are
disjoint. Isomorphic worlds contain both (a,b) and (16a,64b) in the window, equal at
every listed prime. Supported sampled curves exclude those simple scaling twins;
all shipped supported curves have unique lifts with eight descending cheap primes.

The evidence file records exact traces for primes 97,89,83,79,73. After five, each
singular world retains one or two cubic lifts and zero nonsingular lifts; each
genus-two world has no cubic lift. The isomorphic worlds retain at least two
nonsingular lifts. Some new genus-two worlds are recognizable earlier, while
others need the joint bounded consistency check. Point-count size alone is not a
general certificate of refusal. These are finite-window empirical construction
checks, not a universal theorem about genus-two/elliptic point-count sequences.

## 7. Robustness and reproduction

The generator, signatures and transcripts are deterministic and repository-visible.
Evidence checks require informative purchased counts but cannot prove a solver
has not memorized an informative query policy. Fresh server-held worlds, independent
arithmetic-geometry review and frontier calibration are still needed. This PR
remains candidate and does not regenerate maintainer-owned global evidence.
The unrelated cross-PR source-count rulings were removed from this PR.

```bash
python benchmarks/Mathematics/EllipticCurveRecovery/verification/review_audit.py --output /tmp/curve-review.json --export-candidates /tmp/curve-probes
python scripts/check_task_contribution.py --task Mathematics/EllipticCurveRecovery --timeout 300
python -m pytest tests/test_elliptic_curve_recovery.py -q
```

## Current clean Linux diagnostic

Measured at `b02aef3b4281001b0cabd463e0fcf01d38ca6af0` using Ubuntu 22.04, Python 3.10.12, NumPy 1.24.4 and SciPy 1.10.1. The evidence file preserves that revision and its source hashes; this later documentation commit does not change the measured evaluator or reference.

| Variant | Development | Heldout |
|---|---:|---:|
| Reference | 0.875000 | 0.944444 |
| ADAPTIVE=False | 0.875000 | 0.777778 |
| DISCRIMINANT_FILTER=False | 0.791667 | 0.833333 |
| MAX_QUERIES=3 | 0.000000 | 0.000000 |
| MAX_QUERIES=4 | 0.166667 | 0.111111 |

Grid best: **0.000000** development, 0.000000 heldout. Reference repeats were equal. Full grid parameters and diagnostic axes are retained in `review_evidence.json`.

The subsequent full-suite integration audit found an inherited wrapper mismatch
with current main. The task wrapper now uses `sle/frontier_eval_entrypoint.py`;
public files omit heldout and per-world diagnostics. Integration tests opt into
an explicit private sidecar. This wrapper correction leaves the measured evaluator
and reference source unchanged and is validated separately.

`integration_validation_2026-09-12.json` records the subsequent latest-main integration
checks at `122eaaab17b48b106ce82806ca4d766cc2bec567`, including the
real sandbox contribution guard and exact regression scope. Historical full-suite
failures/skips and any successful unchanged-source recheck remain explicitly recorded.
This documentation-only receipt does not change the measured task or framework code.
