# PhotovoltaicTandemDesign-v1 — budgeted finite-absorption tandem design

## Scientific question

Can one design policy choose the number of series-connected junctions, their
band gaps and their finite optical depths as the fabrication budget changes,
while retaining current matching under realistic spectral, thermal and process
perturbations?

This is a transparent detailed-balance optimization benchmark. It is **not** a
device simulator, a material recommendation, a certified efficiency record or
experimental evidence.

## Interface

Edit `solution.py` and implement:

```python
def design_tandem(problem):
    """Return one tandem design for each ordered fabrication-budget cap."""
```

The public `problem` contains:

- an ASTM-G173-derived wavelength grid, the nominal spectral irradiance and its
  integrated incident power;
- nominal cell temperature and three increasing fabrication-budget caps;
- bounds on junction count, band gap and optical depth;
- the minimum adjacent-band-gap separation and all public cost coefficients;
- the public finite-absorption expression and series-connection convention.

Return exactly:

```python
{
    "designs": [
        {
            "bandgaps_ev": [...],
            "optical_depths": [...],
        },
        # exactly one row per public cap
    ]
}
```

Within each row, both arrays must have the same length from one to four. Values
must be finite and inside the public bounds. Band gaps are ordered from the
illuminated top cell to the bottom cell and must decrease by at least the public
minimum separation. The fabrication cost is

```text
cost = junction_overhead_cost * junction_count
     + optical_depth_cost * sum(optical_depths)
```

and row `k` must not exceed `fabrication_budget_caps[k]`. The three designs must
be distinct after rounding every returned value to eight decimal places.

## Public nominal model

At wavelength `lambda`, photon energy is `E = hc/lambda`. A junction with band
gap `Eg` and optical depth `d` absorbs the fraction

```text
A(E; Eg, d) = 1 - exp[-d sqrt(max(E/Eg - 1, 0))].
```

Light not absorbed by a junction is transmitted to the next junction. For each
junction, the short-circuit current is the charge-weighted integral of its
absorbed photon flux. Radiative dark current is the corresponding integral of
cell-temperature black-body photon flux through the same absorptance. At a common
series current `J`, junction voltages obey the ideal radiative diode equation;
trusted code numerically maximizes `J * sum(V_i(J))`. Nominal efficiency is
maximum electrical power divided by incident spectral power.

## Evaluation

Eight interleaved spectral/temperature/budget regimes are used. Five determine
the visible development score and three are evaluator-only held-out transfer
diagnostics. In each regime and budget cap, a weak valid single-junction design
defines zero and a fixed-seed same-model search witness defines one. These are
normalization anchors, not proofs of global optimality or efficiency records;
better feasible designs are clipped to one.

Six sealed perturbations separately test:

- hotter cells;
- alternating band-gap process error;
- thinner absorbers plus parasitic front loss;
- blue- and red-shifted spectra;
- a combined spectral, thermal, band-gap and optical-loss shift.

The visible score is mean nominal normalized performance. Worst-shift
robustness, held-out transfer, efficiency, power, current matching, cost use,
junction count and per-regime records never enter online selection. Malformed,
non-finite, unordered, duplicate, out-of-bound or over-budget artifacts fail
closed.

## Scope and references

The oracle follows the detailed-balance tradition and uses a hash-bound copy of
the ASTM G173 global-tilt spectrum distributed by pvlib-python. It intentionally
omits non-radiative recombination, transport, interfaces, tunnel junctions,
luminescent coupling, series/shunt resistance, thermal balance, real material
availability and manufacturing yield. Any engineering conclusion requires an
independent device solver and experimental validation.

- Shockley & Queisser, *Detailed Balance Limit of Efficiency of p-n Junction
  Solar Cells*, J. Appl. Phys. 32, 510 (1961), DOI: `10.1063/1.1736034`.
- De Vos, *Detailed balance limit of the efficiency of tandem solar cells*,
  J. Phys. D 13, 839 (1980), DOI: `10.1088/0022-3727/13/5/018`.
- Henry, *Limiting efficiencies of ideal single and multiple energy gap
  terrestrial solar cells*, J. Appl. Phys. 51, 4494 (1980), DOI:
  `10.1063/1.328272`.
- Ruhle, *Tabulated values of the Shockley-Queisser limit for single junction
  solar cells*, Sol. Energy 130, 139 (2016), DOI:
  `10.1016/j.solener.2016.02.015`.
- Green, *Limiting photovoltaic efficiency under new ASTM International
  G173-based reference spectra*, Prog. Photovolt. 20, 954–959 (2012), DOI:
  `10.1002/pip.1156`.
- Garcia et al., *Spectral binning for energy production calculations and
  multijunction solar cell design*, Prog. Photovolt. 26, 48–54 (2018), DOI:
  `10.1002/pip.2943`.
- Friedman et al., *Spectral and Concentration Sensitivity of Multijunction
  Solar Cells at High Temperature*, IEEE PVSC (2017), DOI:
  `10.1109/PVSC.2017.8366786`.
- Holmgren et al., *pvlib python*, JOSS 3, 884 (2018), DOI:
  `10.21105/joss.00884`.

## Rules

- Only edit `solution.py`; keep `design_tandem(problem)`.
- NumPy/SciPy only, CPU, no network.
- Do not read `verification/` or `frontier_eval/`.
