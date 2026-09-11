# PR83: bounded numerical repair, admission HOLD

The current package is **HOLD**. No complete valid reference run, shortcut
comparison, contribution-gate pass, or independent frontier calibration has been
established. This branch is a reviewable engineering repair, not an admissible
task or a certification. Original PR ancestor `2dd3302` remains in its history.

## Frozen scientific replay plans

All plans used the trusted `evaluate_candidate` and real Linux candidate sandbox,
Python 3.8.10, NumPy 1.24.4, SciPy 1.10.1, four numerical thread variables set to
one, and a 300-second evaluation timeout. Each listed candidate was fixed before
its pair; no grid, model call, heldout-selected parameter, or new solver attempt
was added after the stop instruction.

| Frozen source | Completed calls | Result |
|---|---:|---|
| `cf799442066bdee7772e9ca0ec2ca3d4ec173116` | 4 | baseline 2 valid / score 0; original HiGHS reference 2 `candidate_worker_exit` |
| `264908df03bde99a7709a856a55ef3d4296160b6` | 10 | baseline 2 valid / score 0; scaled interior-point reference, detection-only, no-order and no-atom pairs: 8 `candidate_runtime_error` |
| `56778e870a173cfa33aa8f34f553cf1ad44af8f7` | 10 | baseline 2 valid / score 0; centered reference and the same three fixed variants: 8 `candidate_runtime_error` |

The 24 calls total six valid baselines and 18 invalid results. Invalid scores
remain `-1e18`, never zero or a correct scientific refusal. The two centered
baseline runs each produced all 18 valid worlds. Failed pairs establish neither
three-axis scientific performance nor a shortcut/reference margin. Repeated
failure metrics were identical; that is not a successful reproducibility claim.
The three `pr83_*sandbox_2026-09-11.json` files retain scalar metrics, candidate
and package hashes, runtime identity, original-record hashes and timings.
Full metrics stay in separate mode-0700 remote private directories.

## What is repaired and what remains unvalidated

The parent repair bounds physical one-way propagation to the published range
without changing RNG draw order, fixes FDR to use interval claims as denominator,
adds counts and zero-denominator tests, and uses the standard 300-second wrapper.
Commit `56778e87` resets the candidate session at every subsequent world and the
development/heldout boundary, and expresses the identical LP as
`x = rough_public_clock_fit + scale*z`. Objective values restore the translation
term. Only a solver status of infeasible can trigger the LP's model refusal;
unboundedness, iteration limits and numerical failures raise errors.

The unvalidated follow-up retains the exact lower convex hull of each affine
clock-row group. For rows `a(t)=a0+t*a1`, an intermediate row with time
`t=(1-lambda)*t0+lambda*t1` and right-hand side at least
`(1-lambda)*b0+lambda*b1` is implied by the two endpoint inequalities. Endpoints
remain; duplicate times keep the tightest bound; calibration and unrecognized
rows remain unchanged. Exact `Fraction` arithmetic on supplied binary floats
decides the chord relation without a tolerance. The envelope objective still
uses **all original selected rows**; objectives and variable bounds are unchanged.
Caching reuses only stages formed by appending/truncating the same row prefix.

Two added data-free tests preserve a stronger one-ulp middle constraint and check
a 54-row fixture. An independent HiGHS LP maximizes each original constraint on
the reduced polytope (54 checks), then compares four fixed objectives on original
and reduced rows (8 solves). All passed. This provides small-instance numerical
verification alongside the mathematical implication; it does **not** establish
runtime, numerical stability, or correctness on all task LPs. In particular, an
independent comparison against the captured real all-row failure LP was planned
but **not run**. No complete task evaluation of the hull version was started.

## Actual tests and bounded diagnostics

| Check | Actual outcome |
|---|---|
| Local centered runtime/unit suite, before hull | 4 passed, excluding Linux sandbox |
| Linux `tests/test_clock_sync_runtime.py` at `56778e87` | 5 passed in 8.38 s; includes real global and `/tmp` marker isolation over all 18 worlds |
| Local suite with hull, `pytest tests/test_clock_sync_runtime.py -q -k 'not real_sandbox'` | 6 passed, 1 deselected, 1.05 s |
| Linux hull tests | not run |
| Full `tests/test_clock_sync_inversion.py` at `56778e87` | original `timeout 900s` expired, exit 124; partial log `........F.F.`; no complete failure trace, pass conclusion or JUnit |
| Standard contribution gate / frontier calibration on final package | not run / not run |

The isolation regression is one additional real task sandbox call, separate
from the 24 fixed scientific replays. The direct oracle-property test attempt is
also separate and must not be counted as a successful sandbox admission run.

Two no-score CandidateProxy diagnostics at `56778e87` returned the same first
development-world answer hash in about 6 seconds. This did not imply whole-task
success. A subsequent bounded development-only diagnostic executed eight fresh
CandidateProxy calls and stopped at the first exported failing LP. Its sole
instrumentation replaced the numerical-failure exception with a private export;
it supplied no truth and changed no observations, scientific parameters or
solver settings. The captured 820-row, 26-variable LP returned **status 1:
iteration limit before convergence**, not an infeasibility certificate. This
is separate from the earlier uncentered diagnostic's status-4 tolerance failure.
No captured matrix, answer, per-world ordering or truth is published. The driver
source and source/derived-candidate hashes are retained for review.

At closeout, all three owned tool sessions were complete: fixed plan exit 0,
oracle tests exit 124 from their preset timeout, capture diagnostic exit 0.
A process inventory found no remaining owned PR83 evaluation/test process.
No additional termination, scientific LP comparison, solver variant, model
calibration or new instance generation was performed after the stop instruction.

## Remaining admission conditions

An independently verified numerical method must complete every world in the
fixed reference/probe/ablation plans within the existing budget; retained failure
records must remain separate. The captured original all-row LP and the hull
version still need an independent feasible-set/objective check on actual task
data before claiming the reduction fixes the real failure. Only then can the
full oracle tests, real contribution gate and newly frozen shortcut expectations
be completed. Independent first-proposal calibration follows those checks.
The task-card expectations remain `null`; builder history and current failed
replays are explicitly separated. Domain review also remains pending.
