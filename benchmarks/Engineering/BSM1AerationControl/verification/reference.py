"""Standalone public-model witness. No oracle imports or hidden instance access.

The public model is reproduced here; independent high-fidelity validation is pending.
"""
import math
import copy
import numpy as np


def _reference_factory(_problem):
    """Oxygen mass-balance feed-forward plus concentration feedback."""
    def step(obs):
        substrate = float(obs["substrate_mg_l"])
        nh = float(obs["ammonia_mg_l"])
        oxygen = float(obs["dissolved_oxygen_mg_l"])
        biomass = float(obs["biomass_mg_l"])
        flow = float(obs["flow_ratio"])
        heterotrophic = .0063 * biomass * substrate / (24 + substrate) * oxygen / (.38 + oxygen)
        nitrification = .0055 * biomass * nh / (1.8 + nh) * oxygen / (.62 + oxygen)
        # Ammonia feedback raises oxygen during concentrated returns; price moderates
        # the target only when ammonia is already controlled.
        target = float(np.clip(1.1 + .065*nh - .08*(obs["electricity_price_ratio"]-1.), .6, 2.5))
        demand = .15 * heterotrophic + .30 * nitrification + .01 * flow * oxygen
        transfer = (demand + 1.5 * (target - oxygen)) / (.24 * max(8.0 - oxygen, .1))
        return {"kla_per_hour": float(np.clip(transfer / max(obs["aeration_availability"], .1), 0, 12)), "internal_recycle": 1.0}
    return step

def make_aeration_controller(problem):
    return _reference_factory(problem)
