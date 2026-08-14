# QuartzCrystalMicrobalanceLab — infer deposition from raw I/Q sweeps

## Scientific setting

A quartz crystal microbalance (QCM) can estimate a rigid film's areal mass from resonance-frequency
shifts, but the instrument records quantized in-phase and quadrature counts rather than mass. The
measurement chain also has a complex gain, offset and phase that drift between two calibration
captures. Missing points, ADC clipping or an I/Q wiring fault can invalidate the inference, while
viscoelastic loading or a changing deposition rate can invalidate the declared rigid linear model.

Supported worlds use a public Butterworth--Van Dyke (BVD) complex-admittance model for harmonics
`n = 1, 3, 5` and the public Sauerbrey relation

```text
Y(f) = 1 / (Rm + i*(2*pi*f*Lm - 1/(2*pi*f*Cm))) + i*2*pi*f*C0
raw_IQ = complex_offset(capture) + complex_gain(capture) * Y(f) + quantization_noise
delta_f_n / n = -56.6 Hz * mass_ug_cm2
mass(t) = deposition_rate * t
```

Complex offset and gain vary linearly between the start and end calibration captures. Development
and held-out worlds include rigid linear deposition, missing raw samples, viscoelastic overtone
dispersion, a deposition-rate change, I/Q conjugation and ADC clipping. This is a deterministic
reduced-order signal-processing laboratory, not a physical deposition experiment.

## Your task

Implement:

```python
def analyze_qcm(problem):
    """Return a calibrated, evidence-bound deposition conclusion and stop decision."""
```

`problem` contains:

- two calibration blocks. Each record supplies a known complex admittance and raw integer I/Q
  counts;
- nine raw admittance sweeps over three harmonics and deposition times 0, 20 and 40 seconds;
- immutable calibration and sweep IDs, capture indices, frequencies, missing values as `None`,
  the ADC limit and public model constants;
- the 60-second prediction horizon and a target areal mass for the deposition stop decision.

Return exactly:

- `calibration`, containing exactly these four keys, each a `[real, imag]` pair:

  | key | |
  |---|---|
  | `start_offset_counts` | complex offset at the first calibration capture |
  | `end_offset_counts` | complex offset at the last calibration capture |
  | `start_complex_gain_counts_per_siemens` | complex gain at the first capture |
  | `end_complex_gain_counts_per_siemens` | complex gain at the last capture |

  The names are part of the contract: a submission whose calibration dictionary has any other
  key set is rejected before it is scored, and the resulting zero is indistinguishable from one
  earned on the science.
- `resonance_frequency_hz_by_sweep` and `quality_factor_by_sweep`, each keyed by every sweep ID;
- `mass_loading_ug_cm2` at 40 seconds, `deposition_rate_ug_cm2_s`, and
  `predicted_mass_ug_cm2` at 60 seconds;
- `additional_deposition_time_s` needed to reach the public target under the supported model;
- `diagnosis`, one of `"supported"`, `"physical_anomaly"`, `"instrument_fault"` or
  `"undetermined"`;
- `confidence` in `[0,1]`, boolean `abstain`, and unique `evidence_ids` drawn only from the
  returned calibration and sweep IDs.

Missing points may be omitted during fitting. Complex calibration, resonance extraction and model
checking must operate on the supplied raw counts. A supported conclusion requires
`diagnosis="supported"` and `abstain=False`. Viscoelastic or changing-rate data should use
`diagnosis="physical_anomaly"` and abstain. I/Q conjugation or clipping should use
`diagnosis="instrument_fault"` and abstain.

## Evaluation

- `combined_score` is the development mean joint of evidence lineage, complex calibration,
  resonance/Q extraction, rigid-film mass/rate recovery, 60-second prediction, target stop
  decision and diagnosis.
- `robustness_score` evaluates the committed prediction and stop time after a sealed future-rate
  shift and a sealed misspecification of the mass-to-frequency Sauerbrey coefficient.
- held-out worlds, reference-preprocessor and oracle-clean-feature controls, fault type,
  supported coverage, false discovery, confidence, calibration residual, clipping, missingness
  and per-world metrics remain evaluator-only.

The reference preprocessing pipeline is a task-calibration witness rather than a hidden solution
available to candidates. The benchmark measures executable inference within the declared BVD and
Sauerbrey families. It does not validate a QCM instrument, coating process, material or scientific
discovery.

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

- Only edit `solution.py`; keep `analyze_qcm(problem)`.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not assume hidden-world order, seeds, drift values, missingness or fault type.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Rodahl et al., DOI `10.1063/1.1145396`; Martin, Granstaff and Frye, DOI
`10.1021/ac00020a015`; Kankare, DOI `10.1021/la025911w`; Nakamoto and Moriizumi, DOI
`10.1143/jjap.29.963`; Na Songkhla and Nakamoto, DOI `10.3390/chemosensors9010009`.

## Inputs the candidate receives

Every key the task passes to the candidate, taken from the baseline's reads and from the
evaluator's own construction of the input mapping. Names are part of the contract: a candidate
that reaches for one of these quantities under a different name raises at runtime and scores
nothing, and that zero cannot be told apart from a zero earned on the science.

| key | |
|---|---|
| `adc_limit` | passed in, unused by the baseline |
| `additional_time_bounds_s` | passed in, unused by the baseline |
| `calibration_blocks` | read by the baseline |
| `deposition_rate_bounds_ug_cm2_s` | passed in, unused by the baseline |
| `deposition_times_s` | passed in, unused by the baseline |
| `diagnosis_values` | passed in, unused by the baseline |
| `harmonics` | passed in, unused by the baseline |
| `mass_loading_bounds_ug_cm2` | passed in, unused by the baseline |
| `mass_model` | passed in, unused by the baseline |
| `measurement_model` | passed in, unused by the baseline |
| `motional_capacitance_initial_f_by_harmonic` | passed in, unused by the baseline |
| `nominal_frequency_hz_by_harmonic` | read by the baseline |
| `prediction_time_s` | passed in, unused by the baseline |
| `quality_factor_bounds` | passed in, unused by the baseline |
| `sauerbrey_hz_per_ug_cm2` | passed in, unused by the baseline |
| `schema_version` | passed in, unused by the baseline |
| `shunt_capacitance_f` | passed in, unused by the baseline |
| `sweeps` | read by the baseline |
| `target_mass_ug_cm2` | passed in, unused by the baseline |
