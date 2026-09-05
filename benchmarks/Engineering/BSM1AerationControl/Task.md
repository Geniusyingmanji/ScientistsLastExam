# BSM1AerationControl — robust aeration and recycle control

Implement `make_aeration_controller(problem)`. It must return a stateful callable receiving one
observation mapping per 30-minute interval and returning finite `kla_per_hour` and
`internal_recycle` actions inside their published bounds.

The trusted deterministic plant is a five-state ASM1-inspired continuously stirred activated-
sludge model with substrate oxidation, nitrification, denitrification, oxygen transfer, biomass
dynamics and time-varying influent. The controller observes the current state, flow ratio and
influent ammonia but never the future trajectory or sealed plant state.

Mean ammonia, total nitrogen and COD-proxy limits are hard gates. Among feasible policies,
`combined_score` rewards lower effluent burden, aeration/recycle energy and action variation above
the shipped dissolved-oxygen PI baseline. A truth-blind feed-forward PI controller defines 1.0;
scores are uncapped. Storm loading, dissolved-oxygen sensor bias and actuator loss are confined to
held-out diagnostics.

This benchmark preserves the principal feedback and energy/water-quality conflict but is not the
official MATLAB/Simulink BSM1 implementation. Admission requires independent trajectory matching
against IWA BSM1 before any process-engineering claim.

Use deterministic NumPy/SciPy/standard-library CPU code only. Do not access the network, create
processes, or read `verification/` and `frontier_eval/`.

References: IWA/COST Benchmark Simulation Model No. 1 general description (2008); Vlad et al.,
*IFAC Proceedings Volumes* 44(1), 6917–6922 (2011), doi:10.3182/20110828-6-IT-1002.01664.
