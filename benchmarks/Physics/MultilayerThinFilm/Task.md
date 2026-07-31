# MultilayerThinFilm — design a broadband antireflection coating

## Scientific background

Multilayer thin-film coatings control light reflection via constructive and destructive
interference between layers. Designing broadband anti-reflection (AR) coatings that minimize
reflectance over the entire visible spectrum (400–800 nm) is a foundational problem in
optical engineering (spectrometers, camera lenses, solar cells). The rugged, multimodal
landscape with coupled material dispersion defeats simple gradient methods.

Reference: Macleod, *Thin-Film Optical Filters* (CRC, 2017); Dobrowolski et al., *Appl. Opt.* 35, 644 (1996).

## Your task

Edit **`solution.py`** so it defines:

```python
def design_coating():
    """Return a dict with:
      - "materials": list of int (indices into [MgF2, SiO2, Al2O3, TiO2, Ta2O5, ZrO2])
      - "thicknesses_nm": list of float (layer thicknesses in nm, each in [1, 500])
    Maximum 12 layers. Goal: minimize mean reflectance over 400-800 nm on BK7 glass."""
```

The evaluator computes spectral reflectance using the **transfer-matrix method** (characteristic
matrix product) at normal incidence from air through your stack onto a BK7 substrate.

## Scoring

```
score = clip( (R_bare - R_achieved) / (R_bare - 0.001), 0, 1 )
```
where R_bare ≈ 4.2% (uncoated glass). Single-layer MgF2 gives R ≈ 1.2% (score ~0.73).
Optimized 4-6 layer designs achieve R < 0.1% (score > 0.97). SoTA broadband AR: R < 0.05%.

## Rules

- Only edit `solution.py`. numpy/scipy only. CPU, seconds. Do not read `verification/`.
