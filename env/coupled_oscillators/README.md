# Coupled mechanical oscillators

This batch world contains four labelled masses connected by an unknown spring
network. Grounding stiffnesses, drag coefficients, spring strengths and active
pairs vary between instances. An experiment prepares initial displacements and
velocities, applies fixed controls, and measures all four displacements and all
four velocities over time. Every experiment is a fresh preparation.

The public model class is ordinary linear mechanics. Discovery concerns the
network, its coefficients, and quantitative consequences of interventions. This
is a tractable system-identification pilot; successful prediction alone does not
establish a new physical law, a mechanism discovery score, contamination
resistance, or calibrated difficulty. Neither sampled parameters nor graph
generation details belong in the agent interface.

The [five-episode evidence review](PILOT_EVIDENCE.md) records local findings,
prospective tests and differences between fitted and finally submitted models.

## Use

From the repository root, with Python 3.8 or later, NumPy and SciPy installed:

```python
from env.coupled_oscillators import World, baseline

world = World(seed=7)  # trusted operator only
description = world.describe()
spec = {
    "times": [i / 10 for i in range(121)],
    "initial_position": [0.7, 0, 0, 0],
}
observation = world.run(spec, noise_key="obs-0001")
records = [{"spec": spec, "observation": observation}]
prediction = baseline(records, {"times": [1, 2, 4], "mass_add": [1, 0, 0, 0],
                                "initial_position": [0.7, 0, 0, 0]})
```

`World` is an operator object. A candidate receives `describe()` and its own
observations through the shared budgeted runner; it must not receive this
directory, the object, the instance seed, or the private panels. `run(...,
noise_key=None)` produces the clean verifier target. A non-null string selects
reproducible additive Gaussian measurement noise; distinct experiments must use
distinct keys to obtain independent noise. Keys are hashed with SHA-256, never
Python's process-dependent hash.

Run the public-data learning demonstration or local checks:

```sh
python -m env.coupled_oscillators.examples.discover --seed 7
python -m pytest env/coupled_oscillators/tests -q
```

The demo uses the twelve plans in `examples/experiments.json`. It reports a
fitted model's predictive errors and a selected paired cut effect. Its fit uses
only public records. The trusted evaluator subsequently accesses fresh clean
targets to measure error; those targets are never used for fitting. This is an
operator-written demonstration, not an agent result.

## Public experiment contract

All arrays follow node order A, B, C, D. A node's baseline mass is exactly 1 kg.
The observation channels are `x_A`, `x_B`, `x_C`, `x_D` in metres, followed by
`v_A`, `v_B`, `v_C`, `v_D` in metres per second. Fixed normalization scales are
1 m for displacement and 2 m/s for velocity. Measurement noise standard
deviations are 0.002 m and 0.003 m/s, independently at every requested time and
channel, including time zero and clamped nodes. Values are signed and not clipped.

| Field | Meaning and bounds |
| --- | --- |
| `times` | Required: 1–241 strictly increasing finite times in [0, 24] seconds. Time zero is optional. |
| `initial_position` | Four values in [-1, 1] m; default zero. |
| `initial_velocity` | Four values in [-2, 2] m/s; default zero. |
| `mass_add` | Four added masses in [0, 3] kg; default zero. |
| `damping_add` | Four added ground drag coefficients in [0, 2] N s/m; default zero. |
| `cut_edges` | At most six distinct unordered node pairs. Cutting an absent pair has no effect. |
| `clamp` | Distinct names of nodes fixed at x=v=0. Their initial coordinates must be zero. |
| `drive` | Null, or exactly `node`, `amplitude` in [-2, 2] N, `frequency` in [0, 2] Hz, and `phase` in [-π, π] radians. |

The drive force is `amplitude * sin(2*pi*frequency*t + phase)`. Setting frequency
to zero and phase to π/2 yields a constant force. A nonzero drive on a clamped
node is invalid. All interventions act from time zero throughout the run.
Clamping retains intact springs to that node as springs to a fixed anchor;
cutting removes both directions of a spring force. Loading changes inertia
without changing spring or drag coefficients. Unknown fields, nonfinite values,
duplicate pairs/nodes, non-increasing times and out-of-range inputs are rejected
before simulation. Requests cannot change the fixed instance.

The public family obeys

```
(1 + mass_add_i) * dv_i/dt = -g_i*x_i - (c_i+damping_add_i)*v_i
                            - sum_j k_ij*(x_i-x_j) + drive_i(t)
dx_i/dt = v_i
```

Here grounding stiffness `g_i` lies in [0.5, 2.0] N/m, intrinsic ground drag
`c_i` in [0.04, 0.25] N s/m, and each present symmetric pair stiffness `k_ij`
in [0.25, 1.2] N/m. Absent pairs have zero stiffness. The initial graph is
connected. There is no coupling drag, hidden mass, nonlinearity, or delay.
The full equation describes the available physical family, not an instance's
sampled network or parameter values.

Cost is `1 + ceil(last_time/4) + ceil(number_of_rows/32)`, from 2 to 15 units.
The kernel evaluates a constant 10 by 10 matrix exponential, with at most 241
requested samples and a fixed 24-second horizon; there is no adaptive numerical
work explosion. Harmonic forcing is represented by two oscillator coordinates.

## Learnability and panel separation

Four independent node displacements with 0.1-second sampling for 12 seconds
excite enough state variation to estimate the 14 unknown coefficients: four
grounding springs, four drags, and six possible pair springs. There are no
unknown sensor gains or masses to make those coefficients scale-ambiguous.
Measured velocities permit integral force-balance regression without numerical
second derivatives. Several excitation directions help avoid symmetries and
poorly conditioned single-trajectory fits.

A feasible twelve-round plan is four independent kicks, three individual cuts,
one loading, one added damping, one clamp, and two drive frequencies. Use the
first experiments to fit and diagnose the model, then use interventions to test
its transportability and distinguish direct links from indirect transmission.
The example plan costs 96 units. A broader graph audit can add the remaining
three individual cuts for fifteen rounds. A single absent or very small endpoint
response is insufficient evidence that a spring is absent.

The operator-only `conditions` panel changes initial position, initial velocity,
duration and regular/irregular sampling on the unmanipulated network. The
`interventions` panel uses the same public regime with cuts, mass loading, added
damping, clamping and harmonic drives; each member contains a manipulation.
Some cuts can be true no-ops, because the panel must not consult hidden topology.
`development` mixes control and manipulated experiments. Panels depend only on
their seed and kind, so a hidden instance cannot tailor its own test conditions.
They are deterministic, finite, and independent of the public examples; they
are not returned by `describe()`.

At the default count of eight, each intervention class is represented. A count
below five necessarily covers fewer classes. Graph and parameter variation
between seeds are construction diversity, without a claim of structural
holdout or resistance to training-data contamination.

## Baseline and verification

`baseline(records, spec)` fits the public force balance with bounded linear least
squares. It integrates each observed trajectory over short windows, uses cubic
Hermite quadrature for displacement integrals, and regularizes toward midpoints
of the public ranges. It uses known actuator settings to handle recorded cuts,
clamps, loading, added damping and forcing. Every possible spring is allowed in
the fit; zero and nonzero coefficients are inferred from public observations.
Prediction then solves the fitted passive model. No `World` object, private seed,
sampled coefficient or private panel is read by the baseline.

The baseline accepts at most 256 records and ignores malformed or mismatched
observations. Intervals longer than 0.5 seconds are omitted from fitting because
their quadrature may be inaccurate; all legal prediction grids remain accepted.
With no usable observations it returns a dense passive midpoint model. This is
a strong physics-informed reference, not a data-free oracle. Fits are not
confidence intervals and do not certify a missing edge.

Independent tests cover four decoupled analytic solutions, constant forcing,
an independent `solve_ivp` calculation with combined controls, passive energy,
absent-link cuts, reproducible noise, strict validation, output ownership, varied
graphs, panel separation and public-data transfer. Across three diagnostic
instances, four noisy kick experiments gave about 0.001–0.002 normalized RMSE
on fresh condition/intervention panels, while zero prediction gave 0.23–0.29.
These are construction sanity checks on named seeds, not a calibrated benchmark
or statistical generalization claim.

The shared runner scores frozen predictions and fresh paired numerical effects.
It does not grade a prose mechanism by comparison with a golden answer. A
scientific claim such as "cutting A–B reduces B's displacement at 1.4 s by
0.1–0.2 m under this preparation" must include its precise preparation,
measurement, cited records, scope and uncertainty interval. The effect alone
does not certify a general graph reconstruction.
