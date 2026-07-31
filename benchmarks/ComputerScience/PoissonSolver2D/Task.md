# PoissonSolver2D — design a more accurate Poisson solver

## Scientific background

The Poisson equation `−∇²u = f` is the workhorse of computational physics (electrostatics,
diffusion, incompressible flow projection, ...). The quality of a numerical solver — its
discretization order, linear solve, and conditioning — directly sets the accuracy/cost
tradeoff of large simulations. Improving the stencil and solve is a long-standing topic in
scientific computing.

## Problem

Solve `−∇²u = f` on the unit square `(0,1)²` with homogeneous Dirichlet boundary conditions
`u = 0`. The evaluator supplies a high-resolution sampled right-hand side `rhs` on the
interior grid. The manufactured exact solution and its spectral content are held out, so
returning a memorized formula is not possible; the task is to implement a genuinely accurate
solver.

## Your task

Edit **`solution.py`** so it defines:

```python
def solve_poisson(n: int, rhs: "np.ndarray") -> "np.ndarray":
    """Return the (n, n) array of u at the interior grid points
    x_i = i*h, i=1..n, with h = 1/(n+1). Boundary values are 0."""
```

The evaluator calls `solve_poisson(127, rhs)` and measures the relative L2 error against the
held-out exact solution on that grid.

## Scoring

With `E` the relative L2 error, `E_baseline` the weak Jacobi baseline error, and `E_ref` a
spectral-solver reference error:

```
combined_score = clip( (log10(E_baseline) − log10(E)) / (log10(E_baseline) − log10(E_ref)), 0, 1 )
```

So the initial Jacobi solver scores ~0, a converged 2nd-order direct solve earns partial
credit, and an accurate sine/spectral Poisson solver reaches 1.0.

## Rules

- Only edit `solution.py`; keep the `solve_poisson(n, rhs)` signature and `(n, n)` output.
- Deterministic, CPU only, seconds-scale, no network. `numpy` and `scipy` only.
- Do not read anything under `verification/` or `frontier_eval/`.
