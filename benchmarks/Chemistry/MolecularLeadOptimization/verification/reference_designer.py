"""Truth-blind reference designer for MolecularLeadOptimization.

Combinatorial enumeration over a small medicinal-chemistry fragment space, filtered locally
against the disclosed spec with RDKit. Used only to verify the task is solvable within the
declared constraints and to measure headroom. Deliberately simple: no genetic algorithm, no
scaffold hopping, no learned model.
"""

import os
import sys
import itertools

from rdkit import Chem, RDConfig, rdBase
from rdkit.Chem import QED, Crippen, Descriptors, FilterCatalog, rdMolDescriptors

rdBase.DisableLog("rdApp.*")
sys.path.append(os.path.join(RDConfig.RDContribDir, "SA_Score"))
import sascorer  # noqa: E402

CORES = [
    "c1ccc(-c2ccccc2)cc1", "c1ccc2[nH]ccc2c1", "c1ccc2ncccc2c1", "c1cnc2[nH]ccc2c1",
    "c1ccc2c(c1)oc1ccccc12", "c1ccc2c(c1)sc1ccccc12", "c1ccc(-c2ccncc2)cc1",
    "c1cc2ccccc2cc1", "c1ccc2[nH]nnc2c1", "c1ccc(-c2nccs2)cc1", "c1ccc(-c2ccco2)cc1",
    "c1ccc(-c2cn[nH]c2)cc1", "C1CCN(c2ccccc2)CC1", "c1ccc(N2CCOCC2)cc1",
    "c1ccc2[nH]c3ccccc3c2c1", "c1ccc(-c2ncccn2)cc1", "O=C(Nc1ccccc1)c1ccccc1",
    "O=S(=O)(Nc1ccccc1)c1ccccc1", "c1ccc(Oc2ccccc2)cc1", "c1ccc(Cc2ccccc2)cc1",
]
SUBS = [
    "", "C", "CC", "OC", "F", "Cl", "C(F)(F)F", "N", "NC", "N(C)C", "O", "C(N)=O",
    "S(N)(=O)=O", "C#N", "C(=O)O", "CO", "CCO", "N1CCOCC1", "N1CCNCC1", "N1CCCC1",
]


def _attach(core_smiles, sub):
    """Replace one aromatic CH on the core with a substituent, via SMILES surgery."""
    if not sub:
        return core_smiles
    mol = Chem.MolFromSmiles(core_smiles)
    if mol is None:
        return None
    for atom in mol.GetAtoms():
        if atom.GetIsAromatic() and atom.GetSymbol() == "C" and atom.GetTotalNumHs() >= 1:
            rw = Chem.RWMol(mol)
            frag = Chem.MolFromSmiles(sub)
            if frag is None:
                return None
            amap = {}
            for a in frag.GetAtoms():
                amap[a.GetIdx()] = rw.AddAtom(a)
            for b in frag.GetBonds():
                rw.AddBond(amap[b.GetBeginAtomIdx()], amap[b.GetEndAtomIdx()], b.GetBondType())
            rw.AddBond(atom.GetIdx(), amap[0], Chem.BondType.SINGLE)
            try:
                out = rw.GetMol()
                Chem.SanitizeMol(out)
                return Chem.MolToSmiles(out)
            except Exception:
                return None
    return None


def design_molecules(spec):
    pains_params = FilterCatalog.FilterCatalogParams()
    pains_params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
    pains = FilterCatalog.FilterCatalog(pains_params)

    mw_lo, mw_hi = spec["mw_range"]
    lp_lo, lp_hi = spec["logp_range"]

    scored = []
    for core, s1, s2 in itertools.product(CORES, SUBS, SUBS):
        smi = _attach(core, s1)
        if smi is None:
            continue
        if s2:
            smi = _attach(smi, s2)
            if smi is None:
                continue
        mol = Chem.MolFromSmiles(smi)
        if mol is None or len(Chem.GetMolFrags(mol)) != 1:
            continue
        mw = Descriptors.MolWt(mol)
        if not (mw_lo <= mw <= mw_hi):
            continue
        logp = Crippen.MolLogP(mol)
        if not (lp_lo <= logp <= lp_hi):
            continue
        if rdMolDescriptors.CalcTPSA(mol) > spec["tpsa_max"]:
            continue
        if rdMolDescriptors.CalcNumRotatableBonds(mol) > spec["rotatable_max"]:
            continue
        if rdMolDescriptors.CalcNumHBD(mol) > spec["hbd_max"]:
            continue
        if rdMolDescriptors.CalcNumHBA(mol) > spec["hba_max"]:
            continue
        if sascorer.calculateScore(mol) > spec["sa_max"]:
            continue
        if not spec["pains_allowed"] and pains.HasMatch(mol):
            continue
        scored.append((QED.qed(mol), Chem.MolToSmiles(mol)))

    scored.sort(key=lambda t: -t[0])
    seen, out = set(), []
    for _, smi in scored:
        if smi in seen:
            continue
        seen.add(smi)
        out.append(smi)
        if len(out) >= spec["max_submissions"]:
            break
    return out
