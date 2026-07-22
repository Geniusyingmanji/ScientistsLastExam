"""Weak valid baseline: perform one assay and make no mechanism claim."""

import numpy as np


def discover_mechanism(species_names, reaction_pairs, experiment, budget_units):
    del budget_units
    n_species = len(species_names)
    n_reactions = len(reaction_pairs)
    initial = np.full(n_species, 1.0 / n_species)
    times = np.asarray((0.0, 0.02, 0.08, 0.3, 1.0, 4.0))
    experiment(405.0, initial, times, [0])
    return {
        "support": np.zeros(n_reactions, dtype=int),
        "log_pre_exponential": np.zeros(n_reactions),
        "activation_energy_j_mol": np.zeros(n_reactions),
        "confidence": 0.0,
        "abstain": True,
    }
