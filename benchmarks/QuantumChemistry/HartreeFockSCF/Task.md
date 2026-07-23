# HartreeFockSCF — find stable finite-basis restricted Hartree–Fock solutions

## Scientific background

Restricted Hartree–Fock (RHF) approximates an even-electron closed-shell molecule with one
Slater determinant.  The occupied spatial orbitals must be orthonormal in the nonorthogonal
atomic-orbital (AO) metric, and the Fock operator depends nonlinearly on the occupied space.
Consequently, ordinary self-consistent-field iteration can converge to different stationary
points, including internally unstable symmetry-preserving solutions.

This task supplies seven small, real, finite-basis molecular Hamiltonians.  It tests whether
one numerical policy can find low-energy, self-consistent occupied spaces across equilibrium,
stretched, heteronuclear, chain, ring and polyatomic regimes.  The task is about numerical RHF
optimization; it does not ask for the correlated exact electronic energy.

## Public problem contract

Implement:

```python
def solve_restricted_hf(problem):
    """Return an (n_ao, n_occupied) real coefficient matrix."""
```

Each `problem` mapping contains:

```text
overlap                         S[p,q], shape (n_ao, n_ao)
core_hamiltonian                h[p,q], shape (n_ao, n_ao)
electron_repulsion_integrals    (p q | r s), chemist order, shape (n_ao,)*4
nuclear_repulsion               E_nuc
electron_count                  closed-shell electron count
occupied_orbital_count          n_occupied = electron_count / 2
nuclear_charges
coordinates_angstrom
```

Return occupied spatial-orbital coefficients `C` satisfying

```text
C.T @ S @ C = I.
```

For the closed-shell density `P = 2*C@C.T`, the trusted evaluator independently forms

```text
J[p,q] = sum_rs P[r,s] * (p q | r s)
K[p,q] = sum_rs P[r,s] * (p r | q s)
F      = h + J - 0.5*K
E_RHF  = 0.5 * sum_pq P[p,q] * (h[p,q] + F[p,q]) + E_nuc.
```

It also checks electron count, density idempotency and the normalized Roothaan–Hall residual

```text
||F P S - S P F|| / (||F|| ||P|| ||S||).
```

Wrong-shape, non-finite, non-real, nonorthonormal or non-self-consistent artifacts fail closed.
Do not return all orbitals: return only the occupied columns.

## Evaluation

The conventional baseline performs one core-Hamiltonian start with Pulay DIIS.  Per-instance
raw utility measures energy improvement above that core guess toward a frozen, fixed-seed,
stable multistart RHF witness and is softly penalized for residual error.  The task-level
`combined_score` rescales mean development utility so the supplied conventional policy is zero
and the multistart witnesses are approximately one.  These witnesses are reproducible local
finite-basis RHF solutions, not proofs of the global determinant minimum.  A valid lower-energy
solution is accepted and clips at one; the reference is never an exclusion threshold.

The trusted evaluator separately retains, without exposing them to proposal or selection:

- interleaved held-out molecules, including a different-size symmetry-breaking ring;
- nearby 3% molecular-geometry contractions or expansions with freshly generated integrals;
- AO permutations and dense well-conditioned changes of basis; and
- the smallest occupied–virtual orbital-rotation energy curvature.

Thus a low residual is necessary but not sufficient: a symmetry-preserving stationary point
can be self-consistent yet internally unstable.  Useful approaches include multiple initial
occupied spaces, damping/level shifting, direct orbital minimization, stability analysis and
targeted rotations followed by renewed SCF.

## Scope and rules

- Only edit `solution.py`; keep `solve_restricted_hf(problem)`.
- Use deterministic Python/NumPy/SciPy CPU code only.
- Handle the supplied Hamiltonian rather than hard-coding a molecule or coefficient matrix.
- No network or process creation.  Do not read `verification/` or `frontier_eval/`.

The systems are deliberately small and use STO-3G or 6-31G AO bases.  RHF omits electron
correlation and can be qualitatively inadequate for stretched bonds; external RHF stability is
also outside the score.  Broader chemistry claims require larger bases, correlated methods and
independent quantum-chemistry validation.

References: Roothaan, *Reviews of Modern Physics* 23, 69–89 (1951),
doi:10.1103/RevModPhys.23.69; Pulay, *Chemical Physics Letters* 73, 393–398 (1980),
doi:10.1016/0009-2614(80)80396-4; Seeger and Pople, *Journal of Chemical Physics* 66,
3045–3050 (1977), doi:10.1063/1.434318; Sun et al., *WIREs Computational Molecular Science*
8, e1340 (2018), doi:10.1002/wcms.1340.
