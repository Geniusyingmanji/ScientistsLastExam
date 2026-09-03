# CrowdedSpectrumAssignment — name the library species in a blended spectrum

A closed library of vibrational species is public. One mixture is measured as a 1-D peak list.
At the default instrument width, lines about 8 cm⁻¹ apart merge, so a two-species blend of a
close pair is indistinguishable from a third library species whose lines sit at the merge
centres. You may zoom a window at the cost of one call; the narrower width splits a blend and
leaves a true singlet alone.

This is species assignment under blending, not Voigt-parameter recovery (that is
`Spectroscopy/NMRSpectrumFitting`) and not a phase diagram on a composition axis (that is
`MaterialsScience/PhaseDiagramDiscovery`).

## Your task

```python
def assign_species(problem, scan, zoom):
    # scan() -> [{"wavenumber", "intensity"}, ...]   free, default resolution
    # zoom(lo, hi) -> peaks in [lo, hi] at zoom resolution, charges one call
    return {"species": [...], "confidence": ..., "abstain": False}
```

When abstaining, omit `species` or leave it empty:

```python
return {"abstain": True, "confidence": ...}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `library` | `{name: [wavenumbers, ...]}` for every candidate species |
| `wavenumber_bounds` | `[400.0, 4000.0]`; all peaks and zoom windows live here |
| `default_resolution_sigma` | Gaussian width of `scan()` (12.0) |
| `zoom_resolution_sigma` | Gaussian width inside a zoom (2.5) |
| `zoom_budget_calls` | how many zooms you may buy on this mixture (8) |
| `min_zoom_width` | narrowest allowed zoom window (30.0) |
| `max_zoom_width` | widest allowed zoom window (250.0) |
| `max_claimed_species` | at most this many species may be claimed (4) |
| `detection_floor` | peaks weaker than this are not reported (0.09) |
| `measurement_model` | prose: what `scan` and `zoom` return |
| `impurity_model` | prose: how a contaminant behaves |
| `abstain_when` | prose: when no unique library subset is supported |

### `scan()` and `zoom(lo, hi)`

`scan()` is free and may be called more than once; it always returns the same default-resolution
peak list. `zoom(lo, hi)` charges one call. The window must be finite, inside
`wavenumber_bounds`, and between `min_zoom_width` and `max_zoom_width` wide. Calling past the
budget raises and the world scores zero.

### What you return

| key | meaning |
|---|---|
| `species` | one entry per claimed species: `{"name": <library key>, "fraction": ...}` |
| `confidence` | finite number in `[0, 1]` |
| `abstain` | boolean; if true, `species` is ignored |

Names must be library keys, fractions in `(0, 1]` summing to one (tolerance 0.05), at most
`max_claimed_species` entries, no duplicates. Anything malformed scores that world zero.

## Scoring

The public `combined_score` is development mechanism recovery, normalised so that declining
every world is exactly zero. The species *set* is gated: a missing or extra name scores zero
mechanism however well the fractions sit. False-discovery, correct refusal, coverage and the
held-out split are reported separately and never averaged.

- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Only edit `solution.py`. Keep `assign_species(problem, scan, zoom)`.
- NumPy/SciPy only. Deterministic CPU code. No network or process creation. Do not read
  `verification/` or `frontier_eval/`.
