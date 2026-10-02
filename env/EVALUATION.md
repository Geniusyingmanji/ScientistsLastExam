# Pilot evaluation protocol 0.4

The frozen `core-c2` results used 0.3. Version 0.4 adds eligibility for the new
material-history world; existing-world formulas, weights and scales are unchanged.
The extension cohort also uses clearer analysis-schema/error feedback and a
different request budget. It is reported separately, not pooled with `core-c2`.

This pilot measures experimental investigation and frozen quantitative prediction
in synthetic worlds. It does not match an agent's prose to a golden mechanism.
The declared task is open; predictions and self-selected effects are checked by
running the world under the requested conditions.

## Frozen prediction score

For each private experiment, divide each prediction error by its world's fixed
public channel scale and take RMSE across channels and observation rows. Omit the
initial row when its coordinate is zero and later observations exist. Transform
error `e` to `100 exp(-e / 0.1)`, then average experiments equally. The nonlinear
transformation and channel scales are design choices; raw errors remain primary
diagnostics and must be reported with the score.

The SLE-Pilot Score is:

- 50% predictions for unseen legal conditions;
- 30% predictions under unseen legal interventions;
- 20% verification of up to three agent-chosen quantitative contrasts.

The predictor is executable Python, frozen before test specifications or outcomes
are shown. Each test uses a fresh sandbox with NumPy/SciPy, no world callback,
network, prior test state or operator files. Its code must contain its fitted
constants/data. Correct mechanism names are neither necessary nor sufficient.

The reference baseline receives exactly the agent's public exploration records.
Baselines differ in sophistication across families, so their scores are diagnostic
comparators rather than a uniform intelligence scale. Report both prediction
error and improvement/deterioration relative to the same-data baseline.

## Agent-chosen contrasts

A contrast specifies control and treatment experiments, a post-initial readout,
evidence observation IDs, scope and a central 90% interval for the mean of eight
fresh treatment-minus-control measurements. Fresh sensor-noise draws are separate
from exploration. These worlds have deterministic latent dynamics; replicas do
not represent independent stochastic biological or physical systems.

The interval score is width plus 20 times distance outside the interval. The
slot score is `100 exp(-interval_score / (0.1 * channel_scale))`. Average over
exactly three slots, giving zero to omitted or duplicate slots. Direction-reversed
pairs and equivalent readouts with padded time grids are duplicates. More general
semantic duplication, relevance of evidence citations and scientific novelty
require review. Wide uninformative intervals are penalized rather than passed
as discoveries.

Public-only eligibility excludes immediate additions/removals and directly
clamped observables. Time-dependent paired readouts use a matched time and a
minimum evolution lag after preparation and every preceding event: microecology
1 h, oscillator 0.25 s, reaction 1 s, heat 0.5 s and gene regulation 0.5 h. These
are declared pilot eligibility resolutions, not estimated physical constants.
Ising temperature is a control, so between-temperature contrasts remain legal.
Material response claims require matched times at least 0.5 s after preparation.
Its continuous field-ramp knots do not directly assign a response, so they do not
restart this lag. Preparation/reset history occurs before the recorded timeline.
The checks require no hidden mechanism and do not establish novelty; other
analytically predetermined or semantically duplicate effects still need review.

This amendment was motivated by development-a1, before any formal requests:
three reaction claims repeated the advertised instantaneous addition rule.
Development-a1 retains its original protocol-0.2 scores and is not pooled with
the amended formal cohort. Prediction formulas, weights and scales did not change.

For an operational *verified nonzero effect*, the fresh mean must lie in the
submitted interval, its absolute value must exceed three estimated standard
errors, and the interval width must be at most 0.2 times the channel scale.
These are pilot thresholds, not a calibrated universal significance test. A null
effect can receive an interval score but is not counted as a nonzero discovery.
Three checked claims do not automatically constitute three independent mechanisms.

## Denominators and uncertainty

- **Model completion:** valid frozen submission and valid predictions for every
  test experiment, divided by all ended runs with healthy infrastructure.
- **Verified effect rate:** at least one verified nonzero contrast, divided by
  all ended runs with healthy infrastructure. This is not a mechanism-discovery rate.
- **End-to-end completion:** completed runs divided by all started/dispatched
  runs, including infrastructure failures and runs still in progress.

Healthy runs that exhaust model/experiment/analysis/time budgets, submit invalid
JSON/code or fail their predictor receive zero overall score. API/network/wire,
sandbox initialization, dispatch and operator failures are separately identified
and omitted only from the model-only denominator. They remain in end-to-end
accounting. Never select successful episodes before averaging.

Average scores within each environment, then average environments equally.
Do not present a full aggregate if an intended environment has no healthy result.
The report includes Wilson intervals for proportions and a stratified bootstrap
interval for the macro score when each environment has at least two results.
Five instances per environment produce a pilot estimate with substantial
uncertainty, not a stable universal model ranking.

## Discovery depth: separate evidence audit

Use the following evidence levels as an auditable description, not an automatic
score inferred from the number of API calls, model confidence or hidden labels:

| Level | Evidence that must be present |
|---|---|
| D0 | Observations or proposed hypotheses without a tested regularity |
| D1 | Reproducible quantitative regularity with stated conditions and uncertainty |
| D2 | Controlled intervention supports a scoped effect; alternatives/confounds identified |
| D3 | An explicit quantitative explanatory model survives a prospective test that discriminates meaningful alternatives |
| D4 | The same explanation transfers to a genuinely changed regime without refitting to that target; failures and boundaries are characterized |

Assign the highest level for which the actual trace supplies all required
evidence, cite observation IDs and the timing of predictions, and record missing
evidence. A correct scalar contrast alone supports at most a scoped effect;
accurate black-box interpolation alone does not establish D3 or D4. Recovery of
the implementation is not required, and equally predictive mechanisms can remain
unidentifiable. Human/agent reviews must report reviewer provenance and agreement
limits; automated numerical checks never certify mechanism depth.

## Frozen execution and accounting

Default core limits are 16 model requests, 14 research turns, at most 32 experiments
and 800 family-defined experimental units, 60 active analysis seconds, and 900
episode wall seconds. The runner reserves 90 seconds for verification and requires
earlier submission when time is short. Each private prediction has at most 15
seconds and is additionally bounded by remaining episode time. Trusted simulator
and reporting work is bounded but can cause a small wall overrun at an operation
boundary. Model idle time does not consume the active analysis allowance.

Source hash, generated panel hashes, model decoding, task profile, world/panel
seeds and confirmation streams are committed in the private cohort manifest.
Each worker checks source/decoding and verifies panel commitments before calling
the API. The shared SQLite ledger counts each admitted request before network
I/O. No retries, quota resets or model substitution are hidden in the runner.
Provider-reported model identifiers and all known token usage are retained;
missing usage is unknown, not zero. Billing is not inferred from public list prices.

## Limits to claims about discovery and contamination

Known physics families help make worlds interpretable and verifiable. They also
make strong equation-based baselines possible. Random parameters, topology and
channel permutations reduce exact-instance memorization but do not prove that a
model could not exploit familiar family structure. The core microecology adapter
still uses one qualitative mechanism family. Separate audits should test new
structures, nuisance transformations, no-experiment controls, mechanism-class
changes and prospective transfer before making broad contamination or discovery
claims. Scaling experiments come after these measurement properties are stable.

## Reduced presentation and prospective tasks

An opt-in `apparatus_only` presentation is available for the mechanical and
binary-ensemble apparatuses. It preserves operations, units, calibration, noise,
budgets and scoring while withholding equations, parameter ranges and family
labels. It is a prompt-information intervention, not a new hidden model family
or proof against memorization. Existing baselines retain family knowledge.
Both public problem and system text are projected and hashed before any request;
the identical projected problem reaches isolated analysis.

The separate prospective protocol in [PROSPECTIVE.md](PROSPECTIVE.md) seals
executable rival predictions and a readout before collecting new measurements.
It distinguishes numerical equivalence, rejection, separation and revision,
without equating any of those checks to unique mechanism identification.
