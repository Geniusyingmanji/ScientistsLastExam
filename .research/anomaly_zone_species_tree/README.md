# AnomalyZoneSpeciesTree construction scripts

The scripts that produced every number in `benchmarks/Biology/AnomalyZoneSpeciesTree/Task.md`,
`TASK_CARD.yaml` and `references/known_best.md`. Run them from the repository root with the
project interpreter; they import the task's oracle directly and never touch the sandbox.

| script | what it produces | runtime |
|---|---|---|
| `run_both.py` | reference and baseline metrics with one row per world | about 45 s |
| `checks.py` | determinism, twenty malformed candidate shapes, blanket abstention, a fixed tree, the reference capped at 125, 250 and 375 loci, Python 3.8 syntax | about 3 min |
| `ablation.py` | the difficulty ladder (one reference choice changed at a time; `AZ_ONLY=<substring>` restricts to matching rungs) | about 15 min |
| `probe.py` | the 102060-strategy shortcut probe: free gene trees, trees re-estimated at a guessed shape, and the true-shape oracle | about 10 min |
| `anomaly_stats.py` | for every tree world, the gene-tree probability of the species-tree topology and of the most frequent topology, their difference and its standard error over `AZ_N` simulated gene trees (default one hundred thousand; `AZ_ONLY=<seed>` restricts to one world) | about 20 min at the default, 80 min at four hundred thousand |
| `truetrees.py` | for every anomaly-zone world, how often quartet consensus over 240 and over 500 true gene trees names the species tree, two hundred replicates | about 1 min |
| `shape_estimates.py` | the reference's site-rate shape estimate and refusal statistic on every world, next to the true shape | about 20 s |
| `fixedshape.py` | the reference with the shape fixed at each of ten guesses instead of estimated, and which tree worlds of each kind it still reads | about 5 min |
| `lba.py` | long-branch attraction measured as the excess rate at which estimated gene trees join the two fast species over the true gene trees of the same loci, for free and gamma-corrected trees, per world and rate class; the minority-imbalance separation on free versus corrected trees; mean-distance neighbour joining; per-locus split recall | about 25 s |

JSON side outputs go to the system temporary directory.
