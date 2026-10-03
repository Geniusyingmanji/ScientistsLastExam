# Heat transport

This world provides repeatable heating experiments on a one-metre material. Each
call begins with a fresh, uniform interior temperature. Three movable probes
report temperature through time. The fixed hidden apparatus may have one or two
diffusivity regions, an unknown flow calibration, and unknown heat loss. The
scientific task is to separate these effects using interventions and predict
responses at new conditions.

The [five-episode evidence review](PILOT_EVIDENCE.md) separates fixed-coefficient
checks, post-refit residuals, numerical implementation changes and missing output.

Only `World.describe()` and experiment responses are agent-facing. This source
directory, private instance fields, test panels and operator metadata are not
agent attachments. No old benchmark evaluator is imported.

The public physical family is

```
∂T/∂t = ∂x(D(x) ∂xT) − u ∂xT − cooling × loss × (T − ambient_temperature) + Q(x)
u = flow × flow_gain
Q(x) = Σ power_i × exp(−(x − position_i)² / (2 width_i²)).
```

`D` is a thermal diffusivity in m²/s, not conductivity in W/(m K); volumetric
heat capacity is absorbed into this coefficient and the source units. It lies
in `[0.006, 0.06]`. If two regions exist, their interface is in `[0.3, 0.7]` m;
temperature and diffusive heat flux are continuous there. The positive flow
gain lies in `[0.02, 0.10]` m/s and the heat-loss coefficient in `[0.01, 0.08]`
s⁻¹. These bounds describe the possible family, not the sampled apparatus.
The two endpoint temperatures are held fixed from t=0. Uniform interior initial
temperature need not match them. All heaters, flow and cooling remain constant
through one experiment. Positive flow transports heat toward increasing x.

Every field below is required, and additional fields are rejected. Numbers must
be finite real numbers; booleans and numeric strings are rejected. Arrays are
JSON lists (Python tuples are also accepted and canonicalized to lists).

| Field | Legal values and units |
|---|---|
| `times` | 1–25 strictly increasing observation times in `[0, 30]` s |
| `probes` | Exactly 3 strictly increasing positions in `[0.05, 0.95]` m |
| `initial_temperature` | Uniform interior temperature in `[0, 80]` °C |
| `boundary_temperatures` | Exactly 2 temperatures in `[0, 80]` °C, at x=0 and x=1 |
| `ambient_temperature` | Surrounding reservoir temperature in `[0, 40]` °C |
| `flow` | Dimensionless signed control in `[-1, 1]`; zero disables advection |
| `cooling` | Dimensionless multiplier in `[0, 3]`; zero disables environmental heat loss |
| `heaters` | 0–3 objects, each containing exactly `position`, `power`, `width` |
| heater `position` | Centre in `[0.05, 0.95]` m |
| heater `power` | Peak local heating rate in `[0, 8]` K/s; sum at most 12 K/s |
| heater `width` | Gaussian standard deviation in `[0.04, 0.20]` m |

Heater power is the **peak rate**, not the spatially integrated rate. A source
near an endpoint is truncated by the material. Sources can overlap. There are no
pulses or mid-experiment control changes. One valid experiment costs one unit;
invalid input changes no state. The output has exactly `axis`, `channels` and
`values`: `axis` repeats the requested times and each values row contains the
three temperatures in probe order. Channels are `probe_1_temperature`,
`probe_2_temperature`, `probe_3_temperature`, all in °C. Fixed normalization
scales are `[20, 20, 20]` °C. Independent Gaussian observation noise has standard
deviation `[0.04, 0.04, 0.04]` °C, without clipping; there is no process noise.
The initial-time observation can be noisy even though its clean value is known.

The operator API is `World(seed)`, `describe()`, `validate(spec)`, `cost(spec)`,
`run(spec, noise_key=...)`, and `panel(panel_seed, kind, count=8)`. Seeds must be
integers in `[0, 2**63−1]`; booleans are rejected. `noise_key=None` selects clean
output for private verification. A string of at most 256 characters selects
noise reproducibly via the instance, key and canonical experiment. Reusing that
combination repeats the same observation; fresh keys create independent draws.
Panels are operator-only, support `development`, `conditions`, `interventions`,
and accept integer counts from 1 to 64. Conditions change initial/boundary/
ambient temperatures and observation times/positions. Intervention panels use
adjacent control/treatment experiments varying flow direction, cooling or source
placement. No panel outcome is supplied by `describe()`.

An experiment ready to submit is in [examples/experiment.json](examples/experiment.json).
For a cooling contrast, start at 40 °C with 20 °C endpoints and ambient, remove
the heaters, and compare `cooling=0` against `cooling=2`. For a directional
transport contrast, hold a source near x=0.3 and compare `flow=-0.8` with
`flow=0.8`. These are public experimental suggestions, not hidden test cases.

A feasible 12–16 experiment investigation can allocate several spatial heating
experiments at zero flow, mirrored sources to test uniform versus layered
transport, signed-flow pairs, and source-free cooling contrasts. Early samples
constrain local heating and diffusion, while late samples constrain propagation
and loss. Moving probes around a suspected interface improves spatial evidence.
Hold back a few rounds to test predictions from competing models. Weak layer
contrast can make interface location poorly identifiable; an accurate predictor
alone does not prove a unique mechanism. This design target is not an empirical
claim that every agent identifies every apparatus within that budget.

The numerical kernel discretizes space and propagates the resulting linear
system exactly in time. Tests compare it with continuum limits and an independent
ODE integrator; spatial error remains. This prototype has not established real
device validity, difficulty calibration or contamination resistance.

`baseline(records, spec)` uses only recorded public observations: it interpolates
temperatures in space and time from up to three experiments closest in public
controls and source profile. With no usable observations it predicts the initial
temperature. Records have `{"spec": ..., "observation": ...}` form; malformed
records are ignored. This baseline is deliberately modest and does not inspect
a `World` instance. [examples/public_predictor.py](examples/public_predictor.py)
shows a dependency-free frozen-predictor interface.

From the repository root, run `python -m unittest discover -s env/heat_transport/tests -p 'test_*.py'`.
