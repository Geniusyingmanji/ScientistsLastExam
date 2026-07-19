# LennardJonesCluster — minimize the energy of atomic clusters

## Scientific background

A Lennard-Jones (LJ) cluster is `N` identical atoms interacting through the pairwise
potential `V(r) = 4·(r⁻¹² − r⁻⁶)` (reduced units, ε = σ = 1). Finding the geometry that
minimizes the total energy is a canonical **global optimization** problem in chemical
physics and molecular mechanics: the energy landscape has a number of local minima that
grows roughly exponentially in `N`. The putative global minima are catalogued in the
Cambridge Cluster Database and are the standard reference values.

## Your task

Implement a function that returns atomic coordinates for several cluster sizes, including
the classic `N=38` double-funnel cluster. Lower total LJ energy is better. You are
optimizing the geometry, not the potential.

Edit **`solution.py`** so it defines:

```python
def build_cluster(n_atoms: int, seed: int = 0) -> "np.ndarray":
    """Return an (n_atoms, 3) float array of 3D coordinates."""
```

The evaluator calls `build_cluster(n)` for each `n` in the test set, computes the LJ energy
of your configuration, and compares it to the known global minimum for that `n`.

## Scoring

For each cluster size the per-task score is the fraction of the baseline→optimum gap closed:

```
gap_closed(n) = (E_baseline(n) − E_found(n)) / (E_baseline(n) − E_global_min(n))
```

clipped to `[0, 1]`, where `E_baseline` is this folder's initial program. The reported
`combined_score` is the mean of `gap_closed` over all test sizes (so the initial program
scores ~0 and matching the known global minima scores 1.0). A configuration with any atoms
closer than a hard-core cutoff or producing non-finite energy is invalid.

## Rules

- Deterministic for a given `(n, seed)`. No network. CPU only, seconds per size.
  The hidden test set includes expert-level cluster sizes where naive local relaxation
  commonly gets trapped in the wrong basin.
- Keep the `build_cluster` signature and the `(n_atoms, 3)` array contract.
- You may use `numpy` and `scipy` only.
