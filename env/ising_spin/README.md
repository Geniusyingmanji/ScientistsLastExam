# Six-spin equilibrium world

This world models six labelled spins with hidden signed pair interactions and
local fields. A scientist can sweep temperature, add external fields, clamp
spins, and weaken individual bonds. Every temperature is a fresh equilibrium
ensemble. The observations are six magnetizations and all fifteen pair moments.
The operator sums all 64 spin configurations exactly, eliminating Monte Carlo
convergence and metastability ambiguity.

Useful discoveries include distinguishing a direct interaction from an indirect
correlation, estimating signs and strengths, identifying supported frustrated
cycles, and predicting collective response after interventions. A six-spin
system can have a smooth susceptibility peak. It has no thermodynamic-limit
phase transition, and numerical prediction accuracy does not certify a mechanism
or a new physical law.

## Use

From the repository root, with Python 3.8 or later, NumPy and SciPy:

```python
from env.ising_spin import World, baseline

world = World(seed=7)  # trusted operator only
description = world.describe()
spec = {"temperatures": [0.5, 0.8, 1.2, 2.0, 3.5, 6.0]}
observation = world.run(spec, noise_key="obs-0001")
records = [{"spec": spec, "observation": observation}]
prediction = baseline(records, {
    "temperatures": [0.7, 1.4, 2.8],
    "clamp": {"A": 1},
    "suppress_bonds": [{"nodes": ["B", "D"], "fraction": 0.5}],
})
```

The candidate receives only the public description and its own experiment
records through the shared runner. The `World` object, its seed, operator
source, examples and private evaluation panels are not candidate attachments.
`noise_key=None` returns the clean verifier target. A string selects reproducible
Gaussian sensor noise via a stable SHA-256 hash; use different keys for
independent observations. Every run leaves the hidden instance unchanged.

```sh
python -m env.ising_spin.examples.discover --seed 7
python -m pytest env/ising_spin/tests -q
```

The example is an operator-written learning demonstration, not an agent result.
It fits only public noisy observations, freezes its predictions, then requests
fresh clean values for diagnostic evaluation. Its twelve experiments cost
36 units. This expansion environment does not change the core four-world cohort.

## Public model and experiment schema

Each spin `s_i` is -1 or +1. The equilibrium energy is

```
H/epsilon = -sum_(i<j) J_ij*(1-suppression_ij)*s_i*s_j
            -sum_i (h_i+external_field_i)*s_i
P(s)      = exp(-(H/epsilon)/temperature) / partition_function
```

The probability is normalized only over states consistent with the clamps.
Temperature is the known reduced quantity `k_B*T/epsilon`; fields and couplings
are expressed in units of the same known energy scale `epsilon`. The hidden
local fields lie in [-0.35, 0.35]. A present coupling has magnitude in [0.2, 1.2];
an absent coupling is zero. Positive couplings favour alignment and negative
couplings favour opposition. The original undirected graph is connected.
There are no higher-order interactions, unknown sensor gains, missing spins or
unknown temperature scales. The public family specifies the law; its sampled
graph and coefficients remain hidden.

| Field | Meaning and bounds |
| --- | --- |
| `temperatures` | Required: 1–32 strictly increasing finite values in [0.35, 6]. Each is a separate equilibrium ensemble. |
| `external_field` | Six additive fields in [-2, 2], in node order A,B,C,D,E,F; default zero. |
| `clamp` | Object mapping names to integer -1 or +1; default `{}`. All six spins may be fixed. |
| `suppress_bonds` | At most 15 distinct controls, each exactly `{"nodes":["A","B"],"fraction":0.5}`. Fraction is in [0, 1]. |

Clamps retain incident interactions. They act as known fixed neighbours for
free spins. A field on a clamped spin adds only a constant energy, so it does
not change expectations. Suppression multiplies a signed coupling by
`1-fraction`, preserving its sign; complete suppression removes the bond.
Suppressing an absent bond has no effect. These controls are static across the
temperature sweep. Initial states, preparation order, cooling rate and run
history have no role in this equilibrium model.

Unknown fields, duplicate unordered bonds, malformed controls, nonfinite values,
zero/fractional clamp values, out-of-range numbers, duplicate temperatures and
non-increasing temperature lists are rejected before calculation.

Output `axis` equals the canonical `temperatures` list; `World.axis_field` is
`"temperatures"`. All coordinates are positive, including claim readouts. The
fixed channel order is `m_A` through `m_F`, followed by `c_A_B`, `c_A_C`, …,
`c_E_F` in lexicographic pair order. Magnetization means `<s_i>`. A pair channel
is the raw moment `<s_i*s_j>`, not the connected covariance. Its connected
counterpart is `c_i_j - m_i*m_j`.

Clean observables lie in [-1, 1], with normalization scale 1 for every channel.
Independent Gaussian sensor noise has standard deviation 0.003 for every
temperature/channel, including clamped observables. No clipping is applied,
so noisy values can exceed these clean physical bounds. This noise represents
measurement error in ensemble averages, not a finite sample of jointly observed
spin configurations. No sampling uncertainty or process noise is simulated.

An experiment costs `1 + ceil(number_of_temperatures/4)` units, from 2 to 9.
Work is bounded by 32 temperatures, 64 configurations and 21 observables. The
partition function uses log-sum-exp normalization to remain numerically stable
at the legal temperature and field extremes.

## Learnability and scientific interpretation

The six means and fifteen pair moments are sufficient statistics for the
documented pairwise equilibrium family. At nonsaturated temperatures, their
response can identify the six fields and fifteen possible couplings, including
zeros. Known temperature and calibrated fields avoid a hidden energy-scale
ambiguity. Low-temperature saturation can weaken identification; several
temperatures and independent field directions improve conditioning.

A feasible twelve-round plan is one unforced temperature sweep, six single-node
positive-field sweeps, two negative-field sweeps, one clamp, one bond suppression,
and one combined field/suppression experiment. Fit interactions from the first
rounds, then use later controls to challenge the fitted predictions. The supplied
plan is a fixed illustration; adaptive choices based on model disagreement can
be more informative. It is not a prescribed golden solution.

Nonzero pair correlation need not indicate a direct bond: even an A–B–C chain
can correlate A and C. A signed cycle is frustrated when the product of its
nonzero coupling signs is negative, so no spin configuration can satisfy all
preferred alignments. Establishing this requires interaction evidence, not just
the signs of observed pair correlations. Bond suppression can test that evidence.

Let `S=sum_i s_i`. The susceptibility of total magnetization to a uniform added
field can be obtained from the measured moments:

```
chi = (6 + 2*sum_(i<j) c_i_j - (sum_i m_i)**2) / temperature
```

Finite differences with weak positive/negative uniform fields independently
test this fluctuation-response prediction. Raw sensor noise can make a derived
variance slightly negative in a nearly saturated ensemble; that is measurement
error, not negative equilibrium susceptibility. Antiferromagnetic or biased
finite systems may show non-monotonic response with temperature. Such a smooth
finite-system maximum does not establish a phase transition.

## Panels and public baseline

The operator-only `conditions` panel varies temperature range, density and
regular/logarithmic versus irregular sampling without interventions. An
equilibrium preparation has no initial-state control to vary. The
`interventions` panel adds local fields, clamps, fractional suppression and
combined controls. Every intervention member has a manipulation, though a
suppressed absent bond can legitimately be a no-op. `development` mixes both.
Panel membership depends on its own seed and kind, not hidden fields or graph;
the instance cannot tailor its test cases. Panels are never included in the
public description. Default eight-member intervention panels include all four
control patterns; shorter panels cover fewer.

`baseline(records, spec)` is a strong physics-informed reference. It fits a
bounded convex inverse-Ising moment objective using only the observed means,
pair moments, public temperature/control settings and documented ranges. Exact
state sums provide model moments and analytic gradients. Weak regularization
favours zero coefficients without assuming a sampled topology. Measured channels
that are mathematically constant under clamps are replaced by their known
constants during fitting. The fit respects known control settings.

The baseline accepts at most 256 records, ignores malformed/misaligned
observations, and uses at most 64 rows chosen evenly through a longer valid
history. L-BFGS-B has explicit iteration, function-evaluation and line-search
limits. With no usable data it predicts independent spins with zero hidden
fields, while respecting the requested external fields and clamps. It neither
constructs a `World` nor reads private parameters, panel outcomes or graph
generation rules. A fitted coefficient is an estimate, not a confidence interval
or an automatic missing-bond certificate.

In a construction sanity check on seeds 7, 46 and 1439, four noisy field/control
sweeps yielded roughly 0.0009–0.0019 RMSE on fresh condition/intervention panels;
zero predictions gave 0.27–0.42 RMSE. This is deliberately learnable model
identification, with substantial observable signal. Difficulty, discovery
depth and contamination resistance have not been calibrated. Changing hidden
graph and parameter seeds alone does not establish structural holdout.

Tests use an independently written 64-state enumerator, analytic independent
spins and chains, global/gauge symmetries, clamp identities, a fluctuation-response
check and a finite antiferromagnetic response peak. They also cover public
separation, reproducible measurement noise, strict validation, graph diversity,
panel separation and transfer of a fit based only on public records. Numeric
effect verification does not grade free-text mechanisms against a golden answer.
