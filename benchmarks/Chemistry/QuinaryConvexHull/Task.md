# QuinaryConvexHull — E_f < 0 is not a new stable

This is not `MaterialsScience/PhaseDiagramDiscovery` (a 1-D powder-XRD binary section) and
not `Spectroscopy/CrowdedSpectrumAssignment` (a stick-library species set). MADE's quinary
cell is the warning: random generators find zero new stables, and MLIP ranking collapses
within ~10 meV/atom of the hull. Binary oxides would clone the existing phase-diagram task,
so this catalog is five elements.

A closed catalog of integer compositions of three atoms into five bins is public. You may
relax a name for its formation energy. The oracle is a frozen analytic mixing-plus-well
model — not a live MACE/ORB/AF3 call. A thermodynamically stable compound is a vertex of
the lower convex hull besides the unaries. Points a few meV above that envelope can still
have E_f < 0. Energies that do not reproduce are glass; an empty hull (unaries only) must
not grow extra stables.

## Your task

```python
def recover_hull(problem, relax):
    # relax(name) -> formation energy in eV/atom, charges one call
    return {"stable": ["A1B1C1D0E0", ...], "confidence": ..., "abstain": False}
```

When abstaining:

```python
return {"abstain": True, "confidence": ...}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `catalog` | every legal composition name, e.g. `A3B0C0D0E0` |
| `elements` | `A`–`E` in that order |
| `n_atoms` | atoms per composition (3); names sum to this |
| `relax_budget_calls` | how many `relax` calls this world allows (42) |
| `max_claimed_stables` | at most this many non-unary names may be claimed (8) |
| `energy_unit` | `eV_per_atom` |
| `measurement_model` | prose: a repeat of `relax` is a new laboratory draw |
| `hull_note` | prose: a stable is a lower-hull vertex besides the unaries |
| `abstain_when` | prose: energies do not reproduce, or no unique hull is supported |

### `relax(name)`

`name` must be a catalog key. Each call charges one unit. Repeating a name redraws the
laboratory. Calling past the budget raises and the world scores zero.

### What you return

| key | meaning |
|---|---|
| `stable` | catalog names of claimed non-unary hull vertices; required unless abstaining |
| `confidence` | finite number in `[0, 1]` |
| `abstain` | boolean; if true, `stable` is ignored |

Unaries may be listed and are ignored. Names must be in `catalog`, unique, and at most
`max_claimed_stables`. Anything malformed scores that world zero.

## Scoring

The public `combined_score` is development mechanism recovery, normalised so that declining
every world is exactly zero. The non-unary vertex *set* is gated: a missing or extra name
scores zero however close the energies sit. Glass worlds must be declined; publishing any
hull on a glass is a false discovery. False-discovery, correct refusal, coverage and the
held-out split are reported separately and never averaged.

- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Only edit `solution.py`. Keep `recover_hull(problem, relax)`.
- NumPy/SciPy only. Deterministic CPU code. No network or process creation. Do not read
  `verification/` or `frontier_eval/`.
