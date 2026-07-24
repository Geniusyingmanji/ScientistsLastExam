# MOSFETDoping — design transferable silicon nMOS halo-profile Pareto archives

## Scientific background

Short-channel silicon MOSFET design is intrinsically multiobjective. A larger channel acceptor
concentration and source/drain pocket implants can raise the electrostatic barrier and suppress
off-state leakage or drain-induced barrier lowering (DIBL), but they also reduce carrier mobility,
increase random-dopant variability and consume an implant-dose budget. A single nominal optimum
therefore does not represent the drive-current versus leakage tradeoff.

This task uses a transparent reduced-order compact model. It combines:

- standard MOS threshold electrostatics and depletion capacitance;
- a one-dimensional screened-Poisson boundary-value solve for drain coupling;
- the Caughey--Thomas doping-dependent electron mobility law;
- charge-sheet on- and subthreshold off-current expressions; and
- a Poisson estimate of random-dopant threshold variation.

It is deliberately **not** a two-dimensional self-consistent drift--diffusion, quantum-corrected
or commercial TCAD calculation. The compact model makes every intermediate quantity executable
and auditable while retaining the central halo-design tradeoffs.

## Your task

Implement one condition-aware archive policy:

```python
def design_doping_archive(problem):
    """Return between 4 and 16 candidate profiles as an (n, 6) array."""
```

Each row has these columns, in this exact order:

```text
[log10 background acceptor concentration in cm^-3,
 log10 source-pocket peak concentration in cm^-3,
 log10 drain-pocket peak concentration in cm^-3,
 source-pocket center / effective channel length,
 drain-pocket center / effective channel length,
 Gaussian pocket sigma / effective channel length]
```

The public `problem` mapping provides column names, bounds, archive-size limits, device geometry,
operating condition, hard process/device constraints and objective scaling. Use the supplied
mapping rather than hard-coding one device. The same policy is called in fresh sessions on four
development and two interleaved held-out devices spanning channel length, EOT, supply voltage,
temperature, flat-band voltage and body depth.

## Evaluation

Each Gaussian profile is expanded on a finite channel grid and evaluated for threshold voltage,
DIBL, subthreshold swing, effective mobility, on/off current, implant dose, maximum active
doping, profile gradient and random-dopant variation. Hard feasibility requires finite values and
all public limits to pass. At least four rows in every returned archive must be nominally feasible.

The visible objective is the two-dimensional Pareto hypervolume of:

1. on-current per unit gate width in mA/um (larger is better); and
2. negative log off-current per unit gate width in nA/um (lower leakage is better).

A conservative eight-profile archive is the zero normalization witness. Fixed-seed 2048-point
scrambled-Sobol screens followed by exact compact-model Pareto selection provide strong nominal
normalization witnesses; they are not global-optimality certificates and better feasible archives
clip at one.

`combined_score` is mean nominal hypervolume on the four development devices. Structural validity
and nominal feasibility are visible during search. The trusted sidecar separately retains:

- nominal performance on two held-out devices;
- threshold, DIBL, swing, mobility, on/off ratio and random-dopant diagnostics;
- worst-shift hypervolume under temperature, effective channel shortening, EOT/flat-band,
  activation/diffusion, source--drain reversal and combined process/operation shifts; and
- nominal and shifted feasibility rates.

High score means simulator-specific compact-model profile optimization. It is not a fabricated
device result, a TCAD replacement, or autonomous discovery of semiconductor physics. Independent
drift--diffusion/quantum-corrected simulation, process integration and measured-device validation
would be required for a physical design claim.

## Rules

- Only edit `solution.py`; keep `design_doping_archive(problem)`.
- Return 4--16 rows with at least four unique finite designs and respect every public bound.
- Deterministic CPU code using the Python standard library, NumPy and SciPy only.
- No network or process creation. Do not read `verification/` or `frontier_eval/`.
- Boolean, non-finite, malformed, duplicated-only, out-of-bound and insufficiently feasible
  archives fail closed.

References: S. M. Sze and K. K. Ng, *Physics of Semiconductor Devices*, 3rd ed., Wiley,
DOI `10.1002/0470068329`; Y. Taur and T. H. Ning, *Fundamentals of Modern VLSI Devices*,
2nd ed., Cambridge University Press, DOI `10.1017/CBO9781139195065`; D. M. Caughey and
R. E. Thomas, “Carrier mobilities in silicon empirically related to doping and field,”
*Proceedings of the IEEE* 55(12), 1967, DOI `10.1109/PROC.1967.6123`.
