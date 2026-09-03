# ComplexBoseLaw — a mixed cavity occupancy is not textbook Planck

This is not `DynamicalSystems/ActiveLawDiscovery` (a two-state polynomial ODE) and not
`Oceanography/AMOCTippingRefusal` (a fold year). This task borrows the shifted exponents
used in NewtonBench's hard distribution-law cell, but restores the physical Bose minus sign;
it is therefore a new counterfactual stress test, not a reproduction of that benchmark cell.
Here the in-family law is

```text
n(ω, T) = 1 / (exp(C * ω**α / T**β) - 1)
```

with hidden `(α, β)` that vary by world, so the paper's printed `(1.5, 2)` cannot be
hard-coded. The laboratory does not return that occupation: a cavity mixes `n` at `ω` with
two nearby frequencies. A Fermi occupation (`+1` in the denominator) and a T-independent
blank must be refused. Vanilla Newtonian gravity is out of scope.

You may buy occupancy measurements `(ω, T)`.

## Your task

```python
def interpret_cavity(problem, measure):
    # measure(omega, temperature) -> occupancy, charges one call
    return {"family": "bose", "C": ..., "alpha": ..., "beta": ..., "confidence": ..., "abstain": False}
```

When abstaining:

```python
return {"abstain": True, "confidence": ...}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `omega_bounds` | allowed frequencies `[0.45, 3.8]` |
| `temperature_bounds` | allowed temperatures `[0.45, 2.4]` |
| `measure_budget_calls` | how many `measure` calls this world allows (36) |
| `family_names` | `bose`, `fermi` |
| `in_family_occupation` | prose: Bose occupation with unknown `C`, `alpha`, `beta` |
| `measurement_model` | prose: the cavity mixes nearby modes; weights are unknown |
| `abstain_when` | prose: Fermi (`+1`) or occupancy independent of temperature |

### `measure(omega, temperature)`

Both arguments must be finite and inside the public bounds. Each call charges one unit.
Calling past the budget raises and the world scores zero.

### What you return

| key | meaning |
|---|---|
| `family` | one of `family_names`; required unless abstaining |
| `C` | positive finite scale; required unless abstaining |
| `alpha` | positive finite frequency exponent; required unless abstaining |
| `beta` | positive finite temperature exponent; required unless abstaining |
| `confidence` | finite number in `[0, 1]` |
| `abstain` | boolean; if true, the law fields are ignored |

Anything malformed scores that world zero.

## Scoring

The public `combined_score` is development mechanism recovery, normalised so that declining
every world is exactly zero. A Bose world scores by how close `(α, β)` (and, weakly, `C`)
are to the hidden exponents; mixing renormalizes `C`, so a textbook `(1, 1)` fit is not
enough. Claiming Bose on Fermi or a blank is a false discovery. False-discovery, correct
refusal, coverage and the held-out split are reported separately and never averaged.

- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Only edit `solution.py`. Keep `interpret_cavity(problem, measure)`.
- NumPy/SciPy only. Deterministic CPU code. No network or process creation. Do not read
  `verification/` or `frontier_eval/`.
