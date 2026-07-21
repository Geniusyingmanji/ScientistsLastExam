# ActiveLawDiscovery — discover dynamical laws by choosing experiments

## Scientific background

Recovering a governing equation requires more than fitting one observed trajectory. The
scientist must choose informative initial conditions and forcings, distinguish real terms from
noise, test the inferred law outside the observed regime, and sometimes conclude that the
declared model library is inadequate.

Each hidden world is a controlled two-state system

```text
d[x,y]/dt = Theta(x,y,u) @ Xi,
```

where the public candidate library is

```text
1, x, y, u, x^2, x*y, y^2, x^3, x^2*y, x*y^2, y^3, x*u, y*u.
```

Most worlds have a sparse coefficient matrix `Xi`, but some are null or contain dynamics
outside this library. Always returning a polynomial mechanism is therefore a false discovery.

## Your task

Implement:

```python
def discover_law(n_states, term_names, experiment, budget_units):
    """Return a dict containing:
      coefficients: (len(term_names), n_states) coefficient matrix
      support:      optional same-shape 0/1 matrix
      confidence:   optional scalar in [0,1]
      abstain:      optional bool; True means no supported in-library law

    experiment(initial_state, controls, n_steps) returns a dict with:
      time:     shape (n_steps + 1,)
      states:   noisy observations, shape (n_steps + 1, n_states)
      controls: applied piecewise-constant controls, shape (n_steps,)
    """
```

`initial_state` must contain two finite values in `[-2,2]`. `controls` may be one scalar or an
array of length `n_steps`, with values in `[-1.5,1.5]`. A query may contain 8–64 integration
steps. It costs `ceil(n_steps / 16)` budget units; exceeding `budget_units` invalidates that
world even if your code catches the callback error. Time spacing is reported by the laboratory.

## Evaluation

- `combined_score` measures sparse term and coefficient recovery on development worlds.
- `robustness_score` measures the same mechanism policy on larger-noise and shifted hidden
  worlds; it is evaluator-only.
- development and validation prediction scores integrate the submitted equation on sealed
  initial conditions and controls.
- null/misspecified abstention, false discoveries, experimental calls and budget are reported
  separately.

These metrics are not collapsed into one “science score.” A high mechanism score with poor
sealed prediction is not a validated law, and abstaining on every world is the normalized
zero-score baseline.

## Rules

- Only edit `solution.py`; keep the `discover_law` signature.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not assume hidden-world order, coefficients, noise level or a fixed trajectory count.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
