# PTAHellingsDowns — a common process is not a gravitational-wave background

This is not `ParticlePhysics/LookElsewhereAnomaly` (a mass histogram plus a trials factor)
and it is not a fit of a strain amplitude. A pulsar-timing array publishes a gravitational-wave
background only when the *spatial* correlations follow the Hellings–Downs quadrupole. A clock
error is a monopole, an ephemeris error is a dipole, and a common uncorrelated red process
(CURN) has no angular kernel. NANOGrav's 15-year data set is the warning: a ~4 nHz monopole
can eat the Hellings–Downs Bayes factor.

Pair angles and one noisy correlation table are public. You may buy parametric replicate tables
from the frozen generator. The callback retains the legacy name `bootstrap`, but it is not a
nonparametric bootstrap of the observed pairs.

## Your task

```python
def interpret_correlations(problem, bootstrap):
    # bootstrap(n) -> n pair-correlation tables, charges ceil(n / bootstrap_batch_size)
    return {"kernel": "hellings_downs", "confidence": ..., "abstain": False}
```

When abstaining, omit `kernel` or leave it unused:

```python
return {"abstain": True, "confidence": ...}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `theta_rad` | pulsar-pair opening angles in radians |
| `rho` | measured pair correlations at those angles |
| `n_pulsars` | number of pulsars in the array (18) |
| `bootstrap_budget_units` | bootstrap-budget units for this array (6) |
| `bootstrap_batch_size` | each `bootstrap(n)` call costs `ceil(n / 20)` units |
| `kernel_names` | `hellings_downs`, `monopole`, `dipole`, `uncorrelated` |
| `measurement_model` | prose: each row is one pair; bootstraps redraw `rho` |
| `hellings_downs_note` | prose: an isotropic GWB is a quadrupole of pulsar angle |
| `abstain_when` | prose: monopole, dipole, or no spatial kernel, or HD is not unique |

### `bootstrap(n)`

`bootstrap(n)` charges `ceil(n / bootstrap_batch_size)` units and returns `n` tables
`{"theta_rad", "rho"}` redrawn from the world's hidden kernel plus measurement noise. `n` must be a
positive integer. Calling past the budget raises and the world scores zero. Bootstraps are
optional: a least-squares kernel comparison on the public table is enough on these arrays.
Because the callback exposes a parametric generator, scores from these synthetic worlds must not
be interpreted as evidence for robustness to real PTA resampling or red-noise misspecification.

### What you return

| key | meaning |
|---|---|
| `kernel` | one of `kernel_names`; required unless `abstain` is true |
| `confidence` | finite number in `[0, 1]` |
| `abstain` | boolean; if true, `kernel` is ignored |

Anything malformed scores that world zero.

## Scoring

The public `combined_score` is development mechanism recovery, normalised so that declining
every world is exactly zero. A Hellings–Downs array scores only if you claim
`hellings_downs`. Claiming Hellings–Downs on a monopole, a dipole, or an uncorrelated process
is a false discovery. False-discovery, correct refusal, coverage and the held-out split are
reported separately and never averaged.

- `sle.contract_lint` is importable and free to call for shape checks. It costs no oracle call.
- Only edit `solution.py`. Keep `interpret_correlations(problem, bootstrap)`.
- NumPy/SciPy only. Deterministic CPU code. No network or process creation. Do not read
  `verification/` or `frontier_eval/`.
