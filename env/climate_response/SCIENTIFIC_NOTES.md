# Operator scientific notes

## Migration and scope

The legacy EnergyBalanceModel task supplied a two-layer equation and asked for
parameter recovery or refusal. This package reimplements the forward dynamics
without importing its evaluator, hides the menu and allows arbitrary quantitative
accounts. It adds selectable annual readout times. The apparatus remains a
controlled synthetic thermal model; its forcing knob is not a real climate
intervention and its parameters are not estimates of Earth's climate.

The hidden heat capacities are positive. Adjacent stores exchange heat
conservatively. Net radiation is q F − λ Ts − κ Ts³; κ is zero in both linear
strata, and positive in the state-dependent stratum. Temperature storage obeys
sum(C_i dT_i/dt) = net radiation. The positive cubic restoration is deliberately
different from the old quadratic drift: negative forcing in the legal range
cannot cause unbounded negative-temperature runaway. No hidden instrument drift
or stochastic weather is added; measurement noise is explicitly disclosed.

The two linear strata use exact float64 annual augmented matrix exponentials.
The nonlinear stratum uses fixed RK4 with 20 substeps/year, at most 3200 steps.
Capacity/exchange ranges follow the legacy calibrated synthetic ranges; cubic
strength is 0.04–0.10 W m⁻² K⁻³. These operator choices are not supplied priors.

## Ambiguity, tests and possible discoveries

A short low-amplitude response can fit a two-store effective model even when an
additional slow store or state-dependent restoration is present. Higher-amplitude
forcing and an amplitude-scaling prediction can reveal departure from a linear
account. Longer pulses and recovery windows can constrain slow memory. A model
may also discover local linearity or predict measured uptake from surface
warming over a specified condition range. These are possible outcomes, not
required golden answers.

Several hidden reservoirs can be observationally similar over 160 years.
Good predictions cannot establish a unique reservoir count, asymptotic climate
sensitivity or a real-world mechanism. Low-amplitude observations may leave
curvature unresolved. Stronger heating is not a universal discriminator between
all reservoir models; competing fitted accounts must make demonstrably distinct
predictions under the chosen test before a discrimination claim.

Independent numerical development uses preselected seeds 73101–73103 only;
future evaluation must exclude these exposed development instances. Checks and
raw numerical errors are retained in the private campaign development artifacts.
Tests cover zero input, alternating legal extrema, a pulse/recovery/negative
forcing sequence, half-step convergence, storage balance, linear superposition,
annual forcing left-limit convention and fresh reset invariance. These checks
bound implementation error on sampled cases, not every point in a continuum.

Readout noise is independent additive Gaussian with public standard deviations,
including repeated preparations. The clean deterministic trajectory is the
conditional mean; there is no clipping bias. Statistical inference on fresh
readouts does not include parameter estimation uncertainty automatically.

Random parameters and private instances prevent reuse of a single numeric answer,
but no structural holdout or contamination-resistance claim is established here.
Baseline shape tests do not measure headroom; no live model results are implied
by this package's tests or experimental status.
