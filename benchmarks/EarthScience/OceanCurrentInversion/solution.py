"""Weak valid baseline: make one drifter observation and no mechanism claim."""

import numpy as np


def discover_currents(domain_m, mode_specifications, observe, budget_units):
    del domain_m, budget_units
    day_s = 86400.0
    observe(
        np.asarray(((30000.0, 30000.0),)),
        0.0,
        np.linspace(0.0, day_s, 7),
    )
    return {
        "coefficients_m_s": np.zeros(len(mode_specifications)),
        "support": np.zeros(len(mode_specifications), dtype=int),
        "confidence": 0.0,
        "abstain": True,
    }
