# Nonlinear retention capacity — unregistered prototype

This is a synthetic nonlinear revision of retention transport. The additional
public control is injected mass (`load`); the observed channel is cumulative
recovered mass divided by that load. Each call starts a fresh preparation.
The scientific question is whether a response calibrated at one injection level
transfers to other levels and interrupted flow histories.

The operator alternatives are storage-capacity saturation versus outlet-flux
saturation, each with reversible exchange. Both approach the same linear
mobile/bound/recovered equations at infinitesimal load. This asymptotic agreement
is not an exact ambiguity at the minimum legal load. A specified rival pair
separates under larger injections; a fitted rival family has **not** yet been
ruled out. Zero-flow readouts remain uninformative. The task asks for predictions
and scoped observable effects, not the author's internal label.

The candidate sees load/time/flow controls, units, noise and reset semantics via
`describe()`. It does not see sampled mechanism, coefficients, seed or targets.
Noise is independent additive readout noise with SD0.002 and no clipping.
An explicit model driver is available as described below; shared registration
remains disabled. Old worlds, cohorts and scores are unchanged.

A frozen exposed development precheck covered 48 trajectories, four injection
levels and three flow designs across four instances. Four tests passed: two
independent fixed-step RK4 checks against the adaptive solver, the analytic
small-load limit, invariants, public validation/noise, and a specified-rival
witness. RK4 shares the derivative but independently implements integration.
Private numerical evidence retains all prediction arrays. This is feasibility
checking, **not a high-difficulty result**. Before model trials: bounded
public-data baseline, explicitly informed family-fit reference with recorded
fits/predictions, Linux sandbox admission, driver and frozen new instances.

Admission update: an explicitly informed two-family fit used six training
experiments (132 units), four starts and at most 3000 forward calls per exposed
instance. It used 1080–1536 calls; maximum held-out RMSE was0.0009751 against a
predeclared0.02 gate. All observations, coefficients and prediction arrays are
privately archived and independently checked (same-family/provisional). The
empirical nearest-record baseline mean RMSE was0.093–0.116. This is feasibility,
not model difficulty. Local admission:5passed/1Linuxskip; Linux:6passed14.78s,
including real isolated analysis/prediction. Explicit `model_driver.py` requires
`capacity-batch-score-1.0`; shared registration remains disabled. Weights are
50% condition prediction,30% intervention prediction,20% effect claims. Load is
part of causal contrast identity; assigned zero prefixes earn no prediction
credit. Candidate contracts disclose these rules before calls.

`order_task.py` adds an unregistered prospective task on this same world. It
reverses three equal-duration flow segments, with an optional identical tail,
while matching load and final time. Any memoryless clock based on an integral
of a function of flow gives identical final predictions in the two arms.
Hidden-state dynamics can give different responses; linear memory can do so
too, so an order effect does not identify saturation or a unique mechanism.
The candidate predicts both absolute fractions. A signed contrast is derived
from those same predictions, preventing contradictory separate submissions.
The task reports exponential RMSE scores with public scales0.1 (absolute)
and0.05 (contrast), and their equally weighted average. It has no claim score.
Common-data baselines, explicit driver integration and new-instance API
confirmation are still pending. The frozen batch scorer above is unchanged.
