# Climate response laboratory

Choose an annual external heating history and measure surface temperature and
net energy uptake. Each request starts from a fresh zero-anomaly reference;
properties of the sealed apparatus stay fixed. A short pulse, a long step, an
amplitude comparison and cooling after switch-off can ask different questions.
The candidate sees an apparatus contract, not equations or a family menu.

```python
from env.climate_response.world import World
world = World(123)  # Operator only: never expose seed or kernel to the agent.
spec = {"forcing_w_m2": [4.0]*20 + [0.0]*20,
        "times_years": [1, 2, 5, 10, 20, 21, 25, 30, 40]}
result = world.run(spec, noise_key="independent-measurement-key")
```

`forcing_w_m2` contains 1–160 annual commands in [−1, 8]. Optional
`times_years` selects whole-year endpoints; its last value equals the history
length. An endpoint uses the forcing during the year just completed, before the
next switch. Channels are `surface_temperature_anomaly_k` and
`toa_imbalance_w_m2`; positive imbalance means net uptake. Independent Gaussian
readout standard deviations are 0.06 K and 0.14 W m⁻². Outputs are not clipped.
No time-zero measurements or assigned positive-time response values are present.

Cost is 8 + measured rows + ceil(history years / 10), at most 184. Removing sample
rows does not change the clean trajectory. Repeating a call creates a fresh
preparation; it does not continue the previous climate experiment.

The operator kernel contains two-reservoir, nonlinear-feedback and
three-reservoir variants. They support different effective descriptions;
matching a variant label is not the research objective or grading rule.
Numerical checks compare independent flux-form DOP853 integration with matrix
exponentials or RK4, check conservative exchange and linear superposition, and
cover annual switches, resets, schema and information separation. Run:

```
python -m unittest discover -s env/climate_response/tests -p 'test_*.py'
```

`baseline` selects the nearest public observed forcing history and interpolates
its measured outputs, or returns zero with no data. It accesses no generator,
parameters or kernel. This weak baseline is not a difficulty calibration.
The package is experimental; registration and campaign membership are explicit
shared-runner decisions. See `SCIENTIFIC_NOTES.md` for scientific limits.
