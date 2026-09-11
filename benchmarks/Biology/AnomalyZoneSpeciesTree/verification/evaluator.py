"""Hidden oracle for AnomalyZoneSpeciesTree.

Eight species, one lineage sampled from each, and a public catalogue of loci that can be
sequenced for a price. The candidate must say which species tree the loci come from, with its
internal branch lengths in coalescent units, or say that no species tree explains them because
one species is a hybrid of two others.

Three things make this hard, and every world carries at least one of them:

    the anomaly zone     when consecutive internal branches of the species tree are short in
                         coalescent units, the most probable gene tree is not the species tree
                         (Degnan and Rosenberg 2006; Degnan 2013 for the unrooted case). Then
                         the most common gene tree, the greedy consensus and concatenation all
                         converge on the wrong tree (Kubatko and Degnan 2007). Quartets are the
                         way out: no quartet is ever anomalous (Allman, Degnan and Rhodes 2011),
                         so a tree assembled from quartet majorities is consistent.
    long-branch attraction  two species evolve an order of magnitude faster than the rest.
                         Sites evolve with gamma-distributed rates of an unpublished shape, and
                         the gene-tree estimate that comes free with every locus is neighbour
                         joining on the plain Jukes-Cantor distance, which omits the gamma
                         correction. The omitted correction compresses the longest distances
                         most, and the two fast species are pulled together (Felsenstein 1978).
                         The bias grows with the substitution rate of the locus, and the
                         correction that removes it needs the shape, which has to be estimated
                         from the alignments: the shapes of a split are spread over a factor of
                         five, so no single guess reads more than two of the four long-branch
                         worlds of a split.
    reticulation         one species descends from two parents, each locus following one of them.
                         Every gene tree is a perfectly good tree; what no species tree can
                         produce is the quartet spectrum, in which the two minority topologies of
                         quartets that contain the hybrid are unequal (Solis-Lemus and Ane 2016).
                         The honest answer is to decline to name a tree.

The candidate buys loci; each purchase returns the alignment and the oracle's own neighbour-joining
tree. Scoring keeps the discovery axes separate and normalises so that declining every world
scores exactly zero.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import msc  # noqa: E402

TAXA = msc.TAXA
N_TAXA = msc.N_TAXA
DEVELOPMENT_BUDGET = 1000
HELDOUT_BUDGET = 1000
CATALOGUE_SIZE = 4500
LOCUS_SITES = (300, 800, 2000)
LOCUS_COST = {300: 1, 800: 2, 2000: 5}
RATE_CLASSES = ("slow", "medium", "fast")
# Substitutions per site per coalescent unit for each class. Even the slow class puts the two
# fast species of a long-branch world a quarter of the way to saturation, so no class escapes the
# site-rate correction; the fast class saturates the long distances outright.
CLASS_RATE = {"slow": 0.03, "medium": 0.1, "fast": 0.3}
# Sites evolve with gamma-distributed rates. The shape differs between worlds and is not
# published: within each kind of world the shapes of a split cover this range on a log-spaced
# grid (see _assign_shapes), so a candidate that corrects its distances has to estimate the shape
# from the alignments; one guessed shape reads at most two of the four long-branch worlds of a
# split.
SHAPE_RANGE = (0.2, 1.0)
# Species-specific rate multipliers: every world carries mild heterogeneity, and the long-branch
# worlds carry two species accelerated by this much. At five to eight times the rate the plain
# Jukes-Cantor distance was biased only on fast loci, and only in some worlds; at ten to fifteen
# times, on species branches of 0.4 to 0.7 coalescent units, the free gene trees join the two
# fast species more often than the true gene trees do in every long-branch world and every rate
# class, and the gamma-corrected distance removes most of that.
MILD_RATE_SIGMA = 0.15
# The anomaly-zone worlds accelerate one non-adjacent pair by this much: enough that a wrong
# site-rate shape biases their gene trees too, not enough to pull the pair together once the
# shape is right.
ANOMALY_PAIR_MULTIPLIER = (4.0, 6.0)
LONG_BRANCH_MULTIPLIER = (10.0, 15.0)
# Branch increments in coalescent units.
SHORT_BRANCH = (0.1, 0.16)
JOIN_BRANCH = (0.15, 0.25)
CHERRY_HEIGHT = (0.4, 0.7)
MODERATE_BRANCH = (0.3, 0.8)
RETICULATE_BRANCH = (0.35, 0.6)
INHERITANCE = (0.4, 0.5)
# Estimated internal branch lengths are scored on a log scale: exp(-|ln(est/true)|).
MIN_BRANCH = 1e-3

WORLD_KINDS = ("anomaly", "long_branch", "reticulate")


# ----------------------------------------------------------------------------------------------
# Species trees
# ----------------------------------------------------------------------------------------------

def _build(structure, heights):
    """Nested tuples of taxon indices with a height per internal node (keyed by the frozenset of
    its leaves) into a `Rooted` with leaves 0..7 and internal nodes in postorder."""
    children = [() for _ in range(N_TAXA)]
    height = [0.0] * N_TAXA

    def visit(node):
        if isinstance(node, int):
            return node, frozenset([node])
        kids = []
        leaves = frozenset()
        for kid in node:
            index, members = visit(kid)
            kids.append(index)
            leaves = leaves | members
        children.append(tuple(kids))
        height.append(float(heights[leaves]))
        return len(children) - 1, leaves

    visit(structure)
    return msc.Rooted(children, height)


def _clades(structure):
    if isinstance(structure, int):
        return frozenset([structure]), []
    members = frozenset()
    found = []
    kids = []
    for kid in structure:
        m, inner = _clades(kid)
        members = members | m
        found.extend(inner)
        kids.append(m)
    found.append((members, kids))
    return members, found


def _assign_heights(structure, increment):
    """Heights by postorder: each internal node sits `increment(clade)` above its tallest child."""
    _, clades = _clades(structure)
    heights = {}
    for members, kids in clades:
        below = max((heights.get(k, 0.0) for k in kids), default=0.0)
        heights[members] = below + float(increment(members, kids))
    return heights


def _anomaly_world(rng):
    p = [int(x) for x in rng.permutation(N_TAXA)]
    if rng.integers(0, 2) == 0:
        structure = (((((((p[0], p[1]), p[2]), p[3]), p[4]), p[5]), p[6]), p[7])
    else:
        structure = ((((((p[0], p[1]), p[2]), p[3]), p[4]), (p[5], p[6])), p[7])
    cherry = frozenset(p[:2])
    short = {frozenset(p[:k]) for k in (3, 4, 5, 6)}

    def increment(members, kids):
        if members == cherry:
            return rng.uniform(*MODERATE_BRANCH)
        if members in short:
            return rng.uniform(*SHORT_BRANCH)
        return rng.uniform(*MODERATE_BRANCH)

    tree = _build(structure, _assign_heights(structure, increment))
    multiplier = list(np.exp(rng.normal(0.0, MILD_RATE_SIGMA, size=N_TAXA))) + [1.0] * (tree.size - N_TAXA)
    # A mildly accelerated pair that is not a cherry: the first taxon and one from the far end.
    for taxon in (p[0], p[6]):
        multiplier[taxon] *= float(rng.uniform(*ANOMALY_PAIR_MULTIPLIER))
    return {"trees": [tree], "gamma": 1.0, "multiplier": multiplier, "hybrid": None}


def _long_branch_world(rng):
    p = [int(x) for x in rng.permutation(N_TAXA)]
    if rng.integers(0, 2) == 0:
        structure = (((((p[0], p[1]), (p[2], p[3])), p[4]), (p[5], p[6])), p[7])
    else:
        structure = ((((p[0], p[1]), (p[2], p[3])), (p[4], p[5])), (p[6], p[7]))
    cherries = {frozenset(p[0:2]), frozenset(p[2:4])}
    join = frozenset(p[0:4])

    def increment(members, kids):
        if members in cherries:
            return rng.uniform(*CHERRY_HEIGHT)
        if members == join:
            return rng.uniform(*JOIN_BRANCH)
        return rng.uniform(*MODERATE_BRANCH)

    tree = _build(structure, _assign_heights(structure, increment))
    multiplier = list(np.exp(rng.normal(0.0, MILD_RATE_SIGMA, size=N_TAXA))) + [1.0] * (tree.size - N_TAXA)
    for taxon in (p[0], p[2]):
        multiplier[taxon] *= float(rng.uniform(*LONG_BRANCH_MULTIPLIER))
    return {"trees": [tree], "gamma": 1.0, "multiplier": multiplier, "hybrid": None}


def _reticulate_world(rng):
    p = [int(x) for x in rng.permutation(N_TAXA)]
    hybrid = p[0]
    first = ((((hybrid, p[1]), (p[2], p[3])), (p[4], p[5])), (p[6], p[7]))
    second = (((p[1], (p[2], p[3])), ((hybrid, p[4]), p[5])), (p[6], p[7]))
    heights = _assign_heights(first, lambda members, kids: rng.uniform(*RETICULATE_BRANCH))
    # The second parental tree shares every height that does not involve the hybrid, and attaches
    # the hybrid below the (p4, p5) cherry.
    second_heights = {}
    for members in heights:
        second_heights[members] = heights[members]
    without = {}
    for members, value in heights.items():
        without[members - {hybrid}] = value
    t_cherry = heights[frozenset([p[4], p[5]])]
    second_heights[frozenset([hybrid, p[4]])] = float(rng.uniform(0.3, 0.7)) * t_cherry
    second_heights[frozenset([p[1], p[2], p[3]])] = heights[frozenset([hybrid, p[1], p[2], p[3]])]
    second_heights[frozenset([hybrid, p[4], p[5]])] = t_cherry
    second_heights[frozenset([p[1], p[2], p[3], hybrid, p[4], p[5]])] = heights[
        frozenset([hybrid, p[1], p[2], p[3], p[4], p[5]])]
    tree_one = _build(first, heights)
    tree_two = _build(second, second_heights)
    multiplier = list(np.exp(rng.normal(0.0, MILD_RATE_SIGMA, size=N_TAXA))) + [1.0] * (tree_one.size - N_TAXA)
    gamma = float(rng.uniform(*INHERITANCE))
    return {"trees": [tree_one, tree_two], "gamma": gamma, "multiplier": multiplier, "hybrid": hybrid}


def _catalogue():
    rows = []
    for index in range(CATALOGUE_SIZE):
        sites = LOCUS_SITES[index % len(LOCUS_SITES)]
        rate_class = RATE_CLASSES[(index // len(LOCUS_SITES)) % len(RATE_CLASSES)]
        rows.append({"locus": index, "sites": sites, "rate_class": rate_class, "cost": LOCUS_COST[sites]})
    return rows


def _world(spec):
    rng = np.random.default_rng(spec["seed"])
    kind = spec["kind"]
    if kind not in WORLD_KINDS:
        raise ValueError("unknown world kind: %r" % (kind,))
    builder = {"anomaly": _anomaly_world, "long_branch": _long_branch_world,
               "reticulate": _reticulate_world}[kind]
    world = builder(rng)
    world.update({"kind": kind, "seed": spec["seed"], "budget": int(spec["budget"]),
                  "catalogue": _catalogue(), "shape": float(spec["shape"])})
    world["truth_splits"] = world["trees"][0].unrooted_splits() if kind != "reticulate" else None
    return world


def _simulate(world, index):
    """One locus: its gene tree under the (network) coalescent and its alignment under the world's
    site-rate shape. Returns the gene tree, its scaled branch lengths and the alignment; the free
    tree and the public row are built from these in `_locus`."""
    entry = world["catalogue"][index]
    rng_tree = np.random.default_rng((world["seed"], 9, index))
    if len(world["trees"]) == 1 or rng_tree.random() < world["gamma"]:
        species = world["trees"][0]
    else:
        species = world["trees"][1]
    gene_tree, scaled = msc.simulate_gene_tree(species, rng_tree, world["multiplier"])
    rng_sites = np.random.default_rng((world["seed"], 11, index))
    alignment = msc.simulate_alignment(gene_tree, scaled, CLASS_RATE[entry["rate_class"]],
                                       entry["sites"], world["shape"], rng_sites)
    return gene_tree, scaled, alignment


def _locus(world, index):
    """Simulate one locus and package it as the candidate sees it."""
    entry = world["catalogue"][index]
    gene_tree, scaled, alignment = _simulate(world, index)
    nj = msc.neighbour_joining(msc.jc_distances(alignment))
    rows = msc.to_strings(alignment)
    return {"locus": index, "sites": entry["sites"], "rate_class": entry["rate_class"],
            "alignment": {TAXA[i]: rows[i] for i in range(N_TAXA)},
            "nj_tree": msc.unrooted_newick(nj)}


class _Campaign:
    """The candidate's only view of the genomes: one locus per call, charged at catalogue price."""

    def __init__(self, world):
        self.world = world
        self.budget = world["budget"]
        self.spent = 0
        self.bought = {}
        self.violated = False

    def __call__(self, locus):
        if isinstance(locus, bool) or not isinstance(locus, (int, np.integer)):
            raise ValueError("locus must be an integer index into the catalogue")
        locus = int(locus)
        if not 0 <= locus < CATALOGUE_SIZE:
            raise ValueError("locus must lie in 0..%d" % (CATALOGUE_SIZE - 1))
        if locus in self.bought:
            return dict(self.bought[locus])
        cost = self.world["catalogue"][locus]["cost"]
        if self.spent + cost > self.budget:
            self.violated = True
            raise RuntimeError("sequencing budget exhausted")
        self.spent += cost
        result = _locus(self.world, locus)
        self.bought[locus] = result
        return dict(result)


PUBLIC_PROBLEM = {
    "taxa": list(TAXA),
    "locus_budget": DEVELOPMENT_BUDGET,
    "catalogue": None,
    "coalescent_model": "one lineage is sampled from each of the eight species; every locus "
                        "is an independent draw of a gene tree under the multispecies coalescent "
                        "on the species tree, with branch lengths measured in coalescent units "
                        "and equal population sizes throughout, so incomplete lineage sorting "
                        "makes gene trees disagree with the species tree and with each other",
    "sequence_model": "along its gene tree each locus evolves under Jukes-Cantor with "
                      "gamma-distributed rate variation across sites; the shape of that gamma "
                      "distribution is the same for every locus of a world, lies between 0.2 "
                      "and 1, and is not published; loci fall into three classes, slow, medium "
                      "and fast, whose substitution rates per coalescent unit differ by about "
                      "a factor of three from class to class, and some species evolve faster "
                      "than others by a factor that is not published",
    "gene_tree_estimate": "each purchase also returns nj_tree, an unrooted gene tree estimated by "
                          "neighbour joining on the plain Jukes-Cantor distance between the "
                          "sequences, without any correction for rate variation across sites; "
                          "it is provided as a convenience and carries the biases of that method",
    "reticulation_model": "some worlds contain one hybrid species that descends from two parents; "
                          "each locus follows one parent or the other with a fixed inheritance "
                          "probability, and no single species tree generates such loci",
    "abstain_when": "the loci cannot have come from any species tree because one species is a "
                    "hybrid; then the verdict is reticulate and no tree is named",
    "answer_format": "verdict is tree or reticulate; when it is tree, newick names an unrooted "
                     "binary tree on exactly the eight taxa with a branch length on every edge, "
                     "the internal ones in coalescent units",
}


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    if submission.get("abstain", False) is True:
        return None, confidence, True
    verdict = submission.get("verdict")
    if verdict == "reticulate":
        return None, confidence, True
    if verdict != "tree":
        raise ValueError("verdict must be 'tree' or 'reticulate'")
    newick = submission.get("newick")
    if not isinstance(newick, str):
        raise ValueError("newick must be a string when the verdict is tree")
    if len(newick) > 4000:
        raise ValueError("newick is unreasonably long")
    _, adjacency = msc.parse_newick(newick)
    splits = msc.splits_of(adjacency)
    if len(splits) != N_TAXA - 3:
        raise ValueError("tree must be binary: %d internal branches, expected %d" % (len(splits), N_TAXA - 3))
    for mask, length in splits.items():
        if not math.isfinite(length) or length < 0.0:
            raise ValueError("branch lengths must be finite and non-negative")
    return splits, confidence, False


def _branch_score(claimed, truth):
    scores = []
    for mask, true_length in truth.items():
        est = max(float(claimed[mask]), MIN_BRANCH)
        scores.append(math.exp(-abs(math.log(est / true_length))))
    return float(np.mean(scores))


def _metrics(world, splits, confidence, abstain):
    blank = {"topology_correct": False, "branch_length_score": 0.0, "mechanism_score": 0.0,
             "false_discovery": False, "correct_refusal": False}
    if world["kind"] == "reticulate":
        blank.update({"mechanism_score": 1.0 if abstain else 0.0, "correct_refusal": bool(abstain),
                      "false_discovery": not abstain})
        return blank
    if abstain:
        # Declaring a hybrid where there is none is a claim about a mechanism, not a shrug.
        blank["false_discovery"] = True
        return blank
    truth = world["truth_splits"]
    if not msc.same_topology(splits, truth):
        # A wrong tree is a false discovery whatever the confidence; confidence only feeds the
        # calibration axis, so a low confidence cannot buy a lower false discovery rate.
        blank["false_discovery"] = True
        return blank
    branch = _branch_score(splits, truth)
    blank.update({"topology_correct": True, "branch_length_score": branch,
                  "mechanism_score": 0.5 + 0.5 * branch})
    return blank


DEVELOPMENT_WORLDS = (
    {"kind": "anomaly", "seed": 71300101, "budget": DEVELOPMENT_BUDGET},
    {"kind": "anomaly", "seed": 71300102, "budget": DEVELOPMENT_BUDGET},
    {"kind": "anomaly", "seed": 71300103, "budget": DEVELOPMENT_BUDGET},
    {"kind": "anomaly", "seed": 71300104, "budget": DEVELOPMENT_BUDGET},
    {"kind": "long_branch", "seed": 71300105, "budget": DEVELOPMENT_BUDGET},
    {"kind": "long_branch", "seed": 71300106, "budget": DEVELOPMENT_BUDGET},
    {"kind": "long_branch", "seed": 71300107, "budget": DEVELOPMENT_BUDGET},
    {"kind": "long_branch", "seed": 71300108, "budget": DEVELOPMENT_BUDGET},
    {"kind": "reticulate", "seed": 71300109, "budget": DEVELOPMENT_BUDGET},
    {"kind": "reticulate", "seed": 71300110, "budget": DEVELOPMENT_BUDGET},
    {"kind": "reticulate", "seed": 71300111, "budget": DEVELOPMENT_BUDGET},
    {"kind": "reticulate", "seed": 71300112, "budget": DEVELOPMENT_BUDGET},
)

HELDOUT_WORLDS = (
    {"kind": "anomaly", "seed": 82410201, "budget": HELDOUT_BUDGET},
    {"kind": "anomaly", "seed": 82410202, "budget": HELDOUT_BUDGET},
    {"kind": "long_branch", "seed": 82410203, "budget": HELDOUT_BUDGET},
    {"kind": "long_branch", "seed": 82410204, "budget": HELDOUT_BUDGET},
    {"kind": "reticulate", "seed": 82410205, "budget": HELDOUT_BUDGET},
    {"kind": "reticulate", "seed": 82410206, "budget": HELDOUT_BUDGET},
)



def _assign_shapes(specs, seed):
    """The site-rate shapes of a split: within each kind of world they are a log-spaced grid over
    SHAPE_RANGE, assigned in an order fixed by the seed, so that no single guessed shape fits
    most of the tree worlds of a split by chance."""
    for kind in WORLD_KINDS:
        members = [spec for spec in specs if spec["kind"] == kind]
        grid = np.exp(np.linspace(math.log(SHAPE_RANGE[0]), math.log(SHAPE_RANGE[1]), len(members)))
        order = np.random.default_rng(seed + WORLD_KINDS.index(kind)).permutation(len(members))
        for spec, position in zip(members, order):
            spec["shape"] = float(grid[position])


_assign_shapes(DEVELOPMENT_WORLDS, 71300100)
_assign_shapes(HELDOUT_WORLDS, 82410200)

ROW_KEYS = ("topology_correct", "branch_length_score", "mechanism_score", "false_discovery",
            "correct_refusal")


def _public_problem(world):
    problem = dict(PUBLIC_PROBLEM)
    problem.update({
        "locus_budget": world["budget"],
        "catalogue": [dict(row) for row in world["catalogue"]],
    })
    return problem


def _evaluate_world(infer_species_tree, spec, split, index):
    world = _world(spec)
    campaign = _Campaign(world)
    problem = _public_problem(world)
    base = {"split": split, "world_index": int(index), "kind": world["kind"],
            "true_newick": world["trees"][0].newick() if world["kind"] != "reticulate" else None,
            "loci_bought": 0, "budget_spent": 0}
    try:
        submission = infer_species_tree(problem, campaign)
        splits, confidence, abstain = _validate_submission(submission)
        if campaign.violated:
            raise RuntimeError("sequencing budget exceeded")
        metrics = _metrics(world, splits, confidence, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_newick": None if abstain else msc.splits_to_newick(splits),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "loci_bought": len(campaign.bought),
            "budget_spent": campaign.spent,
        })
        for key in ("branch_length_score", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key.endswith("_score") else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_newick": None,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "loci_bought": len(campaign.bought),
            "budget_spent": campaign.spent,
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] != "reticulate"]
    unsupported = [r for r in records if r["kind"] == "reticulate"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "topology_rate": float(np.mean([r["topology_correct"] for r in determinable])),
        "branch_length_score": float(np.mean([r["branch_length_score"] for r in determinable])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in records])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_loci_bought": float(np.mean([r["loci_bought"] for r in records])),
        "mean_budget_spent": float(np.mean([r["budget_spent"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
    }


def evaluate(infer_species_tree):
    development = [_evaluate_world(infer_species_tree, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(infer_species_tree, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_WORLDS)]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    valid = 1.0 if dev["valid_count"] > 0 else 0.0
    return {
        "combined_score": dev["normalized_mechanism"] if valid else 0.0,
        "valid": valid,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"] if valid else 0.0,
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_topology_rate": dev["topology_rate"],
        "development_branch_length_score": dev["branch_length_score"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_loci_bought": dev["mean_loci_bought"],
        "development_mean_budget_spent": dev["mean_budget_spent"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_topology_rate": held["topology_rate"],
        "heldout_branch_length_score": held["branch_length_score"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
