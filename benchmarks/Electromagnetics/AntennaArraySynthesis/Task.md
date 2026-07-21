# AntennaArraySynthesis — sidelobe/null synthesis under array impairments

## Scientific background

A linear phased array forms a far-field pattern by choosing one complex excitation per element.
For positions `x_n` measured in nominal wavelengths and angle `theta`, this benchmark uses

```text
AF(theta) = sum_n w_n exp(j 2 pi x_n sin(theta)).
```

The design must preserve a beam in a requested steering direction while suppressing sidelobes
and two interference neighborhoods. Dolph's classical construction shows the beamwidth–sidelobe
tradeoff for ideal broadside arrays. Real arrays also suffer frequency offset, element position
and gain/phase errors, and failed elements; these can elevate peak sidelobes substantially.

## Your task

Implement a policy that handles varying uniform and nonuniform arrays:

```python
def design_array(positions_lambda, steering_angle_deg, interference_angles_deg,
                 mainlobe_half_width_sine, angle_limit_deg, null_half_width_deg,
                 null_weight, l2_norm_limit, element_amplitude_limit):
    """Return one finite complex excitation per supplied element position."""
```

The nominal evaluator samples `[-angle_limit_deg, angle_limit_deg]`. The mainlobe is the region

```text
abs(sin(theta) - sin(steering_angle_deg)) < mainlobe_half_width_sine.
```

Each interference neighborhood spans `+/- null_half_width_deg`. Let `g` be target-direction
gain, `s` the peak sidelobe magnitude divided by `g`, and `q` the peak interference-neighborhood
magnitude divided by `g`. Nominal pattern quality is

```text
quality_db = -20 log10(max(s, null_weight * q)).
```

Overall complex scale and phase are physically irrelevant here. The evaluator divides returned
weights by their finite nonzero nominal target response, then requires the normalized L2 norm
and every normalized element amplitude to stay within the supplied limits. Zero excitation,
malformed values and excessive excitation fail closed; values are never clipped.

## Evaluation

`combined_score` is development-array nominal quality improvement above uniform steering,
normalized by independently calibrated Kaiser-taper/null-projection witnesses. The same policy
is called on interleaved held-out sizes, scan angles and mildly nonuniform geometries. The trusted
evaluator separately measures worst-case quality across:

- nominal-frequency offsets of `-4%` and `+4%`;
- deterministic position errors bounded by `0.008` wavelength;
- deterministic amplitude errors bounded by `2.5%` and phase errors bounded by `2 degrees`;
- every possible single-element failure.

Shifted quality includes a penalty if target gain falls below 0.80. Robustness, held-out transfer,
per-shift patterns and excitation diagnostics are evaluator-only and never control selection.
Reference witnesses are strong reproducible domain policies, not proofs of global optimality;
better feasible patterns are allowed and clip at score one.

## Rules

- Only edit `solution.py`; keep the complete `design_array` signature.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Handle arbitrary supplied element positions and counts; do not hard-code one array.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Dolph, *Proceedings of the IRE* 34(6), 335–348 (1946),
doi:10.1109/JRPROC.1946.225956; Ramsdale & Howerton, *Journal of the Acoustical Society of
America* 68(3), 901–906 (1980), doi:10.1121/1.384777.
