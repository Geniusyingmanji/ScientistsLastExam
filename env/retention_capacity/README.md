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
No model driver or shared registration is supplied yet. Prospective scoring and
API admission remain pending; old worlds, cohorts and scores are unchanged.

A frozen exposed development precheck covered 48 trajectories, four injection
levels and three flow designs across four instances. Four tests passed: two
independent fixed-step RK4 checks against the adaptive solver, the analytic
small-load limit, invariants, public validation/noise, and a specified-rival
witness. RK4 shares the derivative but independently implements integration.
Private numerical evidence retains all prediction arrays. This is feasibility
checking, **not a high-difficulty result**. Before model trials: bounded
public-data baseline, explicitly informed family-fit reference with recorded
fits/predictions, Linux sandbox admission, driver and frozen new instances.
