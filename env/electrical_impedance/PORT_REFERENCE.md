# Public-apparatus port reference

`port_reference.py` predicts terminal voltage using one public noisy source
record and the public query controls. It has no World, seed, private label,
component parameter, circuit menu or target input. It imports only the public
protocol and NumPy. The existing weak baseline remains unchanged.

For the disclosed source resistance `Rs`, parallel load `RL`, source peak
voltage `a`, and complex terminal phasor `z`, the reference computes

```
Y_hat = (a/z - 1)/Rs - 1/RL
z_hat_new = a_new / (1 + Rs_new*(1/RL_new + Y_hat_interp)).
```

It interpolates real and imaginary admittance independently and linearly in
log frequency. Admittance is in siemens, resistances in ohms and voltages in
peak volts under `Re(z exp(+i 2 pi f t))`. There is no parameter fitting,
smoothing, hidden circuit family or passivity projection. Inversion can amplify
and bias noise. The result is a point prediction, without calibrated uncertainty.

`port_reference(records, spec)` returns a values matrix.
`predict_with_diagnostics(records, spec)` additionally returns inversion and
reconstruction diagnostics. Exactly one source record is required. Invalid
records, nonfinite calculations, query frequencies outside the observed closed
band, source phasors with magnitude at or below 0.005 V, and near-cancelled
reconstruction denominators raise typed `ReferenceFailure`. The entire source
arm fails on a near-zero source row; no data are dropped and no other method
is substituted. Finite negative estimated conductance or voltage exceeding the
passive terminal bound remains visible in the output and diagnostics.

The accompanying engineering design was authored by the original electrical
kernel author, so it is **author-informed engineering, not independent review**.
Its proposed study uses the same label-selected instances for a paired source
record comparison: a single 65-frequency noisy acquisition supplies both the
full record and a fixed eight-row subset with shared noise. Actual acquisition
cost is **142 units** per instance. Sparse cost **28 units is counterfactual
visible-data cost**, not a separate cheaper acquisition in that run. The arms
have unequal row budgets; this is not a budget-scaling study.

Primary targets lie between source frequencies and keep the source apparatus
unchanged. Separate targets change source resistance, load or amplitude at
already observed frequencies. Success on those latter targets measures use of
known apparatus algebra. It does not establish a learned internal frequency
law. In particular, both the port reference and weak baseline should agree on
the publicly given amplitude scaling at source knots.

Private central artifacts under `calibration/electrical-port-reference/` retain
the original plan, execution-order addendum, label selection, pure fixtures and
trusted driver. The driver must acquire all sources, persist every planned
method/arm/query prediction or failure and durably seal their hashes **before
any clean target**. It uses a permanent exclusive execution claim, exclusive
output files and a 48-attempt World.run cap. The actual study has cumulative
60 CPU-second and 180 wall-second limits including acquisition, prediction,
targets and I/O. A cutoff preserves returned data and all planned denominators;
no additional scientific calls occur during persistence-only cleanup, and any
cleanup overrun is reported. It has no retry/resume path.

Pure tests use synthetic public phasors and a synthetic driver instrument,
without World trajectories. Label-only selection and code freezing are separate
from actual execution; a freeze alone does not authorize or establish a study
result. No empirical performance result is claimed by this document.

This reference complements the weak comparator. It does not replace shared
scores or old panels, identify internal topology, demonstrate autonomous
discovery or contamination resistance, establish equal-budget superiority, or
fit a scaling law. Full terminal behavior itself need not uniquely determine
internal circuit structure.
