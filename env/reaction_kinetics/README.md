# Reaction kinetics world

A fresh, closed batch reactor contains four assayed species, A–D. The unknown
mechanism is a sparse network of reversible first-order reactions. Every assay
returns all four concentrations in that fixed order. Parameters and graph
topology vary with the private instance seed; an instance remains fixed across
experiments. Graph variation is not a demonstrated contamination-resistance
result.

This is a construction prototype, not a calibrated scientific-discovery
benchmark. Prediction, quantitative contrast verification and expert assessment
of a proposed mechanism remain separate.

## Public experiments

Call `World.describe()` for the complete public contract. A valid experiment is:

```json
{
  "temperature_k": 305,
  "initial_mM": [0, 0.6, 0, 0.4],
  "times_s": [0, 5, 15, 30, 45, 60, 90],
  "interventions": [
    {"time_s": 30, "kind": "temperature", "temperature_k": 345},
    {"time_s": 45, "kind": "add", "amounts_mM": [0.25, 0, 0, 0]}
  ]
}
```

`temperature_k` is between 285 and 365 K. `initial_mM` has four entries, each in
[0, 2] mM, and a total in [0.05, 3] mM. `times_s` has 2–33 strictly increasing
entries, starts at zero and ends by 120 s. `interventions` defaults to an empty
list. It contains at most four events, in strictly increasing time order, after
zero and no later than the final sample. Unknown fields are rejected.

A temperature event takes effect instantly and persists. An `add` event adds
the specified concentrations at fixed volume, without dilution. Each addition
has four entries in [0, 1] mM and a total in [0.000001, 1.5] mM; the initial
concentration plus all additions cannot exceed 6 mM. Events cannot share a time.
An assay at an event time is **after** that event, including a concentration
addition at the last requested time. All experiments restart from their specified
initial concentrations; no vessel state carries over.

Responses contain `axis` (the requested seconds), `channels` (`A`, `B`, `C`, `D`)
and `values` (one four-concentration row per time). Measurement noise is
independent additive Gaussian with standard deviation 0.002 mM for each entry;
it is not clipped, so small negative assay values are possible. There is no
process noise. Public normalization scales are fixed at 1 mM per channel.
Experiment cost is `1 + ceil(len(times_s) / 8) + len(interventions)`.

## Scientific family and possible discoveries

For a directed transfer i → j, the rate is `k_ij(T) * c_i`. A present rate has
`k_ij(325 K)` in [0.006, 0.14] s⁻¹ and activation energy in [14000, 48000] J/mol:

```text
k_ij(T) = k_ij(325 K) exp[-E_ij/R (1/T - 1/325 K)]
R = 8.31446261815324 J/(mol K)
```

The graph is reversible and obeys detailed balance. The identity of its edges,
rate values, equilibrium composition and response to temperature are hidden.
This family supports concrete, testable inferences:

- Short-time responses from different pure starting species distinguish direct
  reactions from transport through intermediate species and reveal branching.
- Responses at several temperatures estimate Arrhenius slopes, including changes
  in relaxation time and equilibrium composition.
- Scaling initial mixtures tests first-order concentration dependence and
  superposition; a measured jump followed by relaxation tests the same model on
  concentration additions.
- Paired temperature switches test whether fitted temperature dependence
  transfers to a new schedule. Total concentration is conserved between
  additions, providing a separate consistency check.

A useful 12-round identification design is four pure-species initial conditions
at each of three temperatures with dense early sampling. Up to four additional
rounds can check a mixed initial condition, a pulse and temperature switches.
This design makes the small system accessible within 12–16 rounds; no agent
study has yet established empirical discovery success at that budget. At very
late times alone, multiple graphs can have indistinguishable equilibrium traces.

## Operator interface and verification

```python
from env.reaction_kinetics import World, baseline

world = World(seed=7)
spec = world.describe()["examples"][0]
observation = world.run(spec, noise_key="obs-0001")
prediction = baseline([{"spec": spec, "observation": observation}], spec)
```

`noise_key=None` produces the clean private verification target. Nonempty string
keys select reproducible noise using a stable hash of version, instance seed,
canonical experiment and key. Reusing the same key and spec reproduces the same
assay; fresh keys supply independent noise. Invalid inputs leave the instance
unchanged. Numeric inputs must be finite, and booleans are not numbers.

The kernel exponentiates a four-by-four concentration generator on each
constant-temperature interval. At most 33 sample rows and four interventions
bound numerical work to at most 37 matrix propagations per experiment. Tiny
floating-point drift is removed after each segment to preserve total mass.

`panel(panel_seed, kind, count=8)` is operator-only and independent of the hidden
instance seed. `development` supplies pure-species temperature experiments;
`conditions` supplies new mixtures, temperatures and sampling regimes without
events; `interventions` supplies temperature switches plus concentration pulses,
with assays at event times. Each kind has a separate deterministic random
stream. Counts must be 1–64. Panels are not disclosed through public discovery
or observations.

The baseline uses only recorded specs and observations to fit a nonnegative
first-order generator from trapezoidal concentration integrals. It uses the
nearest observed temperature and propagates the proposed interventions. It
does not infer activation energies or enforce detailed balance. Sparse or
coarse observations can bias it; with no usable evidence it predicts no
reaction while still applying additions. This is a comparison method, not the
hidden mechanism or a scientific validator.

The trusted Python source, instance fields, panels and this operator discussion
are not public agent attachments. Agents receive `describe()` and budgeted
observation responses through the shared runner. No legacy benchmark evaluator
is imported.

Run tests from the repository root:

```sh
python -m pytest env/reaction_kinetics/tests -q
```

Tests cover analytic two-species relaxation, an independent adaptive ODE solver,
mass conservation, event timing, Arrhenius behavior and detailed balance,
reproducibility, parameter/topology variation, invalid requests, public/private
separation, deterministic panels and the observation-only baseline.
