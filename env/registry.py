"""Explicit environment registry; never exposed to candidate code."""
import importlib

ENVIRONMENTS = ("microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
                "gene_regulation", "ising_spin", "hysteresis_material")


def load_world(name, seed):
    if name not in ENVIRONMENTS:
        raise ValueError("unknown environment")
    module = importlib.import_module("env." + name + ".world")
    return module.World(seed), module.baseline
