"""Weak valid baseline: perform one vehicle experiment and abstain."""

import numpy as np


def discover_gene_network(gene_names, perturb, phenotype_objective, budget_units):
    del budget_units
    n_genes = len(gene_names)
    perturb(np.zeros(n_genes, dtype=float), 20)
    return {
        "weights": np.zeros((n_genes, n_genes), dtype=float),
        "support": np.zeros((n_genes, n_genes), dtype=int),
        "biases": np.full(n_genes, -0.3, dtype=float),
        "decay_rates": np.full(n_genes, 0.6, dtype=float),
        "intervention": np.zeros(n_genes, dtype=float),
        "confidence": 0.0,
        "abstain": True,
    }
