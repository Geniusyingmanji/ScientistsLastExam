"""Conservative valid public-data controller baseline."""
import numpy as np

def make_hvac_controller(problem):
    """Conservative load-compensated thermostat, feasible across the declared shifts."""
    ua = np.asarray(problem["thermal_model"]["envelope_ua_w_k"]) / 1000.0
    occupancy = np.asarray(problem["occupancy_forecast"])
    def step(obs):
        k = int(obs["step"])
        temp = np.asarray(obs["zone_temperature_c"])
        occ = np.asarray(obs["occupancy"])
        occupied_soon = np.any(occupancy[k:min(k + 9, len(occupancy))] > 0, axis=0)
        low = np.where(occupied_soon, 22.0, 19.0)
        high = np.where(occupied_soon, 24.0, 27.0)
        outdoor = float(obs["outdoor_temperature_c"])
        gains = .095 * occ + np.array([.65, .45])
        free = ua * (outdoor - temp) + gains
        heat = np.clip(12.0 * (low - temp) - free, 0, 30)
        cool = np.clip(12.0 * (temp - high) + free, 0, 30)
        net = heat - cool
        vent = np.clip(.35 + .024 * occ, .15, 1.8)
        return {"heating_kw": np.maximum(net, 0).tolist(),
                "cooling_kw": np.maximum(-net, 0).tolist(),
                "ventilation_ach": vent.tolist()}
    return step
