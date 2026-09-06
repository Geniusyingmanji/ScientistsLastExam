# FedBatchBioprocessDesign — robust feed and induction scheduling

## Question and nearest tasks

Design a three-stage feed profile, induction time, and harvest time for a fed-batch culture with
substrate limitation, overflow byproduct inhibition, induction burden, and volume constraints.
Unlike ChemicalProcess/DistillationColumnDesign, this is a dynamic biological reactor. All
kinetics are supplied, so the output is a design and the task is optimization, not discovery.

## Interface

Implement design_process(problem) and return exactly:

    {"feed_rates": [0.05, 0.14, 0.10], "induction_time_h": 12.0, "harvest_time_h": 22.0}

Problem keys are horizon_h, segment_boundaries_h, feed_rate_bounds_lph, feed_substrate_gpl,
induction_time_bounds_h, harvest_time_bounds_h, initial_state, maximum_volume_l,
maximum_acetate_gpl, minimum_final_biomass_g, and kinetics. The kinetics mapping contains mu_max,
kla_per_h, and induction_burden.

There must be exactly three bounded feed rates. The trusted simulator recomputes the trajectory.
Utility is the worst productivity across nominal, growth-rate-shifted, and oxygen-transfer-shifted
conditions; any volume, acetate, or terminal biomass violation gives zero in that condition.
Score is clipped between the fixed constant-feed baseline (0) and a bounded robust grid witness
(1). Feed concentration, capacity, initial state, strain kinetics and oxygen transfer vary across
instances; held-out strain/reactor parameters remain evaluator-only.

This is a reduced-order process simulator, not a claim about a named production strain.

## Public process model and units

`initial_state` is `[X, S, A, P, V]`: biomass, substrate, acetate and product
concentrations in g/L, followed by liquid volume in L. Time is in h and feed F is in L/h.
The state is a reduced phenomenological model; coefficients below are benchmark assumptions,
not measured constants for a named strain. The supplied `mu_max` has units 1/h,
`kla_per_h` has units 1/h, and `induction_burden` is dimensionless.

For each scenario `(m, o)` in `[(1, 1), (0.9, 0.85), (1.08, 0.8)]`, let
`I = 1` at or after `induction_time_h` and zero beforehand. For evaluating the RHS only,
replace negative state components with zero. With the current feed segment's F:

```text
mu = mu_max*m * S/(0.4 + S) / (1 + A/3.0) * (1 - induction_burden*I)
q = mu/0.52
q_cap = 0.52*o*clip(kla_per_h/180.0, 0.65, 1.25)
q_overflow = max(0, q - q_cap)
q_productive = max(0, q - q_overflow)
dX/dt = mu*X - F*X/V
dS/dt = F*feed_substrate_gpl/V - q*X - F*S/V
dA/dt = 0.55*q_overflow*X - F*A/V
dP/dt = 0.12*q_productive*X*I - F*P/V
dV/dt = F
```

Use explicit forward Euler with a step of 0.04 h, shortened only on the last step to
reach `harvest_time_h`. Start at t=0. Select the feed segment using right-sided search
on `segment_boundaries_h[1:]`, capped at index 2; compare induction time against the
step's start time. This discrete simulator, including boundary conventions, defines the
frozen numerical objective. No independent integrator agreement is claimed yet.
Any nonfinite state or component below -0.1 terminates that scenario with utility zero.
At every completed step record the maximum acetate concentration. A scenario is feasible
only if final V <= `maximum_volume_l` + 1e-6, maximum A <= `maximum_acetate_gpl`,
and final X*V >= `minimum_final_biomass_g`.

Scenario utility is final P*V divided by harvest time (g/h); an infeasible scenario gets
zero. Robust utility U is the minimum over the three public scenarios. The baseline uses
feeds `[0.10, 0.10, 0.10]`, induction 10 h, harvest 20 h. The reference searches the 54
combinations of feed rates in `{0.05, 0.14, 0.23}^3`, induction in `{7, 12}` h, and harvest
22 h. Both are recomputed for the current public problem. Score is
`clip((U-U_baseline)/max(1e-12, U_reference-U_baseline), 0, 1)`.
`valid` and `feasibility_rate` currently describe submission-contract validity; physical
constraint violations give zero utility and are not represented by these two fields.
