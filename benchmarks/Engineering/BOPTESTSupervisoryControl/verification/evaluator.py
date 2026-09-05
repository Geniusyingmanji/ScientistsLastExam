"""Deterministic two-zone BOPTEST-style supervisory-control oracle."""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "hard"
DT_H = .25
STEPS = 192
INSTANCE_SPECS = (
    ("dev_office_cool", "development", 3, 11., 8., 0., 0., 1.0),
    ("dev_office_hot", "development", 7, 30., 7., 0., 0., 1.0),
    ("dev_school_mild", "development", 11, 20., 9., 0., 0., 1.0),
    ("dev_lab_variable", "development", 17, 17., 12., 0., 0., 1.0),
    ("heldout_heatwave", "heldout", 23, 34., 6., 3.0, .25, .78),
    ("heldout_cold_snap", "heldout", 29, 5., 10., -4.0, -.30, .82),
)


def _problem(spec):
    name, split, seed, mean_t, swing, weather_bias, sensor_bias, actuator = spec
    t=np.arange(STEPS)*DT_H; weather=mean_t+swing*np.sin(2*np.pi*(t-8)/24)+1.2*np.sin(2*np.pi*t/8+.2*seed)
    weekday=((t//24).astype(int)%7)<5; hour=t%24
    occupancy=np.zeros((STEPS,2)); occupied=weekday & (hour>=7.5) & (hour<=18.0)
    occupancy[:,0]=occupied*(28+10*np.sin(np.pi*(hour-7.5)/10.5))
    occupancy[:,1]=occupied*(16+7*np.sin(np.pi*(hour-8)/10))
    price=.10+.07*((hour>=7)&(hour<16))+.22*((hour>=16)&(hour<21)); carbon=.34+.12*np.sin(2*np.pi*(hour+3)/24)
    return {"sample_period_hours":DT_H,"horizon_steps":STEPS,"zone_count":2,
            "outdoor_temperature_forecast_c":weather.tolist(),"occupancy_forecast":occupancy.tolist(),
            "electricity_price_usd_kwh":price.tolist(),"grid_carbon_kg_kwh":carbon.tolist(),
            "comfort_bounds_occupied_c":[21.0,25.0],"co2_limit_ppm":1100.0,
            "comfort_tolerance":{"mean_excursion_c":0.10,"maximum_excursion_c":0.50,"violation_rate":0.05},
            "action_bounds":{"heating_kw":[0.0,30.0],"cooling_kw":[0.0,30.0],"ventilation_ach":[0.15,1.8]},
            "observation_keys":["step","zone_temperature_c","zone_co2_ppm","outdoor_temperature_c","occupancy"],
            "thermal_model":{"zone_capacitance_j_k":[18e6,15e6],"envelope_ua_w_k":[620.,540.],"interzone_ua_w_k":180.},
            "contract":"factory returns stateful step(observation); each action key has two values"}


def _validate_action(action):
    if not isinstance(action,dict): raise ValueError("action must be a mapping")
    out=[]
    for key,limit in (("heating_kw",30.),("cooling_kw",30.),("ventilation_ach",1.8)):
        value=np.asarray(action.get(key),dtype=float)
        if value.shape!=(2,) or not np.all(np.isfinite(value)): raise ValueError(f"{key} must contain two finite values")
        lower=.15 if key=="ventilation_ach" else 0.0
        if np.any(value<lower) or np.any(value>limit): raise ValueError(f"{key} outside bounds")
        out.append(value)
    if np.any((out[0]>.2)&(out[1]>.2)): raise ValueError("simultaneous heating and cooling")
    return out


def _baseline_factory(problem):
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


def _run(factory,problem,spec):
    name,split,seed,mean_t,swing,weather_bias,sensor_bias,actuator=spec
    controller=factory(copy.deepcopy(problem))
    if not callable(controller): raise ValueError("factory must return a callable controller")
    forecast=np.asarray(problem["outdoor_temperature_forecast_c"]); occ=np.asarray(problem["occupancy_forecast"]); rng=np.random.default_rng(seed)
    actual=forecast+weather_bias+.55*np.sin(np.arange(STEPS)*.41+seed)+rng.normal(0,.08,STEPS)
    temp=np.array([22.,22.]); co2=np.array([520.,520.]); capacitance=np.asarray(problem["thermal_model"]["zone_capacitance_j_k"])*(1.0-(1-actuator)*.35)
    ua=np.asarray(problem["thermal_model"]["envelope_ua_w_k"])*(1.0+(1-actuator)*.45); coupling=float(problem["thermal_model"]["interzone_ua_w_k"])
    comfort=[]; co2_rows=[]; energy=[]; emissions=[]; peaks=[]; movement=[]; previous=np.zeros(6)
    for k in range(STEPS):
        obs={"step":k,"zone_temperature_c":np.maximum(-30,temp+sensor_bias).tolist(),"zone_co2_ppm":co2.tolist(),
             "outdoor_temperature_c":float(actual[k]+sensor_bias),"occupancy":occ[k].tolist()}
        heat,cool,vent=_validate_action(controller(obs)); heat*=actuator; cool*=actuator
        gains=occ[k]*.095+np.array([.65,.45]); exchange=ua*(actual[k]-temp)+coupling*np.array([temp[1]-temp[0],temp[0]-temp[1]])
        temp += DT_H*3600/capacitance*(exchange+1000*(heat-cool+gains))
        production=4.0*occ[k]; co2 += production-DT_H*vent*(co2-420.0); co2=np.clip(co2,400,5000)
        occupied=occ[k]>0; low,high=problem["comfort_bounds_occupied_c"]
        violation=np.where(occupied,np.maximum(low-temp,0)+np.maximum(temp-high,0),0)
        comfort.extend(violation[occupied].tolist()); co2_rows.extend(np.where(occupied,co2,420)[occupied].tolist())
        fan=.55*vent**3; use=(heat/3.2+cool/3.4+fan)*DT_H; energy.append(float(np.sum(use)*problem["electricity_price_usd_kwh"][k])); emissions.append(float(np.sum(use)*problem["grid_carbon_kg_kwh"][k])); peaks.append(float(np.sum(heat+cool+fan)))
        action=np.concatenate([heat,cool,vent]); movement.append(float(np.sum(np.abs(action-previous)))); previous=action
    comfort=np.asarray(comfort or [0.]); co2_rows=np.asarray(co2_rows or [420.]); violation_rate=float(np.mean(comfort>0.05)); mean_violation=float(np.mean(comfort)); max_violation=float(np.max(comfort)); max_co2=float(np.max(co2_rows))
    tolerance=problem["comfort_tolerance"]
    feasible=(mean_violation<=tolerance["mean_excursion_c"] and max_violation<=tolerance["maximum_excursion_c"]
              and violation_rate<=tolerance["violation_rate"] and max_co2<=float(problem["co2_limit_ppm"]))
    cost=float(sum(energy)+.32*sum(emissions)+.075*max(peaks)+3.5*np.mean(comfort)+.002*np.mean(movement))
    return {"feasible":bool(feasible),"cost":cost,"comfort_violation_rate":violation_rate,"mean_comfort_violation_c":mean_violation,"maximum_comfort_violation_c":max_violation,
            "maximum_occupied_co2_ppm":max_co2,"energy_cost_usd":float(sum(energy)),"emissions_kg":float(sum(emissions)),"peak_kw":float(max(peaks))}


def _score_instance(candidate,spec):
    problem=_problem(spec); base=_run(_baseline_factory,problem,spec); ref=_run(_reference_factory,problem,spec)
    if not base["feasible"] or not ref["feasible"] or ref["cost"] >= base["cost"]:
        raise RuntimeError("invalid HVAC normalization anchors: " + spec[0])
    try:
        result=_run(candidate,problem,spec)
        if not result["feasible"]: raise ValueError("comfort or IAQ hard gate violated")
        ref_cost=ref["cost"]
        score=(base["cost"]-result["cost"])/max(base["cost"]-ref_cost,1e-9)
        return dict({"name":spec[0],"split":spec[1],"valid":True,"score":float(score)},**result)
    except Exception as exc:
        return {"name":spec[0],"split":spec[1],"valid":False,"score":0.0,"feasible":False,"cost":1e9,
                "comfort_violation_rate":1.0,"mean_comfort_violation_c":1e6,"maximum_comfort_violation_c":1e6,"maximum_occupied_co2_ppm":1e6,
                "energy_cost_usd":1e6,"emissions_kg":1e6,"peak_kw":1e6,"reason":f"{type(exc).__name__}: {exc}"}


def evaluate(make_hvac_controller):
    rows=[_score_instance(make_hvac_controller,s) for s in INSTANCE_SPECS]; dev=[r for r in rows if r["split"]=="development"]; held=[r for r in rows if r["split"]=="heldout"]
    return {"combined_score":max(0.0,float(np.mean([r["score"] for r in dev]))) if all(r["valid"] for r in dev) else 0.0,"valid":float(all(r["valid"] for r in dev)),
            "comfort_iaq_feasibility_rate":float(np.mean([r["valid"] for r in dev])),"heldout_policy_score":float(np.mean([r["score"] for r in held])),
            "heldout_feasibility_rate":float(np.mean([r["valid"] for r in held])),"mean_energy_cost_usd":float(np.mean([r["energy_cost_usd"] for r in dev])),
            "mean_emissions_kg":float(np.mean([r["emissions_kg"] for r in dev])),"per_instance":rows}
