# LookElsewhereAnomaly — local 5σ is not a discovery

This is not a fit of a resonance amplitude, and it is not
`ParticlePhysics/DiscrepantMeasurements` (that task diagnoses χ² disagreements among
published groups). Here one histogram is scanned in many independent mass windows. A
local 5σ that dies after a trials factor, a blank, or a sideband that rejects the public
background must not be published as a new particle.

The public background is flat. You may buy background-only toys drawn from that prior.

## Your task

```python
def interpret_spectrum(problem, toys):
    # toys(n) -> n background-only count arrays, charges ceil(n / toys_batch_size)
    return {"discovery": True, "mass_gev": ..., "confidence": ..., "abstain": False}
```

When abstaining, omit `discovery` / `mass_gev` or leave them unused:

```python
return {"abstain": True, "confidence": ...}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `mass_gev` | bin centres, GeV; length `n_mass_windows` |
| `counts` | observed integer counts in those bins |
| `expected_background` | public flat prior, counts per bin (80.0) |
| `n_mass_windows` | number of independent mass searches (40) |
| `toys_budget_units` | toy-budget units for this spectrum (8) |
| `toys_batch_size` | each `toys(n)` call costs `ceil(n / 25)` units |
| `five_sigma_global_p` | one-sided global 5σ p-value threshold (2.87e-7) |
| `measurement_model` | prose: Poisson bins; toys are drawn from the public prior |
| `look_elsewhere_note` | prose: `n` windows inflate the local tail |
| `abstain_when` | prose: local excess dies after trials, blank, or sidebands reject the prior |

### `toys(n)`

`toys(n)` charges `ceil(n / toys_batch_size)` units and returns `n` lists of counts
drawn independently from Poisson(`expected_background`) in every bin. The window count
`n` must be a positive integer. Calling past the budget raises and the world scores
zero. At most 200 toys are affordable, so their empirical tail resolution is about
`1/200` and cannot by itself establish a `2.87e-7` global p-value. They are diagnostic
only; a valid 5σ claim needs an analytic or otherwise justified tail correction such as
the public independent-window Bonferroni bound.

### What you return

| key | meaning |
|---|---|
| `discovery` | boolean; required unless `abstain` is true |
| `mass_gev` | finite mass inside the scanned range; required when `discovery` is true |
| `confidence` | finite number in `[0, 1]` |
| `abstain` | boolean; if true, `discovery` and `mass_gev` are ignored |

Anything malformed scores that world zero.

## Scoring

The public `combined_score` is development mechanism recovery, normalised so that
declining every world is exactly zero. A true resonance scores only if you claim it
within two bin widths. Claiming a particle on a fluke, a sculpted background, or a
blank is a false discovery. False-discovery, correct refusal, coverage and the held-out
split are reported separately and never averaged.

- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Only edit `solution.py`. Keep `interpret_spectrum(problem, toys)`.
- NumPy/SciPy only. Deterministic CPU code. No network or process creation. Do not read
  `verification/` or `frontier_eval/`.
