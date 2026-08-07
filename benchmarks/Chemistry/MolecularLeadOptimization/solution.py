"""Initial baseline for MolecularLeadOptimization (weak but valid).

Returns a short fixed list of simple, chemically legal molecules. They parse, but they are far
too small and too plain to survive the physicochemical, synthetic-accessibility, diversity and
novelty filters, so the retained set falls short of the requested size and the score is zero.

Replace this with an actual design procedure: enumerate a fragment space, run a graph genetic
algorithm, do scaffold hopping with matched molecular pairs, or drive a local search directly
against RDKit descriptors.
"""


def design_molecules(spec):
    """Propose SMILES for the requested lead-optimization profile.

    Args:
        spec: dict describing the profile, including
            - ``n_required``            how many molecules must survive every filter,
            - ``mw_range``, ``logp_range``, ``tpsa_max``, ``rotatable_max``,
              ``hbd_max``, ``hba_max``, ``sa_max``, ``pains_allowed``,
            - ``diversity_max_tanimoto``       pairwise Morgan/Tanimoto ceiling within your set,
            - ``panel_novelty_max_tanimoto``   ceiling against the approved-drug panel,
            - ``max_submissions``       how many SMILES you may submit.

    Returns:
        A list of SMILES strings.
    """
    return [
        "CCO",
        "c1ccccc1",
        "CC(=O)O",
        "CCN",
        "C1CCCCC1",
        "CCOCC",
        "CC(C)O",
        "c1ccncc1",
    ]
