# BatteryFastCharging — robust lithium-ion charging-protocol design

## Scientific setting

Fast charging is not simply a matter of selecting the largest admissible current. A high current
can raise terminal voltage, generate heat, reduce charge-transfer efficiency and accelerate
ageing. The operating envelope also changes with initial state of charge, ambient temperature,
internal resistance and available capacity. A protocol that is aggressive for one cell may become
unsafe or poor-performing for a nearby cell manufactured with slightly different properties.

In this task you design a short, open-loop charging-current protocol for a simplified lithium-ion
cell. The trusted evaluator uses a deterministic reduced electro-thermal ageing simulator. It has
a nonlinear voltage response and short-memory polarization: earlier current choices can affect
later voltage headroom. The task is therefore to balance early charge delivery against a gradual
taper near the high-state-of-charge region, while preserving a safety margin for cell-to-cell
variation.

This is a scientific optimization benchmark, not a prescription for charging a real battery. The
simulator is deliberately reduced-order and does not model all electrochemical or safety effects.

## Entrypoint and required result

Only edit `solution.py` and preserve this callable:

```python
def charge_policy(problem):
    return currents
```

Return a finite NumPy-like vector of exactly `problem["time_steps"]` currents. Each element is a
C-rate and must lie in `[0, problem["max_current_c"]]`. The supplied horizon uses sixteen equal
stages. Your policy may use the public `problem` fields to choose a different schedule for a
different nominal cell, but it must return the complete schedule at once; it receives no
within-charge measurements or feedback callback.

Every public field is listed here:

| Field | Meaning |
| --- | --- |
| `time_steps` | Required number of current stages. |
| `dt_hours` | Duration of each stage in hours. |
| `initial_soc` | State of charge at the start of the protocol. |
| `ambient_celsius` | Ambient temperature in degrees Celsius. |
| `internal_resistance` | Nominal internal-resistance parameter. |
| `relative_capacity` | Nominal capacity relative to the task reference cell. |
| `max_current_c` | Maximum permitted C-rate for any stage. |
| `max_voltage` | Terminal-voltage safety limit. |
| `max_temperature_celsius` | Temperature safety limit. |
| `target_soc` | Public operating target for the charge session. |

## Objective and safety constraints

The evaluator rewards delivered charge and useful progress toward a high state of charge. It
penalizes accelerated degradation and excessive thermal excursion. A candidate is invalid if it
returns a malformed schedule, a non-finite value, a wrong number of stages, or a current outside
the public range.

Safety is strict. Nominal cell parameters are public, but the trusted evaluator also tests a
small fixed family of bounded, unobserved manufacturing variants. A schedule that crosses either
the public voltage or temperature limit for any such variant is infeasible for that nominal cell.
You should therefore design a robust taper rather than optimize only for the nominal parameters.
The values, identities and ordering of these variants are evaluator-only.

## Evaluation

Scores are normalized per cell against a conservative constant-current baseline, whose aggregate
score is zero. A reproducible, physics-aware tapered reference policy defines the unit-scale
anchor; it is a feasible comparison witness, not a claimed globally optimal or clinically approved
charging algorithm. The main development score combines average utility with lower-tail utility
across the hidden cell variants, so a schedule that works only on an easy variant is disadvantaged.

Separate held-out nominal cells probe transfer to new temperature, resistance, capacity and
initial-SOC regimes. Held-out scores and per-variant details are reported by the trusted evaluator
but must not be hard-coded or assumed by your policy.

## Rules

- Use deterministic CPU Python with the standard library, NumPy and SciPy only.
- Do not access the network, start processes, read `verification/`, or read `frontier_eval/`.
- Do not assume a hidden-cell order, latent parameter values, reference-current schedule or
  held-out regime.
- Preserve the function name `charge_policy(problem)` and return the schedule directly; do not
  print, save files or rely on mutable global state.

The reduced-order modeling motivation follows Doyle, Fuller and Newman, *Modeling of
Galvanostatic Charge and Discharge of the Lithium/Polymer/Insertion Cell*, *Journal of The
Electrochemical Society* 140(6), 1993, DOI `10.1149/1.2221597`.
