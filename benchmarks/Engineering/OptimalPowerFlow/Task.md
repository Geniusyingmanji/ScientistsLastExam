# OptimalPowerFlow — economic dispatch with sealed N-1 security

## Scientific background

DC optimal power flow dispatches generators at minimum quadratic cost while satisfying global
power balance, generator limits, Kirchhoff's laws and transmission ratings. If `theta` denotes
bus voltage angles, each line `(i,j)` carries

```text
flow_ij = susceptance_ij * (theta_i - theta_j),
B theta = generation - demand.
```

A nominally economical dispatch can overload the remaining network after one line trips. Power
systems therefore use security-constrained OPF and the N-1 criterion; nominal economy and
contingency robustness must be reported separately.

## Your task

Implement a network-general dispatch policy:

```python
def solve_opf(n_bus, generator_buses, demand, p_min, p_max,
              cost_quadratic, cost_linear, lines, susceptances, line_limits):
    """Return one finite power output per generator.

    Cost is sum_i cost_quadratic[i] * p[i]^2 + cost_linear[i] * p[i].
    lines[k] = (from_bus, to_bus); all power quantities use consistent units.
    """
```

The dispatch must exactly balance total demand, remain within generator bounds and satisfy all
nominal line ratings. The evaluator calls the same policy on several meshed networks with
different sizes, topologies, costs, load patterns and congestion. Do not hard-code one dispatch.

## Evaluation

`combined_score` is nominal generation-cost improvement above a safe proportional baseline,
normalized by an independently solved convex DC-OPF reference. The trusted evaluator separately
opens every non-islanding line and retains:

- `robustness_score`: N-1 security-constrained economic quality;
- contingency constraint and outage feasibility rates;
- maximum loading and normalized overload;
- held-out-network nominal and robustness scores; and
- nominal and security-constrained reference costs.

Only nominal development cost controls search. All contingency, robustness, held-out and
per-instance metrics are evaluator-only.

## Rules

- Only edit `solution.py`; keep the full `solve_opf` signature.
- Return a finite vector of exact generator count. Values are rejected, not clipped or repaired.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
