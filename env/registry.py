"""Explicit environment registry; never exposed to candidate code."""
import importlib

ENVIRONMENTS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
                "gene_regulation", "ising_spin", "hysteresis_material", "microecology_causal",
                "orbital_dynamics", "pattern_formation", "electrical_impedance", "spin_echo", "population_drift")

# Registration enables explicit selection; it does not promote a world into an
# existing cohort or certify its scientific difficulty.
EXPERIMENTAL_ENVIRONMENTS = ("microecology_causal", "orbital_dynamics", "pattern_formation",
                            "electrical_impedance", "spin_echo", "population_drift")


def load_world(name, seed):
    if name not in ENVIRONMENTS:
        raise ValueError("unknown environment")
    module = importlib.import_module("env." + name + ".world")
    return module.World(seed), module.baseline
