# AnomalyZoneSpeciesTree — which species tree, when the commonest gene tree is the wrong one?

## 关系与区别 / How this differs from the nearest tasks in this repository

- **`SystemsBiology/GeneNetworkIntervention`** is the other Biology task in the structure cell. It
  recovers a signed regulatory graph from perturbation experiments and then designs an
  intervention. Here the structure is a **phylogeny**: an unrooted binary tree whose leaves are
  species and whose internal branches carry lengths in coalescent units, and the data are
  sequences, not expression levels.
- **`Algorithm/GraphFromDistances`** recovers a graph from exact shortest-path distances. Here the
  distances are estimates from finite sequences under a model with unpublished rate multipliers,
  the loci disagree with each other by construction, and the tree that fits the mean distance is
  not necessarily the species tree.
- **`Physics/HiddenCouplingNetwork`** infers a coupling graph from dynamics it can drive. There is
  no dynamics to drive here: every locus is an independent draw, and the only choice is which
  loci to buy.
- **`PopulationGenetics/DemographicSFS`** is the nearest in biology, a coalescent inversion, but
  it recovers population-size history for one population from a site-frequency spectrum. This
  task recovers the branching order of eight species, where the coalescent is the reason the
  gene trees disagree with the answer.

- **`Microbiology/MetagenomeCompositionAssignment`** also buys sequencing under a budget and
  also declines when the data cannot be explained. Its object is a composition vector over a
  fixed reference library of marker profiles, and it declines when that library cannot explain
  the counts. Here the object is a tree, the loci disagree because of the coalescent and not
  because of a library, and the refusal comes from an asymmetry between minority quartet
  topologies that no tree can produce.

No task in the Frontier-Eng catalogue concerns phylogenetics, the multispecies coalescent or
species-tree estimation.

## The question

Eight species, one sampled genome each. A catalogue of loci is on offer, each with a length in
sites, a rate class and a price. Each locus you buy returns an alignment of eight sequences and,
as a convenience, the neighbour-joining gene tree the sequencing centre computed for it. From what
you buy, name the unrooted species tree and the length of each of its five internal branches in
coalescent units, or say that no species tree generated these loci because one species is a
hybrid.

## Four ways to be wrong

- **The commonest gene tree is not the species tree.** Every locus is a draw from the
  multispecies coalescent on the species tree. When two adjacent internal branches are short
  enough, the species tree lies in the *anomaly zone*: a gene tree with a different topology is
  the most probable one, and the majority vote over gene trees converges to the wrong answer as
  the number of loci grows. Four of the twelve development worlds are built in that zone, with
  adjacent internal branches of 0.1 to 0.16 coalescent units, and in each of them the species
  tree is measured to be behind the most probable gene-tree topology. Concatenating the loci and
  building one tree is inconsistent for the same reason. The other tree worlds are built outside
  the zone, with at most one short internal branch: there the species tree is the most probable
  gene tree, and nothing in the data announces which kind of world you are in. What is never
  anomalous is a **quartet**: for any four species, the species-tree quartet is the most probable
  gene-tree quartet under any branch lengths, and how probable depends only on the length of the
  internal path between the two pairs.
- **Two species evolve fast, and the free gene trees join them.** Two non-adjacent species carry a
  rate multiplier that is not published. Sites evolve with gamma-distributed rates whose shape
  lies between 0.2 and 1 and is not published either, and the sequencing centre's tree uses the
  plain Jukes-Cantor distance, which ignores that. The omission compresses long distances more
  than short ones, so the two long branches are drawn together: long-branch attraction, in its
  distance-method form. Measured against the true gene trees of the same loci, the free trees
  join the two fast species more often by 11 to 64 percentage points on slow loci, 23 to 70 on
  medium loci and 28 to 71 on fast loci, in every such world. The bias is present in every rate
  class and grows with the rate, and averaging the uncorrected distances over loci does not
  remove it, because it is a bias and not noise. Correcting the distances at a guessed shape does
  not remove it either: the shapes of the worlds are spread over a factor of five, gene trees
  corrected at the wrong shape carry an imbalance of their own that names the wrong tree or
  reads as a hybrid, and no single guess reads more than two of the four long-branch worlds of
  the development split, or more than six of its eight tree worlds. The shape has to be
  estimated from the alignments, and pairwise distances alone cannot see it.
- **A hybrid species has no species tree.** In some worlds one species descends from two parents,
  and each locus follows one parent or the other with a fixed inheritance probability. Under any
  species tree the two minority topologies of a quartet are equally probable; a hybrid makes them
  unequal on the quartets that contain it. Nothing in the public problem says which worlds are
  reticulate: the evidence is in the loci you buy, and the free gene trees carry a bias of their
  own that mimics it.
- **Short branches cost loci.** The shortest internal branches are a tenth of a coalescent unit.
  The quartet signal for such a branch is a few per cent of the gene trees, so it takes hundreds
  of loci to read it: over the six anomaly-zone worlds, exhaustive quartet consensus on 240 of
  the true gene trees names the species tree 94 to 99 times in a hundred, and on 500 of them
  every time. A locus of three hundred slow sites often does not resolve such a branch at all.
  The catalogue prices length, not rate class, and the budget buys a fraction of what is on offer.

The reticulate world is the declining case. A tree world is determinable, and declining it is a
false discovery: it claims a mechanism, hybridisation, that is not there.

## Where the budget actually goes

The budget is 1000 units. A locus of 300 sites costs 1, of 800 sites 2, of 2000 sites 5, so the
whole budget is 1000 short loci, 500 medium ones or 200 long ones, in any mixture. The catalogue
holds 500 loci of each rate class and length, 4500 in all. Halving the reference's spend costs it
0.14 of the score and a quarter of the budget 0.54 on the development split, so the
question is not whether to spend but on what: rate class decides whether the short branches are
resolved and whether the long ones are distorted, and length decides how many independent draws
of the coalescent you see.

## What you implement

```python
def infer_species_tree(problem, sequence):
    ...
    return {"verdict": "tree", "newick": "((A:1,B:1):0.12,...);", "confidence": 0.8}
```

### `problem` — every key you are given

| key | meaning |
|---|---|
| `taxa` | the eight species names, `A` to `H` |
| `locus_budget` | how many cost units you may spend on this world (1000) |
| `catalogue` | one entry per locus on offer: `{"locus", "sites", "rate_class", "cost"}`; `locus` is the integer you pass to `sequence`, `sites` is 300, 800 or 2000, `rate_class` is `slow`, `medium` or `fast`, `cost` is 1, 2 or 5 |
| `coalescent_model` | prose: one lineage per species, independent loci under the multispecies coalescent, branch lengths in coalescent units |
| `sequence_model` | prose: Jukes-Cantor with gamma-distributed site rates of an unpublished shape between 0.2 and 1, three rate classes about a factor of three apart, and unpublished per-species rate multipliers |
| `gene_tree_estimate` | prose: what `nj_tree` is and what it does not correct for |
| `reticulation_model` | prose: one hybrid species with a fixed inheritance probability, in some worlds |
| `abstain_when` | prose: when the verdict is `reticulate` |
| `answer_format` | prose: what a tree verdict must contain |

### `sequence(locus)`

Charges the catalogue cost of that locus and returns `{"locus", "sites", "rate_class",
"alignment", "nj_tree"}`. `alignment` maps each taxon to a string of `sites` nucleotides;
`nj_tree` is a Newick string with branch lengths in substitutions per site, unrooted, from
neighbour joining on the plain Jukes-Cantor distance. `locus` must be an integer index into the
catalogue. Buying a locus twice returns the same data and is charged once. Spending past the
budget raises and the world scores zero, so count your units.

### What you return

| key | meaning |
|---|---|
| `verdict` | `"tree"` or `"reticulate"` |
| `newick` | required when the verdict is `tree`: an unrooted binary tree on exactly the eight taxa, each once, with a finite non-negative length on every branch; the five internal lengths are read in coalescent units, the pendant ones are ignored |
| `confidence` | in `[0, 1]`; clipped |
| `abstain` | `True` is accepted as a synonym for the reticulate verdict |

Anything malformed scores that world zero. It is never an infrastructure failure.
`sle.contract_lint` is importable and free to call for shape checks; it costs no locus.

## How you are scored

Twelve development worlds: four in the anomaly zone, four with two fast-evolving species, four
with a hybrid. Each contributes a mechanism score:

- **tree world**: the right unrooted topology scores `0.5 + 0.5 * branch_score`, where the
  branch score is the mean over the five internal branches of `exp(-|ln(estimate / truth)|)`,
  so a length off by a factor of two scores 0.5 on that branch. The wrong topology scores 0 and
  is a false discovery whatever the confidence. Declining scores 0 and is a false discovery.
- **reticulate world**: declining scores 1 and is a correct refusal; any tree scores 0 and is a
  false discovery.

`combined_score` is the mean over the development worlds, renormalised so that **declining every
world scores exactly 0.0**. Naming one fixed tree everywhere also scores 0.0. `confidence` feeds
only the calibration axis: it cannot lower the false discovery rate.

Reported separately, never averaged into one number:

`development_topology_rate` · `development_branch_length_score` ·
`development_false_discovery_rate` · `development_correct_refusal_rate` ·
`development_discovery_coverage` · `development_confidence_calibration` ·
`development_mean_loci_bought` · `development_mean_budget_spent` · `development_raw_mechanism`

A sealed held-out set of six further worlds, two of each kind, is scored too, under the same
keys with the `heldout_` prefix, and is not visible to a searcher. `per_instance` carries one row
per world.

## What each competence is worth

Ablating the reference, one choice changed at a time:

| strategy | score | topology | branch lengths | false discovery | refusal | coverage | held out |
|---|---|---|---|---|---|---|---|
| gamma-corrected distance gene trees from 500 slow loci of 800 sites at a site-rate shape estimated from the alignments, quartet consensus, quartet-frequency lengths, minority-imbalance refusal | **0.912** | 1.00 | 0.82 | 0.00 | 1.00 | 1.00 | 0.903 |
| same, but the sequencing centre's uncorrected gene trees | 0.111 | 0.12 | 0.10 | 0.58 | 1.00 | 0.12 | 0.225 |
| same, shape fixed at 0.5 instead of estimated | 0.575 | 0.62 | 0.52 | 0.25 | 1.00 | 0.75 | 0.685 |
| same, shape fixed at 0.2 | 0.450 | 0.50 | 0.40 | 0.33 | 1.00 | 0.50 | 0.437 |
| same, shape fixed at 1.0 | 0.446 | 0.50 | 0.39 | 0.33 | 1.00 | 0.50 | 0.465 |
| same, shape estimated from 20 loci instead of 60 | 0.913 | 1.00 | 0.83 | 0.00 | 1.00 | 1.00 | 0.906 |
| same, the true shape (an oracle no candidate has) | 0.918 | 1.00 | 0.84 | 0.00 | 1.00 | 1.00 | 0.902 |
| same, medium loci instead of slow | 0.648 | 0.75 | 0.55 | 0.17 | 1.00 | 1.00 | 0.668 |
| same, fast loci instead of slow | 0.320 | 0.38 | 0.26 | 0.42 | 1.00 | 0.62 | 0.632 |
| same, 300-site loci (all 500 of them) instead of 800 | 0.749 | 0.88 | 0.62 | 0.08 | 1.00 | 1.00 | 0.826 |
| same, 2000-site loci (200 of them) instead of 800 | 0.567 | 0.75 | 0.63 | 0.25 | 0.75 | 1.00 | 0.879 |
| same, never declining | 0.412 | 1.00 | 0.82 | 0.33 | 0.00 | 1.00 | 0.403 |
| same, greedy consensus of the gene trees instead of quartets | 0.457 | 0.50 | 0.41 | 0.33 | 1.00 | 1.00 | 0.664 |
| same, one neighbour joining on the mean corrected distance instead of quartets | 0.800 | 0.88 | 0.73 | 0.08 | 1.00 | 1.00 | 0.664 |
| same, constant branch lengths of 0.1 | 0.728 | 1.00 | 0.46 | 0.00 | 1.00 | 1.00 | 0.692 |
| same, half the budget | 0.776 | 1.00 | 0.80 | 0.08 | 0.75 | 1.00 | 0.659 |
| same, a quarter of the budget | 0.369 | 1.00 | 0.74 | 0.33 | 0.00 | 1.00 | 0.158 |
| uncorrected gene trees and fast loci | 0.000 | 0.00 | 0.00 | 0.67 | 1.00 | 0.00 | 0.000 |
| uncorrected gene trees, never declining | 0.000 | 0.25 | 0.18 | 0.83 | 0.00 | 1.00 | 0.000 |
| concatenation of the longest fast loci, plain Jukes-Cantor, never declining (baseline) | 0.000 | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 0.000 |
| declining everything | 0.000 | — | — | 0.67 | 1.00 | 0.00 | 0.000 |

Every row costs something real: trusting the free gene trees costs 0.80, a guessed shape 0.34 to
0.47, never declining 0.50, greedy consensus 0.46, medium loci 0.26, fast loci 0.59, the wrong
locus length 0.16 or 0.35, half the budget 0.14, a quarter 0.54 and constant branch lengths 0.18.
The mean corrected distance is a consistent estimator here and loses 0.11 on the development
split and 0.24 held out: quartet consensus buys statistical efficiency on the short branches, not
consistency. The shape estimate is within ten per cent of the truth on every world, and the true
shape gains 0.006. The reference's branch-length score is 0.82, because it inverts the quartet
frequencies without correcting for gene-tree estimation error, and that is where most of what
remains lives.

**Low-dimensional shortcuts do not solve this task.** A sweep of 102060 strategies was scored on
the loci a candidate would buy: the gene trees taken as the sequencing centre gives them, or
re-estimated by neighbour joining on the gamma-corrected distance at a guessed shape of 0.2,
0.35, 0.5, 0.7 or 1.0, or, as an oracle no candidate has, at the world's true shape; one
catalogue cell for the whole budget, or one cell for the topology and another for the refusal
and the lengths; topology by greedy consensus, the most frequent gene tree, neighbour joining on
the mean distance or quartet consensus; refusal never, on a discordance threshold or on the
minority-imbalance statistic at five levels; branch lengths constant or from the quartet
frequencies. Without the true shape the best of them reaches **0.780** on the development split
and 0.644 held out, against the reference's 0.912 and 0.903 and a ceiling of 1.0; on the free
gene trees the best is 0.319 and 0.215. The best guess averages corrected distances at a shape of
0.5, which reads the worlds whose shape is near 0.5 and over- or under-corrects the rest. With
the true shape the same averaging reaches 0.910 and quartet consensus 0.918, so what stands
between a searcher and the reference is estimating the shape, not knowing the name of the
method.

## Rules

- Only edit `solution.py`; keep `infer_species_tree(problem, sequence)`.
- `sle.contract_lint` is importable and free to call for shape checks. It costs no locus.
- Do not read `verification/` or `frontier_eval/`.
