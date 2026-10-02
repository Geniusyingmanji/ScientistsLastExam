# Spin echo: registered experimental classical world

`spin_echo` is the twelfth registered world, available only through explicit
selection. `World` exposes normalized mean magnetization x/y/z over at most
250 ms, with known instantaneous rotations and a uniform frequency shift.
Source and this document are operator-only; `World.describe()` is the public
instrument contract. It is outside the completed GPT cohorts and the audited
seven-world null bank. Registration does not promote its evidence or difficulty.

The scientific opportunity is to design interventions that distinguish a drop
in ensemble transverse signal caused by static frequency differences from loss
under phenomenological transverse damping. Finite mean-vector measurements do
not uniquely identify microscopic structure. The prototype does not establish
task difficulty, contamination resistance, a discovery rate, or quantum physics
discovery.

## Assigned instrument and private dynamics

Every experiment freshly assigns one initial vector, of norm at most 1, to all
subensembles. For component j, let `u_j = Mx_j + i My_j`. Between pulses the
private implementation uses

```
u_j(t + dt) = u_j(t) exp[(-R2 + i 2π (f_j + detuning_hz)) dt_seconds]
Mz_j(t + dt) = Mz_j(t)
```

There are 1–9 fixed frequencies with positive weights summing to 1. The observed
clean vector is their weighted mean. This finite discrete ensemble can beat and
revive. It is not a continuous Gaussian frequency distribution or a generic
irreversible free-induction decay. Static frequencies are constant through all
pulses and waits within an instance. R2 is common to all components, nonnegative,
and acts on instantaneous laboratory-frame transverse components between ideal
pulses. The norm is contractive between pulses and preserved by pulses.

A pulse actively rotates every component, using the right-hand rule about
`n = (cos(phase_rad), sin(phase_rad), 0)` by `angle_rad`. Positive detuning rotates
+x toward +y. Longitudinal recovery is set to zero (R1=0); waiting z is therefore
constant. Storing a component along z prevents its modeled transverse loss
during that wait. This is an assigned short-window simplification, not a
mechanism to discover. An all-zero initial vector remains zero under every
allowed wait and rotation; it has no clean identification information.

The generator has three private operator strata: static frequency spread with
R2=0, one frequency with positive R2, and spread plus positive R2. The default
stratum uses a separate hashed RNG stream. Spread ensembles have 5, 7 or 9
components with random positive normalized weights, a center in [-10,10] Hz and
a weighted standard deviation in [8,20] Hz. Irreversible and mixed rates are in
[5,14] and [3,12] per second, respectively. Generation has no rejection loop or
outcome-based selection. The broad validated kernel domain allows frequencies
in [-120,120] Hz, 1–9 components and R2 in [0,40] per second. It is wider than the
generated-world domain. Strata and ranges are not in the public description.

Observations add independent, unclipped Gaussian readout noise of standard
deviation 0.002 to each x/y/z coordinate, including time zero and pulse
timestamps. The noise is additive classical instrument noise, not process noise
or quantum shot noise. Noisy vectors can exceed the clean norm bound.

## Public protocol

Required fields are `initial_magnetization` (three real values, Euclidean norm
at most 1 with 1e-12 floating tolerance) and `times_ms` (1–129 strictly increasing
values in [0,250]). Optional fields are `detuning_hz` in [-40,40], default 0, and
`pulses`, default an empty list. Each of at most 12 pulses has exactly
`time_ms`, `angle_rad` in [-2π,2π], and `phase_rad` in [-π,π]. The first pulse is
at least 0.1 ms; all pulse times are at or before the last sample and separated
by at least 0.1 ms, with 1e-12 rounding tolerance. Zero-time and simultaneous
pulses are rejected. The initial vector is specified directly by preparation.

Samples exactly at pulse times are **after** the pulse. Times just before and
after a pulse are separate, ordered observations. Extra sample times do not
change the trajectory; the propagator evaluates from pulse-segment anchors.
Time zero is optional. A one-row time-zero experiment without pulses is valid,
but only observes the assigned preparation plus readout noise. Booleans,
nonfinite values, unknown fields, oversized lists and unordered or duplicate
times fail validation. Cost is
`8 + n_samples + 3*n_pulses + ceil(last_time_ms/25)`, at most 183. A call needs at
most 141 free propagations and 12 rotations over at most 9 components.

`World(seed)` exposes `describe`, `validate`, `cost`, `run`, and `panel`.
`run(spec, noise_key="...")` provides reproducible Gaussian noisy observations
for a key. The owning task must assign a fresh key per new experiment; replaying
the same key and canonical spec intentionally replays the observation. Omitted
or null `noise_key` returns clean values for trusted diagnostics only. Keys are
strings of at most 256 characters. Returned payloads contain only `axis`,
`channels`, and `values`. `_operator_stratum` is a private constructor override
for balanced author diagnostics, never a candidate control. The clean API,
source, seeds, parameters, panels and references must remain operator-owned.

`panel(panel_seed, kind, count=8)` creates parameter-blind fixed schedules;
`kind` is `development`, `conditions` or `interventions`. It does not execute
experiments. Panels do not certify a
structural holdout. They include assigned facts, which the shared public
eligibility policy excludes as described below.

## Public claim eligibility and integration scope

The registered version is `spin_echo-0.1.0-experimental`; task catalog 0.1.6
and eligibility protocol 0.9 add it without changing older scientific rules.
Paired claims use matched readout times. Readouts must be at least **1 ms**
after preparation and each pulse at or before the readout; exact pulse times
and t0 are excluded. The 1 ms lag is a fixed administrative pilot guard, not a
physical detection guarantee or a fitted hidden time constant. Only this world
allows 12 events in that policy; older event limits are unchanged.

The policy rejects every channel if either arm starts from a zero vector.
If all pulses at or before the readout have integer-pi angles (within 1e-12 rad),
z is fixed by initial z and known sign flips, so it is excluded. Under the same
pulse prefix, an initial vector with x=y=0 fixes every coordinate, which excludes
all channels. A future non-pi pulse cannot retroactively make earlier z eligible.
For a pure-z preparation, the first non-pi pulse creates transverse response
but its z projection remains the known initial z times calibrated sign/cosine
factors. A later non-pi pulse can mix the intervening unknown transverse
evolution into z. The guard tracks these public dependencies and excludes z
until that can occur. Once z depends on that response, subsequent waiting alone
does not make it known. The integer-pi tolerance is a floating-point policy
convention, not exact mathematical equivalence.

These exclusions are not an algebraically complete proof that every remaining
contrast requires learned dynamics. Public detuning and ideal rotations can
still supply trivial transformations; scientific evidence review remains
necessary. Full event-time vectors can contain unknown pre-pulse state even
though the rotation rule is known; excluding event boundaries is conservative.
Prediction RMSE remains an instrumentation-inclusive score, not a discovery
certificate. Prospective observations use unclipped additive Gaussian SD 0.002
and zero noise-mean bias bound. Only the declared control fields and public
axis/channels/values may enter evidence packets.

## Baseline and independent numerical reference

`baseline(records, spec)` uses public records only. Its zero-record hypothesis
applies known detuning and ideal rotations with no unknown between-pulse
evolution. With records, it selects the nearest initial/control/pulse feature
vector, interpolates that record's residual relative to the known-control
hypothesis, and adds it to the query hypothesis. It restores assigned time-zero
preparation. It has no private parameter access, fitting, simulator calls, family
menu or mechanism inference. It can fail at new pulses, across pulse
discontinuities, outside the source time range, or on different free evolution.
It is a weak public empirical comparator, not an oracle.

`reference.py` imports neither the production propagator, pulse rotation nor
validator. It offers independently written complex-sum no-pulse FID and one
pi-x echo formulas. For general pulses it integrates the Cartesian Bloch ODE
with DOP853 and applies rotations using matrix exponentials. Trusted canonical
specs are required. The reference shares the declared mathematical assumptions
and input parameters, so numerical agreement checks implementation consistency,
not experimental truth or uniqueness of those assumptions.

## Frozen author verification

The external campaign plan and pre-execution clarification fix six development
seeds and one batch of 112 top-level trajectories, including **all** production
physics fixtures and independent references. Hard limits are 120 attempts,
45 process CPU seconds and 180 wall seconds. Each began/ended attempt, including
expected or unexpected failures, is durably appended to a ledger. Timeout and
CPU exits preserve partial reports. A campaign-level exclusive start file
prevents accidental retry. No model API calls are used. No seeds or difficulty
parameters may be changed based on the outcomes.

The fixed batch includes FID, single echo, general pulse ODE agreement, norm
contraction, sample-grid invariance, legal control/parameter corners, rotation
composition, a semigroup split, zero-state invariance, three injected failures,
key replay/fresh noise, and public-record baseline predictions. Analytic absolute
tolerance is 5e-12; ODE tolerance is 2e-8; norm tolerance is 2e-12. Diagnostic
baseline errors include all x/y/z coordinates at positive times; only the
assigned time-zero row is excluded. Waiting-constant z and known pulse responses
remain included. They can make aggregate errors look easier; this author
diagnostic is not a discovery score or an eligibility mask. Every 0/1/3-record
prediction is retained, including regressions.

The constructed ambiguity pair uses symmetric two-frequency components with
`f = acos(exp(-8*0.020))/(2π*0.020)` and no damping, versus one zero-frequency
component with R2=8/s. They match at 0 and 20 ms; a narrow window, a broader
window and a pi-x echo are compared without tuning a discrimination threshold.
The static construction is **outside** generated static strata: it has two
components and spread below 8 Hz. It illustrates the broader kernel's
limited-design ambiguity, not numerically matched generated worlds. Splitting
one component into duplicate frequencies with split weights yields an exactly
equivalent ensemble; two fixed complex protocols test that implementation fact.
A single echo distinguishes these constructed accounts, not all microscopic
mechanisms.

Run only the contract fixtures without a dynamics budget:

```
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest -p no:cacheprovider env/spin_echo/tests
```

Those fixtures never import or instantiate Kernel/World or call the independent
references; they validate protocols, compile source, check import boundaries,
and evaluate synthetic public-record baseline cases. The completed author batch
belongs to its frozen prototype source and private plan. Do not rerun it from the integrated revision; this historical command
identifies its entrypoint:

```
PYTHONDONTWRITEBYTECODE=1 python3 -B -m env.spin_echo.calibrate --plan /absolute/path/plan.json --output /absolute/path/new-run-directory
```

Author results remain separate private artifacts under the central calibration
area (`spin-echo-author`). The frozen independent physical review is under
`spin-echo-independent-review`: 73 independently budgeted entries, including
nested World/kernel entries, 69 successes, four expected failures, and 109
passing checks; maximum matrix-reference error 1.60e-13. Its conclusion is
same-family/provisional and limited to the declared finite ideal construction.
The integration implementer subsequently changed roles and is not an independent
reviewer of these shared adapters. Integration tests are separate engineering
smoke checks; they do not add observations to the 112-call author research or
73-entry independent review. Raw private manifests, seeds and trajectories are
not published with this documentation.

## Physical sources and limits

E. L. Hahn's original [Spin Echoes, Physical Review 80, 580 (1950)](https://journals.aps.org/pr/abstract/10.1103/PhysRev.80.580)
describes pulse-generated constructive interference in an ensemble with static
frequency differences and a Bloch treatment. Only the publisher's abstract was
accessible in this verification; no inaccessible full-text claim is attributed.

Official MIT [Gradient and Spin Echoes notes](https://web.mit.edu/22.920/www/lecture4/lecture04.html)
explain refocusing static frequency variation with transverse pi pulses, pulse
phase effects and longitudinal storage. The ideal refocusing here follows that
classical account; its phenomenological transverse loss is not reversed.

Official MIT [Rotating Frame and RF Pulses notes](https://web.mit.edu/22.920/www/lecture2/lecture02.html)
provide the rotating-frame and Bloch-equation context. The prototype deliberately
excludes finite-width and off-resonance pulse effects. Its R1=0 model, discrete
frequencies, bounded controls and Gaussian readout are explicit simplifications.
It is not a calibrated NMR/MRI scanner; diffusion, exchange, motion, interaction
spectroscopy, RF imperfections, heating and quantum projective measurements are
outside scope. No tissue or material inference is supported by this synthetic
implementation.
