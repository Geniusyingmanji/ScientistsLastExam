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

Remaining work includes completed real-agent evaluation, richer causal/mechanistic claim
verification, stochastic biological variability, alternative mechanism families,
structural holdouts and calibrated Discovery Depth. Selective depletion and the
synthetic kinetics are idealizations, not evidence about real microorganisms.

## First GPT pilot on g450 — 2026-10-02

One bounded model episode ran on g450 using source commit `c16815e5`. Both the
requested model ID and the ID reported by the configured service were
`gpt-5.6-sol`; this records the service response, not independent model-identity
attestation. Configuration: chat wire, medium reasoning, nonstreaming,
8,000 maximum completion tokens, 180-second request timeout, at most 32 started
requests and 1,800 seconds overall. No automatic retries were permitted.

The simulated world and the isolated Python analysis capability ran on g450
(Python 3.8.10, NumPy 1.24.4, SciPy 1.10.1). The candidate-program smoke test
completed, and a separate analysis preflight confirmed NumPy availability and
the absence of the operator config and kernel file inside the sandbox. The
model did not invoke Python analysis in its recorded episode. HTTPS traveled
through an ephemeral loopback SSH forward to the operator's working HTTPS proxy;
credentials stayed in the trusted g450 process. No model call used the stale
Azure example endpoint discovered during preflight.

The episode ended **incomplete** after the twelfth started model request failed.
Eleven responses had returned; no `commit`, confirmation, or final `interpret`
occurred. The recorded transport error is a sanitized `RuntimeError`; this run
did not retain the underlying HTTP status, so its specific cause is unknown.
No retry or second model episode was started. Later code now retains allowlisted
failure stage/type/HTTP status, without URLs, headers or response error bodies.

Recorded exploration: 32 cultures created, 81 measurements, 11 selective
depletions, two temperature changes, and 133 broker requests, consuming 823 of
1,200 exploration units. One label containing a space was rejected and one
model response contained concatenated JSON objects. The model corrected both
after public feedback. The label character constraints are now explicit in the
public tool description. These interface changes were made **after** the run;
the frozen run archive remains unchanged.

The agent independently chose composition controls, channel-depletion tests,
fresh-culture repetitions, temperature controls and repeated sensor readings.
Three observed contrasts in its repetition panel were:

| Exploratory intervention at culture age 12 h | Endpoint at 24 h | Control mean | Treatment mean | Relative change |
| --- | --- | ---: | ---: | ---: |
| AB: remove peak-03 | A biomass | 1.272423 | 1.760744 | +38.38% |
| AC: remove peak-03 | C biomass | 0.582565 | 0.446751 | −23.31% |
| ABC: remove peak-02 | C biomass | 0.170654 | 0.302321 | +77.15% |

Biomass is mmol C/L. Each table mean is three independent sensor readings of
**one** fresh vessel per arm. These are exploratory repeats, not preregistered
confirmation or biological stochastic replicates. The contrasts motivate
chemical-mediated interaction hypotheses; they do not establish the complete
delayed feedback mechanism or a Discovery Depth score.

The eleven returned responses report 139,285 input and 8,960 output tokens
(148,245 known tokens). The failed request's usage is unknown, hence complete
episode usage is unknown. No configured prices were available for a dollar cost.
All 267 world-log events passed exact replay on the frozen g450 source/runtime.

Raw evidence is retained at `/var/tmp/sle-microecology-gpt-20261002/` on g450,
with a local operator copy and generated HTML/figures at
`/private/tmp/sle-microecology-gpt-result-20261002/`. The frozen code archive
SHA-256 is `49a904ee40bf89e0dd4b6c0f88a841709b0b401852a28c306500d462c2fa35da`.
The world, new driver, transport, post-test episode and CLI regression selection
passed 129 tests after the interface/diagnostic fixes. This is not a full-suite
claim and does not replace the incomplete scientific episode.
