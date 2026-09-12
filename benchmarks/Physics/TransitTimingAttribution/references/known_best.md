# TransitTimingAttribution reference record

This candidate is a deterministic reduced-order transit-timing laboratory. The truth-blind
reference compares quadratic-clock and periodic models with least squares and BIC, refines the
period continuously, chooses its fourth follow-up by model disagreement, and refuses residual
histories inconsistent with the declared families.

## Current reference

The executable revision and complete metrics are recorded in
`experiments/transit_timing_review_replay_2026-09-11.json`. Every candidate below is evaluated
twice through the trusted Linux driver and bubblewrap; the two complete metric dictionaries must
match before the record is accepted.

| Candidate | Combined | Development | Held-out |
|---|---:|---:|---:|
| Truth-blind active reference | 0.430139 | 0.632413 | 0.430139 |
| Baseline, one measurement then refusal | 0.000000 | 0.000000 | 0.000000 |

`combined_score` is the lower of the development and held-out split scores. The reference recovers 16/23 supported mechanisms on development and 17/24 on held-out. Its false
discovery counts are 0/16 and 2/19; correct refusals are 10/10 and 9/10; supported coverage is
16/23 and 18/24. Headroom remains in continuous-period inference, model-discriminating schedules,
forecasting and rejection of both unmodelled processes. The reference is a capable witness, not a
ceiling.

## Model calibration

The committed DeepSeek Flash and Pro draws predate the current continuous-period worlds, second
unsupported family and precision-weighted score. They are retained as `historical_only` protocol
evidence and are not presented as performance on this revision. No new model generation was used
to select the current evaluator or thresholds.

## Baseline

`solution.py` buys one legal follow-up and declines every world. It is valid and scores exactly
0.000000 on both splits by construction. It tests the public callback without receiving discovery
credit.

## Ablation ladder

| Reference change | Combined | Development | Held-out |
|---|---:|---:|---:|
| Full active reference, four follow-ups | 0.430139 | 0.632413 | 0.430139 |
| Forecast fixed to zero | 0.359365 | 0.540351 | 0.359365 |
| Activity model removed | 0.268826 | 0.285567 | 0.268826 |
| Only three follow-ups | 0.232742 | 0.277997 | 0.232742 |
| Only two follow-ups | 0.241203 | 0.259425 | 0.241203 |
| Refusal disabled | 0.000000 | 0.000000 | 0.000000 |

The fourth follow-up adds 0.197398 combined, 0.354416 development and 0.197398 held-out over the three-follow-up
version. Removing model-disagreement evidence, a supported family, forecast skill or refusal all
cost score.

## Shortcut probes

The three grids use fixed four-transit schedules and coarse periodic fits. Selection uses only
development score; the sealed score and new combined score are read afterward. The schedule grid
also includes the 48/50-transit neighbours of the review-identified late follow-up.

| Family | Policies | Combined | Development | Held-out |
|---|---:|---:|---:|
| A: RMS, BIC-gap and residual-correlation thresholds | 1,000 | 0.301806 | 0.574956 | 0.301806 |
| B: RMS and residual correlation, no BIC gate | 200 | 0.159146 | 0.543759 | 0.159146 |
| C: BIC gap and residual correlation, no RMS gate | 200 | 0.322946 | 0.515176 | 0.322946 |
| Reference | - | 0.430139 | 0.632413 | 0.430139 |

`verification/calibrate.py` caches the repeated fits, selects each family on development, then
checks each selected witness with the full in-process evaluator. The strongest family-A witness is
also replayed twice through the external sandbox by `verification/replay_probes.py`. Constant
planet/activity/clock claims, the old call-order counter and reference fitting with refusal disabled
all score exactly zero on both splits. These are measured finite families rather than a universal
shortcut bound.

### Executable shortcut contract (2026-09-12)

The machine-readable guard now includes all three fixed schedule families, alongside the zero
baseline. Its reference, 20% relative margin, score tolerance, score and query budget are unchanged.
Each `verification/shortcut_family_*.py` is a standalone public-input candidate; none imports the
offline calibration script or private evaluator.

Family A is the byte-identical candidate formed by the existing external replay script from
`reference_solver.py` and its `FIXED_SCHEDULE` string. The committed materials did not preserve
winner parameter tuples for B/C. Their candidates were newly reconstructed on source
`00cdb02a02e451259af4abe5ca0da66445773011` from the existing development-only finite grid; this is
new reconstruction evidence, not recovery of the original B/C programs or measurements.

| Family | Schedule | RMS limit | BIC-gap limit | Correlation limit | Grid size |
|---|---|---:|---:|---:|---:|
| A | `(13, 26, 43, 59)` | 1.2 | 3.0 | 0.8 | 1,000 |
| B | `(16, 32, 48, 59)` | 1.0 | 0.0 | 0.35 | 200 |
| C | `(16, 32, 48, 59)` | 99.0 | 6.0 | 0.5 | 200 |

All 1,400 policies completed the original parser and query-validity checks on all 33 development
worlds. Selection maximized only the development score in the original `itertools.product`
order; a strict improvement replaces the incumbent, so ties retain the first policy. Family C
had two equal development maxima; the first was retained. The sealed-world accessor was blocked
and called zero times. All candidate bytes and parameters were frozen before full sandbox replay.
The original inactive limits `gap=0.0` and `RMS=99.0`, unrefined diagnostics, strict threshold
comparisons, budget slicing and confidence `0.8` are preserved. This repair does not upgrade the
historical model records or complete scientific admission.

## Construction errors

- The first score ignored unsupported claims in the headline. Refusal and precision now gate the
  score, so blanket refusal and never refusing both earn zero.
- Fixed world order exposed the label sequence to a module counter. Split-specific deterministic
  shuffling, unequal split sizes and a session reset at every world boundary remove that channel.
- A noise-seeding edit referred to a missing world key and made every measuring candidate invalid.
  Every world now has a private seed, and follow-up noise is keyed by world, coordinate and repeat.
- One unsupported mixture and a few discrete period constants let threshold and lookup grids match
  the reference. Periods are now continuous, two physically different unsupported families are
  represented, and both refusal accuracy and squared discovery precision gate the headline.
- Rebase dropped the generated inventory row. `TASKS.md` is regenerated from the current registry
  after rebasing rather than edited manually.

## Robustness

Successful and invalid evaluations publish identical metric-key sets, including `heldout_*`
aliases. Malformed output, exceptions, invented or duplicate evidence, nonfinite values and caught
budget overspend fail closed. Per-world coordinate seeding is invariant to query order, while
different worlds receive different noise. The baseline, reference and selected probes are replayed
twice and the task-specific contribution gate is run on the clean Linux revision. Candidate status
remains unchanged; external astronomy review and independent photodynamical replication remain
pending.

Scientific grounding: Agol et al. (DOI `10.1111/j.1365-2966.2005.08922.x`) and Holman and Murray
(DOI `10.1126/science.1107822`).
