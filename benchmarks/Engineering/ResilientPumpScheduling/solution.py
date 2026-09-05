"""Weak valid constant-speed pump baseline."""
import numpy as np


def schedule_pumps(problem):
    speed = 1.14 * float(np.mean(problem["demand_forecast_m3_h"])) / float(problem["pump_capacity_m3_h"])
    return {"pump_speed": np.full(int(problem["horizon_hours"]), min(0.94, speed)).tolist()}
