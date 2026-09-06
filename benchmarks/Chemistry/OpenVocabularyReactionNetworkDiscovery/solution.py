"""Legal zero-credit baseline for OpenVocabularyReactionNetworkDiscovery."""
from __future__ import annotations


def discover_reaction_network(problem, probe):
    del problem, probe
    return {
        "species": [
            {
                "atoms": ["C", "C", "N", "O"],
                "bonds": [[0, 3, 1], [1, 2, 1], [2, 3, 1]],
            },
            {
                "atoms": ["C", "C", "N", "O"],
                "bonds": [[0, 1, 1], [1, 2, 1], [2, 3, 1]],
            },
        ],
        "reactions": [
            {"reactant": 0, "product": 1, "activation_energy": 250.0}
        ],
        "abstain": False,
        "confidence": 1.0,
    }
