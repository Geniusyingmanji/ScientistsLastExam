# DeformationMechanismInference — design a geodetic survey and identify volcanic deformation

## Scientific setting

Volcanic unrest can produce similar-looking surface deformation from physically different
sources. Sparse GNSS or InSAR data may support a compact pressure source, sill or dike, while
multi-source and time-dependent rheological responses invalidate that public model family. A
useful inference must therefore select observations, predict unmeasured displacement and retain
the option to refuse an unsupported mechanism.

The public source library contains `mogi`, `sill` and `dike`. Every source uses the parameter row

```text
[x_center_m, y_center_m, depth_m, strength, horizontal_scale_m]
```

with public bounds supplied in `model_library`. The exact public forward expressions and units
are included in that mapping. The common row contains two mechanism-inactive placeholders:
`horizontal_scale_m` is not scored for `mogi`, and `depth_m` is not scored for the reduced-order
`dike`; all five coordinates are active for `sill`. Hidden information consists of source type
and identifiable parameters, noise, null or out-of-family status, and sealed station locations.

## Your task

```python
def infer_deformation_source(survey_bounds_m, model_library, measure, budget_units):
    """Return:
      mechanism_probabilities: mapping with exactly mogi, sill and dike probabilities
      parameters: length-5 row, or [] when abstaining
      confidence: finite scalar in [0,1]
      abstain: bool

    measure(stations_xy_m, modality="gnss") returns:
      stations_xy_m: selected station coordinates, shape (n,2)
      modality: "gnss" or "insar"
      displacement_m: shape (n,3) for GNSS or (n,) for InSAR
      noise_std_m: stated pointwise standard deviation
      look_vector: the fixed InSAR look vector, or [] for GNSS
      budget_cost: charged survey units
    """
```

Each call contains 3–20 unique stations. Its cost is `1 + ceil(n/5)` and total cost may not
exceed 18. Stations must lie inside the square `survey_bounds_m`. Probabilities must be finite,
nonnegative and sum to one. Non-abstaining parameters must satisfy the public bounds.

## Evaluation

- `combined_score` is development mechanism recovery above the always-abstain baseline.
- Supported worlds score source-family probability, bounded parameters and sealed GNSS/InSAR
  prediction using uncertainty-weighted displacement residuals.
- Null and resolvable two-source/rheological worlds reward refusal.
- Mechanism recovery, Brier score, false discovery, correct refusal and discovery coverage are
  reported separately.
- `robustness_score` uses held-out source geometry, noise and station coverage.

This is an elastic reduced-order benchmark, not evidence for a real volcano.

## Oracle and difficulty

The evaluator uses `xarray` to align station/component displacement fields, apply the labeled
InSAR look-vector projection and reduce residuals. The source equations remain the stated local
reduced-order models. Evaluator difficulty levels 1–3 increase geodetic noise, strengthen
out-of-family responses and add supported source worlds; level 1 is the shipped default.

## Rules

- Only edit `solution.py`; keep the complete function signature.
- Deterministic Python/NumPy/SciPy code only; no network or process creation.
- Do not read `verification/` or `frontier_eval/`.
- Survey errors and overspending invalidate the world even when caught.

References: Dzurisin (2003), *Reviews of Geophysics*, doi:`10.1029/2001RG000107`;
Segall (2010), *Earthquake and Volcano Deformation*, ISBN `9780691133027`. These
references motivate the source families and deformation-observation setting; the benchmark
uses the reduced-order equations stated in its public model library.
