# TransientChirpInference

## Scientific problem

Use a finite two-detector strain-observation budget to characterize a transient signal. Decide
whether the data support a coherent windowed chirp, a coherent zero-slope line, or a detector-localized
glitch; estimate initial frequency, chirp frequency slope, event time, and signal amplitude. Abstain when the
low-SNR observations do not distinguish a supported model.

## Candidate interface

Implement `infer_transient(problem, observe)`.

### Every key in `problem`

| key | meaning |
|---|---|
| `candidate_times` | allowed observation epochs in days |
| `detectors` | exactly `['H1', 'L1']` |
| `detector_costs` | mapping `{'H1': 1, 'L1': 1}` |
| `observation_budget_units` | total observation allowance, 24 |
| `minimum_evidence_queries` | minimum distinct query IDs to cite, 6 |
| `model_labels` | allowed labels: `chirp`, `line`, `glitch` |
| `initial_frequency_bounds` | inclusive output bounds `[0.04, 0.18]` cycles/day |
| `frequency_slope_bounds` | inclusive output bounds `[0, 0.05]` cycles/day^2 |
| `event_time_bounds` | inclusive output bounds `[0, 18]` days |
| `amplitude_bounds` | inclusive output bounds `[0, 1]` |
| `signal_model` | prose description of coherent chirp and line families |
| `glitch_model` | prose description of a detector-localized transient |
| `abstain_when` | prose rule for refusing low-SNR ambiguity |
| `evidence_requirement` | prose requirement for current-world query citations |

### `observe(time, detector)`

`time` must be one of `candidate_times` and `detector` must be `H1` or `L1`. Each call costs the
value in `detector_costs`; duplicate `(time, detector)` calls, unknown epochs or detectors, and
overspending fail closed. The callback returns exactly `query_id`, `time`, `detector`, `strain`,
`uncertainty`, and `budget_used`.

## Return value

Return a mapping with boolean `abstain`, finite `confidence` in `[0, 1]`, and at least six distinct
current-world `evidence_query_ids`. A non-abstaining answer additionally contains `model`, finite
`initial_frequency` in `[0.04, 0.18]`, `frequency_slope` in `[0, 0.05]`, finite `event_time` in `[0, 18]`, and finite `amplitude` in
`[0, 1]`. Malformed output or callback violations score invalid instead of crashing.

## Scoring

Correctly labeled supported worlds score model identification (0.45), parameter recovery (0.35),
and amplitude recovery (0.20); incorrect labels and supported-world refusals receive zero. For
chirps and lines, parameter recovery averages initial-frequency quality (tolerance 0.010 cycles/day)
and slope quality (tolerance 0.004 cycles/day^2). Glitch event-time tolerance is 1.2 days. Amplitude
tolerance is 0.30. Confidence is reported as a separate calibration diagnostic, not science credit.
Ambiguous worlds score one for refusal,
zero for a claim. The headline is `max(0, (sum(world_scores) - unsupported_count) / supported_count)`
times correct-refusal rate; both blanket refusal and never refusing score zero.

`development_mechanism_score` and `heldout_mechanism_score` are supported-world model accuracy,
with abstentions counted as incorrect. `*_science_score` reports the separate unnormalized
composite. False-discovery denominators count claims, refusal denominators count ambiguous worlds,
and coverage denominators include every supported world. Counts and denominators accompany rates;
`*_attempted_discovery` reports whether any claim was made. `*_confidence_score` reports
`1 - abs(confidence - decision_correct)` separately, including wrong claims.
`robustness_score` uses the same normalized headline on held-out worlds.

All families have the same reported noise standard deviation; ambiguity comes from weak signal.
Each supported H1 trace has a paired coherent/localized world with exactly the same H1 samples and
noise. L1 evidence is therefore required to distinguish the pair; an H1-only method cannot do so,
regardless of its waveform fit. Chirps and lines still require phase-evolution fits.
Each world receives a fresh copy of `problem`. If a candidate object defines `reset_session()`, the
evaluator calls that hook before each world; ordinary module-level state is otherwise retained.
The initial frequency is in [0.04, 0.18] cycles/day.
The reference spends the full budget on fourteen H1 and ten L1 epochs across the 0--18 day baseline;
adaptive cadences and window-aware joint fits remain explicit headroom. This is a reduced-order phase model,
not a full inspiral waveform.
The quadratic phase is a linear-frequency chirp approximation of the kind used in chirplet
analyses. The Gaussian envelope, day-valued observation coordinates, fixed detector response
scaling, independent Gaussian noise, and paired channel responses are procedural laboratory
choices. H1/L1 denote two synthetic channels; the task does not reproduce LIGO's physical time
scales, antenna response, inter-site delay, nonstationary noise, or a complete inspiral waveform.
A correct answer identifies the declared waveform family and its synthetic parameters, not
astrophysical source parameters or a publishable gravitational-wave detection.

Current in-process reference: 0.654248 development / 0.601739 held-out normalized score. A fair
H1-only variant scores 0/0 because it cannot distinguish paired coherent/localized worlds; the
review-supplied zero-crossing estimator scores 0.186648/0.159037; removing chirp fitting scores
0.240935/0.151832; never refusing gives 0/0. Development-selected finite grids reach
0.331990/0.356481 (216-policy morphology), 0.305562/0.419805 (1,620-policy sign-count),
0.391411/0.438745 (2,916-policy threshold), and 0.275475/0.222719 (324-policy five-slope lookup).
These are finite-grid maxima, not exhaustive algorithmic upper bounds. The reference and selected
threshold witness were each replayed twice with identical full metrics on clean Linux.

## Relationship to nearby tasks

`Gravitation/PTAHellingsDowns` uses angular correlations across many pulsars; this task fits one
time-domain transient using coherence between two detectors. `Exoplanets/RadialVelocityPlanets`
returns planet periods from a fixed Doppler series with activity and aliases; this task acquires
paired-channel samples and recovers transient phase evolution and detector localization.

## Rules and references

- Only edit `solution.py`; keep `infer_transient(problem, observe)`.
- Use deterministic CPU Python, NumPy and the standard library only.
- Do not read `verification/` or `frontier_eval/`, access the network, or create processes.
- `sle.contract_lint` is importable and free to call for shape checks.

The waveform model is a reduced-order analogue of compact-binary chirp searches and detector
glitch vetting. Scientific context: Abbott et al., *Observing gravitational-wave transient GW150914 with minimal assumptions*,
*Phys. Rev. D* 93, 122004 (2016), DOI
`10.1103/PhysRevD.93.122004`; Allen et al., *Phys. Rev. D* 85, 122006 (2012), DOI
`10.1103/PhysRevD.85.122006`.

The linear-frequency model family is motivated by Mohapatra, Nemtzow, Chassande-Mottin and
Cadonati, *Performance of a Chirplet-based analysis for gravitational waves from binary black
hole mergers* (2012), DOI `10.1088/1742-6596/363/1/012031`,
<https://arxiv.org/abs/1111.3621v1>. The cited waveform methods motivate model families and
inference practice; the exact generator, observation budget and score are benchmark design choices.

Mohanty, *Spline Based Search Method For Unmodeled Transient Gravitational Wave Chirps* (2017),
DOI `10.1103/PhysRevD.96.102008`, Section IV.1,
<https://arxiv.org/html/1709.08870v3#S4.I1.i4>, explicitly uses a constant-amplitude quadratic-phase
linear chirp. Its zero-slope limit is the sinusoidal line family used here. This is a model-family
precedent, not a calibration of this laboratory's chosen parameters or physical time scale.
