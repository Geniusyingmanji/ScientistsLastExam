"""Weak valid baseline: make no peak claim without supporting analysis."""


def fit_spectrum(x, spectrum):
    del x, spectrum
    return {
        "centers": [],
        "lorentzian_hwhm": [],
        "gaussian_sigma": [],
        "amplitudes": [],
        "lineshapes": [],
        "confidence": 0.0,
        "abstain": True,
    }
