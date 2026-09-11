"""Hidden oracle for LDMismatchFineMapping.

A genome-wide association study of twenty thousand people found a signal at a locus of sixty
typed variants. The candidate sees the marginal z-score of every variant, the allele
frequencies, and the linkage-disequilibrium matrix of a public reference panel of five hundred
people from a related but not identical population. It must say which typed variants are causal
and with what effect, or say that the association cannot be resolved to a causal set. It may buy
in-sample linkage-disequilibrium rows: the exact correlation of one chosen variant with every
other variant in the study cohort, at one unit each, under a budget of a few rows.

What makes it hard:

    LD mismatch          the reference panel's correlations differ from the cohort's, so a
                         fine-mapping that trusts them is confident and wrong (Benner et al.
                         2017); the mismatch varies between worlds and is not published. In
                         every single-variant world the causal variant has a cohort proxy that
                         the panel does not see as one, so clumping on the panel reports two
                         signals where there is one.
    masking              two causal variants in strong LD with effects of opposite sign: the
                         marginal signal at the second is near zero and carries the wrong sign,
                         so the marginal scan and any conditional analysis on the reference panel
                         miss it or call it with the wrong sign.
    several signals      three causal variants in three haplotype blocks; the strongest block
                         fills the top of the ranking with its proxies, so rows bought by rank
                         are spent on proxies of one signal and the weakest signal is never
                         bought.
    an unresolvable pair a causal variant has a near-duplicate in the cohort, a variant
                         correlated with it at 0.99 or more, that the reference panel shows at
                         0.75 or less; the panel says the pair is resolvable and the cohort says
                         it is not at the fixed cohort size. The stipulated finite-sample
                         likelihood gap cannot distinguish the pair. The answer is to decline to
                         name a causal set. In some of these worlds the pair is the only signal
                         and tops the ranking; in others it is the weaker of three signals and
                         sits below the proxies of the strongest, where rows bought by rank
                         never reach it.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ldsim  # noqa: E402

N_SNP = ldsim.N_SNP
N_GWAS = 20000
N_REF = 500
ROW_BUDGET = 6
MAX_CAUSAL = 3
EFFECT = (0.08, 0.11)            # per-allele effect in phenotype standard deviations
SINGLE_EFFECT = (0.11, 0.14)
MASK_EFFECT = (0.11, 0.15)       # the lead effect of a masked pair
MASK_RATIO = (0.4, 0.7)          # the second effect is minus this fraction of the first
MASK_LD = (0.70, 0.85)
# Every world carries exactly one secondary hit: a variant whose conditional chi-square given the
# exact rows of the primary causal set lies in this band. In a masked world it is the real second
# causal variant, in LD with the lead. In every other world it is a decoy, a non-causal variant
# in weak LD with every causal one that is nevertheless genome-wide significant on its own, so
# that clumping on any LD takes it as an independent signal. The band straddles the plain BIC line (9.9) and the
# Bonferroni line for the sixty typed variants at 0.05 (11.2) and stays below the extended BIC
# penalty (18.1), so no region-wide selection line separates partners from decoys; the LD
# neighbourhood of the lead does.
SECONDARY_CHI = (9.5, 13.5)
SECONDARY_MARGIN = 2.0           # every other non-causal variant is at least this far below the band
DECOY_LD_MAX = 0.3               # a decoy's cohort correlation with every causal variant
NOISE_DRAWS = 60                 # phenotype noise redraws per haplotype draw
PROXY_LD_MAX = 0.85              # no non-causal typed variant is closer than this to a causal one
MISMATCH_ALPHA = (0.1, 1.0)      # coupling of the reference population weights to the cohort weights
SWITCH = (0.02, 0.05)
FOUNDER_ALPHA = 0.7
MIN_EFFECT = 1e-3
# In a single-variant world the causal variant has a cohort proxy that the reference panel does
# not see as one: in-sample r-squared at least TRAP_R2, panel r-squared at most TRAP_REF_R2, and
# the proxy itself genome-wide significant.
TRAP_R2 = 0.3
TRAP_REF_R2 = 0.1
GENOME_WIDE_Z = 5.45
MULTI_STRENGTHS = (1.7, 1.1, 0.8)
MULTI_WEAKEST_RANK = 8           # the weakest of three signals ranks below this many variants by |z|
# An unresolvable world: the causal variant has a near-duplicate, a second typed variant whose
# haplotypes differ from its own on a fraction DUPLICATE_MISMATCH_GWAS of cohort haplotypes and
# on a fraction DUPLICATE_MISMATCH_REF of reference haplotypes, as when a mutation arose on a
# haplotype background that is rare in the cohort and common in the reference population.
DUPLICATE_MISMATCH_GWAS = (0.001, 0.004)
DUPLICATE_MISMATCH_REF = (0.06, 0.15)
# Resolvability is defined by the summary-statistic likelihood with the cohort's own LD, where
# twice the maximised log-likelihood of a configuration S is z_S' R_SS^-1 z_S. A typed world
# has its causal set ahead of every single-variant swap by at least RESOLVED_GAP. An
# unresolvable world has the two members of the pair within UNRESOLVED_GAP of each other, and
# the pair ahead of every other swap by at least RESOLVED_GAP: the data resolve the locus to the
# pair and not within it.
RESOLVED_GAP = 6.0
UNRESOLVED_GAP = 2.0

WORLD_KINDS = ("single", "masked", "multi", "unresolved")
WORLD_SIGNALS = {"single": (1,), "masked": (1, 2), "multi": (1, 2, 3)}   # how many causal variants each typed kind has


def _weights(rng, alpha):
    return rng.dirichlet(np.full(ldsim.N_FOUNDERS, alpha))


def _fit_value(z, R, S):
    S = list(S)
    return float(z[S] @ np.linalg.solve(R[np.ix_(S, S)] + 1e-9 * np.eye(len(S)), z[S]))


def _conditional_chi(z, R, S):
    """Conditional chi-square of every variant given the configuration S (its own members get
    minus infinity)."""
    S = list(S)
    RSS = R[np.ix_(S, S)] + 1e-9 * np.eye(len(S))
    coef = np.linalg.solve(RSS, R[S, :])
    resid = z - z[S] @ coef
    var = 1.0 - np.einsum("ij,ij->j", R[S, :], coef)
    chi = resid ** 2 / np.maximum(var, 1e-9)
    chi[S] = -np.inf
    return chi


def _swap_gap(z, R, causal, exclude=()):
    """How far the causal configuration is ahead of the best configuration that replaces one of
    its members by any other typed variant, in twice the log-likelihood."""
    own = _fit_value(z, R, causal)
    best = -np.inf
    for i in range(len(causal)):
        for j in range(len(z)):
            if j in causal or j in exclude:
                continue
            alt = list(causal)
            alt[i] = j
            best = max(best, _fit_value(z, R, alt))
    return own - best


def _standardize_trait(signal, noise):
    phenotype = signal + noise
    scale = float(phenotype.std())
    return (phenotype - phenotype.mean()) / scale, scale


def _try_world(spec, attempt):
    rng = np.random.default_rng((spec["seed"], attempt))
    kind = spec["kind"]
    w_gwas = _weights(rng, FOUNDER_ALPHA)
    founders = ldsim.founder_panel(rng, N_SNP, w_gwas)
    if founders is None:
        return None
    alpha = float(rng.uniform(*MISMATCH_ALPHA))
    w_ref = rng.dirichlet(alpha * ldsim.N_FOUNDERS * w_gwas + 0.3)
    switch_gwas = float(rng.uniform(*SWITCH))
    switch_ref = float(rng.uniform(*SWITCH))
    duplicate = None
    signals = int(spec.get("signals", 1)) if kind == "unresolved" else len(WORLD_SIGNALS[kind])
    haps = ldsim.mosaic_haplotypes(rng, founders, w_gwas, switch_gwas, 2 * N_GWAS)
    haps_ref = ldsim.mosaic_haplotypes(rng, founders, w_ref, switch_ref, 2 * N_REF)
    if kind == "unresolved":
        # the causal variant's near-duplicate replaces the site after it, in the same block
        block = int(rng.integers(0, len(ldsim.BLOCKS) - 1))
        i = int(rng.integers(ldsim.BLOCKS[block], ldsim.BLOCKS[block + 1] - 1))
        for h, band in ((haps, DUPLICATE_MISMATCH_GWAS), (haps_ref, DUPLICATE_MISMATCH_REF)):
            flip = rng.random(h.shape[0]) < rng.uniform(*band)
            h[:, i + 1] = np.where(flip, 1 - h[:, i], h[:, i])
        duplicate = (i, i + 1)
    G = ldsim.genotypes_from_haplotypes(haps)
    G_ref = ldsim.genotypes_from_haplotypes(haps_ref)
    freq = G.mean(axis=0) / 2.0
    if np.any(freq < 0.05) or np.any(freq > 0.95):
        return None
    R = ldsim.correlation(G)
    R_ref = ldsim.correlation(G_ref)
    off = np.abs(R - np.eye(N_SNP))
    unique = [j for j in range(N_SNP) if off[j].max() <= PROXY_LD_MAX]
    beta = np.zeros(N_SNP)
    causal = []
    if kind == "single":
        trapped = [j for j in unique
                   if any(R[j, p] ** 2 >= TRAP_R2 and R_ref[j, p] ** 2 <= TRAP_REF_R2
                          for p in range(N_SNP) if p != j)]
        if not trapped:
            return None
        j = int(rng.choice(trapped))
        beta[j] = rng.choice([-1, 1]) * rng.uniform(*SINGLE_EFFECT)
        causal = [j]
    elif kind == "masked":
        pairs = [(i, j) for i in range(N_SNP) for j in range(i + 1, N_SNP)
                 if MASK_LD[0] <= R[i, j] <= MASK_LD[1]]
        pairs = [(i, j) for i, j in pairs
                 if max(np.delete(off[i], [i, j]).max(), np.delete(off[j], [i, j]).max()) <= PROXY_LD_MAX]
        if not pairs:
            return None
        i, j = pairs[int(rng.integers(0, len(pairs)))]
        lead = rng.choice([-1, 1]) * rng.uniform(*MASK_EFFECT)
        beta[i] = lead
        beta[j] = -float(rng.uniform(*MASK_RATIO)) * lead
        causal = [i, j]
    elif kind == "multi":
        blocks = [[j for j in unique if lo <= j < hi] for lo, hi in zip(ldsim.BLOCKS[:-1], ldsim.BLOCKS[1:])]
        if any(not b for b in blocks):
            return None
        strengths = list(MULTI_STRENGTHS)
        rng.shuffle(strengths)
        for b, st in zip(blocks, strengths):
            j = int(rng.choice(b))
            beta[j] = rng.choice([-1, 1]) * rng.uniform(*EFFECT) * st
            causal.append(j)
        causal.sort()
    else:
        i, j = duplicate
        others = [p for p in range(N_SNP) if p not in (i, j)]
        if max(np.abs(R[i, others]).max(), np.abs(R[j, others]).max()) > PROXY_LD_MAX:
            return None
        c = int(rng.choice([i, j]))
        causal = [c]
        if signals == 1:
            beta[c] = rng.choice([-1, 1]) * rng.uniform(*EFFECT)
        else:
            # two stronger signals in the other blocks: the pair is a weaker signal, below the
            # proxies of the strongest in the ranking
            other = [[q for q in unique if lo <= q < hi and not lo <= i < hi]
                     for lo, hi in zip(ldsim.BLOCKS[:-1], ldsim.BLOCKS[1:])]
            other = [b for b, (lo, hi) in zip(other, zip(ldsim.BLOCKS[:-1], ldsim.BLOCKS[1:])) if not lo <= i < hi]
            if any(not b for b in other):
                return None
            strengths = list(MULTI_STRENGTHS)
            rng.shuffle(strengths)
            if strengths[0] == max(MULTI_STRENGTHS):
                strengths[0], strengths[1] = strengths[1], strengths[0]
            beta[c] = rng.choice([-1, 1]) * rng.uniform(*EFFECT) * strengths[0]
            for b, st in zip(other, strengths[1:]):
                q = int(rng.choice(b))
                beta[q] = rng.choice([-1, 1]) * rng.uniform(*EFFECT) * st
                causal.append(q)
            causal.sort()
    # the haplotypes and the effects are fixed; the phenotype noise is redrawn until the
    # z-scores satisfy the world's constraints
    signal = G @ beta
    regression_statistics = ldsim.regression_statistics(G)
    for draw in range(NOISE_DRAWS):
        y, phenotype_scale = _standardize_trait(signal, rng.normal(0.0, 1.0, N_GWAS))
        z, bhat, se = ldsim.marginal_z(G, y, regression_statistics)
        # the locus was flagged by the scan: some typed variant is genome-wide significant
        if np.abs(z).max() < GENOME_WIDE_Z:
            continue
        if kind != "masked" and min(abs(z[j]) for j in causal) < 5.0:
            continue
        if kind == "multi":
            order = np.argsort(-np.abs(z))
            weakest = min(causal, key=lambda j: abs(z[j]))
            if int(np.where(order == weakest)[0][0]) < MULTI_WEAKEST_RANK:
                continue
        secondary = None
        if kind == "masked":
            lead, partner = sorted(causal, key=lambda v: -abs(z[v]))
            conditional = _conditional_chi(z, R, [lead])
            if not SECONDARY_CHI[0] <= conditional[partner] <= SECONDARY_CHI[1]:
                continue
            secondary = partner
        else:
            conditional = _conditional_chi(z, R, causal)
            if duplicate is not None:
                conditional[list(duplicate)] = -np.inf
            secondary = int(np.argmax(conditional))
            if not SECONDARY_CHI[0] <= conditional[secondary] <= SECONDARY_CHI[1]:
                continue
            if np.sort(conditional)[-2] > SECONDARY_CHI[0] - SECONDARY_MARGIN:
                continue
            if np.abs(R[secondary, causal]).max() > DECOY_LD_MAX:
                continue
            # the decoy is itself genome-wide significant: a second hit by every marginal rule
            if abs(z[secondary]) < GENOME_WIDE_Z:
                continue
        if kind == "unresolved":
            i, j = duplicate
            swapped = [i + j - v if v in duplicate else v for v in causal]
            if abs(_fit_value(z, R, causal) - _fit_value(z, R, swapped)) >= UNRESOLVED_GAP:
                continue
            if _swap_gap(z, R, causal, exclude=duplicate) < RESOLVED_GAP:
                continue
            if signals == 3:
                order = np.argsort(-np.abs(z))
                if min(int(np.where(order == v)[0][0]) for v in duplicate) < MULTI_WEAKEST_RANK:
                    continue
        elif _swap_gap(z, R, causal) < RESOLVED_GAP:
            continue
        if kind == "single":
            j = causal[0]
            if not any(R[j, p] ** 2 >= TRAP_R2 and R_ref[j, p] ** 2 <= TRAP_REF_R2 and abs(z[p]) >= GENOME_WIDE_Z
                       for p in range(N_SNP) if p != j):
                           continue
        break
    else:
        return None
    # true per-allele effects on the standardised phenotype
    # Use the scale of the actual accepted phenotype draw. Var(signal) + 1
    # substitutes expected noise variance and omits its realised covariance
    # with the signal, so it is not the unit used by the published summaries.
    truth_beta = {j: float(beta[j] / phenotype_scale) for j in causal}
    return {
        "kind": kind, "seed": spec["seed"], "budget": int(spec["budget"]), "attempt": attempt,
        "draw": draw,
        "R": R, "R_ref": R_ref, "z": z, "se": se, "freq": freq,
        "causal": causal if kind != "unresolved" else [], "truth_beta": truth_beta,
        "duplicate": duplicate, "unresolved_causal": list(causal) if kind == "unresolved" else None,
        "signals": signals, "secondary": secondary,
        "unscaled_causal_effects": {j: float(beta[j]) for j in causal},
        "phenotype_scale": phenotype_scale,
        "duplicate_r": None if duplicate is None else (float(R[duplicate]), float(R_ref[duplicate])),
        "mismatch": float(np.mean(np.abs(R_ref - R)[np.abs(R) > 0.3])),
        "gap": _swap_gap(z, R, causal, exclude=duplicate or ()),
    }


_WORLDS = {}


def _world(spec):
    """The world of a spec, built once per process: the construction is deterministic in the
    spec, so a cache changes nothing but the time."""
    key = (spec["kind"], int(spec.get("signals", 1)), int(spec["seed"]), int(spec["budget"]))
    if key not in _WORLDS:
        for attempt in range(400):
            world = _try_world(spec, attempt)
            if world is not None:
                break
        else:
            raise RuntimeError("could not build world %r" % (spec,))
        _WORLDS[key] = world
    return _WORLDS[key]


class _Campaign:
    """The candidate's only view of the cohort's linkage disequilibrium: one row per call. The
    candidate receives the closure returned by `oracle`, not this object, so the budget and the
    ledger are out of its reach."""

    def __init__(self, world):
        self.world = world
        self.budget = world["budget"]
        self.spent = 0
        self.bought = {}
        self.violated = False

    def oracle(self):
        world, budget, bought, state = self.world, self.budget, self.bought, self

        def ld_row(variant):
            if isinstance(variant, bool) or not isinstance(variant, (int, np.integer)):
                raise ValueError("variant must be an integer index")
            variant = int(variant)
            if not 0 <= variant < N_SNP:
                raise ValueError("variant must lie in 0..%d" % (N_SNP - 1))
            if variant in bought:
                return list(bought[variant])
            if state.spent + 1 > budget:
                state.violated = True
                raise RuntimeError("row budget exhausted")
            state.spent += 1
            row = [round(float(v), 6) for v in world["R"][variant]]
            bought[variant] = row
            return list(row)

        return ld_row


PUBLIC_PROBLEM = {
    "n_variants": N_SNP,
    "n_gwas": N_GWAS,
    "n_reference": N_REF,
    "row_budget": ROW_BUDGET,
    "max_causal": MAX_CAUSAL,
    "z": None,
    "standard_error": None,
    "allele_frequency": None,
    "reference_ld": None,
    "association_model": "a quantitative phenotype with unit variance was regressed on each typed "
                         "variant separately in a cohort of n_gwas unrelated people; z is the "
                         "marginal t-statistic of each variant and standard_error the marginal "
                         "per-allele standard error; the phenotype is additive in the causal "
                         "variants, at most max_causal of them, each with a per-allele effect on "
                         "the standardised phenotype; every causal variant is typed",
    "reference_ld_model": "reference_ld is the sample correlation matrix of the typed variants in "
                          "a public panel of n_reference people from a related population; its "
                          "haplotype frequencies differ from the cohort's by an amount that is "
                          "not published, so its correlations differ from the cohort's",
    "row_model": "ld_row(variant) returns the exact correlation of that variant with every typed "
                 "variant in the study cohort itself, charged at one unit; buying a row twice "
                 "returns the same row and is charged once",
    "abstain_when": "the association cannot be resolved to a set of causal variants because a "
                    "causal variant, whether the only one or one of several, has a near-duplicate "
                    "in the cohort, so that the data support two configurations equally; then the "
                    "verdict is unresolved and no variant is named",
    "answer_format": "verdict is typed or unresolved; when it is typed, causal lists the indices "
                     "of the causal variants, at most max_causal, and effects lists their "
                     "per-allele effects on the standardised phenotype in the same order",
}


def _public_problem(world):
    problem = dict(PUBLIC_PROBLEM)
    problem.update({
        "row_budget": world["budget"],
        "z": [round(float(v), 6) for v in world["z"]],
        "standard_error": [round(float(v), 8) for v in world["se"]],
        "allele_frequency": [round(float(v), 6) for v in world["freq"]],
        "reference_ld": [[round(float(v), 6) for v in row] for row in world["R_ref"]],
    })
    return problem


def _validate_submission(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence):
        raise ValueError("confidence must be finite")
    confidence = float(np.clip(confidence, 0.0, 1.0))
    if submission.get("abstain", False) is True:
        return None, None, confidence, True
    verdict = submission.get("verdict")
    if verdict == "unresolved":
        return None, None, confidence, True
    if verdict != "typed":
        raise ValueError("verdict must be 'typed' or 'unresolved'")
    causal = submission.get("causal")
    effects = submission.get("effects")
    if not isinstance(causal, (list, tuple)) or not isinstance(effects, (list, tuple)):
        raise ValueError("causal and effects must be lists")
    if not 1 <= len(causal) <= MAX_CAUSAL or len(effects) != len(causal):
        raise ValueError("causal must name 1..%d variants with one effect each" % MAX_CAUSAL)
    out = []
    for v, e in zip(causal, effects):
        if isinstance(v, bool) or not isinstance(v, (int, np.integer)):
            raise ValueError("variant indices must be integers")
        v = int(v)
        if not 0 <= v < N_SNP:
            raise ValueError("variant index out of range")
        e = float(e)
        if not math.isfinite(e):
            raise ValueError("effects must be finite")
        out.append((v, e))
    if len({v for v, _ in out}) != len(out):
        raise ValueError("causal lists a variant twice")
    return [v for v, _ in out], [e for _, e in out], confidence, False


def _metrics(world, causal, effects, abstain):
    blank = {"set_f1": 0.0, "effect_score": 0.0, "mechanism_score": 0.0,
             "false_discovery": False, "correct_refusal": False}
    if world["kind"] == "unresolved":
        # Naming a variant here is a claim the data cannot support, whichever variant it is.
        blank.update({"mechanism_score": 1.0 if abstain else 0.0, "correct_refusal": bool(abstain),
                      "false_discovery": not abstain})
        return blank
    if abstain:
        # Declaring the locus unresolvable where it is resolvable is a claim, not a shrug.
        blank["false_discovery"] = True
        return blank
    truth = set(world["causal"])
    called = set(causal)
    if not called <= truth:
        # Naming a non-causal variant is a false discovery whatever else is right.
        blank["false_discovery"] = True
        return blank
    tp = len(called & truth)
    f1 = 2.0 * tp / (len(called) + len(truth))
    scores = []
    for v, e in zip(causal, effects):
        t = world["truth_beta"][v]
        if e * t <= 0:
            scores.append(0.0)
        else:
            scores.append(math.exp(-abs(math.log(max(abs(e), MIN_EFFECT) / abs(t)))))
    effect = float(np.mean(scores))
    blank.update({"set_f1": f1, "effect_score": effect,
                  "mechanism_score": f1 * (0.5 + 0.5 * effect)})
    return blank


DEVELOPMENT_BUDGET = ROW_BUDGET
HELDOUT_BUDGET = ROW_BUDGET

DEVELOPMENT_WORLDS = (
    {"kind": "single", "seed": 51200101, "budget": DEVELOPMENT_BUDGET},
    {"kind": "single", "seed": 51200102, "budget": DEVELOPMENT_BUDGET},
    {"kind": "single", "seed": 51200103, "budget": DEVELOPMENT_BUDGET},
    {"kind": "masked", "seed": 51200104, "budget": DEVELOPMENT_BUDGET},
    {"kind": "masked", "seed": 51200105, "budget": DEVELOPMENT_BUDGET},
    {"kind": "masked", "seed": 51200106, "budget": DEVELOPMENT_BUDGET},
    {"kind": "multi", "seed": 51200107, "budget": DEVELOPMENT_BUDGET},
    {"kind": "multi", "seed": 51200108, "budget": DEVELOPMENT_BUDGET},
    {"kind": "unresolved", "signals": 1, "seed": 51200109, "budget": DEVELOPMENT_BUDGET},
    {"kind": "unresolved", "signals": 3, "seed": 51200110, "budget": DEVELOPMENT_BUDGET},
    {"kind": "unresolved", "signals": 3, "seed": 51200111, "budget": DEVELOPMENT_BUDGET},
    {"kind": "unresolved", "signals": 3, "seed": 51200112, "budget": DEVELOPMENT_BUDGET},
)

HELDOUT_WORLDS = (
    {"kind": "single", "seed": 62310201, "budget": HELDOUT_BUDGET},
    {"kind": "masked", "seed": 62310202, "budget": HELDOUT_BUDGET},
    {"kind": "masked", "seed": 62310203, "budget": HELDOUT_BUDGET},
    {"kind": "multi", "seed": 62310204, "budget": HELDOUT_BUDGET},
    {"kind": "unresolved", "signals": 1, "seed": 62310205, "budget": HELDOUT_BUDGET},
    {"kind": "unresolved", "signals": 3, "seed": 62310206, "budget": HELDOUT_BUDGET},
)

ROW_KEYS = ("set_f1", "effect_score", "mechanism_score", "false_discovery", "correct_refusal")


def _evaluate_world(fine_map, spec, split, index):
    # One scientific world owns one candidate process and private tmpfs.  Keep all
    # paid LD callbacks inside that session, but never carry state across worlds
    # (including the development/heldout boundary).  A failed reset is a runtime
    # failure, so it must escape the invalid-submission handler below.
    reset_session = getattr(fine_map, "reset_session", None)
    if callable(reset_session):
        reset_session()
    world = _world(spec)
    campaign = _Campaign(world)
    problem = _public_problem(world)
    base = {"split": split, "world_index": int(index), "kind": world["kind"],
            "true_causal": list(world["causal"]), "rows_bought": 0}
    try:
        submission = fine_map(problem, campaign.oracle())
        causal, effects, confidence, abstain = _validate_submission(submission)
        if campaign.violated:
            raise RuntimeError("row budget exceeded")
        metrics = _metrics(world, causal, effects, abstain)
        target = metrics["mechanism_score"]
        row = dict(base)
        row.update({key: metrics[key] for key in ROW_KEYS})
        row.update({
            "valid": True,
            "abstained": bool(abstain),
            "claimed_causal": None if abstain else list(causal),
            "confidence": round(confidence, 6),
            "confidence_calibration_score": round(1.0 - (confidence - target) ** 2, 6),
            "rows_bought": len(campaign.bought),
        })
        for key in ("set_f1", "effect_score", "mechanism_score"):
            row[key] = round(float(row[key]), 6)
        return row
    except Exception as exc:  # noqa: BLE001 - a bad candidate scores zero, it does not crash this
        row = dict(base)
        row.update({key: (0.0 if key.endswith(("_score", "_f1")) else False) for key in ROW_KEYS})
        row.update({
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "claimed_causal": None,
            "confidence": 0.0,
            "confidence_calibration_score": 0.0,
            "rows_bought": len(campaign.bought),
        })
        return row


def _split_summary(records):
    determinable = [r for r in records if r["kind"] != "unresolved"]
    unsupported = [r for r in records if r["kind"] == "unresolved"]
    raw = float(np.mean([r["mechanism_score"] for r in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "raw_mechanism": raw,
        "set_f1": float(np.mean([r["set_f1"] for r in determinable])),
        "effect_score": float(np.mean([r["effect_score"] for r in determinable])),
        "false_discovery_rate": float(np.mean([r["false_discovery"] for r in records])),
        "correct_refusal_rate": float(np.mean([r["correct_refusal"] for r in unsupported])),
        "discovery_coverage": float(np.mean([not r["abstained"] for r in determinable])),
        "confidence_calibration": float(np.mean([r["confidence_calibration_score"] for r in records])),
        "mean_rows_bought": float(np.mean([r["rows_bought"] for r in records])),
        "valid_count": sum(bool(r["valid"]) for r in records),
        "world_count": len(records),
        "determinable_world_count": len(determinable),
        "unsupported_world_count": len(unsupported),
        "false_discovery_count": sum(bool(r["false_discovery"]) for r in records),
        "correct_refusal_count": sum(bool(r["correct_refusal"]) for r in unsupported),
        "discovery_attempt_count": sum(not r["abstained"] for r in determinable),
        "mechanism_score_sum": sum(float(r["mechanism_score"]) for r in records),
    }


def evaluate(fine_map):
    development = [_evaluate_world(fine_map, spec, "development", index)
                   for index, spec in enumerate(DEVELOPMENT_WORLDS)]
    heldout = [_evaluate_world(fine_map, spec, "heldout", index)
               for index, spec in enumerate(HELDOUT_WORLDS)]
    dev = _split_summary(development)
    held = _split_summary(heldout)
    valid = 1.0 if dev["valid_count"] > 0 else 0.0
    result = {
        "combined_score": dev["normalized_mechanism"] if valid else 0.0,
        "valid": valid,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"] if valid else 0.0,
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_raw_mechanism": dev["raw_mechanism"],
        "development_set_f1": dev["set_f1"],
        "development_effect_score": dev["effect_score"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "development_confidence_calibration": dev["confidence_calibration"],
        "development_mean_rows_bought": dev["mean_rows_bought"],
        # Evaluator-only: the sealed split is removed from the search-visible metric view by the
        # visibility contract, so a searcher cannot steer on it.
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_set_f1": held["set_f1"],
        "heldout_effect_score": held["effect_score"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "heldout_raw_mechanism": held["raw_mechanism"],
        "per_instance": development + heldout,
    }
    for split, summary in (("development", dev), ("heldout", held)):
        for name in ("world_count", "valid_count", "determinable_world_count",
                     "unsupported_world_count", "false_discovery_count",
                     "correct_refusal_count", "discovery_attempt_count", "mechanism_score_sum"):
            result[split + "_" + name] = summary[name]
    return result
