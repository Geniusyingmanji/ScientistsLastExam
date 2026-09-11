# AnomalyZoneSpeciesTree — reference results

Every number here is produced by running code in this directory or the construction scripts in
`.research/anomaly_zone_species_tree/` at the repository root. Nothing is copied from a table.

## Reproducing

```
python3 frontier_eval/run_eval.py --candidate verification/reference_quartet_consensus.py \
    --metrics-out /tmp/metrics.json
```

## Reference — `verification/reference_quartet_consensus.py`

Truth-blind: it reads only the public problem and the budgeted sequencing campaign.

| metric | development | held out |
|---|---|---|
| mechanism score (normalized) | **0.912** | 0.903 |
| topology rate | 1.00 | 1.00 |
| branch-length score | 0.82 | 0.81 |
| false discovery rate | 0.00 | 0.00 |
| correct refusal rate | 1.00 | 1.00 |
| discovery coverage | 1.00 | 1.00 |
| confidence calibration | 0.95 | — |
| loci bought | 500 of 4500 | 500 of 4500 |
| budget spent | 1000 of 1000 | 1000 of 1000 |

Its design: buy slow loci of 800 sites in catalogue order until the budget is spent; estimate the
shape of the gamma distribution of site rates from the first sixty loci, by matching the share of
sites that are constant across all eight sequences to what a tree built at each candidate shape
predicts under that shape; discard the sequencing centre's gene trees and re-estimate each one by
neighbour joining on the Jukes-Cantor distance corrected at the estimated shape; count the three
topologies of each of the 70 quartets across the gene trees; decline when, for some species, the
sum over the 35 quartets containing it of the squared difference between the two minority counts
divided by their sum exceeds 260; otherwise take the one of the 10395 unrooted eight-taxon trees
that agrees with the most quartet observations, and read each internal branch length from the
median majority frequency of the quartets whose path is exactly that branch, inverting
`p = 1 - (2/3) exp(-t)`.

**The reference is deliberately not at the ceiling.** Its branch-length score is 0.82 on the
development split. Three things are left on the table: every quartet is counted with the same
weight whether the gene tree resolved it well or barely; the inversion ignores gene-tree estimation
error, which flattens the frequencies towards a third and biases every length downward; and the
refusal is a fixed threshold on one statistic rather than a test of the fitted tree against the
whole quartet spectrum. One evaluation of the reference takes fifteen to thirty seconds on the
construction laptop, depending on load. The maintainer measured the previous version, which took
ten seconds here, at thirty-eight to forty seconds on the evaluation host, so this one should
take one to two minutes there; `eval_time_seconds` says 120.

## Model draws — not performed

No frontier model has seen this task. It was built on a machine without a model endpoint, so the
admission bar (no first proposal reaches the reference) is not measured. `lineage.calibration_runs`
on the task card is empty and `calibration_evidence_status` says so. The first draw should follow
the exemplar's protocol: three seeds, three proposals each, `greedy_rewrite`, budget 3, against
the reference's 0.912.

## Baseline — `solution.py`

Buys the longest fast loci until the budget is spent (200 loci of 2000 sites), concatenates them,
computes the plain Jukes-Cantor distance on the whole alignment, builds one neighbour-joining tree
and reports its internal lengths in substitutions per site as if they were coalescent units.
Never declines, confidence 0.9.

| metric | development | held out |
|---|---|---|
| combined score | **0.0000** | 0.0000 |
| raw mechanism | 0.000 | — |
| topology rate | 0.00 | 0.00 |
| branch-length score | 0.00 | 0.00 |
| false discovery rate | 1.00 | 1.00 |
| correct refusal rate | 0.00 | 0.00 |

Confidently wrong rather than empty: every world on both splits is a false discovery.
Concatenation is inconsistent in the anomaly zone, the uncorrected distance on the fastest loci
joins the two fast-evolving species, and the hybrid worlds get a tree like everything else.

## Difficulty ladder

One choice of the reference changed at a time. Held out is the normalized held-out mechanism.

| strategy | score | topology | branch lengths | false discovery | refusal | coverage | loci | held out |
|---|---|---|---|---|---|---|---|---|
| gamma-corrected distance gene trees from 500 slow loci of 800 sites at an estimated site-rate shape, quartet consensus, quartet-frequency lengths, minority-imbalance refusal | **0.912** | 1.00 | 0.82 | 0.00 | 1.00 | 1.00 | 500 | 0.903 |
| same, but the sequencing centre's uncorrected gene trees | 0.111 | 0.12 | 0.10 | 0.58 | 1.00 | 0.12 | 500 | 0.225 |
| same, shape fixed at 0.5 instead of estimated | 0.575 | 0.62 | 0.52 | 0.25 | 1.00 | 0.75 | 500 | 0.685 |
| same, shape fixed at 0.2 | 0.450 | 0.50 | 0.40 | 0.33 | 1.00 | 0.50 | 500 | 0.437 |
| same, shape fixed at 1.0 | 0.446 | 0.50 | 0.39 | 0.33 | 1.00 | 0.50 | 500 | 0.465 |
| same, shape estimated from 20 loci instead of 60 | 0.913 | 1.00 | 0.83 | 0.00 | 1.00 | 1.00 | 500 | 0.906 |
| same, the true shape (an oracle no candidate has) | 0.918 | 1.00 | 0.84 | 0.00 | 1.00 | 1.00 | 500 | 0.902 |
| same, medium loci instead of slow | 0.648 | 0.75 | 0.55 | 0.17 | 1.00 | 1.00 | 500 | 0.668 |
| same, fast loci instead of slow | 0.320 | 0.38 | 0.26 | 0.42 | 1.00 | 0.62 | 500 | 0.632 |
| same, 300-site loci (all 500 of them) instead of 800 | 0.749 | 0.88 | 0.62 | 0.08 | 1.00 | 1.00 | 500 | 0.826 |
| same, 2000-site loci (200 of them) instead of 800 | 0.567 | 0.75 | 0.63 | 0.25 | 0.75 | 1.00 | 200 | 0.879 |
| same, never declining | 0.412 | 1.00 | 0.82 | 0.33 | 0.00 | 1.00 | 500 | 0.403 |
| same, refusal threshold 180 | 0.912 | 1.00 | 0.82 | 0.00 | 1.00 | 1.00 | 500 | 0.903 |
| same, refusal threshold 340 | 0.912 | 1.00 | 0.82 | 0.00 | 1.00 | 1.00 | 500 | 0.903 |
| same, constant branch lengths of 0.1 | 0.728 | 1.00 | 0.46 | 0.00 | 1.00 | 1.00 | 500 | 0.692 |
| same, greedy consensus of the gene trees instead of quartets | 0.457 | 0.50 | 0.41 | 0.33 | 1.00 | 1.00 | 500 | 0.664 |
| same, one neighbour joining on the mean corrected distance instead of quartets | 0.800 | 0.88 | 0.73 | 0.08 | 1.00 | 1.00 | 500 | 0.664 |
| same, half the budget | 0.776 | 1.00 | 0.80 | 0.08 | 0.75 | 1.00 | 250 | 0.659 |
| same, a quarter of the budget | 0.369 | 1.00 | 0.74 | 0.33 | 0.00 | 1.00 | 125 | 0.158 |
| uncorrected gene trees and fast loci | 0.000 | 0.00 | 0.00 | 0.67 | 1.00 | 0.00 | 500 | 0.000 |
| uncorrected gene trees, never declining | 0.000 | 0.25 | 0.18 | 0.83 | 0.00 | 1.00 | 500 | 0.000 |
| concatenation of the longest fast loci, plain Jukes-Cantor, never declining (baseline) | 0.000 | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 200 | 0.000 |
| declining everything | 0.000 | — | — | 0.67 | 1.00 | 0.00 | 0 | 0.000 |

The ladder is not a difficulty measurement; that would be a frontier draw. What it shows is where
the score lives: re-estimating the gene trees is worth 0.80, estimating the shape rather than
guessing it 0.34 to 0.47, declining 0.50, quartets over greedy consensus 0.46, slow loci over
medium 0.26 and over fast 0.59, the locus length 0.16 or 0.35, half the budget 0.14, a quarter of
it 0.54 and the branch lengths 0.18. Quartet consensus against one neighbour joining on the mean
corrected distance is worth 0.11 on the development split and 0.24 held out. The mean corrected
distance is a consistent estimator of the species tree under the coalescent, so that gap is
statistical efficiency on the short branches and not consistency; the anomaly zone is what makes
the most frequent gene tree and the greedy consensus inconsistent, and those lose 0.46 and more.
The shape estimate is within ten per cent of the truth on every world, and twenty loci estimate
it as well as sixty; the true shape gains 0.006. The refusal threshold has slack: on the
reference's loci at its own estimated shape the statistic is at most 146.7 on a tree world and at
least 598.3 on a reticulate one, so 180 and 340 change nothing.

Why the free gene trees cost 0.80 is worth stating precisely. Per locus the free trees are not
uniformly worse: on the anomaly-zone worlds they recover the true gene tree's internal splits
about as often as the corrected trees do (0.76 against 0.78 on the reference's loci). On the
long-branch worlds they are worse per locus (0.66 against 0.77) and, what matters more, their
errors have a direction: they join the two fast species, so over 500 loci the errors add up
instead of cancelling. That is what turns a per-locus estimation error into a wrong species tree
and a spurious reticulation signal, and it is why the free trees decline seven of the eight
development tree worlds when the threshold is in place and name six of them wrong when it is not.

Capping the reference at a fixed number of loci, in catalogue order, regardless of budget:

| loci | development | held out |
|---|---|---|
| 125 | 0.369 | 0.158 |
| 250 | 0.776 | 0.659 |
| 375 | 0.903 | 0.881 |
| 500 (reference) | 0.912 | 0.903 |

The loci are a real cost and not a convenience. Over the six anomaly-zone worlds, exhaustive
quartet consensus on 240 of the true gene trees, with no sequence estimation at all, names the
species tree 94 to 99 times in a hundred over two hundred replicates, and on 500 of them every
time (`truetrees.py` in the construction directory is the check, two hundred replicates per world; the numbers per world are 0.980,
0.950, 0.955, 0.940, 0.970 and 0.990).

## The site-rate shape, estimated

The shape of the gamma distribution of site rates is not published. It cannot be read from
pairwise distances, so the reference reads it from a joint statistic, the share of sites that are
constant across all eight sequences, pooled over its first sixty loci. On every world the
estimate is within ten per cent of the truth, and the refusal statistic at that estimate keeps
tree and reticulate worlds far apart (`shape_estimates.py`):

| world | split | kind | true shape | estimated | statistic | verdict |
|---|---|---|---|---|---|---|
| 71300101 | development | anomaly | 1.000 | 1.050 | 59.5 | tree |
| 71300102 | development | anomaly | 0.342 | 0.370 | 22.8 | tree |
| 71300103 | development | anomaly | 0.200 | 0.220 | 79.8 | tree |
| 71300104 | development | anomaly | 0.585 | 0.620 | 130.2 | tree |
| 71300105 | development | long branch | 0.342 | 0.370 | 91.2 | tree |
| 71300106 | development | long branch | 1.000 | 1.050 | 97.5 | tree |
| 71300107 | development | long branch | 0.200 | 0.180 | 96.5 | tree |
| 71300108 | development | long branch | 0.585 | 0.620 | 49.4 | tree |
| 71300109 | development | reticulate | 1.000 | 1.050 | 945.3 | reticulate |
| 71300110 | development | reticulate | 0.585 | 0.620 | 705.2 | reticulate |
| 71300111 | development | reticulate | 0.342 | 0.370 | 598.3 | reticulate |
| 71300112 | development | reticulate | 0.200 | 0.220 | 613.0 | reticulate |
| 82410201 | held out | anomaly | 1.000 | 1.050 | 68.6 | tree |
| 82410202 | held out | anomaly | 0.200 | 0.180 | 67.2 | tree |
| 82410203 | held out | long branch | 1.000 | 1.050 | 139.3 | tree |
| 82410204 | held out | long branch | 0.200 | 0.220 | 146.7 | tree |
| 82410205 | held out | reticulate | 0.200 | 0.220 | 788.3 | reticulate |
| 82410206 | held out | reticulate | 1.000 | 1.050 | 1007.1 | reticulate |

The shapes are a log-spaced grid over 0.2 to 1 within each kind of world, assigned in an order
fixed by the split's seed, so no single guess fits most of the tree worlds of a split by chance:
over ten guesses from 0.2 to 1.0 (`fixedshape.py`), none reads more than two of the four
development long-branch worlds, and the best of them, 0.4, reads six of the eight development
tree worlds for a score of 0.690. That is what the fixed-shape rungs of the ladder measure: a guess of 0.5 loses 0.34, and 0.2 or
1.0 lose 0.47, mostly by declining tree worlds: gene trees corrected at the wrong shape carry an
imbalance of their own, which the refusal reads as a hybrid, and where they do not they name the
wrong tree. A shape guessed too small pulls the two fast species apart, which is the attraction
with its sign reversed and just as wrong.

## Long-branch attraction, measured

The quantity is the share of gene trees that join the two fast species as sisters, in the true
gene trees of the loci (that share is incomplete lineage sorting, not attraction), in the
sequencing centre's plain Jukes-Cantor trees and in gamma-corrected trees at the world's true
shape. The attraction is the excess of an estimated tree over the truth. 1000 loci of 300 sites or
500 of 800, per world and rate class, from `lba.py`.

| world | class | sites | true | free | excess | corrected | excess |
|---|---|---|---|---|---|---|---|
| 71300105 | slow | 300 | 12.6 | 39.0 | +26.4 | 18.8 | +6.2 |
| 71300105 | slow | 800 | 10.0 | 43.8 | +33.8 | 18.8 | +8.8 |
| 71300105 | medium | 800 | 12.6 | 51.4 | +38.8 | 20.4 | +7.8 |
| 71300105 | fast | 800 | 11.0 | 53.6 | +42.6 | 21.2 | +10.2 |
| 71300106 | slow | 300 | 14.8 | 48.8 | +34.0 | 23.6 | +8.8 |
| 71300106 | slow | 800 | 14.0 | 50.4 | +36.4 | 20.4 | +6.4 |
| 71300106 | medium | 800 | 16.2 | 73.4 | +57.2 | 26.6 | +10.4 |
| 71300106 | fast | 800 | 14.6 | 68.2 | +53.6 | 30.4 | +15.8 |
| 71300107 | slow | 300 | 11.0 | 26.8 | +15.8 | 15.4 | +4.4 |
| 71300107 | slow | 800 | 9.0 | 34.2 | +25.2 | 16.8 | +7.8 |
| 71300107 | medium | 800 | 10.8 | 37.8 | +27.0 | 19.4 | +8.6 |
| 71300107 | fast | 800 | 11.8 | 41.2 | +29.4 | 22.6 | +10.8 |
| 71300108 | slow | 300 | 13.0 | 27.8 | +14.8 | 18.0 | +5.0 |
| 71300108 | slow | 800 | 15.8 | 26.4 | +10.6 | 16.4 | +0.6 |
| 71300108 | medium | 800 | 13.8 | 36.4 | +22.6 | 17.6 | +3.8 |
| 71300108 | fast | 800 | 14.2 | 41.8 | +27.6 | 23.4 | +9.2 |
| 82410203 | slow | 300 | 13.6 | 41.4 | +27.8 | 21.2 | +7.6 |
| 82410203 | slow | 800 | 16.2 | 52.8 | +36.6 | 22.2 | +6.0 |
| 82410203 | medium | 800 | 11.0 | 64.8 | +53.8 | 25.0 | +14.0 |
| 82410203 | fast | 800 | 13.0 | 60.2 | +47.2 | 24.8 | +11.8 |
| 82410204 | slow | 300 | 10.6 | 68.0 | +57.4 | 25.4 | +14.8 |
| 82410204 | slow | 800 | 13.2 | 76.8 | +63.6 | 21.2 | +8.0 |
| 82410204 | medium | 800 | 9.0 | 79.4 | +70.4 | 23.0 | +14.0 |
| 82410204 | fast | 800 | 11.2 | 82.4 | +71.2 | 26.0 | +14.8 |

Percentages of gene trees; the standard error of each share is 1 to 2 points. The excess of the
free trees is positive in every world and every class, and grows with the rate. The gamma
correction removes most of it and not all: the corrected distance is unbiased but noisy on the
long branches, and neighbour joining on noisy distances keeps a small attraction of its own. That
residual is one of the things a better gene-tree estimator would remove.

The same bias, seen from the refusal statistic and from the mean-distance tree, both at the true
shape:

| class | sites | imbalance on free trees, max over tree worlds | min over reticulate worlds | on corrected trees, max tree | min reticulate |
|---|---|---|---|---|---|
| slow | 300 | 889.7 | 144.6 | 381.3 | 297.9 |
| slow | 800 | 974.9 | 99.3 | 604.9 | 599.4 |
| medium | 800 | 1609.8 | 117.3 | 422.0 | 450.1 |
| fast | 800 | 1165.0 | 198.1 | 519.2 | 409.4 |

On the free trees no threshold separates a tree world from a hybrid world in any class: the tree
worlds are above the hybrid ones. On the corrected trees every class separates them, and the
reference's class and length by the widest margin, which the threshold at 260 sits inside.
Neighbour joining on the mean uncorrected distance recovers the species tree in none of the six
long-branch worlds in any cell; on the mean corrected distance it recovers all six in every cell.

## Anomaly-zone statistics

For every tree world, from `anomaly_stats.py`: the probability that a gene tree has the species
tree's unrooted topology, the probability of the most frequent topology, and the difference in
units of its multinomial standard error. Four hundred thousand gene trees for the anomaly-zone
worlds, one hundred thousand for the long-branch worlds, generator seed 5.

| world | kind | p(species tree) | p(most frequent) | difference / se | rank of the species tree |
|---|---|---|---|---|---|
| 71300101 | anomaly | 0.0086 | 0.0107 | 9.5 | 4 |
| 71300102 | anomaly | 0.0027 | 0.0034 | 5.4 | 9 |
| 71300103 | anomaly | 0.0018 | 0.0023 | 5.2 | 22 |
| 71300104 | anomaly | 0.0035 | 0.0044 | 6.7 | 9 |
| 82410201 | anomaly | 0.0085 | 0.0105 | 9.3 | 4 |
| 82410202 | anomaly | 0.0096 | 0.0113 | 7.3 | 3 |
| 71300105 | long branch | 0.0828 | 0.0828 | 0.0 | 1 |
| 71300106 | long branch | 0.0567 | 0.0567 | 0.0 | 1 |
| 71300107 | long branch | 0.1069 | 0.1069 | 0.0 | 1 |
| 71300108 | long branch | 0.0425 | 0.0425 | 0.0 | 1 |
| 82410203 | long branch | 0.0580 | 0.0580 | 0.0 | 1 |
| 82410204 | long branch | 0.0677 | 0.0677 | 0.0 | 1 |

The six anomaly-zone worlds are anomalous by at least five standard errors. The rank is reported
for orientation only: with thousands of distinct topologies at probabilities of a few thousandths,
it moves between runs, and the difference and its standard error are the measurement. The test in
`tests/test_anomaly_zone_species_tree.py` does not compare against the empirical maximum: it
names a competitor topology in advance for each world, the most frequent topology of a run with
seed 5, and checks with fresh gene trees under another seed that the species tree is behind it.
The six long-branch worlds are built with at most one short internal branch and are outside the
zone: there the species tree is the most frequent gene tree, majority vote is consistent, and
what breaks it is the bias in the free trees, not the coalescent.

## Shortcut probe

The question this repository learned to ask after a submitted task turned out to be solvable by a
two-parameter grid search: **how far does a low-dimensional strategy get without the science?**

102060 strategies were scored on the loci a candidate would buy. The gene trees come from one of
seven sources: the sequencing centre's free trees; trees re-estimated by neighbour joining on the
gamma-corrected distance at a guessed shape of 0.2, 0.35, 0.5, 0.7 or 1.0; or, as an oracle no
candidate has, at the world's true shape. The purchase is one of the nine catalogue cells for the
whole budget, or one cell for the topology and another for the refusal statistic and the branch
lengths with half the budget each (81 purchases). The topology is by greedy consensus, the most
frequent gene tree, neighbour joining on the mean distance or quartet consensus; the refusal
never, on a mean gene-tree discordance of 0.5, 0.6 or 0.7, or on the minority-imbalance statistic
at 0.33, 0.48, 0.67, 1.0 or 1.33 per locus; the branch lengths constant at 0.05, 0.1, 0.2 or 0.4,
or from the quartet frequencies.

| family | strategies | best development | its held out |
|---|---|---|---|
| everything a candidate can do (free trees or a guessed shape) | 87480 | **0.780** | 0.644 |
| the free gene trees | 14580 | 0.319 | 0.215 |
| shape guessed at 0.2 | 14580 | 0.672 | 0.655 |
| shape guessed at 0.35 | 14580 | 0.690 | 0.445 |
| shape guessed at 0.5 | 14580 | 0.780 | 0.644 |
| shape guessed at 0.7 | 14580 | 0.647 | 0.216 |
| shape guessed at 1.0 | 14580 | 0.555 | 0.635 |
| quartet consensus, free trees or a guessed shape | 21870 | 0.693 | 0.685 |
| neighbour joining on the mean distance, free trees or a guessed shape | 21870 | 0.780 | 0.644 |
| greedy consensus, free trees or a guessed shape | 21870 | 0.579 | 0.236 |
| most frequent gene tree, free trees or a guessed shape | 21870 | 0.446 | 0.000 |
| one catalogue cell, free trees or a guessed shape | 9720 | 0.693 | 0.685 |
| never declining, free trees or a guessed shape | 9720 | 0.370 | 0.353 |
| declining on gene-tree discordance, free trees or a guessed shape | 29160 | 0.232 | 0.000 |
| medium loci for the topology, free trees or a guessed shape | 29160 | 0.657 | 0.194 |
| fast loci for the topology, free trees or a guessed shape | 29160 | 0.657 | 0.194 |
| constant branch lengths, free trees or a guessed shape | 69984 | 0.666 | 0.558 |
| the true shape (oracle), any method | 14580 | 0.918 | 0.902 |
| the true shape, without quartet consensus | 10935 | 0.910 | 0.864 |
| reference | — | 0.912 | 0.903 |
| ceiling | — | 1.000 | 1.000 |

The best a candidate can do without estimating the shape is 0.780, which is 86 per cent of the
reference on the development split and 71 per cent held out. That strategy averages distances
corrected at a shape of 0.5 over 500 slow 300-site loci for the topology and reads the refusal
and the lengths from 250 slow 800-site loci; it reads the worlds whose shape is near 0.5 and
names the wrong tree on the one development world where the guess over-corrects most, and
trails further held out. At the true shape the same averaging reaches 0.910 and quartet consensus 0.918,
so the science that stands between a searcher and the reference is estimating the shape, not the
name of the consensus method; quartet consensus over the mean distance is then a matter of
efficiency, worth 0.11 on the reference's loci. Every strategy on the free gene trees stays under
0.32. The probe's own weakness is that it never estimates a gene-tree parameter from the data,
and doing that is the first thing the task asks for.

In the first version of the worlds, with the fast species at five to eight times the rate, the
best free-tree strategy reached 0.838 against a reference of 0.877, because the bias was
confined to fast loci and slow loci gave it the topology and the refusal for free. The review of
the first pull request caught that. In the second version the shape was published, and the
review of the second pull request found that re-estimating the distances at the published shape
reached 0.859 against a reference of 0.873; the shape is now unpublished and spread over the
worlds, and estimating it is part of the task.

## Construction errors, found by the checkpoints and by review

Four before any model saw the task, three by the review of the first pull request, and one by
the review of the second.

- **There was no long-branch attraction.** The first two-fast-species worlds put the fast species
  on ordinary branches, and the uncorrected distance moved zero to half a per cent of gene trees.
  The analytic four-point condition showed why: attraction needs the fast species' sisters to be
  short and the branch between them shorter. The worlds became two cherries joined by a branch of
  0.1 to 0.2 coalescent units, with the fast species one from each cherry.
- **The budget could not buy the answer.** At 80 units no quartet strategy recovered any
  anomaly-zone tree and the refusal statistic did not separate hybrid from tree worlds. A
  sorted-difference statistic also turned out to have a null mean independent of the sample
  size, so it could never be thresholded; it was replaced by the chi-square form. The budget was
  raised to 480 and the branches lengthened until the reference read them.
- **One anomaly world was not anomalous.** At short branches of 0.12 to 0.2 coalescent units one
  held-out species tree was the most frequent gene tree by simulation. The range is now 0.1 to
  0.16.
- **The reference tied the probe.** At a budget of 400 the reference lost one development world
  by 0.2 quartet votes out of 243, and the probe's best strategy tied it there at 0.779 against
  0.774 while trailing held out at 0.682 against 0.917. Neither reweighting the quartets, mixing
  rate classes nor bootstrap support moved that world off the edge; each flipped a different
  world. The budget was raised to 480.
- **The attraction was measured as the wrong quantity, and held in two worlds of six.** The
  first version of this document reported the raw rate at which free trees join the two fast
  species, ten to thirty per cent, most of which is incomplete lineage sorting that the true gene
  trees carry too. Measured as the excess over the true gene trees of the same loci, the
  attraction was positive in only two of the six worlds on fast loci and absent on slow loci,
  which is exactly where the probe's best strategy was buying. The fast species went to ten to
  fifteen times the rate on species branches of 0.4 to 0.7 coalescent units, and the excess is
  positive in every world and every class, as the table above shows.
- **Every tree world was said to be in the anomaly zone.** Only the six anomaly-zone worlds are;
  the six long-branch worlds have at most one short internal branch and their species tree is the
  most frequent gene tree. The construction script had filtered to the anomaly worlds while the
  task text, the card and a test named after every tree world claimed otherwise. All of them now
  say exactly what was measured, and the anomaly statistics are reported as probabilities with a
  standard error rather than as a rank.
- **A wrong tree at low confidence escaped the false discovery count.** A tree world named wrong
  counted as a false discovery only above a confidence of 0.5, while a tree on a hybrid world or a
  refusal on a tree world counted unconditionally, so a constant confidence of 0.49 lowered the
  reported rate without changing the score. A wrong tree is now a false discovery whatever its
  confidence, and confidence feeds only the calibration axis.
- **The published shape made the correction a lookup.** The review of the second pull request
  added one row to the shortcut grid, re-estimating the distances at the published shape, and it
  reached 0.859 against a reference of 0.873. The shape is now unpublished, spread over a factor
  of five within each kind of world on a grid fixed by the split's seed, and the reference
  estimates it from the constant-site share. Two side effects of that change were found by the
  checkpoints. First, with the shape spread out the slow rate class became the right one, because
  it is the least saturated and the correction has the least to repair there; the medium class
  the reference had used names two development worlds wrong. Second, the anomaly-zone worlds turned out
  to be sampling-limited: 240 true gene trees name their species tree only 94 to 99 times in a
  hundred, so a run could fail a world with no estimation error at all, and the budget was
  raised to 1000 with 500 loci per catalogue cell, where 500 true gene trees name it every time.

## Robustness

- Twenty malformed candidate shapes — raising, `None`, an empty mapping, a string, a bad verdict,
  a tree verdict without `newick`, an integer `newick`, garbage Newick, a missing taxon, a
  duplicated taxon, no branch lengths, a negative length, a NaN length, an unresolved tree, a NaN
  confidence, a string confidence, overspending the budget, a locus of 9999, a float locus and a
  Newick string of five thousand characters — all score zero with `valid = 0`, and none raises out
  of the evaluator.
- Two consecutive evaluations of the reference are key-identical, and so are their JSON payloads.
- Declining every world scores exactly 0.0 by construction of the normalisation, in the verdict
  form and in the `abstain: true` form; naming one fixed tree everywhere scores 0.0 with a false
  discovery rate of 1.0 at confidence 0.9 and at confidence 0.2 alike.
- Every source file compiles under Python 3.8 syntax, which is what the evaluation host runs.
