"""Frozen oracle for MolecularLeadOptimization (hidden from the agent).

Multi-parameter lead optimization. The candidate proposes SMILES; the oracle keeps only
molecules that satisfy a physicochemical and substructure-filter profile, are mutually
dissimilar, and are structurally novel with respect to a reference panel of approved
small-molecule drugs. The score is the mean drug-likeness (QED) of the retained set,
normalized against the same statistic computed on the approved-drug panel itself.

Every property comes from RDKit, the community-standard cheminformatics toolkit:
QED (Bickerton et al. 2012), the synthetic accessibility score (Ertl and Schuffenhauer 2009),
Lipinski and Veber descriptors, and the PAINS substructure catalogue (Baell and Holloway 2010).
Nothing here is a bespoke reimplementation.

The reference panel SMILES were each verified against their published average molecular weight
before being admitted (maximum deviation 0.02 g/mol; see references/known_best.md).
"""

from __future__ import annotations

import os
import sys

import numpy as np

_SA_READY = False


def _rdkit():
    """Import RDKit and the contributed SA-score module exactly once."""
    global _SA_READY
    from rdkit import Chem, RDConfig, rdBase
    from rdkit.Chem import AllChem, Crippen, DataStructs, Descriptors, FilterCatalog, QED
    from rdkit.Chem import rdMolDescriptors

    rdBase.DisableLog("rdApp.*")
    if not _SA_READY:
        sa_path = os.path.join(RDConfig.RDContribDir, "SA_Score")
        if sa_path not in sys.path:
            sys.path.append(sa_path)
        _SA_READY = True
    import sascorer

    return {
        "Chem": Chem,
        "QED": QED,
        "Descriptors": Descriptors,
        "Crippen": Crippen,
        "rdMD": rdMolDescriptors,
        "AllChem": AllChem,
        "DataStructs": DataStructs,
        "FilterCatalog": FilterCatalog,
        "sascorer": sascorer,
    }


# Approved small-molecule drugs. Each SMILES was checked against its published average
# molecular weight; the panel defines the reference drug-likeness level, and candidates must be
# structurally novel relative to it.
DRUG_PANEL = (
    "CC(=O)Oc1ccccc1C(=O)O",
    "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
    "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1",
    "CCCc1nn(C)c2c(=O)[nH]c(-c3cc(S(=O)(=O)N4CCN(C)CC4)ccc3OCC)nc12",
    "CC(C)NCC(O)COc1cccc2ccccc12",
    "CN1c2ccc(Cl)cc2C(c2ccccc2)=NCC1=O",
    "CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CC[C@@H](O)C[C@@H](O)CC(=O)O",
    "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "COc1ccc2cc(C(C)C(=O)O)ccc2c1",
    "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
    "CC(=O)Nc1ccc(O)cc1",
    "OC(Cn1cncn1)(Cn1cncn1)c1ccc(F)cc1F",
    "O=C(O)c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O",
    "CCOC(=O)N1CCC(=C2c3ccc(Cl)cc3CCc3cccnc32)CC1",
    "COc1ccc2[nH]c(S(=O)Cc3ncc(C)c(OC)c3C)nc2c1",
    "CNC1CCC(c2ccc(Cl)c(Cl)c2)c2ccccc21",
    "CC(C)NCC(O)COc1ccc(CC(N)=O)cc1",
    "COc1ccc(CCN(C)CCCC(C#N)(C(C)C)c2ccc(OC)c(OC)c2)cc1OC",
    "COC(=O)C1=C(C)NC(C)=C(C(=O)OC)C1c1ccccc1[N+](=O)[O-]",
    "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O",
)

# Development profile, disclosed to the agent through Task.md and the spec.
#
# `n_required` is deliberately far above what a single generation can write down: the binding
# constraint is not drug-likeness (QED saturates near 0.95 for almost any well-formed
# medicinal-chemistry scaffold) but how many *mutually dissimilar* high-quality scaffolds a
# search can discover. Scoring is a smooth ramp in portfolio size, so partial portfolios earn
# partial credit and there is no cliff.
#
# Sized against measurement, not guesswork. At an earlier n_required of 40, GPT-5.6 scored
# 0.86-1.25 across four valid budget-one draws - three of them above 0.95 - by hand-writing
# roughly fifty diverse molecules without running any search at all. Requiring 120 puts the
# portfolio out of reach of recall and forces a programmatic generator.
DEV_PROFILE = {
    "key": "oral_lead",
    "n_required": 120,
    "mw_range": [250.0, 500.0],
    "logp_range": [-1.0, 5.0],
    "tpsa_max": 140.0,
    "rotatable_max": 10,
    "hbd_max": 5,
    "hba_max": 10,
    "sa_max": 4.5,
    "pains_allowed": False,
    "diversity_max_tanimoto": 0.25,
    "panel_novelty_max_tanimoto": 0.40,
    "max_submissions": 2000,
}

# Evaluator-only profile: tighter physicochemical windows and a stricter diversity ceiling.
# Never disclosed; reported as robustness_score. A search tuned to the development scaffold
# space should lose ground here.
SEALED_PROFILE = {
    "key": "tight_permeable",
    "n_required": 60,
    "mw_range": [260.0, 470.0],
    "logp_range": [0.0, 5.0],
    "tpsa_max": 110.0,
    "rotatable_max": 9,
    "hbd_max": 4,
    "hba_max": 9,
    "sa_max": 4.0,
    "pains_allowed": False,
    "diversity_max_tanimoto": 0.20,
    "panel_novelty_max_tanimoto": 0.40,
    "max_submissions": 2000,
}

# The reference level is a quality anchor, so the panel pool must not be a single molecule.
MIN_PANEL_POOL = 5

_CACHE: dict = {}


def _fingerprint(rd, mol):
    return rd["AllChem"].GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)


def _pains_catalog(rd):
    if "pains" not in _CACHE:
        fc = rd["FilterCatalog"]
        params = fc.FilterCatalogParams()
        params.AddCatalog(fc.FilterCatalogParams.FilterCatalogs.PAINS)
        _CACHE["pains"] = fc.FilterCatalog(params)
    return _CACHE["pains"]


def _properties(rd, smiles: str):
    """Parse one SMILES and compute every scored property. Returns None if unusable."""
    mol = rd["Chem"].MolFromSmiles(smiles)
    if mol is None:
        return None
    if mol.GetNumAtoms() == 0:
        return None
    # Reject multi-fragment entries (salts, mixtures): a lead is one covalent species.
    if len(rd["Chem"].GetMolFrags(mol)) != 1:
        return None
    try:
        return {
            "mol": mol,
            "canonical": rd["Chem"].MolToSmiles(mol),
            "qed": float(rd["QED"].qed(mol)),
            "sa": float(rd["sascorer"].calculateScore(mol)),
            "mw": float(rd["Descriptors"].MolWt(mol)),
            "logp": float(rd["Crippen"].MolLogP(mol)),
            "tpsa": float(rd["rdMD"].CalcTPSA(mol)),
            "rotatable": int(rd["rdMD"].CalcNumRotatableBonds(mol)),
            "hbd": int(rd["rdMD"].CalcNumHBD(mol)),
            "hba": int(rd["rdMD"].CalcNumHBA(mol)),
        }
    except Exception:  # noqa: BLE001 - a pathological molecule is simply infeasible
        return None


def _feasible(rd, props, profile) -> bool:
    lo, hi = profile["mw_range"]
    if not (lo <= props["mw"] <= hi):
        return False
    lo, hi = profile["logp_range"]
    if not (lo <= props["logp"] <= hi):
        return False
    if props["tpsa"] > profile["tpsa_max"]:
        return False
    if props["rotatable"] > profile["rotatable_max"]:
        return False
    if props["hbd"] > profile["hbd_max"]:
        return False
    if props["hba"] > profile["hba_max"]:
        return False
    if props["sa"] > profile["sa_max"]:
        return False
    if not profile["pains_allowed"] and _pains_catalog(rd).HasMatch(props["mol"]):
        return False
    return True


def _panel_state(rd, profile):
    """Feasible panel members and the reference score for this profile. Cached per profile."""
    key = f"panel::{profile['key']}"
    if key in _CACHE:
        return _CACHE[key]
    entries = []
    for smi in DRUG_PANEL:
        props = _properties(rd, smi)
        if props is None:
            continue
        props["fp"] = _fingerprint(rd, props["mol"])
        entries.append(props)
    feasible = [p for p in entries if _feasible(rd, p, profile)]
    feasible.sort(key=lambda p: -p["qed"])
    selected = _greedy_diverse(rd, feasible, profile["diversity_max_tanimoto"])
    # The anchor is a quality level, not a target set size: the mean drug-likeness of the
    # structurally distinct approved drugs that satisfy this profile. The panel is far smaller
    # than `n_required`, which is intentional — no real drug set is the target here.
    ref = (
        float(np.mean([p["qed"] for p in selected]))
        if len(selected) >= MIN_PANEL_POOL
        else None
    )
    state = {
        "all_fps": [p["fp"] for p in entries],
        "reference_mean_qed": ref,
        "reference_pool": len(selected),
    }
    _CACHE[key] = state
    return state


def _greedy_diverse(rd, sorted_props, max_tanimoto):
    """Select highest-QED-first, admitting a molecule only if it is dissimilar to all kept."""
    kept = []
    for props in sorted_props:
        ok = True
        for other in kept:
            sim = rd["DataStructs"].TanimotoSimilarity(props["fp"], other["fp"])
            if sim >= max_tanimoto:
                ok = False
                break
        if ok:
            kept.append(props)
    return kept


def _score_profile(rd, design_molecules, profile) -> dict:
    panel = _panel_state(rd, profile)
    spec = {k: v for k, v in profile.items() if k != "key"}
    spec["objective"] = "maximize mean QED of the retained set"

    try:
        raw = design_molecules(dict(spec))
    except Exception as exc:  # noqa: BLE001 - candidate faults are scored, not raised
        return {
            "profile": profile["key"],
            "valid": False,
            "reason": "raised: %s" % type(exc).__name__,
            "score": 0.0,
        }

    if isinstance(raw, str) or not hasattr(raw, "__iter__"):
        return {
            "profile": profile["key"],
            "valid": False,
            "reason": "expected an iterable of SMILES strings",
            "score": 0.0,
        }
    submitted = list(raw)
    if len(submitted) > profile["max_submissions"]:
        return {
            "profile": profile["key"],
            "valid": False,
            "reason": f"submitted {len(submitted)} > max {profile['max_submissions']}",
            "score": 0.0,
        }
    if not all(isinstance(s, str) for s in submitted):
        return {
            "profile": profile["key"],
            "valid": False,
            "reason": "all submissions must be SMILES strings",
            "score": 0.0,
        }

    seen: set[str] = set()
    parsed = 0
    candidates = []
    for smi in submitted:
        props = _properties(rd, smi)
        if props is None:
            continue
        parsed += 1
        if props["canonical"] in seen:
            continue
        seen.add(props["canonical"])
        if not _feasible(rd, props, profile):
            continue
        props["fp"] = _fingerprint(rd, props["mol"])
        # Structural novelty against the approved-drug panel: submitting a known drug back
        # is recall, not design.
        novel = True
        for panel_fp in panel["all_fps"]:
            if rd["DataStructs"].TanimotoSimilarity(props["fp"], panel_fp) >= profile[
                "panel_novelty_max_tanimoto"
            ]:
                novel = False
                break
        if novel:
            candidates.append(props)

    candidates.sort(key=lambda p: -p["qed"])
    retained = _greedy_diverse(rd, candidates, profile["diversity_max_tanimoto"])
    n = profile["n_required"]

    result = {
        "profile": profile["key"],
        "valid": True,
        "submitted": len(submitted),
        "parsed": parsed,
        "unique": len(seen),
        "feasible_novel": len(candidates),
        "retained": len(retained),
        "required": n,
        "reference_mean_qed": panel["reference_mean_qed"],
    }
    if panel["reference_mean_qed"] is None:
        result["score"] = 0.0
        result["reason"] = "profile admits too few panel members to anchor a reference level"
        return result

    # Portfolio value: quality summed over the diverse retained set, amortized over the
    # requested portfolio size. A short portfolio earns proportional partial credit, so the
    # score is smooth in both breadth and quality rather than a pass/fail on the count.
    top = retained[:n]
    portfolio = float(np.sum([p["qed"] for p in top])) / float(n)
    result["mean_qed"] = float(np.mean([p["qed"] for p in top])) if top else 0.0
    result["portfolio_fill"] = len(top) / float(n)
    result["mean_sa"] = float(np.mean([p["sa"] for p in top])) if top else 0.0
    # Uncapped: fielding a full portfolio above the approved-drug quality level exceeds 1.0.
    result["score"] = float(max(0.0, portfolio / panel["reference_mean_qed"]))
    result["beats_drug_panel"] = bool(
        len(top) >= n and result["mean_qed"] > panel["reference_mean_qed"]
    )
    return result


def evaluate(design_molecules) -> dict:
    rd = _rdkit()
    dev = _score_profile(rd, design_molecules, DEV_PROFILE)
    sealed = {"profile": SEALED_PROFILE["key"], "score": 0.0, "valid": False}
    if dev.get("valid"):
        sealed = _score_profile(rd, design_molecules, SEALED_PROFILE)

    return {
        "combined_score": float(dev.get("score", 0.0)),
        "valid": 1.0 if dev.get("valid") else 0.0,
        "feasibility_rate": (
            float(dev.get("retained", 0)) / float(dev.get("required", 1))
            if dev.get("valid")
            else 0.0
        ),
        "robustness_score": float(sealed.get("score", 0.0)),
        "beats_drug_panel": bool(dev.get("beats_drug_panel", False)),
        "development": dev,
        "sealed": sealed,
    }
