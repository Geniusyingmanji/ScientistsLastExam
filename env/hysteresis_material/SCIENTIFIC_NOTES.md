# Trusted operator scientific notes — do not expose to discovery agents

## Construction and physical interpretation

The identical instrument interface hides two different scalar dissipative
mechanisms. A private, domain-separated SHA-256 draw from the world seed chooses
the family; the family is available only as `World(seed)._family`, with values
`relaxation` and `bistable`. No sampled parameter, seed, or family identifier
appears in the public description, returned observation, schema, or panels.
Both families use exactly the same time-parameter range, so the family label is
not encoded as disjoint fast/slow parameter bins.

Write controlled field as H, latent response as x and observed ideal response as
y = gain*x + offset. The common observation gain is in [0.85, 1.15], offset in
[−0.04, 0.04], and mobility time tau in [5, 14] s. These are **private operator
ranges**, not a public model menu.

* **Relaxation:** dx/dt = (tanh(c*H+b) − x)/tau, with c in [1, 1.8] and b in
  [−0.06, 0.06]. This is Debye-type relaxation of a saturating mean response. It
  also follows from independent two-state elements with heat-bath transition
  rates summing to 1/tau and mean equilibrium tanh(c*H+b). There is one stable
  response at every held field. Finite sweep rates create loops; a sufficiently
  slow sweep follows the single-valued equilibrium curve and its loop area
  tends to zero. At held H, the squared displacement from equilibrium is a
  Lyapunov function. The deterministic mean-field limit omits process noise.
* **Bistable:** tau*dx/dt = a*x − x^3 + c*H + b, with a in [0.75, 1.15], c in
  [0.6, 0.9], b in [−0.025, 0.025]. This is overdamped relaxation in
  V(x,H) = x^4/4 − a*x^2/2 − (c*H+b)*x. At fixed H,
  dV/dt = −(dV/dx)^2/tau ≤ 0. The small tilt preserves two stable wells at zero
  field; large signed fields erase the branch. The quasistatic loop remains
  nonzero because a metastable branch ends at a spinodal. Finite sweep rates
  add bifurcation delay: the kernel is not an exactly rate-independent relay.

The second family is an ideal deterministic, low-activation-noise model of an
overdamped bistable material coordinate. It omits thermal escape, aging, spatial
domains, inertia and irreversible fatigue. Consequently it supports persistent
memory in this model; a finite experiment on a real material cannot prove
infinite retention. No hybrid arbitrary formula is used to add a third class.

For a complete slow sweep spanning both spinodals, the bistable geometric area
is 3*gain*a^2/(2*c), independent of the small bias; it ranges from about 0.797 to
3.802 response×field units. This is a geometric loop area, not an asserted
calorimetric dissipation measurement. The spinodal tilts are
c*H+b = ±2*(a/3)^(3/2); their fields always lie within ±0.834, inside the public
±1.5 range. The monostable geometric area vanishes as the reciprocal sweep
duration in the slow limit. A very rapid bistable sweep may fail to switch, so
area need not decrease monotonically from the fastest tested rate.

## State bounds and finite reset

All experiments begin with x=0, then execute the same finite reset prescription,
300 s at H=±1.5. Preparation steps follow; then the measured clock starts. The
public contract states this as a reproducible history, never exact equilibrium.
Protocol knots alter only the field, not x or y. No clipping enforces stability.

The interval [−2, 2] is invariant under every legal field history. For relaxation,
tanh lies in [−1, 1] so the vector field points inward at both boundaries. For
bistability, at x=2 the largest numerator is
1.15*2 − 8 + 0.9*1.5 + 0.025 = −4.325; at x=−2 the corresponding smallest
numerator is +4.325. Thus |y| ≤ 1.15*2 + 0.04 = 2.34, below the advertised
conservative ideal-output bound of 2.5. Gaussian observation noise is unbounded
and deliberately not clipped.

Reset removes possible prior-state differences far below measurement noise,
even though the actual kernel always starts from the same reference state:

* Relaxation contracts two initial states in [−2, 2] by exp(−300/tau), so their
  measured difference is at most 4*1.15*exp(−300/14) < 2.3e−9.
* For the positive bistable reset, c*H+b ≥0.875. Over x in [−2, 1] the drift
  numerator is at least 0.875−2*(1.15/3)^(3/2) >0.4, so every trajectory reaches
  x≥1 by 105 s. Thereafter the derivative of the drift is at most
  (1.15−3)/14 = −1.85/14. Any two trajectories differ by at most one latent
  unit at 105 s, giving measured difference at 300 s at most
  1.15*exp(−1.85*(300−105)/14) <7.5e−12. Negative reset follows by sign reversal.
  Solver error can exceed these mathematical residuals but remains far below
  the 0.006 measurement standard deviation. Corner tests bound computed reset
  differences by 1e−8 latent units.

At zero field the bistable drift points upward at x=0.8 and downward at x=−0.8
for every parameter in the ranges. Thus opposite completed resets retain at
least 1.6*0.85=1.36 response units of separation during a zero-field hold. In the
relaxation family that separation decays exponentially, and at 300 s is below
1.2e−9 response units. This establishes a diagnostic that works across the
declared private ranges, not merely a difference in labels on sampled seeds.

## Numerics, tests and bounded work

Constant-field relaxation uses its exact exponential solution. Other segments
use adaptive LSODA with relative tolerance 2e−9, absolute tolerance 2e−11, and
dense output. The observation grid does not choose the integration mesh. Every
segment ends before the next field slope changes. Durations, knots, sample rows
and preparation steps are bounded; no sampled parameter creates stiffness
outside the documented private ranges. A solver failure raises a generic error,
without returning hidden metadata or a partial prediction.

Tests independently implement DOP853 trajectories, the exponential constant
field limit, and the unbiased Landau logistic-square limit. They also check
fixed-field dissipation, invariant boundaries, reset corners, maximum controls,
replay, measurement noise, observation-grid invariance, public/private
separation, rate/reversal panel coverage, and public-record-only baseline use.
`calibrate.py` saves clean and noisy diagnostic traces, noisy training records,
disjoint held-out development conditions/interventions and raw baseline errors.
The complete local suite has 58 passing tests (about 1.0 s in the development
runtime). A stress protocol using all 20 knots, 129 rows, 3600 s of observation
and 600 s of preparation ran in under 0.03 s per call across both sampled
families; this is measured runtime evidence, not a universal timing guarantee.

## Development calibration and interpretation

Development seeds are 7, 46, 1439, 8743 (reserved from formal evaluation). The
first two happen to choose relaxation and the last two bistability. No formal
outcomes or paid model calls are used. Fixed instrumental scale/noise values
were selected before calibration and have not been adjusted to model scores.

| Seed | Operator family | Loop area, 20 s leg | 120 s leg | 1200 s leg | Opposite-reset difference after 300 s at zero field |
|---|---|---:|---:|---:|---:|
| 7 | relaxation | 2.2464 | 0.9988 | 0.1073 | 2.61e−11 |
| 46 | relaxation | 2.5788 | 0.7405 | 0.0756 | 0 |
| 1439 | bistable | 0.8605 | 5.4804 | 3.3868 | 2.1566 |
| 8743 | bistable | 3.8595 | 3.2649 | 1.5773 | 1.8689 |

The empirical baseline's mean prediction-only scores over 64 disjoint
development queries are 1.605, 20.329 and 26.751 with 0, 4 and 12 noisy records;
mean NRMSE is 0.7494, 0.4792 and 0.4454. It has no equation/family advantage.
Large residual errors reflect its limited history matching, and do not establish
that a scientific task is inherently difficult. A fitted dynamical model should
be a stronger comparator. The registered baseline is deliberately identified as
empirical, not as an expert upper bound.

This task tests discrimination between two constructed mechanisms through a
concealed apparatus interface. It does not establish contamination resistance,
open-ended novel discovery, or recovery of a unique physical equation. The
family mixture and panels affect aggregate scores. A formal cohort that balances
the two mechanisms should record that sampling design privately and not expose
the mechanism menu to the agent. Raw replayable data are saved outside Git by:

```sh
python -m env.hysteresis_material.calibrate --output /absolute/operator/path/hysteresis-development-v1.json
```

## Integration handoff

Register `env.hysteresis_material.world:World` and its exported `baseline` (also
available directly at `env.hysteresis_material.baseline:baseline`). The axis field
is `times`; the only channel is `response`; scale is 1; measurement noise is
0.006. The panel kinds `development`, `conditions`, `interventions` all work.

For paired claims, suggest a public eligibility resolution of **0.5 s after
t=0** and matched observation times across arms. Preparation and reset occur
before that clock and are not observed. Knots change the field continuously
between segments, and response is never assigned by a knot; therefore do not
restart an assignment-avoidance lag at every knot. This is an eligibility
resolution, not a claim that all transients equilibrate in 0.5 s, or a scientific
depth certificate. Immediate t=0 preparation contrasts can be scientifically
meaningful, but the existing pilot's general post-initial rule excludes them.
