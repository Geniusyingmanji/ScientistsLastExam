"""Oracle: Lorenz-system chaos control via closed-loop Lyapunov reduction.

The controller is treated as a black-box sampled-data feedback law: it is evaluated once at
the start of each integration step and its output is held constant over that RK4 step.  The
maximum Lyapunov exponent is estimated with a two-trajectory Benettin method, so the measured
closed-loop map includes the state dependence of *any* deterministic controller without
requiring or approximating an explicit controller Jacobian.
"""
import numpy as np

SIGMA, RHO, BETA = 10.0, 28.0, 8.0/3.0
DT = 0.01
T_TOTAL = 100.0
N_STEPS = int(T_TOTAL / DT)
U_MAX_SQ = 50.0  # max average ||u||^2
PERTURBATION = 1e-7
RENORM_INTERVAL = 10
BURN_IN_STEPS = 2000

def _rk4_step(f, t, y, dt):
    k1 = f(t, y)
    k2 = f(t + dt/2, y + dt/2 * k1)
    k3 = f(t + dt/2, y + dt/2 * k2)
    k4 = f(t + dt, y + dt * k3)
    return y + dt/6 * (k1 + 2*k2 + 2*k3 + k4)

def _safe_control(controller, state):
    """Evaluate one controller call and enforce the public componentwise actuator limit."""
    u = np.asarray(controller(state.copy()), dtype=float).ravel()
    if u.shape != (3,) or not np.all(np.isfinite(u)):
        raise ValueError("controller must return three finite values")
    return np.clip(u, -20.0, 20.0)


def _lorenz_step(state, control):
    """Advance one zero-order-held controlled Lorenz step."""
    def dynamics(_t, s):
        return np.array([
            SIGMA * (s[1] - s[0]) + control[0],
            s[0] * (RHO - s[2]) - s[1] + control[1],
            s[0] * s[1] - BETA * s[2] + control[2],
        ])
    return _rk4_step(dynamics, 0.0, state, DT)


def _compute_mle(controller, n_steps=N_STEPS, initial_state=None, burn_in_steps=BURN_IN_STEPS):
    """Estimate the maximum exponent of the actual sampled-data closed-loop map.

    A reference and a nearby trajectory receive independently evaluated feedback.  Periodic
    renormalization keeps their separation in the local linear regime.  This is deliberately
    black-box: finite-difference propagation captures ``du/dx`` for smooth feedback and also
    gives the operational local stability of clipped or piecewise feedback laws.
    """
    x = np.array([1.0, 1.0, 1.0] if initial_state is None else initial_state,
                 dtype=float)
    if x.shape != (3,) or not np.all(np.isfinite(x)):
        raise ValueError("initial state must contain three finite values")
    direction = np.array([1.0, 0.0, 0.0], dtype=float)
    x_perturbed = x + PERTURBATION * direction
    lyap_sum = 0.0
    total_u_sq = 0.0
    elapsed = 0.0
    burn_in_steps = max(0, min(int(burn_in_steps), int(n_steps) - RENORM_INTERVAL))

    for step in range(int(n_steps)):
        u = _safe_control(controller, x)
        u_perturbed = _safe_control(controller, x_perturbed)
        total_u_sq += np.sum(u**2)
        x = _lorenz_step(x, u)
        x_perturbed = _lorenz_step(x_perturbed, u_perturbed)
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(x_perturbed)):
            raise ValueError("controlled trajectory became non-finite")

        if (step + 1) % RENORM_INTERVAL == 0:
            delta = x_perturbed - x
            separation = float(np.linalg.norm(delta))
            if not np.isfinite(separation) or separation <= 1e-15:
                # Numerically indistinguishable trajectories imply contraction at least to
                # machine precision.  Preserve a direction for the remaining experiment.
                separation = 1e-15
                delta = direction * separation
            direction = delta / separation
            if step + 1 > burn_in_steps:
                lyap_sum += np.log(separation / PERTURBATION)
                elapsed += RENORM_INTERVAL * DT
            x_perturbed = x + PERTURBATION * direction

    if elapsed <= 0.0:
        raise ValueError("trajectory too short for Lyapunov estimation")
    mle = lyap_sum / elapsed
    avg_u_sq = total_u_sq / int(n_steps)
    return float(mle), float(avg_u_sq)

# Uncontrolled MLE (precomputed once)
_MLE_UNCONTROLLED = None

def evaluate(design_controller):
    global _MLE_UNCONTROLLED
    if _MLE_UNCONTROLLED is None:
        _MLE_UNCONTROLLED, _ = _compute_mle(lambda x: np.zeros(3))

    try:
        controller = design_controller(SIGMA, RHO, BETA)
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": str(e), "feasibility_rate": 0.0}

    if not callable(controller):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "not callable", "feasibility_rate": 0.0}

    try:
        mle, avg_u_sq = _compute_mle(controller)
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0,
                "error_message": str(e), "feasibility_rate": 0.0}

    # Constraint: average control energy
    if avg_u_sq > U_MAX_SQ:
        return {"combined_score": 0.0, "valid": 0.0,
                "error_message": f"control energy {avg_u_sq:.2f} > {U_MAX_SQ}", "feasibility_rate": 0.0}

    # Score: reduction in MLE (uncontrolled ~0.9, target -0.5 for full stabilization)
    mle_target = -0.5
    mle_unc = _MLE_UNCONTROLLED
    score = max(0.0, min(1.0, (mle_unc - mle) / (mle_unc - mle_target)))
    return {"combined_score": float(score), "valid": 1.0, "feasibility_rate": 1.0,
            "raw_score": float(mle), "mle": round(mle, 4),
            "mle_uncontrolled": round(mle_unc, 4),
            "avg_control_energy": round(avg_u_sq, 4),
            "mle_method": "two_trajectory_benettin_sampled_feedback"}
