# Isotope Flux Identifiability

Implement `infer_fluxes(problem, trace)` returning exactly
`{"abstain": bool, "fluxes": {"net": v, "exchange_total": x}, "confidence": number}`.
Refusal requires an empty flux dictionary. Otherwise finite real v in [0,1.2]
and x in [0,2] are required. Booleans are not numbers. Confidence in [0,1]
predicts mechanism quality >=0.5 or a correct refusal. Extra keys, individual
exchange-branch claims, nonfinite values and wrong containers are invalid.

The reduced carbon-balanced network has one-carbon A and two-carbon B,C:
feed -> A; 2A -> B; B -> C; two parallel C -> B routes; C -> drain.
`reaction_ids`, `pool_ids`, `stoichiometry` (pool rows, reaction columns),
`atom_transitions` (zero-based atom positions), `flux_parameterization`,
`identifiable_combinations`, `pool_sizes=[1,1.5,2]` and `flux_bounds` are public.
Reaction fluxes in amount/time units are `[2*v,v,v+x,x1,x2,v]`, x=x1+x2,
with any nonnegative split x1,x2. This exactly satisfies S*f=0. Pool sizes
are molecular amounts, not carbon counts. Reverse routes have identical atom
mapping; **their separate fluxes are structurally unidentifiable**. Only their
sum is scored. This is a cyclic reversible condensation network, not a general
metabolic reconstruction or an implementation of the full EMU framework.

Every pool starts completely unlabeled. A feed step has labeled-carbon fraction
u, from `tracer_menu={"full":1,"half":0.5}`. Its A labeling fraction is
`q(t)=u*(1-exp(-2*v*t/pool_A))`. Condensation independently samples two molecules
from the well-mixed A pool. Ordered B/C isotopomers are [00,01,10,11], with
source `g=[(1-q)^2,(1-q)*q,q*(1-q),q^2]`. Exact balance equations are

`dB/dt = (v*g + x*C - (v+x)*B)/pool_B`

`dC/dt = ((v+x)*B - (v+x)*C)/pool_C`.

B,C are four-vectors normalized to one, initially [1,0,0,0]. The oracle uses
adaptive RK45 (relative tolerance 2e-8, absolute 2e-10). Observations aggregate
[00,01+10,11] into M+0,M+1,M+2. `observation_model` specifies independent
multinomial counts, `ions_per_pool=10000`. Covariance of observed fractions is
`(diag(p)-p*p.T)/10000`, with independent B/C and separate samples.

Call `trace(tracer_id,time_ids)` with a menu string and a nonempty list of
distinct integer indices into `sampling_times=[0.5,1,2,4,8,16]` (time units).
Return fields: `time_ids` in requested order, `counts` of shape len(time_ids),2,3,
`ions_per_pool`, and `cost=len(time_ids)`. `budget_units=6`; repeated samples
are allowed in separate calls and charged again. Any invalid query or overrun
permanently invalidates the world, even if caught. Initial public inputs and
menus are identical across all worlds. At zero net influx all pools stay
unlabeled for every x; refuse the pair because exchange cannot be recovered.

For supported positive-net worlds mechanism quality is
`max(0,1-mean(abs(estimate-truth)/maximum(truth,0.1))/0.6)` over (v,x).
A supported refusal gets zero; a zero-net refusal gets one; a zero-net claim
gets zero. Normalize development mean q as `max(0,(q-1/3)/(2/3))`, so always
refusing gets exactly zero. Development has two supported worlds and one
zero-net world; held-out has shifted fluxes and the same composition.
`valid` requires all six worlds valid. Sealed metrics report mechanism, false
claim and total claim counts, their ratio, supported coverage, correct refusal,
Brier loss and held-out scientific quality. Invalid worlds earn no credit.
All procedural worlds are repository-visible, not private test data.

Baseline refuses. Input-only reference samples all full-tracer times, uses
three-start bounded nonlinear least squares and a local Jacobian rank check.
This is not a global profile-likelihood certification. Candidate budget is
120 CPU seconds. Independent tests compare full isotopomers to a reduced
mass-balance ODE, but comparison against INCA and external domain review remain
pending; no frontier difficulty or general-network correctness is claimed.

[Antoniewicz et al. (2007)](https://doi.org/10.1016/j.ymben.2006.09.001)
motivates atom-subset balance, and [Young (2014)](https://doi.org/10.1093/bioinformatics/btu015)
describes INCA. No external software/data is redistributed.
Nearest tasks: MetabolicStrainDesign optimizes knockouts with known flux constraints;
ReactionMechanismFitting fits chemical rate models; DemographicSFS infers
population history. Here isotope atom transport limits which flux combinations
can be inferred from budgeted tracer measurements.

The shared `sle.contract_lint` discovery checks apply to this contract.
