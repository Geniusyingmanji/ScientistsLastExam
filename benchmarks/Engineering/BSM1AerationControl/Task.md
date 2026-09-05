# BSM1AerationControl — robust aeration and recycle control

Implement `make_aeration_controller(problem)`. It must return a stateful callable receiving one
observation mapping per 30-minute interval and returning finite `kla_per_hour` and
`internal_recycle` actions inside their published bounds.

The trusted deterministic plant is a five-state ASM1-inspired continuously stirred activated-
sludge model with substrate oxidation, nitrification, denitrification, oxygen transfer, biomass
dynamics and time-varying influent. The controller observes the current state, flow ratio and
influent ammonia but never the future trajectory or sealed plant state.

Flow-weighted mean ammonia, total nitrogen and COD-proxy limits are hard gates. Among feasible policies,
`combined_score` rewards lower effluent burden, upper-decile ammonia, time-priced aeration/recycle energy and action variation above
the shipped dissolved-oxygen PI baseline. A truth-blind oxygen mass-balance feed-forward/feedback controller defines 1.0;
scores are uncapped. Storm loading, dissolved-oxygen sensor bias and actuator loss are confined to
held-out diagnostics.

This benchmark preserves the principal feedback and energy/water-quality conflict but is not the
official MATLAB/Simulink BSM1 implementation. Admission requires independent trajectory matching
against IWA BSM1 before any process-engineering claim.

Use deterministic NumPy/SciPy/standard-library CPU code only. Do not access the network, create
processes, or read `verification/` and `frontier_eval/`.

References: IWA/COST Benchmark Simulation Model No. 1 general description (2008); Vlad et al.,
*IFAC Proceedings Volumes* 44(1), 6917–6922 (2011), doi:10.3182/20110828-6-IT-1002.01664.

## Complete public input contract

Numeric values below are the first public example; per-instance arrays and coefficients vary.
All keys and shapes are part of the contract; forecasts contain exactly `horizon_steps` samples.

| Key | Type, shape or meaning |
|---|---|
| `sample_period_hours` | 0.5 |
| `horizon_steps` | 144 |
| `observation_keys` | array [9] |
| `action_keys` | array [2]; ['kla_per_hour', 'internal_recycle'] |
| `action_bounds` | mapping; fields listed below |
| `action_bounds.kla_per_hour` | array [2]; [0.0, 12.0] |
| `action_bounds.internal_recycle` | array [2]; [0.0, 1.0] |
| `effluent_limits` | mapping; fields listed below |
| `effluent_limits.mean_ammonia_mg_l` | 20.0 |
| `effluent_limits.mean_total_nitrogen_mg_l` | 60.0 |
| `effluent_limits.mean_cod_proxy_mg_l` | 130.0 |
| `model` | five-state ASM1-inspired continuously stirred reactor; deterministic Euler integration with 3-minute internal steps |

Each observation contains scalar `substrate_mg_l`, `ammonia_mg_l`, `nitrate_mg_l`, `dissolved_oxygen_mg_l`, `biomass_mg_l`, `flow_ratio` and `influent_ammonia_mg_l`. The first five are the current reactor state (oxygen may be biased). Return scalar `kla_per_hour` and `internal_recycle`; the action is held for 0.5 hours, with ten internal Euler steps. The deterministic reduced kinetics use Monod rates `r_het=.0063*X*S/(24+S)*O/(.38+O)`, `r_nit=.0055*X*NH/(1.8+NH)*O/(.62+O)`, `r_den=.012*X*S/(16+S)*NO/(.9+NO)*(1-O/(1.25+O))`. Oxygen balance is `.24*kLa*(8-O)-.15*r_het-.30*r_nit-.01*flow_ratio*O`. The model retains bounded state projection as a screening approximation, not official ASM1.

## 关系与区别 / Relationship to nearby tasks

ResilientPumpScheduling returns an open-loop water schedule, BOPTESTSupervisoryControl returns a building controller, and CatalystDeactivationLab infers reaction behavior. Here the artifact is wastewater observation-to-action feedback under a five-state reactor approximation.

## Admission and reference scope

This package remains **candidate**. The metadata difficulty is a target, not a certified result. The runnable reference uses public inputs only. Local shortcut and ablation diagnostics are recorded in `references/known_best.md`; they do not replace clean Linux sandbox replay, independent domain review, Frontier-Eng overlap review or a frozen frontier-model calibration draw.

### Current reference and remaining difficulty

Oxygen mass-balance feed-forward and dissolved-oxygen feedback with full recycle. Ten internal integration substeps replace the coarse control-period Euler step. The reference accounts for observed oxygen demand; the constant-action sweep remains an explicit admission probe, not a certificate of expert-level difficulty. The optimization reference defines 1 by construction; a discovery reference is evaluated against the fixed recovery ceiling. Neither fact certifies difficulty.

### Dynamic operating conditions and objective

Observation keys also include scalar `electricity_price_ratio` and `aeration_availability`.
The price is 4.0 during hours 16–21 of each day and 0.8 otherwise. Availability is 0.35 during a
four-hour daily compressor derating interval and 1.0 otherwise; its phase is not supplied ahead
of time. Actual kLa is command × observed availability × held-out actuator factor. Concentrated
return-flow ammonia pulses occur at hidden times independently of the smooth daily flow.
The daily ammonia scale is 27 mg/L before pulses; this leaves the shipped baseline feasible
under derating without relaxing the public effluent limits.

After warmup, S, NH and NO means are flow weighted. Let NH_tail be the arithmetic mean of the
largest ceil(0.1*n) ammonia concentrations. Cost is `4*NH + 2*NH_tail + 1.35*(NH+NO) + .16*S
+ mean(price*(.04*kLa_command**2 + 1.45*recycle**2)) + .28*action_variation`.
`problem.objective` describes this objective. The diagnostic `upper_decile_ammonia_mg_l`
reports NH_tail. These are transparent synthetic operating assumptions, not official BSM1
compliance criteria. A fixed-action scan remains mandatory: the present version still has a
strong constant-action shortcut and is not certified as expert difficulty.
