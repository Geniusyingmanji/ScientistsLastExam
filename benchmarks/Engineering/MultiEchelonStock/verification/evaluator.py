"""Oracle: multi-echelon inventory optimization — minimize cost with service constraint.

3-stage supply chain: factory → warehouse → retailer. Agent sets base-stock levels.
Oracle simulates demand over T periods and computes holding + backorder costs.
"""
import numpy as np

N_STAGES = 3
T_PERIODS = 200
HOLDING_COST = [1.0, 2.0, 5.0]  # per unit per period at each stage
BACKORDER_COST = [10.0, 20.0, 50.0]
LEAD_TIMES = [3, 2, 1]  # periods
SERVICE_TARGET = 0.95

def _simulate(base_stocks, seed=42):
    rng = np.random.default_rng(seed)
    # Demand: Poisson(20) at retailer
    demands = rng.poisson(20, T_PERIODS)
    inventory = [np.zeros(T_PERIODS + max(LEAD_TIMES) + 1) for _ in range(N_STAGES)]
    orders = [np.zeros(T_PERIODS + max(LEAD_TIMES) + 1) for _ in range(N_STAGES)]
    total_cost = 0.0
    backorders_total = 0
    for t in range(T_PERIODS):
        # Retailer (stage 2) faces demand
        for s in range(N_STAGES - 1, -1, -1):
            if s == N_STAGES - 1:
                demand_s = demands[t]
            else:
                demand_s = orders[s + 1][t]
            # Receive shipment from lead time ago
            if t >= LEAD_TIMES[s]:
                inventory[s][t] += orders[s][t - LEAD_TIMES[s]]
            # Fill demand
            filled = min(inventory[s][t], demand_s)
            inventory[s][t] -= filled
            backorder = demand_s - filled
            # Order up to base-stock
            position = inventory[s][t] + sum(orders[s][t-LEAD_TIMES[s]+1:t+1]) if t > 0 else inventory[s][t]
            order = max(0, base_stocks[s] - position)
            orders[s][t] = order
            # Costs
            total_cost += HOLDING_COST[s] * max(inventory[s][t], 0)
            total_cost += BACKORDER_COST[s] * backorder
            if s == N_STAGES - 1:
                backorders_total += (1 if backorder > 0 else 0)
        # Carry inventory
        for s in range(N_STAGES):
            inventory[s][t + 1] = inventory[s][t]
    service_level = 1 - backorders_total / T_PERIODS
    return total_cost / T_PERIODS, service_level

def evaluate(optimize_inventory):
    try:
        base_stocks = np.asarray(optimize_inventory(N_STAGES, LEAD_TIMES, HOLDING_COST,
                                                      BACKORDER_COST, SERVICE_TARGET), dtype=float)
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": str(e), "feasibility_rate": 0.0}
    if base_stocks.shape != (N_STAGES,):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "need 3 values", "feasibility_rate": 0.0}
    base_stocks = np.clip(base_stocks, 0, 200)
    cost, sl = _simulate(base_stocks)
    # Penalize if service level not met
    sl_penalty = max(0, SERVICE_TARGET - sl) * 10
    # Baseline: large buffer (expensive but safe)
    cost_base, _ = _simulate(np.array([80, 60, 40]))
    cost_sota = cost_base * 0.5  # ~50% cost reduction with optimal stocking
    effective_cost = cost + sl_penalty * cost_base
    score = max(0.0, min(1.0, (cost_base - effective_cost) / (cost_base - cost_sota)))
    return {"combined_score": float(score), "valid": 1.0, "feasibility_rate": 1.0,
            "avg_cost_per_period": round(cost, 2), "service_level": round(sl, 4)}
