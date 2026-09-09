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

The first `measure(radius_um, time_s)` call at each distinct radius costs five units: four setup
units plus one measurement unit. Later calls at an already configured radius cost one unit.
Both arguments must be values listed in `problem`. Repeated measurements are allowed and receive
independent deterministic noise. The returned mapping contains exactly these keys:

| key | meaning |
|---|---|
| `measurement_id` | immutable identifier for this measurement |
| `radius_um` | bleach radius used |
| `time_s` | time after bleaching |
| `recovery_fraction` | normalized fluorescence recovery in `[0, 1]` |
| `recovery_standard_error` | one-standard-error uncertainty |
| `cost_units` | cost of this call (`5` for the first call at a radius, otherwise `1`) |
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

`PopulationGenetics/DemographicSFS` infers demographic histories from allele-frequency summaries,
and `Ecology/OccupancyDetectionDesign` separates occupancy from imperfect detection in repeated
surveys. `Biology/CatalystDeactivationLab` attributes kinetic failure in reactor time courses, while
`Spectroscopy/ActiveNoiseSpectroscopy` reconstructs environmental spectra from controlled quantum
probes. Those tasks use different scientific artifacts, misspecified families, refusal semantics,
and instance generators. Here the artifact is a shared intracellular transport-binding mechanism
and sealed FRAP predictions; the false worlds specifically violate transport scaling, pool count,
or radius-independent binding under an active bleach-radius design.

## Every `problem` key

| key | meaning |
|---|---|
| `bleach_radii_um` | list of allowed bleach-radius numbers |
| `sample_times_s` | list of allowed post-bleach time numbers |
| `measurement_budget_units` | total cost-unit budget, including first-use radius setup |
| `minimum_evidence_measurements` | minimum evidence count for a supported or named unsupported diagnosis |
| `prediction_contexts` | ordered list of `{"radius_um": number, "time_s": number}` mappings for `predicted_recovery` |
| `parameter_bounds` | mapping from each reported parameter key to a two-number `[lower, upper]` list |
| `model_family` | supported reaction-diffusion family |
| `unsupported_families` | allowed resolvable model-inadequacy diagnoses |
| `measurement_model` | callback cost and observation description |
| `abstain_when` | refusal rule |

The keys of `parameter_bounds` are exactly `diffusion_coefficient_um2_s`, `mobile_fraction`,
`binding_on_rate_s`, and `binding_off_rate_s`. Access a prediction context as
`context["radius_um"]` and `context["time_s"]`; its position is the required position in
`predicted_recovery`.

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

The split-prefixed `mechanism_score` is the fraction of all worlds with a scientifically adequate
family decision. A supported-world claim counts only when its continuous `science_score` is at
least `0.5`; an unsupported world counts only for the correct named refusal. Each split publishes
`mechanism_correct_count` and `mechanism_total_count`. Wrong, weak, undetermined, and invalid claims
remain in the denominator and count as incorrect.

Supported worlds score continuous recovery of the four parameters and the supplied conditional
recovery predictions. Errors in `D`, `k_on`, and `k_off` are measured on a logarithmic scale;
mobile-fraction and prediction errors are continuous. Named unsupported worlds score only when the
candidate both abstains and attributes the correct failure family.

Within supported worlds, parameter and prediction quality form a continuous science score with a
small confidence-calibration factor. The split `combined_score` is the mean of that supported-world
composite multiplied by the exact-diagnosis rate across all unsupported worlds. Thus partial or
incorrect refusal reduces the headline score, and never-refuse, fixed-label refusal, and blanket
`undetermined` strategies score exactly zero. The evaluator separately reports mechanism recovery,
false-discovery rate, correct-refusal rate, supported discovery coverage, attempted-discovery rate,
their denominators, and all held-out axes.

## Rules

The 16-unit truth-blind reference uses four times at each endpoint radius and scores `0.927573`
development / `0.890764` held out. The stronger one-endpoint half-budget ablation scores
`0.109060 / 0.107372`; fixing the two binding rates or never refusing scores
`0.000000 / 0.000000`. An optimizer-free 3,798-point coarse model grid reaches
`0.728143 / 0.707547`.

- Only edit `solution.py`; preserve `infer_frap_binding(problem, measure)`.
- Use deterministic CPU Python, NumPy, SciPy, and the standard library only.
- Do not read `verification/` or `frontier_eval/`, access the network, or create processes.
