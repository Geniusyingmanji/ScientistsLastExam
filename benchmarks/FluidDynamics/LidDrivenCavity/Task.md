# LidDrivenCavity-v2 — construct a converged incompressible-flow solution

## Scientific problem

The two-dimensional lid-driven cavity is a canonical validation problem for steady
incompressible Navier--Stokes solvers.  Fluid in the unit square is driven by a unit-speed top
lid; the bottom and side walls are stationary.  The task spans the laminar steady range
`100 <= Re <= 400` and multiple odd uniform grids.  It tests whether one program can construct
a full flow solution, not whether it can reproduce one published centerline.

Use the streamfunction--vorticity formulation

```text
u = d(psi)/dy
v = -d(psi)/dx
omega = dv/dx - du/dy = -laplacian(psi)
u*d(omega)/dx + v*d(omega)/dy = laplacian(omega) / Re
```

Arrays use `[y, x]` indexing on an `N x N` uniform grid from 0 to 1.  The top row is the moving
lid.  Set `psi=0` on all walls.  For grid spacing `h=1/(N-1)`, the trusted oracle uses the
second-order Thom wall-vorticity convention

```text
bottom: omega[0,1:-1]  = -2*psi[1,1:-1]/h**2
top:    omega[-1,1:-1] = -2*psi[-2,1:-1]/h**2 - 2/h
left:   omega[1:-1,0]  = -2*psi[1:-1,1]/h**2
right:  omega[1:-1,-1] = -2*psi[1:-1,-2]/h**2
```

Corner vorticity is not scored because the lid velocity is discontinuous there.

## Artifact

Implement

```python
def solve_cavity(Re, N):
    """Return (streamfunction, vorticity), each a finite real (N,N) array."""
```

The input Reynolds number and grid size are public.  The same implementation is called on every
development, held-out-Reynolds and grid-refinement case.  Do not return velocity or pressure:
the trusted oracle derives velocity independently from `psi`, and the streamfunction artifact
enforces incompressibility by construction.

## Scoring and validity

- The development score combines full-field velocity/streamfunction agreement with an
  independently generated converged continuation reference and the complete discrete Poisson,
  vorticity-transport and wall residuals.  It is normalized above a valid zero-interior-flow
  weak baseline, and each case receives zero utility unless all three public physics gates pass;
  near-reference field similarity alone is not sufficient.
- `feasibility_rate` is the fraction of development cases below public relative-residual gates:
  Poisson `<=0.03`, vorticity transport `<=0.05`, and wall consistency `<=0.05`.
- Held-out Reynolds-number transfer, independent grid-refinement consistency and Ghia et al.
  centerline diagnostics are evaluator-only.  They do not enter proposal feedback or parent
  selection.
- Wrong shape, non-finite values, `abs(psi)>2`, or `abs(omega)>12*N` are invalid and fail closed.

The reference is a deterministic second-order streamfunction--vorticity Newton--Krylov
continuation solution.  It is checked against its independently recomputed algebraic residual,
grid refinement and the Re=100 tables of Ghia, Ghia and Shin.  A high benchmark score is evidence
for this controlled steady laminar model, not turbulence, experimental validation or general CFD
capability.

## Rules

- Only edit `solution.py`; keep the `solve_cavity(Re, N)` signature.
- Deterministic CPU code using Python, NumPy and SciPy only; no network or process creation.
- The complete evaluation makes eight calls and shares one wall-time budget.  Reuse only public
  numerical structure; each scientific case starts in a fresh process and private temporary
  filesystem.
- Do not read `verification/` or `frontier_eval/`.

## References

- Ghia, Ghia and Shin, *High-Re solutions for incompressible flow using the Navier--Stokes
  equations and a multigrid method*, Journal of Computational Physics 48(3), 387--411 (1982),
  DOI `10.1016/0021-9991(82)90058-4`.
- Botella and Peyret, *Benchmark spectral results on the lid-driven cavity flow*, Computers &
  Fluids 27(4), 421--433 (1998), DOI `10.1016/S0045-7930(98)00002-4`.
- Erturk, Corke and Gokcol, *Numerical solutions of 2-D steady incompressible driven cavity flow
  at high Reynolds numbers*, International Journal for Numerical Methods in Fluids 48(7),
  747--774 (2005), DOI `10.1002/fld.953`.
