"""Conservative valid public-data controller baseline."""
import numpy as np

def make_aeration_controller(_problem):
    integral = 0.0
    def step(obs):
        nonlocal integral
        error = 2.0-float(obs["dissolved_oxygen_mg_l"]); integral = float(np.clip(integral+.12*error, -1.5, 1.5))
        return {"kla_per_hour": float(np.clip(4.0+2.4*error+integral, 0, 12)), "internal_recycle": .58}
    return step
