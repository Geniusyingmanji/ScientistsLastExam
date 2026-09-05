"""Frozen forward model: transmission spectra of transiting planets.

The physics kept is the part that makes molecular identification hard and the part the field is
actually arguing about. In the isothermal, well-mixed limit the transit depth is

    D(lambda) = (Rp/Rs)^2 + 2 Rp H / Rs^2 * ln( sum_i x_i sigma_i(lambda) + kappa_grey
                                                + kappa_ray * (lambda_0/lambda)^4 )

so a species shows up as the *logarithm* of its cross-section. Three consequences drive the task:

  * a grey cloud deck raises the floor inside the logarithm and mutes every feature at once, which
    is why a spectrum can be uninformative rather than merely noisy;
  * abundance and the scale height enter the same way over a limited band, so a weak feature of an
    abundant species and a strong feature of a trace one are not distinguishable;
  * two species whose bands overlap in the observed range are not separable at any signal-to-noise
    the budget can buy, which is exactly the reported situation for DMS against C2H4 and
    chloroethane in the K2-18 b spectrum.

Cross-sections are synthesised as fixed sums of Gaussian bands rather than taken from a line list.
That is a deliberate limit and it is stated on the card: the task measures whether a searcher can
tell an identifiable system from an unidentifiable one under a budget, not whether it knows real
opacities.
"""
from __future__ import annotations

import numpy as np

WAVELENGTHS = np.linspace(0.6, 5.3, 188)          # microns, JWST-like coverage
BAND_EDGES = np.linspace(0.6, 5.3, 13)            # twelve bands the budget is spent on

# (name, [(centre, width, strength), ...]). The pairs that overlap are deliberate.
SPECIES = {
    "H2O":  [(1.40, 0.11, 1.0), (1.90, 0.14, 1.3), (2.70, 0.18, 1.1)],
    "CH4":  [(1.66, 0.09, 0.9), (2.32, 0.12, 1.0), (3.30, 0.16, 1.6)],
    "CO2":  [(2.02, 0.06, 1.2), (4.30, 0.12, 2.4)],
    "CO":   [(2.35, 0.05, 0.7), (4.65, 0.09, 1.5)],
    "NH3":  [(1.50, 0.08, 0.6), (2.25, 0.10, 0.8), (3.00, 0.13, 0.9)],
    "SO2":  [(4.05, 0.10, 1.4)],
    # The confusable pair. Their bands sit on top of each other, which is the situation reported for
    # DMS against C2H4 and chloroethane in the K2-18 b reanalyses. The offsets are small on purpose:
    # at a first attempt they differed by 0.02 um and the fit could still separate them - the
    # design matrix had condition number 93 and the individual amplitudes were recoverable - which
    # made the refusal regime a matter of signal-to-noise rather than of identifiability. Moving
    # them to within a few thousandths of a micron makes the pair genuinely inseparable at any
    # allocation of the budget, which is the claim the task needs to be able to make.
    "DMS":  [(3.400, 0.150, 1.0), (3.850, 0.120, 0.8)],
    "C2H4": [(3.396, 0.152, 1.0), (3.856, 0.121, 0.8)],
}
SPECIES_ORDER = tuple(sorted(SPECIES))
CONFUSABLE = frozenset({"DMS", "C2H4"})


def cross_sections():
    """Fixed opacity templates on the wavelength grid, one row per species."""
    table = np.zeros((len(SPECIES_ORDER), WAVELENGTHS.size))
    for index, name in enumerate(SPECIES_ORDER):
        for centre, width, strength in SPECIES[name]:
            table[index] += strength * np.exp(-0.5 * ((WAVELENGTHS - centre) / width) ** 2)
    return table


def spectrum(abundances, grey, rayleigh, depth, scale):
    """Noise-free transit depth for one atmosphere."""
    opacity = abundances @ cross_sections()
    floor = grey + rayleigh * (1.0 / WAVELENGTHS) ** 4
    return depth + scale * np.log(opacity + floor + 1e-12)
