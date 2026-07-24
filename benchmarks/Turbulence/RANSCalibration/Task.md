# RANSCalibration-v2 — calibrate a transferable algebraic channel-flow closure

## Scientific setting

Wall-bounded turbulence closures must reproduce more than a log-law slope. A useful compact
eddy-viscosity model should jointly match the mean velocity and Reynolds shear, retain the exact
fully developed channel momentum balance, and transfer across friction Reynolds number.

This task uses published direct-numerical-simulation statistics at
`Re_tau = 180, 395, 590, 950`. The data are from Perrone, Kuerten, Ridolfi and Scarsoglio,
Zenodo `10.5281/zenodo.5749302` (concept DOI `10.5281/zenodo.4916024`), CC-BY-4.0.
The development objective uses `Re_tau = 180, 395`; the two higher-Re profiles and all
wall-coordinate calibration shifts are evaluator-only.

The public closure has four parameters:

```text
kappa            in [ 0.20,  0.70]
A_plus           in [ 5.00, 80.00]
outer_linear     in [-3.00,  3.00]
outer_quadratic  in [-3.00,  3.00]
```

For wall coordinate `eta = y_plus / Re_tau`, define

```text
outer = (2 eta - eta^2) (3 - 4 eta + 2 eta^2)
        exp(outer_linear eta + outer_quadratic eta^2)
damping = 1 - exp(-y_plus / A_plus)
nu_t_plus = 0.5 * (sqrt(1 + ((kappa Re_tau / 3) outer damping)^2) - 1)
```

The mean-momentum equation is then solved directly:

```text
(1 + nu_t_plus) dU_plus/dy_plus = 1 - eta
-<u'v'>_plus = nu_t_plus dU_plus/dy_plus.
```

Consequently, every accepted parameter vector obeys the channel total-shear balance by
construction. The optimization challenge is to choose one transferable four-parameter closure,
not to evade the governing relation.

## Your task

```python
def calibrate_rans():
    """Return the four closure parameters as a mapping or length-four vector."""
```

The preferred mapping has exactly these keys:

```python
{
    "kappa": ...,
    "A_plus": ...,
    "outer_linear": ...,
    "outer_quadratic": ...,
}
```

## Evaluation

The visible score combines development-profile RMSE for mean velocity and Reynolds shear. The
standard `kappa=0.41, A_plus=26` closure is the zero normalization witness; a deterministic
calibrated development witness defines the unit anchor. Better fits clip at one.

The trusted evaluator separately retains:

- nominal transfer to `Re_tau = 590, 950`;
- worst-case error under `±2.5%` wall-coordinate calibration-scale shifts;
- velocity and Reynolds-shear RMSE for each Reynolds number; and
- positivity and total-shear residual diagnostics.

This is an interpretable reduced-order closure-calibration problem. It is not a full k-epsilon
calibration, a universal RANS model, evidence for separated-flow prediction, or autonomous
discovery of turbulence physics. Those claims require transport-equation solvers, additional
flow families, independent CFD implementations and experimental validation.

## Rules

- Only edit `solution.py`; keep `calibrate_rans()`.
- Return exactly four finite real numbers inside the public bounds.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
- Boolean, complex, malformed, non-finite and out-of-bound artifacts fail closed.
