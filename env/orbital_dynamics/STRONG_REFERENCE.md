# Author-informed continuous-family reference

`strong_reference.py` fits three continuous parameters from public trajectory
records: `mu`, radial exponent `p`, and linear drag. The author supplies the
family

`acceleration = -mu * position / (radius^2 + 0.25^2)^((p+1)/2) - drag * velocity`.

The center resolution is public. The force equation and this three-parameter
family are extra information that candidate agents do not receive. This is an
author-informed reference, separate from the registered empirical baseline.
It supplies no class-identification verdict. It does not establish a complete
law, autonomous discovery, contamination resistance or calibrated difficulty.
A single fitted point does not describe parameter uncertainty, alternative
minima, model misspecification or observationally equivalent laws.

## Fitting and prediction

`fit(records, limits=None)` accepts 1–6 records containing public `spec` and
`observation`, plus optional public `id` and `cost`. Observations must have the
four declared channels, matching times and finite numeric values. Extra private
fields are rejected. Neither fitting nor prediction accepts a `World`, seed,
stratum, private parameter object or query outcome.

There is one `scipy.optimize.least_squares` call, with method `trf`, a two-point
finite-difference Jacobian and the fixed start `[1, 2, 0.03]`. The broad bounds
are `[0.6, 1, 0]` through `[1.4, 3, 0.15]`. They are author-declared fitting
bounds, not the hidden generator's stratum menu. There is no class screen,
multistart search, adaptive source selection or retry after a bad fit.

Residuals use the public per-channel noise standard deviations. Time-zero rows
and all exact impulse-boundary rows are excluded. Excluding the whole boundary
row is conservative: an absolute post-impulse velocity contains unknown prior
evolution, but its instantaneous increment is assigned by the controls.

Prediction uses independently written Cartesian equations, RK45 integration and
ordered impulse application. It imports only the public protocol from this
environment, never its private kernel or parameter generator. An event adds
`delta_v` before a same-time sample. The reference uses `rtol=1e-8`,
`atol=1e-10`, and maximum step `0.05 T`.

| Per-fit limit | Ceiling |
|---|---:|
| Optimizer `max_nfev` | 30 |
| Actual residual calls, including finite differences | 160 |
| CPU / wall time | 30 / 60 s |
| RHS calls across the fit | 1,200,000 |
| RHS calls per trajectory | 60,000 |

Limits can be reduced, never increased. Actual residual and RHS counters are
checked before each extra call. Time is checked before residuals, at every RHS
call, between segments and after solver/optimizer returns. Thus time stopping is
cooperative at bounded numerical callbacks, not an operating-system process
kill. Standalone predictions have 10 s CPU, 20 s wall and 60,000 RHS ceilings.
Returned usage includes calls attempted and completed, trajectory counts, CPU
time and wall time. Prediction budget errors carry their usage and limits.

A normal optimizer return preserves its endpoint, including a finite
unconverged endpoint. An interruption preserves the last fully completed finite
residual point by chronological order, even if its loss is worse than an earlier
point. Finite-difference evaluations are included in that chronology. It is
marked unconverged with the stop reason; it is not presented as an optimizer
solution. An interruption before any complete residual returns `model=None`.
No second model is fitted or selected as a substitute. All failed and
unconverged cases remain in the calibration accounting.

## Planned balanced development check

The private plan was written before any new calibration trajectories. It uses
a fixed finite pool, inspecting only `operator_stratum` to select the first two
instances of each stratum. Selection generates zero trajectories and consults
no scores. The pool and actual instance seeds remain in `plan-private.json`.

All six are development instances. The pool is not expanded if a stratum lacks
two instances. The old four-instance development sample, its missing conservative
inverse-square stratum and its original diagnostic results remain unchanged.
Label balance in six instances is not a representative population or a formal
candidate-model cohort.

Each instance supplies exactly six noisy source trajectories: radii
`0.85, 1.2, 1.75 L` crossed with positive tangential speeds `0.55, 0.95 L/T`,
with zero radial speed and no impulse. All use times
`[0, 0.15, 0.3, 0.5, 0.75, 1, 1.5, 2, 2.5, 3] T`.
Each instance is fitted once. Its model and fit diagnostics are written before
any private query outcome is generated. There are four fixed `conditions`
queries and four fixed `interventions` queries per instance, with deterministic
private panel seeds. Canonical specs and control signatures excluding sample
times must differ from all sources; overlap causes failure, not resampling.

The private driver compares the frozen reference point and the existing public
empirical baseline using the same six source records. Primary diagnostic errors
exclude time zero and exact impulse rows. Exact impulse rows are separate
assignment-boundary diagnostics, never discovery evidence. A further mask uses
the public pilot lag of 0.25 T after preparation and every prior impulse.
All metrics use the existing public scales and noise levels. The descriptive
`100*exp(-NRMSE/0.1)` number is not an official combined score.

All six planned fits and all 48 planned queries per method remain in the
denominators. Missing jobs or failed predictions contribute zero descriptive
score; errors averaged only over available valid predictions are explicitly
conditional. Convergence, model availability, budget stops and failed or
unavailable metrics are reported separately. A usable finite interrupted point
may be evaluated, but remains marked unconverged throughout.

## Private execution and tests

The private directory is
`calibration/orbital-strong-reference/` under the operator artifact root. It
contains `plan-private.json`, `calibration_driver.py` and small driver-fixture
tests. It is not candidate context. Raw source records, fitted models and query
targets belong only in new private output directories. Every artifact uses
exclusive creation, and a run refuses an existing output directory.

After review, freeze on the intended checkout and run the frozen design on the
designated CPU host, `62910175`. From the repository root, with `artifact_dir`
pointing to that private directory and the scientific Python environment active:

```sh
PYTHONPATH="$PWD" python "$artifact_dir/calibration_driver.py" freeze \
  --plan "$artifact_dir/plan-private.json" \
  --output "$artifact_dir/freeze-private.json"
PYTHONPATH="$PWD" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python "$artifact_dir/calibration_driver.py" run \
  --freeze "$artifact_dir/freeze-private.json" \
  --output "$artifact_dir/run-private"
```

Freeze fixes the plan, implementation hashes and all panel specs without
generating trajectories. Run rejects changed implementation hashes. Neither
command calls a model API. The six-instance calibration has **not** been run
as part of implementation. No performance conclusion is available yet.

```sh
python -m pytest -q env/orbital_dynamics/tests/test_strong_reference.py
PYTHONPATH="$PWD" python -m pytest -q "$artifact_dir/test_calibration_driver.py"
```

Tests use analytic circles, explicit event assignments, forced budget/numerical
failures and inert driver fixtures. Private constructors and kernels are blocked
in fitter tests. A one-circle fit checks numerical consistency without asserting
that it identifies `mu` and `p` separately. These implementation checks are not
a new independent scientific review.
