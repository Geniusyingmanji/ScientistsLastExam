# Construction validation — 2026-10-01

This records an operator-written simulator/verification demonstration, not a model
evaluation or independent scientific review. No model API was called.

## Executed checks

- macOS, Python 3.14.7, NumPy 2.5.3, SciPy 1.18.1; Matplotlib 3.11.2 for plots.
- `test_microecology_world.py`, `test_scientific_episode.py`,
  `test_evidence_episode.py`, `test_posttest_episode.py`: **117 passed**, plus
  14 subtests. This includes 33 new world tests.
- `test_posttest_cli.py`, `test_readme_inventory_counts.py`: **26 passed**, plus
  5 subtests; disjoint files from the preceding run.
- Total: **143 passed**, zero skipped in these selected files; subtests are not
  added to the test total. This is not the full repository suite.
- ODE solutions were compared with independently configured DOP853 and Radau
  integrators on three parameter instances; material accounting was checked
  through growth, filtering, transfers, feeding and fraction depletion.
- The JSON action file ran and replayed exactly (17 events).
- The JSONL CLI returned three parseable lines for description, inventory reply
  and the session summary.
- The complete seed-7 demo ran and replayed exactly (1,225 events). Its plotted
  public observations were visually inspected.
- Linux `--program` execution uses the existing CandidateProxy path, but its real
  Linux sandbox execution was **not run in this macOS construction check**.

## Frozen-prediction demonstration

The public-action policy screened all three anonymous fractions and selected
`peak-01` from the C biomass response at 24 h. All preparations received the same
0.02 mmol C nutrient pulses at 16 and 20 h. The selected fraction was depleted
at 8, 12, 16 and 20 h. Eight new sensor-noise replicates per arm checked each claim.

| Declared numerical check | Mean treatment − control (mmol C/L) | Result |
| --- | ---: | --- |
| C response to selected fraction removal | 0.542677 | prediction supported |
| A response to the same removal | 0.861574 | prediction supported |
| A response with C absent | -0.000247 | within the declared near-zero interval |
| Deliberately reversed C prediction | 0.541897 | prediction refuted |

These results support the declared contrasts in this synthetic instance. The
missing-C control checks one implication of mediation, not uniqueness of the
entire feedback mechanism. Interval checking does not validate the natural-language
interpretation. No Discovery Depth score is inferred.

The run used 841 exploration units, 1,760 reserved-confirmation units and 289
broker requests. Reported net material-accounting residual was 0.0 mmol C at
machine precision. The checks use tolerances; exact mathematical zero is not a
general numerical guarantee.

Construction smoke runs with seeds 0 and 42 selected `peak-01` and `peak-02`,
respectively. In both runs the three numerical hypotheses were supported and the
reversed-direction control was refuted. These are development instances, not a
sealed structural generalization study.

## Evidence bindings

The private operator report contains the full recipe, seven source-file digests,
runtime versions, observations and events. It is retained outside Git. Public
report and demonstration data are also retained with the generated result page.

- `public-report.json` and `operator-report.json` retain their own content digests.
- Exact replay checks the matching source/runtime and reruns the recorded JSON
  actions, including fresh confirmation, before comparing the complete report.
- JUnit was saved for the 117-test run. The separate 26-test run is recorded by
  its terminal result; this document does not imply an additional JUnit artifact.

Remaining work includes real agent evaluation, richer causal/mechanistic claim
verification, stochastic biological variability, alternative mechanism families,
structural holdouts and calibrated Discovery Depth. Selective depletion and the
synthetic kinetics are idealizations, not evidence about real microorganisms.
