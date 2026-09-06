# MiplibPrimalIncumbent — improve a feasible integer assignment on frozen MIPLIB models

## Scientific setting

MIPLIB 2017 is the standard library of mixed-integer linear programs. A primal heuristic
searches for a better feasible assignment without proving optimality. The official MIPLIB
checker is a primal check: bounds, row activity, integrality, and objective. Duals are not
part of that contract, and this task does not score them.

This conversion vendors three small all-integer MIPLIB 2017 instances (`gen-ip002`,
`gen-ip021`, `gen-ip054`) rather than fetching live models or redistributing `.sol` files,
whose pages do not state a separate license. All three are classified `easy` and
`=opt=` in solufile v36 (2026-01-26). Because a proven optimum exists, the score is
**clipped at one**. That is the honest conversion of an open-incumbent cell onto instances
that can be audited in-repo without a network and without solution files.

This is not permutation flow-shop scheduling. The object is a general integer assignment
on an authentic MIPLIB constraint matrix, not a job permutation and not a makespan.

## Your task

Implement:

```python
def improve_primal(problem):
    """Return one dense integer assignment in frozen MPS column order."""
```

The same function is called once for each instance. `problem` contains:

| key | value |
|---|---|
| `name`, `sense` | instance name and `"minimize"` |
| `n_variables`, `n_constraints` | dimensions |
| `variable_names` | MPS column names in frozen order |
| `objective` | objective coefficients in that order |
| `lower_bounds` | finite lower bounds (all 0 on this subset) |
| `row_senses` | `"L"`, `"G"`, or `"E"` per row |
| `rhs` | right-hand sides |
| `row_ptr`, `column_indices`, `coefficients` | CSR constraint matrix |
| `mps_sha256` | hash of the vendored MPS file |
| `constraint_abs_tol`, `constraint_rel_tol`, `integrality_tol` | MIPLIB checker tolerances |

Return a Python list of exactly `n_variables` integers. Floats, booleans, sparse dicts,
and missing entries are rejected rather than rounded.

## Scoring

For a feasible minimization objective `z`, with weak-feasible baseline `b` and frozen
MIPLIB optimum `r`,

```text
clip01( (b - z) / (b - r) )
```

Returning the shipped weak feasible assignment scores zero. Matching the dated optimum
scores one. Because these three models are proven optimal, the formula is clipped at
one: a floating residual that undershoots `r` is not a new MIPLIB record.

The dated optima, quoted from solufile v36, are:

| instance | variables | baseline `b` | frozen optimum `r` |
|---|---:|---:|---:|
| `gen-ip002` | 41 | 0 | -4783.733392 |
| `gen-ip021` | 35 | 4808.1407336654 | 2361.45419519 |
| `gen-ip054` | 30 | 10700.711798467 | 6840.96564179 |

## Difficulty ladder

| ablation | combined_score |
|---|---:|
| shipped weak feasible integers | 0.000 |
| coordinate ±1 descent, 1448 checks | 0.734 |
| dated proven optimum | 1.000 |

The local-search probe does not reach 1. Memorizing a published optimum still does;
the score is clipped for that reason.

## Tools and scope

- NumPy, SciPy, and the standard library are available. No MIP solver is introduced here.
- Networkless, single-process, bounded by the framework timeout.
- Only edit `solution.py`; keep `improve_primal(problem)`.
- Do not read `verification/` or `frontier_eval/`.
- The MPS files under `references/instances/` are the same models as the CSR payload.

## Relation to nearby tasks

- **PermutationFlowShop (#21)** is Engineering × combinatorial too, but the object is a
  job permutation and the check is makespan. This task checks a dense integer assignment
  against an authentic MIPLIB matrix.
- Open MIPLIB incumbents with unpublished `.sol` licenses stay gated: this conversion
  uses only vendored MPS and published `=opt=` numbers.
- Not a Frontier-Eng design task: the object is a general integer assignment on a
  frozen MIPLIB matrix, not a simulator-backed engineering layout.
