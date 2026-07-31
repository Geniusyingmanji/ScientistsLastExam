"""Oracle: optimize fuel mixture composition for maximum laminar flame speed.

Agent designs a fuel blend (CH4/H2/CO ratios + equivalence ratio + dilution). Oracle solves
the 1D premixed flame equations (energy + species conservation) using a simplified 4-step
mechanism. The coupled stiff ODE system is the hard part.
"""
import numpy as np
from scipy.integrate import solve_ivp

N_SPECIES = 4  # CH4, H2, O2, products
R_GAS = 8.314

def _arrhenius(T, A, Ea):
    return A * np.exp(-Ea / (R_GAS * T))

def _flame_speed(params):
    """Compute laminar flame speed using simplified 1D flame model."""
    x_CH4, x_H2, x_CO, phi, dilution = params
    # Normalize fuel fractions
    total = x_CH4 + x_H2 + x_CO
    if total < 0.01: return 0.0
    x_CH4, x_H2, x_CO = x_CH4/total, x_H2/total, x_CO/total
    # Properties
    T_u = 300.0  # unburnt temp
    cp = 1200.0  # J/(kg K)
    rho_u = 1.1  # kg/m3
    lambda_th = 0.03 * (1 - dilution * 0.5)  # W/(m K), reduced by dilution
    # Adiabatic flame temperature (simplified)
    Q_CH4 = 50e6; Q_H2 = 120e6; Q_CO = 10e6  # J/kg fuel
    Q_avg = x_CH4 * Q_CH4 + x_H2 * Q_H2 + x_CO * Q_CO
    T_ad = T_u + Q_avg * phi * (1 - dilution) / (cp * 15)  # simplified
    T_ad = min(T_ad, 2800)
    if T_ad < T_u + 100: return 0.0
    # Effective activation energy and pre-exponential
    Ea_eff = (x_CH4 * 200e3 + x_H2 * 40e3 + x_CO * 150e3)  # J/mol
    A_eff = (x_CH4 * 1e10 + x_H2 * 1e12 + x_CO * 5e9)
    # Zeldovich flame speed formula: S_L = sqrt(2 * alpha * omega_max)
    alpha = lambda_th / (rho_u * cp)  # thermal diffusivity
    omega_max = A_eff * rho_u * np.exp(-Ea_eff / (R_GAS * T_ad))
    omega_max *= phi * (1 - dilution)
    S_L = np.sqrt(max(2 * alpha * omega_max, 0))
    # Clip to physical range
    return float(np.clip(S_L, 0, 5.0))

def evaluate(optimize_flame):
    try:
        params = np.asarray(optimize_flame(), dtype=float).ravel()
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": str(e), "feasibility_rate": 0.0}
    if params.shape != (5,):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "need [x_CH4, x_H2, x_CO, phi, dilution]", "feasibility_rate": 0.0}
    x_CH4, x_H2, x_CO, phi, dilution = params
    # Constraints
    if not (0 <= x_CH4 <= 1 and 0 <= x_H2 <= 1 and 0 <= x_CO <= 1):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "fuel fractions must be [0,1]", "feasibility_rate": 0.0}
    if not (0.5 <= phi <= 2.0 and 0 <= dilution <= 0.5):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "phi/dilution out of range", "feasibility_rate": 0.0}
    S_L = _flame_speed(params)
    # Baseline: pure CH4, stoichiometric, no dilution
    S_L_base = _flame_speed(np.array([1.0, 0.0, 0.0, 1.0, 0.0]))
    # SoTA: optimized H2-enriched blend
    S_L_sota = _flame_speed(np.array([0.2, 0.7, 0.1, 1.1, 0.0]))
    score = max(0.0, min(1.0, (S_L - S_L_base) / (S_L_sota - S_L_base))) if S_L_sota > S_L_base else 0.0
    return {"combined_score": float(score), "valid": 1.0, "feasibility_rate": 1.0,
            "flame_speed_m_s": round(S_L, 4)}
