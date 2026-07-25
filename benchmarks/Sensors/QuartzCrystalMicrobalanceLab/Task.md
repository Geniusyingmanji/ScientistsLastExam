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

- `calibration`, containing start/end complex offsets and complex gains as `[real, imag]` pairs;
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

## Rules

- Only edit `solution.py`; keep `analyze_qcm(problem)`.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- Do not assume hidden-world order, seeds, drift values, missingness or fault type.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.

References: Rodahl et al., DOI `10.1063/1.1145396`; Martin, Granstaff and Frye, DOI
`10.1021/ac00020a015`; Kankare, DOI `10.1021/la025911w`; Nakamoto and Moriizumi, DOI
`10.1143/jjap.29.963`; Na Songkhla and Nakamoto, DOI `10.3390/chemosensors9010009`.
