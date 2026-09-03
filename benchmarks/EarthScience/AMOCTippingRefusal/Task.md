# AMOCTippingRefusal — a dip in the fingerprint is not a fold

This is not `ClimateScience/EnergyBalanceModel` (named two-layer parameters) and not
`DynamicalSystems/ActiveLawDiscovery` (sparse polynomial ODE library). The public series is
an AMOC-like fingerprint through `year_now`. Some hidden worlds have a cubic fold whose
collapse still lies in the future; equally plausible worlds are red noise with no fold, or
an ice-restored unique attractor that still declines with freshwater. Quoting a collapse
year on those worlds is the failure Ditlevsen-style extrapolations were criticised for.

You may hold freshwater and start from the upper or lower well, or continue the hidden
forcing from the historical end state.

## Your task

```python
def interpret_amoc(problem, probe):
    # probe(freshwater_offset, duration_years, mode) -> {"years", "amoc"}
    # mode is one of problem["modes"]: plus, minus, continue
    return {"has_tipping": True, "collapse_year": ..., "confidence": ..., "abstain": False}
```

When abstaining:

```python
return {"abstain": True, "confidence": ...}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `historical_years` | integer years from `year_start` through `year_now` |
| `historical_amoc` | fingerprint at those years (higher is a stronger overturning) |
| `year_start` | first historical year (1870) |
| `year_now` | last historical year (2020) |
| `probe_budget` | how many `probe` calls this world allows (6) |
| `min_duration_years` | shortest allowed probe (20) |
| `max_duration_years` | longest allowed probe (100) |
| `freshwater_offset_low` | lowest allowed freshwater offset (−0.6) |
| `freshwater_offset_high` | highest allowed freshwater offset (0.6) |
| `modes` | `plus`, `minus`, `continue` |
| `measurement_model` | prose: plus/minus hold F(year_now)+offset from x=±1; continue starts from the historical end and keeps the hidden F(year)+offset |
| `abstain_when` | prose: red noise, ice-restored unique attractor, or plus/minus probes do not support hysteresis |

### `probe(freshwater_offset, duration_years, mode)`

`freshwater_offset` must lie in `[freshwater_offset_low, freshwater_offset_high]`.
`duration_years` must lie in `[min_duration_years, max_duration_years]`. `mode` must be
one of `modes`. Each call charges one unit. Overspend raises and the world scores zero.

### What you return

| key | meaning |
|---|---|
| `has_tipping` | boolean; required unless abstaining |
| `collapse_year` | finite year; required when `has_tipping` is true |
| `confidence` | finite number in `[0, 1]` |
| `abstain` | boolean; if true, the tipping fields are ignored |

Anything malformed scores that world zero.

## Scoring

The public `combined_score` is development mechanism recovery, normalised so that declining
every world is exactly zero. A true fold scores only if you claim it and the year lies
within 25 years of the hidden crossing. Claiming a tip on red noise or ice restore is a
false discovery. False-discovery, correct refusal, coverage and the held-out split are
reported separately and never averaged.

- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Only edit `solution.py`. Keep `interpret_amoc(problem, probe)`.
- NumPy/SciPy only. Deterministic CPU code. No network or process creation. Do not read
  `verification/` or `frontier_eval/`.
