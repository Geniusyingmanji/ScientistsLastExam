# ModalDamageAttribution — is the modal shift damage, or the weather?

## 关系与区别 / How this differs from the nearest tasks in this repository

- **`ClimateScience/ForcedSignalAttribution`** is the closest: both ask whether a measured shift is
  a real mechanism or a confound, both charge for measurements, and both decline when the evidence
  supports neither. It differs in the artifact and in the refusal: there the answer is a scalar
  amplitude with an interval and the refusal is "this model cannot be trusted"; here the answer is a
  **discrete element index** plus a severity, and the refusal is "the mechanism is outside the
  declared family" — a support change, not a damaged element.
- **`Geophysics/GravityInversion`** also inverts a physical field with a model-inadequacy refusal,
  but its unknowns are continuous source parameters and it has no environmental confound.
- **`ParticlePhysics/DiscrepantMeasurements`** is evidence about published numbers and their stated
  uncertainties; there is no physical model to invert and no new measurement to buy.
- **`Acoustics/RoomImpulseResponse`** and **`StructuralEngineering/TrussWeightMinimization`** share
  the vibration and structural setting but are optimization: they design a structure, they do not
  diagnose one.

No task in the Frontier-Eng catalogue (47 tasks in the paper appendix, 95 entries in its
`TASK_DETAILS`) concerns structural health monitoring, modal analysis or damage localisation; its
structural cell is weight and compliance minimisation.

## The question

A structure is a chain of `mass_count` masses joined by `mass_count + 1` springs, the first and
last of them to ground. You are given a **validated model** of it, its commissioning frequencies,
and a budget of measurement days. Has an internal element lost stiffness, which one and by how
much — or is the shift you see not damage at all?

## Four ways to be wrong

- **The weather moves every frequency.** Temperature scales every spring by one common factor, so
  it multiplies every eigenvalue equally. The commissioning campaign measured the healthy structure
  only inside `baseline_temperature_range`, and the true stiffness law bends at both ends of that
  band. A healthy structure measured outside it, compared against a linearly extrapolated baseline,
  has moved several per cent and looks badly damaged. **The ratios `f_k / f_1` are exactly
  invariant to any common stiffness factor** — that is the confound, removed rather than modelled.
- **The model is not the structure.** `nominal_masses` and `nominal_springs` carry up to
  `model_error_scale` of relative error against the structure the commissioning campaign measured.
  Taking the model's own healthy ratios as the reference point inherits that error as a permanent
  apparent shift. The commissioning frequencies are measurements of the real thing, and their
  ratios are the honest baseline.
- **A support change is not damage.** A ground spring can lose restraint. It moves the frequencies
  by as much as a damaged element does — the two signal ranges overlap by construction — and no
  member of the declared family reproduces its pattern. The family is exactly one **internal**
  element at one severity; a support change is outside it, and the honest answer is to decline.
- **A quiet day is a noisy measurement.** Each day publishes an excitation quality, and the noise
  on its frequencies scales as `base_relative_noise / sqrt(excitation_quality)`. Excitation is
  independent of temperature, so there is no day that is both quiet-proof and confound-proof.

A healthy structure is **not** the declining case: "no damage" is the finding. Declining there is a
missed finding; claiming damage there is a false alarm.

## Where the budget actually goes

The smallest damage in these worlds shifts the ratios by under two per cent, and a single day
carries about one per cent of ratio noise at the best excitation and three times that at the worst.
Nine high-excitation days bring the noise to a third of one per cent; one day does not — measuring
once instead of nine times costs a third of the score. Choosing days is choosing signal-to-noise,
and the temperature of a day is a distraction once you work in ratios.

## What you implement

```python
def attribute_damage(problem, measure):
    ...
    return {"damaged": True, "element": 4, "severity": 0.27, "confidence": 0.8, "abstain": False}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `mass_count` | number of masses (8); springs are indexed `0..mass_count`, the ends to ground |
| `mode_count` | how many modal frequencies each measurement returns (5) |
| `measurement_budget_days` | how many days you may measure on this structure (9) |
| `damage_element_range` | `[1, mass_count - 1]`: the internal springs, the only damage family |
| `damage_severity_range` | `[0.12, 0.40]`: the stiffness fraction a damaged element loses |
| `severity_tolerance` | absolute severity error at which the severity score reaches zero (0.04) |
| `base_relative_noise` | relative frequency noise at excitation quality 1.0 (0.006) |
| `baseline_temperature_range` | the band the commissioning campaign covers |
| `nominal_masses` | `mass_count` floats: the validated healthy masses |
| `nominal_springs` | `mass_count + 1` floats: the validated healthy stiffnesses at the reference temperature |
| `model_error_scale` | relative error those two carry against the real structure (0.03) |
| `calendar` | one entry per available day: `{"day", "temperature_celsius", "excitation_quality"}` |
| `commissioning_baseline` | rows of `{"temperature_celsius", "frequencies_hz"}` measured on the healthy structure |
| `structure_model` | prose: how frequencies follow from masses and springs |
| `damage_model` | prose: exactly one internal spring loses stiffness; the ground springs are not in the family |
| `thermal_confound` | prose: temperature is one common factor, and the law is not linear outside the baseline band |
| `measurement_model` | prose: what a day of measurement returns and how its noise scales |
| `abstain_when` | prose: when the evidence fits no single-element damage |

### `measure(day)`

Charges one day and returns `{"day", "temperature_celsius", "excitation_quality",
"frequencies_hz"}` for the structure **as it is now**. `day` must be an integer index into the
calendar. Measuring past the budget raises and the structure scores zero, so count your days.
Repeating a day re-draws its noise, which is what makes averaging worth the budget.

### What you return

| key | meaning |
|---|---|
| `damaged` | `True` if you claim an element has lost stiffness |
| `element` | the internal spring index, `1..mass_count-1`, required when `damaged` is true |
| `severity` | the fraction of stiffness lost, in `(0, 1)`, required when `damaged` is true |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` to decline: the evidence fits no single-element damage |

Anything malformed scores that structure zero. It is never an infrastructure failure.
`sle.contract_lint` is importable and free to call for shape checks; it costs no measurement day.

## How you are scored

Ten development structures: six damaged, two healthy, two with a changed support. Each contributes
a mechanism score:

- **damaged**: naming the right element scores `0.5 + 0.5 * severity_score`, where the severity
  score falls linearly from 1 to 0 as the severity error reaches `severity_tolerance`. Naming the
  wrong element scores 0 and is a false discovery — it sends a crew to the wrong span. Saying "no
  damage" or declining scores 0.
- **healthy**: `damaged = False` scores 1; claiming damage scores 0 and is a false alarm; declining
  scores 0.
- **support change**: declining scores 1; any claim scores 0 and is a false discovery.

`combined_score` is the mean over the development structures, renormalised so that **declining
every structure scores exactly 0.0**. Never claiming damage also scores 0.0.

Reported separately, never averaged into one number:

`localisation_rate` · `severity_score` · `healthy_false_alarm_rate` · `false_discovery_rate` ·
`correct_refusal_rate` · `discovery_coverage` · `confidence_calibration`

A sealed held-out set of nine further structures is scored too and is not visible to a searcher.

## What each competence is worth

Ablating the reference — one choice changed at a time:

| strategy | score | localisation | severity | healthy false alarm | false discovery | refusal | coverage | held out |
|---|---|---|---|---|---|---|---|---|
| commissioning baseline + ratios + family search + relative-residual refusal | **0.733** | 0.83 | 0.46 | 0.00 | 0.10 | 1.00 | 1.00 | 0.587 |
| same, healthy ratios from the published model instead of the campaign | 0.544 | 0.83 | 0.28 | 0.00 | 0.10 | 1.00 | 0.88 | 0.515 |
| same, absolute frequencies instead of ratios | 0.418 | 0.33 | 0.11 | 0.00 | 0.00 | 1.00 | 0.50 | 0.214 |
| same, never declining | 0.483 | 0.83 | 0.46 | 0.00 | 0.30 | 0.00 | 1.00 | 0.301 |
| same, coldest days instead of highest excitation | 0.613 | 0.67 | 0.30 | 0.00 | 0.10 | 1.00 | 0.88 | 0.391 |
| same, one day instead of nine | 0.250 | 0.50 | 0.17 | 0.00 | 0.20 | 1.00 | 0.62 | 0.239 |
| same, severity grid of 0.05 instead of 0.01 | 0.721 | 0.83 | 0.42 | 0.00 | 0.10 | 1.00 | 1.00 | 0.691 |
| temperature-extrapolated absolute frequencies, never declining | 0.000 | 0.33 | 0.00 | 1.00 | 0.80 | 0.00 | 1.00 | 0.000 |
| declining everything | 0.000 | — | — | 0.00 | 0.00 | 1.00 | 0.00 | 0.000 |
| never claiming damage | 0.000 | — | — | 0.00 | 0.00 | 0.00 | 1.00 | 0.000 |

Every row costs something real: taking the healthy ratios from the published model instead of the
campaign costs 0.19, working in absolute frequencies 0.32, never declining 0.25, measuring once
instead of nine times 0.48, and choosing the coldest days 0.12. The reference's severity score is
0.46 against a tolerance of four per cent, and that is where most of what remains lives.

**Low-dimensional shortcuts do not solve this task.** A sweep of 2812 strategies of the form
"average the shift over the highest-excitation days, declare healthy below a threshold, decline
above a second, otherwise name the mode with the largest deviation and scale the severity from the
shift" reaches **0.382** without the ratio insight and 0.259 with it, against the reference's 0.733
and a ceiling of 1.0.

## Rules

- Only edit `solution.py`; keep `attribute_damage(problem, measure)`.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no measurement day.
- Do not read `verification/` or `frontier_eval/`.
