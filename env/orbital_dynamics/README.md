# Orbital dynamics — registered, experimental

A bounded planar test-particle laboratory for learning motion laws from position
and velocity records. Every experiment resets the initial state. Positive-time
Cartesian velocity impulses can perturb a trajectory; all four observable
channels remain available. The origin is smooth, so inward trajectories do not
encounter a point-force singularity.

This apparatus is registered as the ninth world, with experimental status and public claim
eligibility rules for dynamical readouts. Registration does not establish
scientific difficulty or discovery depth, and it does not revise frozen cohorts
or historical scores. The source, this README, scientific notes, manifest,
numerical reference and development reports are **trusted operator material**.
Candidate context contains only
`World.describe()` and requested noisy observations. The public description is
identical across all hidden instances and does not list the private alternatives.

## Interface and controls

```python
from env.orbital_dynamics import World, baseline

world = World(7)  # Operator-only instance selection.
spec = {
    "position": [1.2, 0.0],
    "velocity": [0.0, 0.8],
    "times": [0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0],
    "impulses": [{"time": 3.0, "delta_v": [0.18, -0.08]}],
}
observation = world.run(spec, noise_key="operator-replicate-1")
prediction = baseline([{"spec": spec, "observation": observation}], spec)
```

| Quantity | Public instrument contract |
|---|---|
| Position | Two Cartesian coordinates, initial radius 0.75–2 L |
| Velocity | Two Cartesian components, initial speed at most 1.5 L/T |
| Observation axis | `times`, 1–65 strictly increasing samples in [0, 12] T; zero optional |
| Impulses | At most 3, strictly increasing times in (0, last sample] |
| Impulse magnitude | Each norm ≤0.5 L/T; sum of norms ≤0.8 L/T |
| Observation channels | `x`, `y`, `vx`, `vy`, always in this order |
| Fixed scales | 2 L, 2 L, 1.5 L/T, 1.5 L/T |
| Measurement noise SD | 0.0015 L, 0.0015 L, 0.002 L/T, 0.002 L/T |
| Center resolution | 0.25 L; finite dynamics through the center |
| Cost | `8 + sample_count + 4*impulse_count + ceil(last_time/2)`; maximum 91 |

L and T are laboratory units. They are not asserted to represent a real planetary
system. Measurements add independent Gaussian noise, without clipping or process
noise. The clean private verifier uses `noise_key=None`. A string key gives stable
noise for the same instance and canonical experiment; different keys select
independent pseudorandom draws. Adding sampling times preserves the clean
trajectory, but keys are hashed with the full spec, so it need not preserve noisy
values at common times.

At an event, position stays continuous and `delta_v` is added to the current
velocity. The measurement at the exact event time is **after** the impulse. An
event at the last observation is legal and has no later dynamical observation.
Time-zero values and exact impulse *differences* follow public assignment rules;
they are not evidence of a discovered motion law. An absolute post-impulse
velocity still depends on the preceding unknown trajectory. There is no direct
force or acceleration channel.

## Public claim eligibility

The integration uses a fixed pilot minimum lag of **0.25 T**. A selected claim
readout must be at least 0.25 T after the reset at time zero and at least 0.25 T
after **each impulse at or before that readout**. Equality at the lag boundary is
eligible; time-zero, exact-event and shorter-lag readouts are ineligible. An
impulse later than the selected readout does not affect its lag eligibility.
Paired comparisons must select the same physical observation time in both
experiments; matching row indices alone is insufficient when the time grids
differ. These rules apply to claim verification, not to which observations the
apparatus permits.

The lag is a public resolution policy for this pilot, not a fitted dynamical
timescale or evidence that every eligible effect is informative. Assigned reset
values and instantaneous impulse jumps are known controls, not discovered
dynamics. Passing the lag and matched-time checks does not by itself establish
causal isolation, a unique law, or scientific depth. Other predetermined effects
and public symmetries still require semantic review.

## Learning opportunities and limits

Distinct radial dependence can alter orbit shape, radial excursion and responses
to new initial radii or impulses. Velocity-dependent dissipation changes angular
momentum and the reversal experiment. Conservation must be tested under the
appropriate conditions: it is not valid to assume energy or angular momentum
remains constant during every experiment.

A single circular trajectory is insufficient to distinguish radial laws that
agree at that radius. Short arcs can also confound strength and radial dependence,
or hide weak dissipation under noise. Probe more than one radius, use impulses
that change radius, and retain failed extrapolations. Precise predictions alone
do not prove a unique physical law, scientific depth or contamination resistance.

The reference baseline transfers the nearest public trajectory after aligning
the initial radial direction, subtracting its known inertial motion/impulses and
adding the query's known motion/impulses. With no observations it predicts inertial
motion. It never receives a world, force equation, parameter, instance seed, or
clean query target. It is deliberately a weak empirical comparator; its poor
performance does not establish difficulty.

`panel(panel_seed, kind, count)` is operator-only and independent of hidden world
parameters. `conditions` changes initial position, velocity and duration without
impulses. `interventions` always includes one or two impulses. `development`
contains both. The kind enters seed derivation; identical panel seeds do not
produce identical condition and intervention specs. Panels are reproducible, not
a proof of generalization to an unseen mechanism family.

## Validation and development report

```sh
python -m pytest -q env/orbital_dynamics/tests
python -m env.orbital_dynamics.calibrate --output /new/private/path/orbital-diagnostics.json
```

The calibration CLI refuses to overwrite an existing result. It records 12 noisy
public training experiments per reserved development seed (7, 46, 1439, 8743),
12 independent development queries, costs, runtime, numerical effort, and weak
baseline predictions at 0/4/12 observed experiments. Numerical error is checked
against independently formulated polar equations solved with Radau. The report
also constructs matched circular trajectories to show exact ambiguity and then
tests radius/impulse interventions. Private targets remain in the operator report.

The four reserved seeds happen to cover the alternative-power and dissipative
strata, not the conservative inverse-square stratum; the mapping was not changed
to make the development sample balanced. All strata are separately exercised by
explicit-parameter physical tests and matched-law diagnostics. Balanced cohort
sampling, if later desired, must be an explicit operator policy.

See [SCIENTIFIC_NOTES.md](SCIENTIFIC_NOTES.md) for the private construction,
potential derivation, numerical checks and validity limits, and
[development/README.md](development/README.md) for calibration summaries and
private evidence provenance. Raw development diagnostics are retained only in
the central private artifact store, outside this Git directory; they are
diagnostic evidence, not formal evaluation results.
