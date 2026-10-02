# Operator scientific notes

These notes disclose private construction and must not enter candidate context.
The apparatus is registered as the ninth experimental world. Registration adds
no mechanism label to a prediction score and does not change historical results.

## Construction and distinct physics

For planar position **r**, velocity **v**, radius r, and fixed ε=0.25 L,

\[
\dot{\mathbf r}=\mathbf v,\qquad
\dot{\mathbf v}=-\mu\frac{\mathbf r}
 {(r^2+\epsilon^2)^{(p+1)/2}}-\gamma\mathbf v.
\]

The test particle has unit mass; it does not move the center or interact with
other experiments. At large radius the attractive acceleration magnitude tends
to μ/rᵖ. The coefficient μ has units L^(p+1)/T²; numerical parameters use the
fixed apparatus units. It is not one universal physical gravitational constant
shared between exponents.

Three operator strata share exactly one public description:

| Private stratum | Construction |
|---|---|
| `softened_inverse_square` | p=2, γ=0 |
| `softened_alternative_power` | p sampled in [1.35,1.65] or [2.35,2.65], γ=0 |
| `softened_inverse_square_drag` | p=2, γ sampled in [0.045,0.10] T⁻¹ |

All strata sample μ in [0.8,1.2]. A stable hash separates structure, continuous
parameters and panel random streams. Each instance fixes its parameters. There
is no switch controlled by elapsed experiment number or input spelling.

This is a restricted family of smooth central attractions with optional isotropic
linear drag. Changing p remains variation within one parametric mathematical
family. Adding drag changes velocity dependence, time-reversal behavior and
conservation conditions. Neither fact makes this an unrestricted search over
physical mechanisms. The softened p=2 model is Newton-like far from the center;
it is not exact point-mass Newtonian gravity near the center. Softening itself can
produce non-Keplerian orbit geometry, so precession alone cannot establish p≠2.
There are no relativistic, many-body, tidal, stochastic, or moving-center effects.

## Potential and conservation conditions

Write q=r²+ε². Integrating `dU/dr = μ r q^(-(p+1)/2)` gives

\[
U_p(r)=-\frac{\mu}{p-1}(r^2+\epsilon^2)^{(1-p)/2},\quad p\ne1.
\]

For p>1 this convention sets U(∞)=0. At p=1 the primitive is

\[
U_1(r)=\frac{\mu}{2}\log\frac{r^2+\epsilon^2}{L_0^2},\qquad L_0=1\,L.
\]

The logarithmic potential cannot also be zero at infinity. As p→1 the p≠1
expression contains a divergent additive constant; *potential differences*
converge to those of U₁. World generation avoids p=1; the kernel supports this
analytic limit for an explicit numerical test. Force is the negative gradient
of this potential, verified by independent centered finite differences. μ=0 is
also supported only as a test limit, not sampled as a world instance.

The zero-at-infinity expression can lose precision when subtracting potentials
extremely close to p=1 because its additive constant is large. The independent
review observed this cancellation at the next representable value above 1.
Generated exponents, force evolution and the exact p=1 branch are unaffected;
the operator helper is not a stable potential-difference implementation for
arbitrarily near-1 exponents.

Let `E=|v|²/2+U(r)` and `h=x*vy-y*vx`. On any interval without an impulse,

\[
\dot E=-\gamma|\mathbf v|^2,\qquad
\dot h=-\gamma h.
\]

Consequently E and h are conserved when γ=0. When γ>0, h follows an exponential
law, and E changes by the integrated dissipated work. Angular momentum zero
remains zero even with drag. At an impulse **d** applied to pre-impulse velocity
**v⁻**,

\[
\Delta E=\mathbf v^-\!\cdot\mathbf d+|\mathbf d|^2/2,\qquad
\Delta h=x d_y-y d_x.
\]

These jumps are not dissipation or solver errors. Observation noise also makes
raw measured invariants fluctuate; testing exact equalities on noisy samples is
inappropriate. Softening alone does not break conservation or time reversal.

An exact conservative circle at radius R has angular frequency
`ω²=μ/(R²+ε²)^((p+1)/2)`. Choosing μ separately for different p so this frequency
matches produces the same entire circular trajectory. Thus infinitely precise
observations on that circle do not identify the radial law away from R. The
matched-law development diagnostic holds this frequency fixed, then changes
initial radius or applies a radial component of impulse. It shows separation of
those specified alternatives, not unique identification among all possible laws.

## Finite domain and numerical work

Initial radius is 0.75–2 L, initial speed ≤1.5 L/T, total impulse magnitude ≤0.8
L/T, and the horizon is at most 12 T. These are input bounds, not an assertion
that every particle remains on a bound orbit. Outward trajectories are integrated
for the same finite horizon; no escape classifier changes observations.

Softening bounds the force and its derivatives at r=0. For sampled p>1, the
deepest allowed potential magnitude is below 7.2 L²/T². Since drag cannot increase
energy and each impulse increases `sqrt(2*(E-U_min))` by at most its magnitude,
all generated clean trajectories have speed below
`sqrt(1.5² + 2*7.2) + 0.8 < 4.9 L/T`. Thus radius stays below 61 L over 12 T.
These loose analytic bounds are not clipping rules. Gaussian measurement noise
has unbounded support and need not satisfy them.

The production Cartesian integrator uses DOP853, relative tolerance `2e-10`,
absolute tolerance `2e-12`, maximum step `0.08 T`, and a hard budget of 60,000
right-hand-side evaluations across all event segments. Sampling uses dense
output; the observation grid never inserts integration boundaries. Only impulses
split the trajectory. The event state is updated before copying same-time
observations. Nonfinite outputs, unsuccessful solves and exceeded numerical work
raise bounded errors instead of returning a partial or invented trajectory.
There is no automatic retry with different tolerances or a substitute model.

SciPy documents DOP853 as an eighth-order explicit Runge–Kutta method with
seventh-order dense interpolation. Its tolerances control local estimates, so we
also check global trajectory errors independently. See the primary
[SciPy solve_ivp documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).

The independent reference evolves `(r, theta, radial_velocity, angular_momentum,
drag_work)` using Radau, independently written polar equations and Cartesian
conversion at impulses. It never calls the production derivative, potential, or
trajectory helper. It applies only to test trajectories away from r=0. Analytic
free motion and damped free motion, analytic circles, radial passages through the
softened center, energy/work balance, impulse jumps, rotation/reflection symmetry,
and conservative time reversal provide complementary tests. Work-limit failure
and sample-grid invariance are engineering checks, not scientific evidence.

## Development interpretation

The four reserved seeds are for reproducibility and diagnostics only. Their
sampled strata are two alternative-power and two drag instances. The missing
inverse-square stratum and the lower-power range are covered by explicit-parameter
unit tests and matched-law diagnostics; there is no claim that these four seeds
are representative. No API calls, candidate model runs, official holdout scores,
or target selection use the development report.

The empirical baseline is limited by nearest-trajectory transfer and may not
improve monotonically as records are added. An inferred law can be much better;
weak baseline failure is not evidence of hard discovery. The report keeps all
0/4/12-record comparisons, numerical reference errors and runtimes rather than
selecting a favorable count. It also records exact circular ambiguity and the
small short-arc drag contrast. Any future task should ask for prospective
counterexamples, transfer across radii and controls, and a scoped account of
remaining alternatives, with independently reviewed evidence requirements.

## Claim integration and evidence scope

The public pilot requires a selected claim readout at least 0.25 T after reset
and after every impulse at or before that readout. A lag of exactly 0.25 T is
eligible. Comparisons must use matched physical observation times in both
experiments. The apparatus still permits earlier observations and exact-event
measurements; the restriction concerns claim verification. This fixed lag is a
resolution policy, not a timescale fitted to private parameters or a guarantee
of practical detectability. Assigned resets and instantaneous jumps alone do not
establish discovery, and eligibility does not replace semantic review of known
symmetries, causal isolation, or remaining alternatives.

The pre-integration independent review supported the numerical construction and
the scoped distinguishability/nonidentifiability claims (A=yes, B=yes). Its
public-research verdict was C=partial because shared eligibility was not yet
installed. The integration addresses that implementation requirement; it does
not constitute a new independent review or promote the earlier verdict. The
review remains same-family/provisional, with integrity unavailable and the
canonical evidence helper unresolved; its precheck establishes only artifact
existence and hashes.

Calibration summaries and private artifact locations are recorded in
[development/README.md](development/README.md). Raw trajectories, private
parameters and diagnostic targets remain in the central private store. Neither
the original calibration nor the review demonstrates candidate discovery,
contamination resistance, arbitrary-law uniqueness or calibrated difficulty.
