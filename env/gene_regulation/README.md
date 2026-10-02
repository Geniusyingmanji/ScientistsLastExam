# Gene regulation world — expansion cohort

Four normalized gene-expression states interact through a hidden, sparse signed
network. Positive edges activate and negative edges repress. Saturating
production, feedback and unequal response times make this a nonlinear system.
All four genes are observed and can be experimentally targeted. Each experiment
starts anew; the private mechanism remains fixed across experiments.

This construction prototype belongs to the expansion cohort. Its inclusion does
not alter the frozen core cohort. Parameter and topology variation are not proof
of contamination resistance, and agent discovery performance is not calibrated.

## Public model

For gene j:

```text
dx_j/dt = gamma_j [sigmoid(b_j + sum_i W_ij (2 x_i - 1) + u_j) - x_j]
sigmoid(z) = 1 / (1 + exp(-z))
```

Time is in hours. `W` is source-by-target and has no self-edges. Present signed
weights have absolute values in [0.65, 3.2], biases lie in [-0.6, 0.6], and
response/decay rates lie in [0.15, 0.8] h⁻¹. Clean expression stays in [0, 1].
The graph, signs and parameters must be inferred. The family does not guarantee
that every instance exhibits every possible behavior.

## Experiments and intervention semantics

`World.describe()` gives the complete public interface. For example:

```json
{
  "initial_expression": [0.4, 0.4, 0.4, 0.4],
  "initial_drive": [0, 0, 0, 0],
  "times_h": [0, 1, 2, 3, 5, 8, 10, 14, 20, 24],
  "interventions": [
    {"time_h": 2, "kind": "set_drive", "drive": [2.5, 0, 0, 0]},
    {"time_h": 8, "kind": "set_drive", "drive": [0, 0, 0, 0]}
  ]
}
```

- `initial_expression` has four entries in [0, 1], ordered G1–G4. These are
  externally prepared expression states, not hidden equilibrium presets.
- `initial_drive` defaults to four zeros. Each drive vector has four entries in
  [-3, 3] with at most two nonzero entries. All four genes are targetable.
- `times_h` has 2–41 strictly increasing entries, starts at zero and ends by 24 h.
- `interventions` defaults to an empty list and contains at most four events.
  Event times strictly increase, are greater than zero, and do not exceed the
  final sample time. Unknown fields and nonfinite values are rejected.

Each `set_drive` replaces the **whole** drive vector and persists until replaced.
Positive drive represents overexpression-like stimulation of synthesis;
negative drive represents knockdown-like suppression. The intervention adds to
synthesis log-odds. It is neither a specified fold change nor a clamp on the
observed expression. Its size is therefore not a measured biological efficacy.
An explicit zero-vector event ends a pulse. Different genes may be targeted in
different intervals, provided no interval targets more than two simultaneously.

Expression is continuous at a drive change. A sample at the switch time has the
same expression as immediately before it; subsequent evolution uses the new
drive. A switch at the final time does not change that final expression. A
targeted gene responds over time, and untargeted genes can respond through
network paths. State preparation and drive are reset on each experiment.

The result has `axis` (requested hours), `channels` (G1–G4), and `values` (one
four-expression row per requested time). Independent Gaussian measurement noise
has standard deviation 0.004 per entry and is not clipped. Thus an assay can
slightly exceed [0, 1], although the clean state cannot. There is no process
noise. All public normalization scales are fixed at 1 expression unit.

Cost is `1 + ceil(len(times_h) / 10) + len(interventions)`.

## Discoverable mechanisms and experiment design

The family includes sparse signed feedback and feedforward circuits. Concrete
questions supported by the interventions include:

- Which genes activate or repress a downstream gene? Contrasting positive and
  negative drives, multiple starting states and early response times separates
  direct effects from delayed effects through intermediate genes.
- Does stronger stimulation saturate? Comparing drive amplitudes tests the
  nonlinear response rather than simple concentration scaling.
- Does a pulse switch the system to a persistent expression state? Some mutual
  activation circuits retain a high state after the drive ends; initial-state
  dependence and a reversal perturbation test that interpretation.
- Does a downstream gene respond transiently and then partially adapt? A fast
  activating path combined with slower repression can produce that behavior.
  Delayed negative feedback can also attenuate a sustained response.

A compact design uses two unperturbed runs from low and high initial expression,
eight single-gene positive/negative drive runs, then four pulse-and-recovery runs
and up to two paired perturbations. This provides 10–16 informative experiments
for a four-state model without latent regulators. It is an intended design,
not a measured guarantee of identifiability or discovery within 16 rounds.
Equilibrium measurements alone generally do not identify the signed network.
Partial adaptation must not be reported as perfect adaptation or a biological
homeostasis result. These are synthetic dynamical mechanisms.

## Operator interface

```python
from env.gene_regulation import World, baseline

world = World(7)
spec = world.describe()["examples"][1]
observation = world.run(spec, noise_key="obs-0001")
prediction = baseline([{"spec": spec, "observation": observation}], spec)
```

`noise_key=None` selects clean private verification output. A nonempty string
selects reproducible noise from a stable hash of version, seed, canonical spec
and key. Fresh keys provide independent noise. Invalid requests leave the world
unchanged. The simulator uses fixed-step fourth-order Runge–Kutta with steps no
larger than 0.04 h and splits exactly at samples and input changes. The 24 h
horizon and at most 44 positive-duration segments bound integration to at most
644 steps (2576 right-hand-side evaluations). Floating-point endpoint drift is
clipped to the known state domain; numerical failures are checked explicitly.

`panel(panel_seed, kind, count=8)` is operator-only, deterministic and independent
of the private world seed. Counts are 1–64. `development` combines initial-state,
single-gene and pulse probes. `conditions` changes initial states and sample
times without drive. `interventions` changes one- or two-gene pulse amplitudes
and timings, including assays during and after the pulse. Panels are absent from
public descriptions and observations.

The baseline fits a regularized affine dynamical approximation to recorded
expression increments, midpoint expression and known drive. Its predictions are
projected into [0, 1]. It uses no private parameters or World methods. With no
usable data it uses the public unregulated model with zero bias and the midpoint
decay rate. A linear approximation can miss saturation, thresholds and memory;
it is a comparison baseline, not the hidden model or a mechanism validator.

Source, hidden instance fields and test panels are trusted operator material,
not public agent attachments. No legacy benchmark evaluator is imported.

Run verification from the repository root:

```sh
python -m pytest env/gene_regulation/tests -q
```
