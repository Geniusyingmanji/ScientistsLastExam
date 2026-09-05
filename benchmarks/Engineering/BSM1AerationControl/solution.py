"""Weak valid dissolved-oxygen PI baseline."""
import numpy as np


def make_aeration_controller(problem):
    del problem
    integral = 0.0
    def step(observation):
        nonlocal integral
        error = 2.0 - float(observation["dissolved_oxygen_mg_l"])
        integral = float(np.clip(integral + 0.12*error, -1.5, 1.5))
        return {"kla_per_hour": float(np.clip(4.0+2.4*error+integral, 0.0, 12.0)),
                "internal_recycle": 0.58}
    return step
