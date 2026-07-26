# DiffractionGratingDesign — polarization-tolerant multilayer relief design

Design a five-layer, one-dimensional binary dielectric relief that directs
transmitted light into diffraction order `+1`. The policy must work across the
development wavelength and incidence-angle grid for both TE and TM polarization.

```python
def design_grating(problem):
    """Return an array with shape (problem['layer_count'], 3).

    Each row is [depth_um, ridge_fill_fraction, lateral_offset_fraction].
    """
```

The trusted evaluator uses a Fourier-modal rigorous coupled-wave analysis
(RCWA) solver, checks lossless energy conservation, evaluates unseen material
and wavelength families, and applies sealed etch, overlay, index and angle
shifts. The search score uses development target-order efficiency only. Held-out
and robustness metrics remain evaluator-only.

The design must obey the public depth, fill, offset, minimum-feature and total-
depth limits. Return finite real values without clipping or hidden I/O.

Method references:

- Moharam and Gaylord, “Rigorous coupled-wave analysis of planar-grating
  diffraction,” JOSA 71, 811 (1981), DOI `10.1364/JOSA.71.000811`.
- Moharam et al., “Stable implementation ... enhanced transmittance matrix
  approach,” JOSA A 12, 1077 (1995), DOI `10.1364/JOSAA.12.001077`.
- Lalanne and Morris, “Highly improved convergence ... TM polarization,” JOSA A
  13, 779 (1996), DOI `10.1364/JOSAA.13.000779`.
- Li, “Use of Fourier series in the analysis of discontinuous periodic
  structures,” JOSA A 13, 1870 (1996), DOI `10.1364/JOSAA.13.001870`.

This is a deterministic, isotropic, lossless 1D computational benchmark. A high
score is not evidence of fabrication, measured efficiency or a new photonic
device.
