# Operator scientific notes

## Replicated populations and changed scientific scope

The legacy OccupancyDetectionDesign task fixed 48 sites, a realized occupancy
vector, spatial locations and accessibility. It asked for a predefined effect
label, parameters or refusal. This new package reuses the occupancy/detection
idea, not its evaluator or grading rule. It instead provides independent
64-site populations at selected habitat strata, which are redrawn between
experiments. There is no persistence across calls, no spatial dependence and no
accessibility variable. It must not be described as an exact conversion of the
old fixed-site design or a spatial occupancy benchmark.

Within an experiment the latent Bernoulli occupancy of each site is drawn ONCE.
It persists across the 1–3 visits. Conditional on occupancy and habitat, visit
detections are independent. The generator has linear-logit occupancy,
quadratic-logit occupancy and a confounded regime where detection reliability
changes with habitat in the opposite direction to occupancy. These labels are
private sampling strata, not required discoveries. Rapid and intensive methods
have different unknown detection probabilities; neither is perfect.

For occupancy probability ψ and visit detection probabilities p_j, population
expectations are ψ p_1, ψ[1−product(1−p_j)], ψ product(p_j) for first, any and
all detections. Each output is the average of 64 independent binary indicators.
Thus its mean is exact and its variance is at most 1/(4×64). The channels share
sites and are correlated; treating them as independent understates uncertainty.
There is no additive Gaussian noise or clipping. Independent experiment keys
redraw occupancy AND detection, so replicate means target the same population
law rather than one fixed realized set of occupied sites.

For a normalized linear readout with weights w_j, a safe standard deviation
upper bound is sum(abs(w_j)*0.0625), by covariance Cauchy–Schwarz. This remains
valid with channel dependence. Chebyshev-based fresh-panel validation can use
that bound; it should not assume a Gaussian likelihood. Bounds are conservative
and a test may legitimately remain inconclusive with 4–16 replicate panels.

## What might be learned

One visit observes ψ p, leaving occupancy and detection confounded: ψ=.5,p=.6
and ψ=.75,p=.4 both yield .3 detections in expectation. Two visits with the same
method predict any-detection probabilities .42 and .48, respectively, and
all-detection probabilities .18 and .12. Repeated visits can therefore separate
these particular accounts if enough independent panels resolve the contrast.
Finite noisy panels can still leave them unresolved; this example is an analytic
design argument, not a model performance result.

Habitat-related nondetection may arise from occurrence or survey reliability.
Comparing visit multiplicity and methods can constrain those explanations.
Quadratic effective trends can be assessed through new habitat strata without
requiring the hidden generator's exact algebra. These are population
associations. Selecting a habitat is not an intervention on an individual site,
so habitat response alone does not establish a causal ecological mechanism.

The aggregate channels omit full individual histories, abundance, turnover,
spatial ecology, species interactions and heterogeneous site effects beyond
habitat. They cannot establish unique causes outside this synthetic model.
Perfect-detection and no-occupancy limiting fixtures validate implementation;
they are not actual generator strata supplied to the agent.

## Evidence and exposure

Development seeds 74101–74103 are exposed and must be excluded from prospective
model instances. Before collecting results, the private development plan fixed
27 exact-enumeration cases, a 512-panel Monte Carlo check and maximum call/work
limits. Raw panel fractions and diagnostics are private campaign artifacts.
These are implementation checks; no model evaluation, baseline headroom,
structural holdout or contamination-resistance result is implied.
