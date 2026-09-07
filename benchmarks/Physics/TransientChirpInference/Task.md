# TransientChirpInference

## Scientific problem

Use a finite two-detector strain-observation budget to characterize a transient signal. Decide
whether the data support a coherent chirp, a coherent narrow-band line, or a detector-localized
glitch; estimate the chirp frequency slope, event time, and signal amplitude. Abstain when the
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
`frequency_slope` in `[0, 0.05]`, finite `event_time` in `[0, 18]`, and finite `amplitude` in
`[0, 1]`. Malformed output or callback violations score invalid instead of crashing.

## Scoring

Supported worlds score model identification (0.55), continuous parameter recovery (0.20),
amplitude recovery (0.15), and confidence (0.10). Ambiguous worlds score only for refusal.
`combined_score` is development mechanism recovery normalized so blanket abstention is exactly
zero; model accuracy, false discovery, refusal, feasibility, budget, and held-out transfer remain
separate axes. Held-out worlds and truth are evaluator-only.

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
