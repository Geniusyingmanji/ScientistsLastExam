"""Frozen oracle for MultilayerThinFilm — Transfer Matrix Method.

Computes spectral reflectance of a multilayer thin-film stack on BK7 glass substrate using
the characteristic matrix method. Agent designs layer materials + thicknesses to minimize
average reflectance over 400-800 nm (broadband antireflection). Score = 1 - mean_R.
"""
import numpy as np

# Material refractive indices (Cauchy model: n(λ) = A + B/λ² + C/λ⁴, λ in μm)
MATERIALS = {
    0: {"name": "MgF2",  "A": 1.380, "B": 0.00340, "C": 0.0},
    1: {"name": "SiO2",  "A": 1.458, "B": 0.00354, "C": 0.0},
    2: {"name": "Al2O3", "A": 1.766, "B": 0.00510, "C": 0.0},
    3: {"name": "TiO2",  "A": 2.200, "B": 0.01500, "C": 0.0},
    4: {"name": "Ta2O5", "A": 2.100, "B": 0.01200, "C": 0.0},
    5: {"name": "ZrO2",  "A": 2.050, "B": 0.01000, "C": 0.0},
}
N_SUBSTRATE_BK7 = 1.517  # BK7 glass at ~550nm (simplified constant)
MAX_LAYERS = 12
WAVELENGTHS = np.linspace(400, 800, 200) * 1e-3  # in μm


def _refractive_index(mat_id, wl_um):
    m = MATERIALS[mat_id % len(MATERIALS)]
    return m["A"] + m["B"] / wl_um**2 + m["C"] / wl_um**4


def _reflectance_spectrum(materials, thicknesses_nm):
    """Compute reflectance R(λ) for a multilayer stack on BK7, normal incidence from air."""
    n_layers = len(materials)
    R_spectrum = np.zeros(len(WAVELENGTHS))
    for iw, wl in enumerate(WAVELENGTHS):
        # Build characteristic matrix product
        M = np.eye(2, dtype=complex)
        for i in range(n_layers):
            n_i = _refractive_index(materials[i], wl)
            d_i = thicknesses_nm[i] * 1e-3  # nm -> μm
            delta = 2 * np.pi * n_i * d_i / wl
            cos_d, sin_d = np.cos(delta), np.sin(delta)
            eta_i = n_i  # normal incidence, TE
            layer_matrix = np.array([
                [cos_d, -1j * sin_d / eta_i],
                [-1j * eta_i * sin_d, cos_d]
            ])
            M = M @ layer_matrix
        # Fresnel coefficient (air -> stack -> substrate)
        eta_0 = 1.0  # air
        eta_s = N_SUBSTRATE_BK7
        B, C_val = M @ np.array([1.0, eta_s], dtype=complex)
        r = (eta_0 * B - C_val) / (eta_0 * B + C_val)
        R_spectrum[iw] = float(np.abs(r)**2)
    return R_spectrum


# Baseline: bare glass reflectance
_R_BARE = ((1.0 - N_SUBSTRATE_BK7) / (1.0 + N_SUBSTRATE_BK7))**2  # ~4.2%
_R_BARE_MEAN = _R_BARE  # uniform over spectrum for simplified model


def evaluate(design_coating):
    """Score a coating design. Agent returns (materials, thicknesses_nm)."""
    try:
        result = design_coating()
        materials = list(result["materials"])
        thicknesses = np.asarray(result["thicknesses_nm"], dtype=float)
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": str(e), "feasibility_rate": 0.0}

    n_layers = len(materials)
    if n_layers == 0 or n_layers > MAX_LAYERS or len(thicknesses) != n_layers:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "bad layer count", "feasibility_rate": 0.0}
    if not all(0 <= m < len(MATERIALS) for m in materials):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "invalid material id", "feasibility_rate": 0.0}
    if np.any(thicknesses < 1) or np.any(thicknesses > 500):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "thickness out of [1, 500] nm", "feasibility_rate": 0.0}

    R = _reflectance_spectrum(materials, thicknesses)
    mean_R = float(np.mean(R))

    # Score against the physical lower bound R=0, not an invented literature "SoTA".
    # This remains interpretable even when a design improves on a historical coating.
    score = (_R_BARE_MEAN - mean_R) / _R_BARE_MEAN
    score = float(max(0.0, min(1.0, score)))

    return {
        "combined_score": score,
        "valid": 1.0,
        "feasibility_rate": 1.0,
        "mean_reflectance": round(mean_R, 6),
        "n_layers": n_layers,
    }
