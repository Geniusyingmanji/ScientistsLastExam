# Single Molecule Kinetics

Implement `infer_kinetics(problem, observe)`. Return exactly
`{"abstain": bool, "rates": [k01,k10], "efficiencies": [e0,e1], "confidence": number}`.
On refusal both arrays must be empty. Otherwise rates lie in [0.1,3] per second
and efficiencies in [0.05,0.95]. Confidence is finite in [0,1], the probability
that this claim has mechanism quality at least 0.5 (or this refusal is correct).
Booleans as numbers, extra keys, nesting, NaN and infinity are invalid.

Public problem has `model_family=two_state_instantaneous_poisson`,
`parameter_bounds` as above, `exposure_menu=[0.1,0.2,0.4]` seconds,
`trace_length=400`, `photon_rate=200` photons/second, `budget_units=1600`, and
`detector_model` describing the following model. Every world has identical
initial problem and query menu. Call `observe(exposure, length)` with an exact
menu exposure and integer length 400. It returns `counts` of shape 400,2
(donor,acceptor), `exposure`, and `cost=length*exposure/0.1`. Each independent
trace starts in stationarity. Total cost cannot exceed 1600; any invalid or
excess acquisition permanently invalidates that world even if its exception
is caught. Queries charge exposure, not randomly realized photon counts.

For the two-state continuous-time generator `Q=[[-k01,k01],[k10,-k10]]`,
`P(dt)=expm(Q*dt)`. Conditional on sampled state s, counts are independent
Poisson with means `200*dt*(1-e_s)` and `200*dt*e_s`. These are instantaneous
state emissions scaled by dt, **not integrated emissions across jumps**.
There is no bleaching, background, detector dead time or cross-talk in this
reduced model. All transitions and emissions use independent draws.

Supported worlds have distinct emissions and rates in the public bounds.
Null worlds have one stationary emitter at efficiency 0.5. Alias worlds have
two states with identical efficiency 0.5 and arbitrary switching rates: summing
over latent paths proves their observations are the same iid Poisson process
as null worlds. Refusal is correct for either; no reason-label distinction is
required. Supported worlds are scored under the best simultaneous permutation
of the two rate and efficiency arrays. Mechanism quality is
`max(0,1-(mean(abs(log(k/k_true)))+3*mean(abs(e-e_true)))/1.2)`.
A supported refusal gets zero. An unsupported refusal gets one, a claim zero.
Mean development scientific quality is normalized as `max(0,2*mean-1)`, making
all-refusal and all-null policies exactly zero. There are four development
worlds (two supported, one null, one alias) and four shifted held-out worlds
with the same composition. `valid` requires all eight worlds valid.

Sealed metrics separately report mechanism quality, false claims/total claims
(with max(1,denominator)), counts, supported coverage, unsupported refusal,
confidence Brier loss, and held-out scientific quality. Brier correctness uses
the threshold 0.5 above. Invalid worlds receive no scientific credit.
The repository contains procedural worlds; held-out means excluded from search
score, not secret data. Candidate evaluation budget is 120 CPU seconds.

Baseline refuses without querying. Input-only reference acquires two 0.2-second
traces, checks shot-noise-corrected efficiency variance, then fits a two-state
HMM by two-start Baum–Welch and converts its transition matrix to CTMC rates.
It is a classical reference, not evidence of expert difficulty. This first
implementation has eight worlds, no population hierarchy and no exposure-shift
predictive metric; external ebFRET comparison and stronger calibration are pending.

[van de Meent et al. (2014)](https://doi.org/10.1016/j.bpj.2013.12.055)
motivates hidden-state inference in single-molecule FRET. No external code or
data is redistributed. Nearest tasks: HamiltonianLearning uses quantum
observations; EnzymeKineticsLaw selects bulk rate laws; GeneNetworkIntervention
infers regulation. This task infers classical hidden-state switching from photons.

The shared `sle.contract_lint` discovery checks apply to this contract.
