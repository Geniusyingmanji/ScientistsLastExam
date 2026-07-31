"""Baseline: single-layer MgF2 quarter-wave at 550nm."""
import numpy as np

def design_coating():
    """Return a coating design: materials (list of int) and thicknesses (nm)."""
    # Single quarter-wave MgF2 at 550nm: d = λ/(4n) = 550/(4*1.38) ≈ 99.6 nm
    return {
        "materials": [0],        # MgF2
        "thicknesses_nm": [99.6]
    }
