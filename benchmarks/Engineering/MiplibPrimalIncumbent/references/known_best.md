# MiplibPrimalIncumbent — measured values

Every number here is produced by running code in this package, or quoted from the dated
MIPLIB solufile cited in `references/anchors.json`.

## Reference

The 1.0 point is the dated MIPLIB 2017 solufile v36 proven optimum, not a feasible
assignment redistributed here. Official `.sol` files are not in the package. The checker
is primal-only: an assignment that matches the dated objective and passes bounds, rows,
and integrality scores one and is clipped there because these three models are `=opt=`.

| instance | variables | dated optimum | source |
|---|---:|---:|---|
| gen-ip002 | 41 | -4783.733392 | solufile v36 `=opt=` |
| gen-ip021 | 35 | 2361.45419519 | solufile v36 `=opt=` |
| gen-ip054 | 30 | 6840.96564179 | solufile v36 `=opt=` |

The reference is capability-complete for a primal heuristic (a feasible integer vector)
and deliberately not an open-incumbent claim: a proven optimum exists, so beating it is
a residual, not a library record.

## Baseline — `solution.py`

| | gen-ip002 | gen-ip021 | gen-ip054 | mean |
|---|---:|---:|---:|---:|
| baseline objective | 0 | 4808.1407336654 | 10700.711798467 | |
| baseline score | 0 | 0 | 0 | **0** |

Weak feasible integers: the origin on gen-ip002 (every row is `≤` with a large enough
RHS), and two small-magnitude feasible points on the other two. Returning them scores
zero. The origin is infeasible on gen-ip021 and gen-ip054.

## Difficulty ladder

Dropping one capability of a competent primal search must drop the score.

| ablation | combined_score | what was removed |
|---|---:|---|
| shipped baseline | 0.000 | no search |
| coordinate ±1 descent, 4 sweeps then 200 random tweaks (1448 checks) | **0.734** | no branching, no cutting planes, no global bound |
| dated proven optimum | 1.000 | — |

Per instance at the coordinate-descent probe: gen-ip002 0.861 (obj -4119.06), gen-ip021
0.843 (obj 2746.02), gen-ip054 0.499 (obj 8776.08). None reaches the dated optimum.
Removing the random tweaks and keeping only the four sweeps still improves every
instance above the baseline.

## Shortcut probe

Low-dimensional local search, 1448 evaluations, seed 0: best combined score **0.734**,
below the reference. That is not a two-parameter grid that saturates the task.

Memorizing a published optimal assignment still scores one; that is a protocol on-ramp
and is why the score is clipped. SciPy is mounted. A `scipy.optimize.milp` call has
terminated under the no-process seccomp policy on the builder host; that is not a
defense against every solver reuse.

## Model draws

Not run. This conversion has no `batch_evolve.py --run-role calibration` on a clean
tree. The admission line (first proposal must not reach the reference) is therefore
untested. A searcher that recalls the public MIPLIB optimum would hit 1.0; a searcher
restricted to local integer moves, on this probe, does not.

## Construction errors

The first design fetched official `.sol` files at evaluation time. Those pages do not
state a redistribution license, so live download was dropped. Open MIPLIB incumbents
without a vendorable weak feasible point stayed gated. `gen-ip016` was tried and
dropped because no weak feasible integer was on hand. Padding the score as uncapped
against a proven `=opt=` would have reported residuals as new library records; the
conversion clips instead.

## Robustness

Twelve malformed submissions — `None`, `[]`, a raising callable, too-short and too-long
lists, floats, booleans, a dict, a string, mixed int/float, `None` entries, and nested
lists — all score 0 with `valid = 0`, and none raises out of the evaluator. The
all-zero point is feasible on gen-ip002 and infeasible on the other two.
