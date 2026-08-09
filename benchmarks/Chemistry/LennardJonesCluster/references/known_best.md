# LennardJonesCluster — known best values

Find the minimum-energy configuration of N atoms interacting through a Lennard-Jones potential.
Putative global minima come from decades of computational search collected in the Cambridge
Cluster Database; for most sizes they are conjectured rather than proven, so a lower energy is a
genuine result and the score is uncapped.

## Anchors

| N | global minimum energy (reduced units) |
|---:|---:|
| 13 | −44.326801 |
| 19 | −72.659782 |
| 38 | −173.928427 |

Score per size is the ratio of achieved to reference energy, both negative:

```text
score = max(0, E_achieved / E_reference)     # no upper clamp
```

Reaching the listed minimum scores exactly 1.0. Worked example at N=13 with reference
−44.326801: an energy of −22.163 scores 0.5000, −44.327 scores 1.0000, and an energy below the
reference scores above 1.0.

## Why uncapped

The Cambridge Cluster Database minima are putative. N=38 in particular is the classic
double-funnel case whose global minimum was found only after the icosahedral basin had misled
searches for years, which is precisely the regime where beating a listed value is meaningful.
Clipping at 1.0 would erase that distinction.

## Feasibility

A configuration is rejected if any pair is inside the hard-core distance, if the shape is wrong,
or if the energy is non-finite. Rejected configurations score 0 rather than a large negative
number, so a candidate cannot mine the potential's singularity.

## Reproduce

```bash
python -m frontier_science eval --task Chemistry/LennardJonesCluster
```
