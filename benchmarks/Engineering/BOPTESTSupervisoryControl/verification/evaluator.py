"""Deterministic two-zone BOPTEST-style supervisory-control oracle."""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "flagship"
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
            "action_bounds":{"heating_kw":[0.0,18.0],"cooling_kw":[0.0,18.0],"ventilation_ach":[0.15,1.8]},
            "observation_keys":["step","zone_temperature_c","zone_co2_ppm","outdoor_temperature_c","occupancy"],
            "thermal_model":{"zone_capacitance_j_k":[18e6,15e6],"envelope_ua_w_k":[620.,540.],"interzone_ua_w_k":180.},
            "contract":"factory returns stateful step(observation); each action key has two values"}


def _validate_action(action):
    if not isinstance(action,dict): raise ValueError("action must be a mapping")
    out=[]
    for key,limit in (("heating_kw",18.),("cooling_kw",18.),("ventilation_ach",1.8)):
        value=np.asarray(action.get(key),dtype=float)
        if value.shape!=(2,) or not np.all(np.isfinite(value)): raise ValueError(f"{key} must contain two finite values")
        lower=.15 if key=="ventilation_ach" else 0.0
        if np.any(value<lower) or np.any(value>limit): raise ValueError(f"{key} outside bounds")
        out.append(value)
    if np.any((out[0]>.2)&(out[1]>.2)): raise ValueError("simultaneous heating and cooling")
    return out


def _baseline_factory(problem):
    def step(obs):
        temp=np.asarray(obs["zone_temperature_c"]); occ=np.asarray(obs["occupancy"])
        heat=np.clip(4.2*(21.6-temp),0,18); cool=np.clip(4.2*(temp-24.4),0,18)
        heat=np.where(occ>0,heat,np.clip(2.0*(17.0-temp),0,18)); cool=np.where(occ>0,cool,np.clip(2.0*(temp-29.0),0,18))
        vent=np.clip(.25+.025*occ,.15,1.55)
        return {"heating_kw":heat.tolist(),"cooling_kw":cool.tolist(),"ventilation_ach":vent.tolist()}
    return step


def _reference_factory(problem):
    weather=np.asarray(problem["outdoor_temperature_forecast_c"]); prices=np.asarray(problem["electricity_price_usd_kwh"]); occupancy=np.asarray(problem["occupancy_forecast"])
    previous_h=np.zeros(2); previous_c=np.zeros(2)
    def step(obs):
        nonlocal previous_h,previous_c
        k=int(obs["step"]); temp=np.asarray(obs["zone_temperature_c"]); occ=np.asarray(obs["occupancy"])
        future_occ=occupancy[min(k+4,len(occupancy)-1)]; expensive=prices[k]>.24
        target_low=np.where((occ>0)|(future_occ>0),21.35,17.0); target_high=np.where((occ>0)|(future_occ>0),24.65,29.0)
        if not expensive and k+4<len(weather):
            target_low=np.where(future_occ>0,21.75,target_low); target_high=np.where(future_occ>0,24.25,target_high)
        heat=np.clip(3.1*(target_low-temp)+.16*np.maximum(0,18-weather[k]),0,18); cool=np.clip(3.1*(temp-target_high)+.16*np.maximum(0,weather[k]-25),0,18)
        heat=.55*previous_h+.45*heat; cool=.55*previous_c+.45*cool; previous_h,previous_c=heat,cool
        co2=np.asarray(obs["zone_co2_ppm"]); vent=np.clip(.18+.018*occ+.0013*np.maximum(0,co2-850),.15,1.45)
        return {"heating_kw":heat.tolist(),"cooling_kw":cool.tolist(),"ventilation_ach":vent.tolist()}
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
    feasible=mean_violation<=1.35 and max_violation<=5.5 and max_co2<=float(problem["co2_limit_ppm"])+80
    cost=float(sum(energy)+.32*sum(emissions)+.075*max(peaks)+3.5*np.mean(comfort)+.002*np.mean(movement))
    return {"feasible":bool(feasible),"cost":cost,"comfort_violation_rate":violation_rate,"mean_comfort_violation_c":mean_violation,"maximum_comfort_violation_c":max_violation,
            "maximum_occupied_co2_ppm":max_co2,"energy_cost_usd":float(sum(energy)),"emissions_kg":float(sum(emissions)),"peak_kw":float(max(peaks))}


def _score_instance(candidate,spec):
    problem=_problem(spec); base=_run(_baseline_factory,problem,spec); ref=_run(_reference_factory,problem,spec)
    try:
        result=_run(candidate,problem,spec)
        if not result["feasible"]: raise ValueError("comfort or IAQ hard gate violated")
        if not base["feasible"]: raise RuntimeError("internal baseline is infeasible")
        ref_cost=ref["cost"] if ref["feasible"] else .92*base["cost"]
        score=(base["cost"]-result["cost"])/max(base["cost"]-ref_cost,1e-9)
        return dict({"name":spec[0],"split":spec[1],"valid":True,"score":float(score)},**result)
    except Exception as exc:
        return {"name":spec[0],"split":spec[1],"valid":False,"score":0.0,"feasible":False,"cost":1e9,
                "comfort_violation_rate":1.0,"mean_comfort_violation_c":1e6,"maximum_comfort_violation_c":1e6,"maximum_occupied_co2_ppm":1e6,
                "energy_cost_usd":1e6,"emissions_kg":1e6,"peak_kw":1e6,"reason":f"{type(exc).__name__}: {exc}"}


def evaluate(make_hvac_controller):
    rows=[_score_instance(make_hvac_controller,s) for s in INSTANCE_SPECS]; dev=[r for r in rows if r["split"]=="development"]; held=[r for r in rows if r["split"]=="heldout"]
    return {"combined_score":float(np.mean([r["score"] for r in dev])),"valid":float(all(r["valid"] for r in dev)),
            "comfort_iaq_feasibility_rate":float(np.mean([r["valid"] for r in dev])),"heldout_policy_score":float(np.mean([r["score"] for r in held])),
            "heldout_feasibility_rate":float(np.mean([r["valid"] for r in held])),"mean_energy_cost_usd":float(np.mean([r["energy_cost_usd"] for r in dev])),
            "mean_emissions_kg":float(np.mean([r["emissions_kg"] for r in dev])),"per_instance":rows}
