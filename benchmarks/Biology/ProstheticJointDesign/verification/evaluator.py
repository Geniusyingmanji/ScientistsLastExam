"""Oracle: prosthetic knee joint geometry optimization.

Agent designs the femoral condyle shape (radius of curvature, cam profile) and tibial
insert geometry to maximize range-of-motion while maintaining contact stress below a
threshold. Oracle computes Hertzian contact mechanics + kinematic rollback analysis.
"""
import numpy as np

N_PARAMS = 8  # 4 for femoral profile + 4 for tibial insert
FLEX_ANGLES = np.linspace(0, 120, 25)  # degrees

def _hertz_contact_stress(R1, R2, load, E=500e6, nu=0.3):
    """Hertzian contact stress for 2D (cylinder-on-flat or cylinder-on-cylinder)."""
    E_star = E / (2 * (1 - nu**2))
    R_eff = 1.0 / (1.0/max(R1, 0.001) + 1.0/max(R2, 0.001)) if R2 < 1e6 else R1
    # Contact half-width
    a = np.sqrt(2 * load * R_eff / (np.pi * E_star))
    # Max contact pressure
    p_max = np.sqrt(load * E_star / (np.pi * R_eff))
    return float(p_max), float(a)

def _evaluate_joint(params):
    """Evaluate knee joint through full flexion range."""
    # Femoral condyle: sagittal radii at 4 flexion zones
    R_fem = params[:4] * 0.001  # mm to m, range [15, 50] mm
    # Tibial insert: dish radii at 4 zones
    R_tib = params[4:] * 0.001  # mm to m, range [20, 100] mm
    body_weight = 800  # N (80 kg person)
    max_stress_limit = 25e6  # Pa (PE yield ~25 MPa)
    scores = []
    for i, angle in enumerate(FLEX_ANGLES):
        zone = min(int(angle / 30), 3)
        r1 = R_fem[zone]; r2 = R_tib[zone]
        # Load increases with flexion (more body weight on bent knee)
        load = body_weight * (1 + 0.01 * angle)
        stress, contact_width = _hertz_contact_stress(r1, r2, load)
        # Kinematic score: larger R_fem allows more rollback (good)
        rollback = r1 * np.sin(np.radians(angle)) * 1000  # mm
        # Stability: R_tib should be larger than R_fem (conforming)
        conformity = min(r2 / max(r1, 0.001), 3.0) / 3.0
        # Stress penalty
        stress_ok = 1.0 if stress < max_stress_limit else max(0.0, 2.0 - stress / max_stress_limit)
        scores.append(rollback / 50.0 * conformity * stress_ok)  # normalized
    return float(np.mean(scores))

def evaluate(design_joint):
    try:
        params = np.asarray(design_joint(N_PARAMS), dtype=float)
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": str(e), "feasibility_rate": 0.0}
    if params.shape != (N_PARAMS,):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "need 8 params", "feasibility_rate": 0.0}
    # Bounds
    params[:4] = np.clip(params[:4], 15, 50)   # femoral radii mm
    params[4:] = np.clip(params[4:], 20, 100)  # tibial radii mm
    raw = _evaluate_joint(params)
    # Baseline: uniform 30mm femoral, 50mm tibial
    raw_base = _evaluate_joint(np.array([30,30,30,30, 50,50,50,50], dtype=float))
    raw_sota = raw_base * 2.0  # ~2x improvement target
    score = max(0.0, min(1.0, (raw - raw_base) / (raw_sota - raw_base)))
    return {"combined_score": float(score), "valid": 1.0, "feasibility_rate": 1.0,
            "joint_quality": round(raw, 4)}
