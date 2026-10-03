# Evidence and implementation lineage in the five heat episodes

The five archived public packets contain coefficient estimation, qualitative
contrasts and some fixed-coefficient prediction checks. They also show why a
reported transfer residual must be tied to the fit data and the exact numerical
implementation that produced it.

This fresh review used partial public exports, inert candidate source and saved
numbers. It performed no fitting, simulation, candidate execution or private
score inspection. Findings remain same-family, provisional and pending external
review; integrity audit unavailable. A missing final artifact remains missing.
No original score, failure or depth annotation was changed.

| Public packet | Evidence present | Main limitation |
|---|---|---|
| `review-core-006` | Qualitative prior expectations and measured contrasts | The only attempted fit times out; final heuristic coefficients have no completed fitted-model validation in the export |
| `review-core-007` | Earlier fitted coefficients are retained for later heater/mixed-condition assessment | Uniform/piecewise comparison uses unequal sampling; later stress assessment times out; final solver changes |
| `review-core-008` | Fitted coefficients precede later observations | Quantitative transfer/stress analysis fails; no fitted piecewise rival and a changed final grid |
| `review-core-009` | In-sample model comparison and a final vector matching the later fit | The later fit uses all 32 records before reporting subgroup “transfer” errors; an effective diffusivity falls outside the supplied range |
| `review-core-010` | One completed uniform-diffusion fit, followed by note-level estimates | Flow estimate changes without a successful intervening fit; no bound final predictor is present |

In packet 009, round-7 code selects all 32 observations, fits them, then reports
approximately 0.12038 and 0.12008 °C RMSE for groups named transfer and checks.
These are post-refit subgroup residuals. They cannot establish prospective
performance of the earlier model. Its final right diffusivity is approximately
0.0059058 m²/s, below the public lower bound of 0.006. This is a discrepancy in
the candidate's effective-fit parameter; it is not evidence that the hidden
world violates its public range.

Packet 007 does preserve an earlier coefficient set while checking later
conditions. Its reported 0.04684 °C aggregate covers all 16 then-available
records, so it is not solely a new-target error. Its uniform-versus-piecewise
comparison uses different time sampling and cannot be read as a clean
common-observation ranking. Those qualifications preserve the useful
fixed-coefficient evidence without inflating its scope.

Parameter identity alone is insufficient. The successfully assessed solver in
007 uses a 101-point upwind discretization; the final predictor uses a 401-point
centered discretization with rounded same coefficients. Packet 008 also changes
its numerical grid after fitting. These source differences are not independent
measurements of final error. A future snapshot should bind code and parameters,
and later implementation changes should be recorded as new versions.

Several rival arguments need better controls. Packet 006 shifts a heater while
keeping the probe fixed, thereby changing heater–probe distance; that contrast
alone does not isolate material asymmetry. Packet 008 invokes lack of a
temperature discontinuity, although the supplied two-region family already
requires temperature continuity at an interface. Superposition likewise follows
both supplied linear families. These observations can be useful, but do not by
themselves discriminate the proposed alternatives.

All five problems supply the PDE, source shape, signed flow, boundary conditions
and uniform/two-region material family; see [PUBLIC_PRIORS.md](../PUBLIC_PRIORS.md).
Discovery claims concern instance-level identification and predictive adequacy
within those assumptions. A failed numerical analysis or missing final code is
not automatically a failed scientific mechanism.

The structured private review preserves 391 checked evidence pointers and
92 exact extracts across all five unchanged inputs. Key anchors include packet
007 rounds 2 and 4, packet 008 round 3 and failed rounds 6/12, packet 009 round 7,
and packet 010's null `/final_candidate` plus declared gaps. All ordering claims
refer to archived report rounds rather than authenticated replay chronology.
Saved-number contrasts do not establish fresh-replicate interval coverage.
