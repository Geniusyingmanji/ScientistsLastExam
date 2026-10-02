# Electrical impedance experimental world

This experimental world measures complex terminal voltage across a sealed passive,
stable linear electrical one-port. The public instrument supplies a sinusoidal
source, a known series resistance and a known parallel load. An experiment selects
1–65 frequencies in 2–5000 Hz and returns real and imaginary voltage in volts.
Every frequency is an independent steady state. There is no transient API.

Only `World.describe()` and noisy experimental readouts are candidate-facing.
This directory, including its manifest and scientific notes, is operator material.
The description is identical across private structures and does not reveal a
topology menu, component bounds, sampled values or seeds. Explicit full-description tasks, frequency claims, noise, calibration and public-evidence
adapters are supplied. The separate apparatus_only presentation remains unaudited
and rejects this world. No candidate execution is part of these integration checks.

The observables can support research into frequency dependence, phase, relaxation
scales, resonant behavior and transfer under external loading. They do not uniquely
identify internal circuitry. Public amplitude linearity and known external
voltage-divider effects are instrument facts; reproducing those alone does not
establish an unknown frequency response or mechanism.

`protocol.py` owns controls, units, noise and examples. `kernel.py` constructs
private passive circuits and solves at most 65 linear systems of dimension at
most two. `reference.py` independently evaluates complex impedances.
`baseline.py` uses only public records, transferring amplitude-normalized voltage
from the nearest source/load setting and interpolating in log frequency. It does
not fit a circuit or use hidden parameters. With no records it ignores current
into the sealed box and predicts the known external divider.

The frozen development plan preceded all spectra. Its first execution passed
40 numerical and boundary tests using 24 spectra, including three deliberately
failed work/nonfinite/linear-solve checks. Four fixed development instances used
32 further spectra including independent references; four predeclared ambiguity
comparisons used eight. Total: **64 spectra, 0.280 CPU seconds**, with no unplanned
failure, seed replacement, model API, fitting or candidate run. These resource
figures describe this local development run, not general throughput.

The four development instances contained three double-RC devices, one RLC device
and **no single-RC device**. Explicit numerical fixtures cover all three structures,
but this does not fill the empirical single-RC calibration gap. The development
set is not balanced.

Across 16 fresh queries, the weak baseline's mean RMSE was 0.3158, 0.07594 and
0.04883 V with zero, one and three source records respectively. All denominators
are 16/16. A diagnostic that divides out source amplitude and removes each
quadrature's frequency mean also improved: 0.1291, 0.02673 and 0.02389 in gain
units. This makes the recorded improvement more specific than just reproducing
known amplitude scaling; it is still a small empirical interpolation result,
not an autonomous discovery or difficulty result.

A constructed RC/RLC pair matches exactly at 100 Hz. Across 99.9–100.1 Hz the
largest quadrature difference was 0.00003192 V, against 0.001 V measurement noise.
Across the predeclared broad sweep the largest difference was 0.4859 V. Changing
external load at the matched frequency retained equality to roundoff. A separate
single-branch versus split-parallel-RC construction is analytically equivalent
at every frequency and external setting. Details and limitations are in
[SCIENTIFIC_NOTES.md](SCIENTIFIC_NOTES.md).

Raw spectra, seeds, private plans and failures remain in the central operator
artifact directory `calibration/electrical-impedance-development/` under the
development run's artifact root. They are not published here. The root contains
the pre-probe plan and numerical-conditioning amendment; `run-001/` contains
raw diagnostics, an append-only spectrum log, test XML, source hashes and runtime
counts. This package publishes only aggregate calibration facts.

The independent review supported the bounded numerical instrument and specified
ambiguity examples, while finding registration incomplete at that frozen source
revision. A later, separately recorded implementation added explicit experimental
registration as the eleventh world. This does not revise the earlier review's
not-ready conclusion or change its frozen hashes and failures.

Shared claim policy treats `frequencies_hz` as independent steady states, without
an assigned initial row or temporal lag. A paired claim selects the same row and
voltage channel in both arms; the selected frequencies may differ for a spectral
contrast. An isolated apparatus contrast uses the same frequency. Changing both
frequency and apparatus is a combined contrast. Public amplitude scaling and
known divider transformations do not certify a discovered mechanism.

Fresh public observations receive distinct operator-generated noise keys; the
clean `World.run(..., noise_key=None)` path and keyed replays remain operator-only.
The shared noise contract is unclipped Gaussian with zero bias; calibration has
no initial-value predictor. Evidence packets allow only the four public control
fields and bind their `frequencies_hz` to observation rows. Snapshots can save and
bind frequency predictors without executing them. The existing prospective
mechanism-discrimination schema accepts an unobserved frequency target. Its
regime-transfer gate still requires a changed non-axis apparatus control, so a
frequency-only target is not counted by that particular transfer gate.

Only explicit experimental selection is enabled. Historical model cohorts, the
seven-world audited null bank, score formulas, and older scientific task content
remain unchanged. Existing apparatus projections normalize only deliberate task
catalog and policy revision metadata. Neither integration nor the weak-baseline
smoke run assigns a discovery depth or task-difficulty grade.
