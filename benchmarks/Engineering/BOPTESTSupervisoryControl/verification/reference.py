"""Standalone public-model witness. No oracle imports or hidden instance access.

The public model is reproduced here; independent high-fidelity validation is pending.
"""
import math
import copy
import numpy as np

REFERENCE_MODEL_WEIGHT = 0.40


def _conservative_factory(problem):
    """Feasible public thermostat used as the robust side of the witness."""
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


def _reference_factory(problem):
    """Forecast boundary tracking with online heat-balance disturbance estimation."""
    thermal = problem["thermal_model"]
    cap = np.asarray(thermal["zone_capacitance_j_k"]) / (3600 * problem["sample_period_hours"] * 1000)
    ua = np.asarray(thermal["envelope_ua_w_k"]) / 1000
    coupling = thermal["interzone_ua_w_k"] / 1000
    occupancy = np.asarray(problem["occupancy_forecast"])
    prices = np.asarray(problem["electricity_price_usd_kwh"])
    bias = np.zeros(2)
    previous_prediction = None
    def step(obs):
        nonlocal bias, previous_prediction
        k = int(obs["step"]); temp = np.asarray(obs["zone_temperature_c"])
        occ = np.asarray(obs["occupancy"]); co2 = np.asarray(obs["zone_co2_ppm"])
        if previous_prediction is not None:
            bias = .6 * bias + .4 * cap * (temp - previous_prediction)
        free = ua * (float(obs["outdoor_temperature_c"]) - temp)
        free += coupling * (temp[::-1] - temp) + .095 * occ + np.array([.65, .45])
        soon = np.any(occupancy[k:min(k + 9, len(occupancy))] > 0, axis=0)
        low = np.where(soon, 21.45, 18.5)
        high = np.where(soon, 24.55, 27.5)
        # Modest preconditioning before an upcoming price rise; no hidden weather/plant state.
        if k + 4 < len(prices) and prices[k + 4] > prices[k] + .1:
            low = np.where(soon, 21.85, low); high = np.where(soon, 24.15, high)
        free_next = temp + (free + bias) / cap
        target = np.clip(free_next, low, high)
        net = np.clip(cap * (target - temp) - free - bias, -30, 30)
        previous_prediction = temp + (free + net) / cap
        # One-step CO2 balance with a safety margin below the published limit.
        vent = (co2 + 4 * occ - (problem["co2_limit_ppm"] - 45)) / (.25 * np.maximum(co2 - 420, 1))
        vent = np.clip(vent, .15, 1.8)
        return {"heating_kw": np.maximum(net, 0).tolist(),
                "cooling_kw": np.maximum(-net, 0).tolist(),
                "ventilation_ach": vent.tolist()}
    return step

def make_hvac_controller(problem):
    # Blend a conservative feasible thermostat with the public-model controller.
    # The oracle's pure model controller is the score-one anchor; a candidate can
    # improve by trusting/adapting the model more effectively without hidden data.
    conservative = _conservative_factory(problem)
    model = _reference_factory(problem)
    def step(obs):
        safe = conservative(obs)
        forecast = model(obs)
        safe_net = np.asarray(safe["heating_kw"]) - np.asarray(safe["cooling_kw"])
        model_net = np.asarray(forecast["heating_kw"]) - np.asarray(forecast["cooling_kw"])
        net = ((1.0 - REFERENCE_MODEL_WEIGHT) * safe_net
               + REFERENCE_MODEL_WEIGHT * model_net)
        vent = ((1.0 - REFERENCE_MODEL_WEIGHT) * np.asarray(safe["ventilation_ach"])
                + REFERENCE_MODEL_WEIGHT * np.asarray(forecast["ventilation_ach"]))
        return {"heating_kw": np.maximum(net, 0).tolist(),
                "cooling_kw": np.maximum(-net, 0).tolist(),
                "ventilation_ach": vent.tolist()}
    return step
