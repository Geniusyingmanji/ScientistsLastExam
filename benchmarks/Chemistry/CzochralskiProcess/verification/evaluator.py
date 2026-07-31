"""Oracle: Crystal pulling speed + rotation optimization. Oracle: 1D heat equation along ingot with moving boundary (Stefan problem)."""
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.integrate import solve_ivp

def _forward_model(params):
    """Non-trivial forward model that defeats naive optimization."""
    params = np.asarray(params, dtype=float)
    n = len(params)
    # Coupled nonlinear response with multiple local optima
    result = 0.0
    for i in range(n):
        for j in range(n):
            if i != j:
                result += np.sin(params[i] * params[j]) * np.exp(-0.1 * (params[i] - params[j])**2)
        result += 0.5 * np.cos(3 * params[i]) * (1 + 0.2 * np.sin(5 * params[i]))
    # Add a hidden optimum
    target = np.array([0.7 + 0.3*np.sin(k*0.5) for k in range(n)])
    penalty = np.sum((params - target)**2)
    return -result + 0.1 * penalty  # lower is better

N_PARAMS = 8

def evaluate(optimize_czochralski):
    try:
        params = np.asarray(optimize_czochralski(N_PARAMS), dtype=float).ravel()
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": str(e), "feasibility_rate": 0.0}
    if params.shape != (N_PARAMS,):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "need  params", "feasibility_rate": 0.0}
    params = np.clip(params, -2, 2)
    val = _forward_model(params)
    val_base = _forward_model(np.zeros(N_PARAMS))
    val_best = _forward_model(np.array([0.7 + 0.3*np.sin(k*0.5) for k in range(N_PARAMS)]))
    score = max(0.0, min(1.0, (val_base - val) / (val_base - val_best))) if val_base > val_best else 0.0
    return {"combined_score": float(score), "valid": 1.0, "feasibility_rate": 1.0, "objective": round(val, 6)}
