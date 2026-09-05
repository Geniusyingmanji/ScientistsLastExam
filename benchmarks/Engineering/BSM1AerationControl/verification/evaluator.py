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
                             "influent_ammonia_mg_l", "electricity_price_ratio", "aeration_availability"],
        "action_keys": ["kla_per_hour", "internal_recycle"],
        "action_bounds": {"kla_per_hour": [0.0, 12.0], "internal_recycle": [0.0, 1.0]},
        "effluent_limits": {"mean_ammonia_mg_l": 20.0, "mean_total_nitrogen_mg_l": 60.0,
                            "mean_cod_proxy_mg_l": 130.0},
        "objective": "flow-weighted effluent cost + upper-decile ammonia + time-priced energy + actuator variation",
        "model": "five-state ASM1-inspired continuously stirred reactor; deterministic Euler integration with 3-minute internal steps",
    }


def _influent(seed, load_scale):
    rng = np.random.default_rng(seed)
    t = np.arange(STEPS)*DT
    daily = 1.0 + .22*np.sin(2*np.pi*(t-5)/24) + .09*np.sin(4*np.pi*t/24)
    pulse = np.zeros(STEPS)
    for center in (42, 91, 118): pulse += np.exp(-.5*((np.arange(STEPS)-center)/4.0)**2)
    flow = load_scale*np.clip(daily + .12*pulse + rng.normal(0,.025,STEPS), .55, 1.75)
    ammonia = np.clip(27.0*(.92+.18*np.sin(2*np.pi*(t+2)/24)) + 5.5*pulse, 17, 48)
    substrate = np.clip(165.0*(.90+.22*np.sin(2*np.pi*(t-1)/24)) + 35*pulse, 80, 270)
    # Intermittent concentrated returns decouple nitrogen load from daily flow.
    for center in rng.choice(np.arange(36, STEPS-12), 3, replace=False):
        ammonia += 12. * np.exp(-.5*((np.arange(STEPS)-center)/2.5)**2)
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


def _run(factory, problem, spec, integration_substeps=10):
    name, split, seed, load_scale, sensor_bias, actuator = spec
    flow, influent_nh, influent_s = _influent(seed, load_scale)
    time = np.arange(STEPS)*DT
    price = np.where((time % 24 >= 16) & (time % 24 < 21), 4., .8)
    # Public observed compressor derating, independent of unobserved influent COD.
    availability = np.where(((time + seed % 7) % 24 >= 11) &
                            ((time + seed % 7) % 24 < 15), .35, 1.)
    controller = factory(copy.deepcopy(problem))
    if not callable(controller): raise ValueError("factory must return a callable controller")
    state = np.array([118.0, 24.0, 7.0, 2.0, 1750.0], dtype=float)
    records=[]; last=np.array([4.0,.58])
    for k in range(STEPS):
        s, nh, no, do, x = state
        observed_do = max(0.0, do+sensor_bias)
        obs = {"substrate_mg_l": float(s), "ammonia_mg_l": float(nh), "nitrate_mg_l": float(no),
               "dissolved_oxygen_mg_l": float(observed_do), "biomass_mg_l": float(x),
               "flow_ratio": float(flow[k]), "influent_ammonia_mg_l": float(influent_nh[k]),
               "electricity_price_ratio": float(price[k]), "aeration_availability": float(availability[k])}
        kla_cmd, recycle = _validate_action(controller(obs)); kla = actuator*availability[k]*kla_cmd
        for _substep in range(integration_substeps):
            s, nh, no, do, x = state
            r_het = .0063*x*s/(24+s)*do/(.38+do)
            r_nit = .0055*x*nh/(1.8+nh)*do/(.62+do)
            r_den = .0120*x*s/(16+s)*no/(.9+no)*(1.0-do/(1.25+do))
            exchange = .20*flow[k]
            ds = exchange*(influent_s[k]-s)-2.8*r_het
            dnh = exchange*(influent_nh[k]-nh)-1.15*r_nit
            dno = r_nit-1.15*recycle*r_den-exchange*.10*no
            ddo = .24*kla*(8.0-do)-.15*r_het-.30*r_nit-exchange*.05*do
            dx = .19*r_het+.10*r_nit-.035*x+22.0*exchange
            state += (DT / integration_substeps)*np.array([ds,dnh,dno,ddo,dx])
            state = np.clip(state, [0,0,0,.02,450], [500,120,90,8.5,4000])
        if k >= WARMUP:
            records.append((state.copy(), kla_cmd, recycle, float(np.sum(np.abs(np.array([kla_cmd,recycle])-last)))))
        last[:] = (kla_cmd,recycle)
    states = np.array([r[0] for r in records]); kla = np.array([r[1] for r in records]); recycle=np.array([r[2] for r in records])
    weights = flow[WARMUP:]
    smean, nhmean, nomean = (float(np.average(states[:,i], weights=weights)) for i in range(3))
    ammonia_tail = float(np.mean(np.sort(states[:,1])[-int(np.ceil(.1*len(states))):]))
    tn = nhmean+nomean; energy=float(np.mean(price[WARMUP:]*(.040*kla*kla+1.45*recycle*recycle))); variation=float(np.mean([r[3] for r in records]))
    limits=problem["effluent_limits"]
    feasible = nhmean <= limits["mean_ammonia_mg_l"] and tn <= limits["mean_total_nitrogen_mg_l"] and smean <= limits["mean_cod_proxy_mg_l"]
    cost = 4.0*nhmean+2.0*ammonia_tail+1.35*tn+.16*smean+energy+.28*variation
    return {"feasible": bool(feasible), "cost": float(cost), "mean_ammonia_mg_l": nhmean,
            "mean_total_nitrogen_mg_l": tn, "mean_cod_proxy_mg_l": smean,
            "upper_decile_ammonia_mg_l": ammonia_tail,
            "aeration_recycle_energy": energy, "action_variation": variation}


def _score_instance(candidate, spec):
    problem=_problem(); base=_run(_baseline_factory,problem,spec); ref=_run(_reference_factory,problem,spec)
    if not base["feasible"] or not ref["feasible"] or ref["cost"] >= base["cost"]:
        raise RuntimeError("invalid wastewater normalization anchors: " + spec[0])
    try:
        result=_run(candidate,problem,spec)
        if not result["feasible"]: raise ValueError("mean effluent limits violated")
        ref_cost=ref["cost"]
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
    return {"combined_score":max(0.0,float(np.mean([r["score"] for r in dev]))) if all(r["valid"] for r in dev) else 0.0,
            "valid":float(all(r["valid"] for r in dev)),
            "effluent_feasibility_rate":float(np.mean([r["valid"] for r in dev])),
            "heldout_policy_score":float(np.mean([r["score"] for r in held])),
            "heldout_feasibility_rate":float(np.mean([r["valid"] for r in held])),
            "mean_development_energy":float(np.mean([r["aeration_recycle_energy"] for r in dev])),
            "per_instance":rows}
