"""Deterministic five-state BSM1-inspired activated-sludge control oracle."""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "hard"
DT = 0.5
STEPS = 144
WARMUP = 32
INSTANCE_SPECS = (
    ("dev_dry", "development", 3, 1.00, 0.00, 1.00),
    ("dev_rain", "development", 7, 1.18, 0.00, 1.00),
    ("dev_weekend", "development", 11, 0.90, 0.00, 1.00),
    ("dev_variable", "development", 17, 1.08, 0.00, 1.00),
    ("heldout_storm", "heldout", 23, 1.32, 0.12, 0.88),
    ("heldout_sensor_actuator", "heldout", 29, 1.12, -0.18, 0.76),
)


def _problem():
    return {
        "sample_period_hours": DT, "horizon_steps": STEPS,
        "observation_keys": ["substrate_mg_l", "ammonia_mg_l", "nitrate_mg_l",
                             "dissolved_oxygen_mg_l", "biomass_mg_l", "flow_ratio",
                             "influent_ammonia_mg_l"],
        "action_keys": ["kla_per_hour", "internal_recycle"],
        "action_bounds": {"kla_per_hour": [0.0, 12.0], "internal_recycle": [0.0, 1.0]},
        "effluent_limits": {"mean_ammonia_mg_l": 20.0, "mean_total_nitrogen_mg_l": 60.0,
                            "mean_cod_proxy_mg_l": 130.0},
        "model": "five-state ASM1-inspired continuously stirred reactor; deterministic Euler integration",
    }


def _influent(seed, load_scale):
    rng = np.random.default_rng(seed)
    t = np.arange(STEPS)*DT
    daily = 1.0 + .22*np.sin(2*np.pi*(t-5)/24) + .09*np.sin(4*np.pi*t/24)
    pulse = np.zeros(STEPS)
    for center in (42, 91, 118): pulse += np.exp(-.5*((np.arange(STEPS)-center)/4.0)**2)
    flow = load_scale*np.clip(daily + .12*pulse + rng.normal(0,.025,STEPS), .55, 1.75)
    ammonia = np.clip(31.0*(.92+.18*np.sin(2*np.pi*(t+2)/24)) + 5.5*pulse, 17, 48)
    substrate = np.clip(165.0*(.90+.22*np.sin(2*np.pi*(t-1)/24)) + 35*pulse, 80, 270)
    return flow, ammonia, substrate


def _validate_action(action):
    if not isinstance(action, dict): raise ValueError("controller action must be a mapping")
    kla, recycle = float(action.get("kla_per_hour", math.nan)), float(action.get("internal_recycle", math.nan))
    if not math.isfinite(kla) or not math.isfinite(recycle): raise ValueError("actions must be finite")
    if not 0 <= kla <= 12 or not 0 <= recycle <= 1: raise ValueError("action outside public bounds")
    return kla, recycle


def _baseline_factory(_problem):
    integral = 0.0
    def step(obs):
        nonlocal integral
        error = 2.0-float(obs["dissolved_oxygen_mg_l"]); integral = float(np.clip(integral+.12*error, -1.5, 1.5))
        return {"kla_per_hour": float(np.clip(4.0+2.4*error+integral, 0, 12)), "internal_recycle": .58}
    return step


def _reference_factory(_problem):
    integral = 0.0; previous = 4.0
    def step(obs):
        nonlocal integral, previous
        nh, flow = float(obs["ammonia_mg_l"]), float(obs["flow_ratio"])
        target = float(np.clip(1.35+.045*nh+.45*(flow-1), 1.5, 3.1))
        error = target-float(obs["dissolved_oxygen_mg_l"]); integral = float(np.clip(integral+.10*error, -1.2, 1.2))
        desired = 1.6+2.65*error+integral+.075*float(obs["influent_ammonia_mg_l"])*flow
        kla = float(np.clip(.65*previous+.35*desired, 0, 12)); previous = kla
        recycle = float(np.clip(.38+.025*float(obs["nitrate_mg_l"])+.10*(flow-1), .25, .92))
        return {"kla_per_hour": kla, "internal_recycle": recycle}
    return step


def _run(factory, problem, spec):
    name, split, seed, load_scale, sensor_bias, actuator = spec
    flow, influent_nh, influent_s = _influent(seed, load_scale)
    controller = factory(copy.deepcopy(problem))
    if not callable(controller): raise ValueError("factory must return a callable controller")
    state = np.array([118.0, 24.0, 7.0, 2.0, 1750.0], dtype=float)
    records=[]; last=np.array([4.0,.58])
    for k in range(STEPS):
        s, nh, no, do, x = state
        observed_do = max(0.0, do+sensor_bias)
        obs = {"substrate_mg_l": float(s), "ammonia_mg_l": float(nh), "nitrate_mg_l": float(no),
               "dissolved_oxygen_mg_l": float(observed_do), "biomass_mg_l": float(x),
               "flow_ratio": float(flow[k]), "influent_ammonia_mg_l": float(influent_nh[k])}
        kla_cmd, recycle = _validate_action(controller(obs)); kla = actuator*kla_cmd
        r_het = .0063*x*s/(24+s)*do/(.38+do)
        r_nit = .0055*x*nh/(1.8+nh)*do/(.62+do)
        r_den = .0120*x*s/(16+s)*no/(.9+no)*(1.0-do/(1.25+do))
        exchange = .20*flow[k]
        ds = exchange*(influent_s[k]-s)-2.8*r_het
        dnh = exchange*(influent_nh[k]-nh)-1.15*r_nit
        dno = r_nit-1.15*recycle*r_den-exchange*.10*no
        ddo = .24*kla*(8.0-do)-.15*r_het-.30*r_nit-exchange*.05*do
        dx = .19*r_het+.10*r_nit-.035*x+22.0*exchange
        state += DT*np.array([ds,dnh,dno,ddo,dx])
        state = np.clip(state, [0,0,0,.02,450], [500,120,90,8.5,4000])
        if k >= WARMUP:
            records.append((state.copy(), kla_cmd, recycle, float(np.sum(np.abs(np.array([kla_cmd,recycle])-last)))))
        last[:] = (kla_cmd,recycle)
    states = np.array([r[0] for r in records]); kla = np.array([r[1] for r in records]); recycle=np.array([r[2] for r in records])
    smean, nhmean, nomean = (float(np.mean(states[:,i])) for i in range(3))
    tn = nhmean+nomean; energy=float(np.mean(.040*kla*kla+1.45*recycle*recycle)); variation=float(np.mean([r[3] for r in records]))
    limits=problem["effluent_limits"]
    feasible = nhmean <= limits["mean_ammonia_mg_l"] and tn <= limits["mean_total_nitrogen_mg_l"] and smean <= limits["mean_cod_proxy_mg_l"]
    cost = 4.0*nhmean+1.35*tn+.16*smean+energy+.28*variation
    return {"feasible": bool(feasible), "cost": float(cost), "mean_ammonia_mg_l": nhmean,
            "mean_total_nitrogen_mg_l": tn, "mean_cod_proxy_mg_l": smean,
            "aeration_recycle_energy": energy, "action_variation": variation}


def _score_instance(candidate, spec):
    problem=_problem(); base=_run(_baseline_factory,problem,spec); ref=_run(_reference_factory,problem,spec)
    try:
        result=_run(candidate,problem,spec)
        if not result["feasible"]: raise ValueError("mean effluent limits violated")
        if not base["feasible"]: raise RuntimeError("internal baseline is infeasible")
        ref_cost=ref["cost"] if ref["feasible"] else .92*base["cost"]
        score=(base["cost"]-result["cost"])/max(base["cost"]-ref_cost,1e-9)
        return dict({"name":spec[0],"split":spec[1],"valid":True,"score":float(score)},**result)
    except Exception as exc:
        return {"name":spec[0],"split":spec[1],"valid":False,"score":0.0,"feasible":False,
                "cost":1e9,"mean_ammonia_mg_l":1e6,"mean_total_nitrogen_mg_l":1e6,
                "mean_cod_proxy_mg_l":1e6,"aeration_recycle_energy":1e6,"action_variation":1e6,
                "reason":f"{type(exc).__name__}: {exc}"}


def evaluate(make_aeration_controller):
    rows=[_score_instance(make_aeration_controller,s) for s in INSTANCE_SPECS]
    dev=[r for r in rows if r["split"]=="development"]; held=[r for r in rows if r["split"]=="heldout"]
    return {"combined_score":float(np.mean([r["score"] for r in dev])),
            "valid":float(all(r["valid"] for r in dev)),
            "effluent_feasibility_rate":float(np.mean([r["valid"] for r in dev])),
            "heldout_policy_score":float(np.mean([r["score"] for r in held])),
            "heldout_feasibility_rate":float(np.mean([r["valid"] for r in held])),
            "mean_development_energy":float(np.mean([r["aeration_recycle_energy"] for r in dev])),
            "per_instance":rows}
