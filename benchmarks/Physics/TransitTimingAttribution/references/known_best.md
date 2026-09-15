# TransitTimingAttribution reference record

This candidate is a deterministic reduced-order transit-timing laboratory. The public objective
uses development worlds only; held-out diagnostics are sealed confirmation evidence. Every result
below identifies the contract under which it was measured.

## Current reference

The current truth-blind reference fits planet, activity, and quadratic-clock families by known-noise
least squares and BIC. At each of five paid follow-ups it retains alternatives from all three
families and chooses the transit with greatest weighted predictive disagreement. Periodic fits are
then refined continuously, and a claim must also beat stationary-extra-component and phase-evolution
models. It never reads evaluator state or hidden labels.

On the current three-panel development contract its `combined_score` is
`0.5948352385872625`; its held-out robustness diagnostic is `0.28205283692823513`.
Development mechanism accuracy is 36/51, correct refusal is 18/18, FDR is 0, and mean normalized
design score is `0.415729`. This is a capable witness, not a score ceiling. Remaining headroom is in
mechanism separation, forecast accuracy, and query design.

The preceding public contract used fixed horizons and a four-query budget. Its final reference score
was `0.7546806731724828`; the Linux admission record is
`experiments/transit_timing_admission_2026-09-14.json`. Those values are historical and are not
presented as measurements of the current evaluator.

## Model calibration

Older DeepSeek and gpt-5.6-sol/high draws predate the current multi-panel worlds, variable horizons,
acquisition-design term, and cubic precision penalty. They remain protocol history only.

On clean Linux revision `270e7df2`, DeepSeek Flash and Pro each made two independent
selection-blind first proposals with proposal budget one and replicate identifiers 17 and 29.
Thinking was disabled by a repository-external localhost adapter that injected
`thinking.type=disabled`; both exact model IDs first returned visible smoke output. All four
proposals were valid. Flash scored `0` and `0.000862`; Pro scored `0.018452` and `0`. The maximum
is 3.10% of the `0.594835` reference. These are endpoint draws without server-side seed control,
not paired seeded samples or iterative improvement. The compact source-bound record is
`experiments/transit_timing_admission_2026-09-16.json`; prompts, generated programs, endpoints,
credentials, and local run directories are excluded.

No model output was used to select development seeds, the fixed-policy winner, score weights, or
reference constants.

## Baseline

`solution.py` purchases two legal follow-ups, cites both returned query IDs, and makes a deterministic
high-confidence planet claim. It never refuses. It is valid and scores exactly `0.0` because false
claims on unsupported worlds drive correct refusal to zero. This satisfies the confidently-wrong C15
baseline requirement rather than obtaining zero by blanket abstention.

## Ablation ladder

All current ablations reuse the reference fitting and evidence logic and change one declared
capability. Values below were replayed twice through the clean Linux trusted driver and bubblewrap;
each pair produced identical complete metrics.

| Candidate | Development | Held-out |
|---|---:|---:|
| Full active reference, five follow-ups | 0.594835 | 0.282053 |
| Limit reference to three follow-ups | 0.238873 | 0.390392 |
| Remove activity-family fits | 0.252756 | 0.111324 |
| Replace the forecast with zero | 0.526721 | 0.247541 |
| Remove out-of-family evidence requirement | 0.052701 | 0.046845 |

The development objective shows a 0.355962 contribution from the final two active measurements,
a 0.068114 contribution from fitted forecasting, a 0.342079 contribution from retaining the
activity family, and a 0.542135 contribution from explicit
out-of-family comparison. Held-out ablations are reported rather than used for selection; their
non-monotonic ordering is a limitation, not a tuning signal.

## Shortcut probes

The current C12 scan is development-only. It tests 8 schedules expressed as fractions of each
world's candidate-visible follow-up interval, 5 RMS limits, 4 supported-family BIC gaps, 4 residual
correlation limits, and 6 out-of-family BIC gaps: 3,840 fixed policies total. The scan uses the same
truth-blind fitting and evidence code as the reference but has no adaptive query selection.

The strongest configuration uses fractions `(0.00, 0.20, 0.45, 0.70, 1.00)`, RMS limit `1.3`,
supported-family gap `6.0`, correlation limit `0.5`, and out-of-family gap `6.0`. Its development
score is `0.4321528299414905`, or 72.65% of the `0.5948352385872625` reference, below the retained
80% guard (`0.47586819086981`). Its held-out diagnostic is `0.4286032064756491`; this larger sealed
value was not used to choose the configuration. The executable probe is
`verification/reference_no_active_design.py`.

The earlier A/B/C fixed-world grids reached 0.574956, 0.543759, and 0.515176 against the previous
0.754681 reference. They exposed the fixed-anchor overfitting problem but do not run on the current
variable-horizon contract and are no longer declared as current probes. Constant-family,
order-counter, never-refuse, malformed, and overspend candidates remain separate degenerate or
security controls rather than an exhaustive shortcut bound.

## Construction errors

- An early headline used `min(development, heldout)`, exposing sealed feedback to proposal selection.
  The public headline now uses development only while sealed failures remain a validity gate.
- Unsupported worlds initially had zero headline weight. The score now subtracts blanket-refusal
  reward and multiplies by correct-refusal rate and discovery precision.
- Fixed world order allowed a module counter to recover labels. Every world now resets candidate
  state, and each split has independently shuffled panels and a different composition.
- The first confidently-wrong baseline cited IDs before purchasing observations and was invalid.
  It now cites two actual measurements and remains valid at score zero.
- Fixed horizons let a few absolute anchors overfit the development worlds. The current contract
  varies initial length, noise, maximum follow-up, forecast horizon, periods, amplitudes, activity
  nuisance frequency, clock coefficients, and unsupported-family parameters across three panels.
- The score previously ignored acquisition quality. Correct supported claims now earn a normalized
  local-sensitivity design term, and repeated transit numbers cannot earn duplicate design credit.
- A maintainer changed seven reference constants and exceeded the older reference by 13%. The current
  scan includes the analogous evidence thresholds and normalized fixed schedules, and the strongest
  such policy is below the declared margin.

## Robustness

Development and held-out worlds are deterministic but use disjoint three-seed panels. Development
has 69 worlds (51 supported, 18 unsupported); held-out has 60 (42 supported, 18 unsupported).
Initial series length, noise, physical coefficients, available follow-up interval, and forecast
horizon vary by world. Exact instance order, counts, and seeds are not candidate contracts.

The evaluator publishes mechanism, design, FDR, refusal, and coverage numerators or denominators by
split. Mechanism denominators contain all supported worlds, including abstentions. Unsupported worlds
are included in refusal and FDR accounting. Search-visible output excludes held-out and robustness
metrics. Every world starts a fresh candidate session. Exceptions, malformed output, invented or
duplicate evidence, nonfinite values, invalid queries, and caught budget overspend fail closed with
the same metric-key shape.

The current reference transfers imperfectly: its held-out headline diagnostic is 0.282053, below the
fixed probe's 0.428603, even though its held-out mechanism and design diagnostics are stronger. This
is disclosed as residual generalization risk. Sealed values were not used to tune the evaluator,
reference, fixed-policy grid, or thresholds.

## Model-family citations and scope

- Agol et al. (2005), DOI `10.1111/j.1365-2966.2005.08922.x`, and Holman and Murray
  (2005), DOI `10.1126/science.1107822`, motivate transit-timing observations.
- Lithwick, Xie and Wu (2012), DOI `10.1088/0004-637X/761/2/122`, supports sinusoidal
  approximations near first-order resonance. It does not validate orbital or mass recovery from the
  benchmark's fitted modulation period.
- Oshagh et al. (2013), DOI `10.1051/0004-6361/201321309`, supports spot-induced timing
  bias. The secondary activity sinusoid is a phenomenological nuisance surrogate.
- Allan (1975), NBS Technical Note 669, describes linear frequency drift producing quadratic time
  deviation. Coefficients, noise, and budgets are procedural benchmark choices.

This benchmark evaluates attribution inside declared synthetic residual families. It is not a
photodynamical analysis or a real-observatory scheduling prescription.
