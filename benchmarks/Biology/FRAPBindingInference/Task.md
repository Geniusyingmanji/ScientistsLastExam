# FRAPBindingInference - separate intracellular diffusion from reversible binding

Fluorescence recovery after photobleaching (FRAP) measures how quickly fluorescence returns to a
bleached region. A slow curve does not by itself identify slow diffusion: reversible binding can
produce a similar trace. You must choose bleach radii and sampling times, fit a shared
reaction-diffusion mechanism, and decline when the curves resolve a model outside that family.

## Interface

Implement:

```python
def infer_frap_binding(problem, measure):
    ...
```

`measure(radius_um, time_s)` costs one unit. Both arguments must be values listed in `problem`.
Repeated measurements are allowed and receive independent deterministic noise. The returned mapping
contains exactly these keys:

| key | meaning |
|---|---|
| `measurement_id` | immutable identifier for this measurement |
| `radius_um` | bleach radius used |
| `time_s` | time after bleaching |
| `recovery_fraction` | normalized fluorescence recovery in `[0, 1]` |
| `recovery_standard_error` | one-standard-error uncertainty |
| `cost_units` | cost of this call |
| `spent_units` | cumulative cost in the current world |

Calling beyond the budget or with an unlisted radius or time invalidates that world even if your
program catches the callback exception.

## Supported model

The supported family has one freely diffusing fluorescent pool that reversibly exchanges with an
immobile bound pool. Its parameters are the diffusion coefficient `D`, mobile fraction `M`,
binding-on rate `k_on`, and binding-off rate `k_off`. For bleach radius `r`, the radial transport
rate is

```text
lambda = 4 D / r**2.
```

The unbleached deficit is the sum of two exponential modes. Their decay rates are the roots

```text
mu_fast, mu_slow = 0.5 * (
    lambda + k_on + k_off
    +/- sqrt((lambda + k_on + k_off)**2 - 4 * lambda * k_off)
)
```

with free equilibrium fraction `k_off / (k_on + k_off)`. If

```text
a = (lambda * free_fraction - mu_slow) / (mu_fast - mu_slow),
```

then the recovery fraction is

```text
M * (1 - a * exp(-mu_fast * t) - (1-a) * exp(-mu_slow * t)).
```

The binding rates are shared across radii. Changing the bleach radius changes transport but not the
chemistry; this is the information that separates diffusion from binding.

## Related tasks

`EnzymeKineticsLaw` distinguishes competing reaction-rate laws, `NMRSpectrumFitting` resolves
overlapping spectral components, and `ForceFieldCalibration` identifies pair potentials from
energy and force queries. Here the scientific artifact is instead a coupled intracellular
transport-binding mechanism inferred by actively perturbing FRAP length and time scales, including
attribution of three ways in which that mechanism can fail.

## Every `problem` key

| key | meaning |
|---|---|
| `bleach_radii_um` | allowed bleach radii |
| `sample_times_s` | allowed post-bleach sampling times |
| `measurement_budget_units` | total one-unit measurement budget |
| `minimum_evidence_measurements` | minimum evidence count for a supported or named unsupported diagnosis |
| `prediction_contexts` | ordered `radius_um`/`time_s` pairs for `predicted_recovery` |
| `parameter_bounds` | numeric lower and upper bounds for all four reported parameters |
| `model_family` | supported reaction-diffusion family |
| `unsupported_families` | allowed resolvable model-inadequacy diagnoses |
| `measurement_model` | callback cost and observation description |
| `abstain_when` | refusal rule |

The possible diagnoses are:

- `supported`: the shared diffusion-binding family is adequate;
- `anomalous_transport`: recovery follows a fractional transport time law;
- `two_mobile_pools`: two freely diffusing pools have different diffusion coefficients;
- `spatially_varying_binding`: the apparent binding rate changes with bleach radius;
- `undetermined`: the evidence is insufficient for a scientific claim.

The three named unsupported diagnoses and `undetermined` require `abstain=True`. `supported`
requires `abstain=False`.

## Submission

Return exactly:

```python
{
    "diagnosis": "supported",
    "diffusion_coefficient_um2_s": 0.7,
    "mobile_fraction": 0.82,
    "binding_on_rate_s": 0.35,
    "binding_off_rate_s": 0.12,
    "predicted_recovery": [0.1, 0.4, 0.3, 0.7, 0.6, 0.8, 0.75, 0.85],
    "confidence": 0.8,
    "abstain": False,
    "evidence_measurement_ids": ["m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08"],
}
```

All numeric values must be finite. Parameters must lie inside `parameter_bounds`, confidence and
predictions must lie in `[0, 1]`, and predictions must follow the order of `prediction_contexts`.
Evidence identifiers must be distinct and must have been returned in the current world. A named
scientific diagnosis requires at least `minimum_evidence_measurements`; an `undetermined`
abstention requires at least one.

`sle.contract_lint` is importable for free shape checks and consumes no measurement budget.

## Scoring

Supported worlds score continuous recovery of the four parameters and the supplied conditional
recovery predictions. Errors in `D`, `k_on`, and `k_off` are measured on a logarithmic scale;
mobile-fraction and prediction errors are continuous. Named unsupported worlds score only when the
candidate both abstains and attributes the correct failure family.

`combined_score` is the mean development-world science score with a small confidence-calibration
factor, clipped to `[0, 1]`. Blanket `undetermined` abstention is valid and scores exactly zero.
The evaluator separately reports mechanism recovery, false-discovery rate, correct-refusal rate,
supported discovery coverage, attempted-discovery rate, their denominators, and all held-out axes.

## Rules

- Only edit `solution.py`; preserve `infer_frap_binding(problem, measure)`.
- Use deterministic CPU Python, NumPy, SciPy, and the standard library only.
- Do not read `verification/` or `frontier_eval/`, access the network, or create processes.
