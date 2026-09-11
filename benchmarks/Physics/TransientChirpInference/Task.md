# TransientChirpInference

## Scientific problem

Use a finite two-detector strain-observation budget to characterize a transient signal. Decide
whether the data support a coherent chirp, a coherent narrow-band line, or a detector-localized
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

Correctly labeled supported worlds score model identification (0.30), parameter recovery (0.50),
and amplitude recovery (0.20); incorrect labels and supported-world refusals receive zero. For
chirps and lines, parameter recovery averages initial-frequency quality (tolerance 0.008 cycles/day)
and slope quality (tolerance 0.003 cycles/day^2). Glitch event-time tolerance is one day. Amplitude
tolerance is 0.25. Confidence is reported as a separate calibration diagnostic, not science credit.
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
Chirps and lines may have identical early/late sign-change counts, requiring phase-evolution fits.
Each world receives a fresh copy of `problem`. If a candidate object defines `reset_session()`, the
evaluator calls that hook before each world; ordinary module-level state is otherwise retained.
The initial frequency is in [0.04, 0.18] cycles/day.
The reference observes t=0..11, leaving later localized transients and more adaptive schedules
as explicit headroom. This is a reduced-order phase model, not a full inspiral waveform.

Current reference: 0.821949 development / 0.685320 held-out normalized score. Removing H1/L1
coherence gives 0.480612/0.476616; removing chirp fitting gives 0.459307/0.377229; fixing slopes
to 0.02 gives 0.660241/0.533228; never refusing gives 0/0. The original noise/sign-count shortcut
gives 0/0. Development-selected finite grids reach 0.584719/0.519672 (216-policy morphology),
0.565033/0.459472 (1,620-policy sign-count), 0.440667/0.286497 (2,916-policy threshold), and
0.661183/0.556308 (324-policy five-slope lookup). These are finite-grid maxima, not exhaustive
algorithmic upper bounds.

## Relationship to nearby tasks

`Gravitation/PTAHellingsDowns` uses angular correlations across many pulsars; this task fits one
time-domain transient using coherence between two detectors. It also differs from photometric
microlensing tasks, which select lensing models from flux measurements rather than strain phase
evolution and detector localization.

## Rules and references

- Only edit `solution.py`; keep `infer_transient(problem, observe)`.
- Use deterministic CPU Python, NumPy and the standard library only.
- Do not read `verification/` or `frontier_eval/`, access the network, or create processes.
- `sle.contract_lint` is importable and free to call for shape checks.

The waveform model is a reduced-order analogue of compact-binary chirp searches and detector
glitch vetting. Scientific context: Abbott et al., *Phys. Rev. X* 6, 041015 (2016), DOI
`10.1103/PhysRevX.6.041015`; Allen et al., *Phys. Rev. D* 85, 122006 (2012), DOI
`10.1103/PhysRevD.85.122006`.
