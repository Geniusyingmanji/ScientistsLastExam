# ConvectionDiffusionOpt-v2 — identify transport and design a robust heater layout

## Scientific setting

You control heaters in a two-dimensional device whose steady temperature satisfies the public
homogeneous model

```text
-d/dx(kappa_x dT/dx) - d/dy(kappa_y dT/dy)
+ velocity_x dT/dx + velocity_y dT/dy + loss T = Q,   T|boundary = 0.
```

Each heat source contributes

```text
Q_i(x,y) = strength_i exp(-((x-x_i)^2+(y-y_i)^2)/(2*source_width^2)).
```

The five coefficients are unknown. A visible desired temperature field is supplied for each
world. You may spend a limited experimental budget on calibration heater/sensor layouts, then
must submit both the inferred mechanism and a four-source layout that reproduces the desired
field. Some apparatuses have no heat response or have spatially varying transport outside the
public homogeneous model; confidently fitting those worlds is a false discovery.

## Entrypoint

```python
def design_thermal_policy(
    grid_shape,
    parameter_names,
    parameter_bounds,
    design_specification,
    experiment,
    budget_units,
):
    """Return parameters, source_positions, source_strengths, confidence and abstain."""
```

`design_specification` contains the visible grid, desired `target_temperature`, source geometry
and power limits, and the declared robustness envelope. A call

```python
experiment(source_positions, source_strengths, sensor_positions)
```

returns noisy temperatures at 4--24 chosen interior sensors. It costs
`1 + n_sources + ceil(n_sensors/8)` units. You may use 1--3 calibration sources per call and
must not exceed the supplied 12-unit budget, even if your code catches a callback exception.

Return a dictionary with:

- `parameters`: five finite values in the supplied bounds;
- `source_positions`: finite `(4,2)` positions inside the supplied margin;
- `source_strengths`: four finite strengths satisfying individual and total-power limits;
- `confidence`: a finite scalar in `[0,1]`;
- `abstain`: a boolean. If true, the numerical mechanism/design fields are ignored.

## Evaluation

- `combined_score` is development joint mechanism/prediction/design quality above an always-
  abstain baseline.
- mechanism, diagnostic prediction and nominal target-field design scores are retained
  separately.
- evaluator-only robustness applies transport, placement, calibration and combined shifts.
- held-out worlds use new transport/source regimes and higher observation noise.
- null and spatially heterogeneous worlds separately measure correct refusal and false discovery.

The metrics are not evidence of a real device discovery. Independent discretization,
high-fidelity or experimental replication remains necessary.

## Checking your submission's shape before spending a call

`sle.contract_lint` is importable inside the sandbox. Calling it costs no oracle
budget and reveals nothing about the science — every check is about form, and none touches a
score, a hidden world or a reference value.

```python
from sle.contract_lint import mapping, finite_array, in_range, explain

ok, why = mapping(submission, required=["a", "b"])
if not ok:
    ...  # `why` names the missing or unexpected keys
```

Available: `finite_array`, `binary_array`, `mapping`, `in_range`, `probabilities`,
`sequence_of_str`, and `explain` to join failures into one message. Each returns `(ok, reason)`
with a specific reason — "expected shape (12000, 1), got (3, 3)" rather than "invalid submission".

This exists because a rejected submission and a hard scientific problem both score zero, and this
task is one where submissions have been rejected often enough that the distinction matters.

## Rules

- Only edit `solution.py` and preserve the entrypoint signature.
- Deterministic Python/NumPy/SciPy/standard-library CPU code only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
- Do not assume hidden-world order, coefficients, reference source positions or noise values.

Reference: Hinze et al., *Optimization with PDE Constraints*, Springer (2009),
DOI `10.1007/978-1-4020-8839-1`.
