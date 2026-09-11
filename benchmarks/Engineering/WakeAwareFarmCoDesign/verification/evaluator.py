"""Deterministic Gaussian/Jensen hybrid wake oracle for layout-yaw co-design."""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "hard"
DIRECTIONS = np.arange(0.0, 360.0, 30.0)
ANCHOR_LAYOUT_STARTS = 600
ANCHOR_LAYOUT_STEPS_M = (120.0, 60.0, 30.0, 160.0, 80.0, 40.0, 20.0, 10.0)
ANCHOR_ALTERNATIONS = 3
YAW_GRID_DEG = (-25.0, -17.5, -15.0, -10.0, -7.5, 0.0, 7.5, 10.0, 15.0, 17.5, 25.0)
WITNESS_YAW_GRID_DEG = (-25.0, -15.0, -7.5, 0.0, 7.5, 15.0, 25.0)
WITNESS_LAYOUT_STEPS_M = (120.0, 60.0, 30.0)
WITNESS_ALTERNATIONS = 1
WITNESS_LAYOUT_STARTS = 12
LAYOUT_PASSES_PER_SCALE = 2
_REFERENCE_CACHE = {}
_REFERENCE_COMPONENT_CACHE = {}
INSTANCE_SPECS = (
    ("dev_westerly", "development", 9, 1900., 1700., 3, 265., 34.),
    ("dev_bimodal", "development", 12, 2450., 1900., 7, 230., 62.),
    ("dev_coastal", "development", 10, 2200., 1800., 11, 300., 48.),
    ("dev_variable", "development", 9, 1800., 1800., 17, 190., 78.),
    ("heldout_narrow", "heldout", 12, 2700., 1700., 23, 248., 41.),
    ("heldout_rotated", "heldout", 10, 2100., 2050., 29, 322., 55.),
)


def _problem(spec):
    name, split, n, width, height, seed, dominant, spread = spec
    distance = np.minimum((DIRECTIONS-dominant)%360, (dominant-DIRECTIONS)%360)
    second = np.minimum((DIRECTIONS-(dominant+145))%360, ((dominant+145)-DIRECTIONS)%360)
    probability = np.exp(-.5*(distance/spread)**2)+.42*np.exp(-.5*(second/(spread*.75))**2)+.08
    probability /= probability.sum()
    speed = 8.4+.9*np.cos(np.radians(DIRECTIONS-dominant))+.35*np.sin(np.radians(2*DIRECTIONS+seed))
    return {"turbine_count":n,"boundary_width_m":width,"boundary_height_m":height,
            "rotor_diameter_m":120.0,"minimum_spacing_rotor_diameters":4.0,
            "wind_directions_deg":DIRECTIONS.tolist(),"wind_speeds_m_s":speed.tolist(),
            "wind_probabilities":probability.tolist(),"yaw_limit_deg":25.0,
            "air_density_kg_m3":1.225,"power_coefficient":0.44,"thrust_coefficient":0.80,
            "wake_expansion_public":0.055,"yaw_power_exponent":1.88,
            "contract":"return layout_xy_m [n,2] and yaw_by_direction_deg [12,n]"}


def _grid(problem, stagger=False):
    n=int(problem["turbine_count"]); cols=int(math.ceil(math.sqrt(n*float(problem["boundary_width_m"])/float(problem["boundary_height_m"]))))
    rows=int(math.ceil(n/cols)); xs=np.linspace(180,float(problem["boundary_width_m"])-180,cols); ys=np.linspace(180,float(problem["boundary_height_m"])-180,rows)
    out=[]
    for j,y in enumerate(ys):
        for i,x in enumerate(xs):
            if len(out)<n: out.append([float(np.clip(x+(90 if stagger and j%2 else 0),120,float(problem["boundary_width_m"])-120)),float(y)])
    return np.asarray(out)


def _validate(problem, value):
    if not isinstance(value,dict): raise ValueError("submission must be a mapping")
    layout=np.asarray(value.get("layout_xy_m"),dtype=float); yaw=np.asarray(value.get("yaw_by_direction_deg"),dtype=float)
    n=int(problem["turbine_count"]); nd=len(problem["wind_directions_deg"])
    if layout.shape!=(n,2) or yaw.shape!=(nd,n) or not np.all(np.isfinite(layout)) or not np.all(np.isfinite(yaw)):
        raise ValueError("wrong layout/yaw shape or non-finite value")
    if np.any(layout[:,0]<0) or np.any(layout[:,0]>problem["boundary_width_m"]) or np.any(layout[:,1]<0) or np.any(layout[:,1]>problem["boundary_height_m"]):
        raise ValueError("turbine outside boundary")
    minimum=float(problem["rotor_diameter_m"])*float(problem["minimum_spacing_rotor_diameters"])
    distance=np.sqrt(np.sum((layout[:,None,:]-layout[None,:,:])**2,axis=2))+np.eye(n)*1e9
    if float(np.min(distance))<minimum-1e-8: raise ValueError("minimum spacing violated")
    if np.max(np.abs(yaw))>float(problem["yaw_limit_deg"])+1e-12: raise ValueError("yaw limit violated")
    return layout,yaw


def _direction_value(problem, layout, yaw_row, direction_index, expansion=None, direction_shift=0.0):
    expansion=float(expansion if expansion is not None else problem["wake_expansion_public"])
    rotor=float(problem["rotor_diameter_m"]); radius=rotor/2; rho=float(problem["air_density_kg_m3"])
    cp=float(problem["power_coefficient"]); ct=float(problem["thrust_coefficient"]); induction=.5*(1-math.sqrt(1-ct))
    direction=float(problem["wind_directions_deg"][direction_index]); speed=float(problem["wind_speeds_m_s"][direction_index])
    probability=float(problem["wind_probabilities"][direction_index])
    theta=math.radians(direction+direction_shift); down=layout[:,0]*math.cos(theta)+layout[:,1]*math.sin(theta); cross=-layout[:,0]*math.sin(theta)+layout[:,1]*math.cos(theta)
    effective=np.full(len(layout),speed); order=np.argsort(down)
    for pos,j in enumerate(order):
        deficits=[]
        for i in order[:pos]:
            dx=down[j]-down[i]
            if dx<=0: continue
            yi=math.radians(float(yaw_row[i])); sigma=radius+expansion*dx
            center=cross[i]+.5*ct*math.cos(yi)**2*math.sin(yi)*dx
            deficit=2*induction*math.cos(yi)**2/(1+expansion*dx/radius)**2*math.exp(-.5*((cross[j]-center)/sigma)**2)
            deficits.append(deficit)
        effective[j]=speed*max(0.0,1-math.sqrt(sum(x*x for x in deficits)))
    yaw_rad=np.radians(yaw_row); power=.5*rho*math.pi*radius**2*cp*effective**3*np.cos(yaw_rad)**float(problem["yaw_power_exponent"])
    return float(probability)*float(np.sum(power))*8760/1e9


def _farm_value(problem, layout, yaw, expansion=None, direction_shift=0.0):
    return float(sum(_direction_value(problem, layout, yaw[d], d, expansion, direction_shift)
                     for d in range(len(problem["wind_directions_deg"]))))


def _baseline(problem):
    layout=_grid(problem,False); yaw=np.zeros((len(problem["wind_directions_deg"]),len(layout)))
    return layout,yaw


def _refine_yaw(problem, layout, yaw, grid=YAW_GRID_DEG):
    """One deterministic coordinate sweep over the public yaw controls."""
    directions = problem["wind_directions_deg"]
    for d in range(len(directions)):
        best = _direction_value(problem, layout, yaw[d], d)
        for j in range(len(layout)):
            chosen = float(yaw[d, j])
            for value in grid:
                yaw[d, j] = value
                quality = _direction_value(problem, layout, yaw[d], d)
                if quality > best + 1e-12:
                    best, chosen = quality, value
            yaw[d, j] = chosen
    return yaw


def _refine_layout(problem, layout, yaw, steps):
    """Coordinate layout refinement with a convergence sweep at every scale."""
    for step_size in steps:
        for _ in range(LAYOUT_PASSES_PER_SCALE):
            improved = False
            best = _farm_value(problem, layout, yaw)
            for j in range(len(layout)):
                for axis in range(2):
                    for sign in (-1.0, 1.0):
                        trial = layout.copy(); trial[j, axis] += sign * step_size
                        try:
                            _validate(problem, {"layout_xy_m": trial, "yaw_by_direction_deg": yaw})
                        except ValueError:
                            continue
                        quality = _farm_value(problem, trial, yaw)
                        if quality > best + 1e-12:
                            layout, best, improved = trial, quality, True
            if not improved:
                break
    return layout


def _reference(problem):
    key=(problem["turbine_count"],problem["boundary_width_m"],problem["boundary_height_m"],
         tuple(problem["wind_speeds_m_s"]),tuple(problem["wind_probabilities"]))
    if key in _REFERENCE_CACHE:
        layout,yaw=_REFERENCE_CACHE[key]; return layout.copy(),yaw.copy()
    rng=np.random.default_rng(7201+int(problem["turbine_count"])); candidates=[_grid(problem,False),_grid(problem,True)]
    base=_grid(problem,True)
    witness_seed_best = reference_seed_best = None
    for draw in range(ANCHOR_LAYOUT_STARTS):
        trial=base+rng.normal(0,70,base.shape); trial[:,0]=np.clip(trial[:,0],40,float(problem["boundary_width_m"])-40); trial[:,1]=np.clip(trial[:,1],40,float(problem["boundary_height_m"])-40)
        try:
            _validate(problem,{"layout_xy_m":trial,"yaw_by_direction_deg":np.zeros((len(problem["wind_directions_deg"]),len(trial)))})
        except ValueError:
            pass
        else:
            candidates.append(trial)
        if draw == WITNESS_LAYOUT_STARTS - 1:
            zero = np.zeros((len(problem["wind_directions_deg"]), int(problem["turbine_count"])))
            witness_seed_best = max(candidates, key=lambda x: _farm_value(problem, x, zero)).copy()
        if draw == 79:
            zero = np.zeros((len(problem["wind_directions_deg"]), int(problem["turbine_count"])))
            reference_seed_best = max(candidates, key=lambda x: _farm_value(problem, x, zero)).copy()
    zero=np.zeros((len(problem["wind_directions_deg"]),int(problem["turbine_count"])))
    ranked = sorted(candidates, key=lambda x: _farm_value(problem, x, zero), reverse=True)
    starts = [reference_seed_best] + ranked[:2]
    optimized = []
    # Reproduce the runnable witness path exactly inside the anchor envelope. This makes
    # the score-one component anchors dominate the witness by construction rather than
    # relying on a different greedy path landing in a better local basin.
    layout, yaw = witness_seed_best.copy(), zero.copy()
    for _ in range(WITNESS_ALTERNATIONS):
        yaw = _refine_yaw(problem, layout, yaw, WITNESS_YAW_GRID_DEG)
        layout = _refine_layout(problem, layout, yaw, WITNESS_LAYOUT_STEPS_M)
    yaw = _refine_yaw(problem, layout, yaw, WITNESS_YAW_GRID_DEG)
    optimized.append((layout, yaw))
    for initial in starts:
        if initial is None:
            continue
        layout, yaw = initial.copy(), zero.copy()
        for _ in range(ANCHOR_ALTERNATIONS):
            yaw = _refine_yaw(problem, layout, yaw)
            layout = _refine_layout(problem, layout, yaw, ANCHOR_LAYOUT_STEPS_M)
        yaw = _refine_yaw(problem, layout, yaw)
        optimized.append((layout, yaw))
    layout, yaw = max(optimized, key=lambda pair: _farm_value(problem, *pair))
    component_pairs = list(optimized)
    for stagger in (False, True):
        component_layout = _grid(problem, stagger)
        component_yaw = _refine_yaw(problem, component_layout, zero.copy())
        component_pairs.append((component_layout, component_yaw))
    _REFERENCE_COMPONENT_CACHE[key] = {
        "layout_value": max(_farm_value(problem, pair[0], zero) for pair in component_pairs),
        "yaw_gain": max(_farm_value(problem, *pair)-_farm_value(problem, pair[0], zero)
                        for pair in component_pairs),
    }
    _REFERENCE_CACHE[key]=(layout.copy(),yaw.copy())
    return layout,yaw


def _score_instance(candidate,spec):
    problem=_problem(spec); base=_baseline(problem); ref=_reference(problem)
    # Development scoring runs the PUBLIC wake expansion exactly as published in the problem
    # mapping; the widened-expansion and rotated-direction variants are
    # robustness-only and never control combined_score.
    low=_farm_value(problem,*base); high=_farm_value(problem,*ref)
    zero = np.zeros_like(base[1])
    components = _REFERENCE_COMPONENT_CACHE[(problem["turbine_count"],problem["boundary_width_m"],problem["boundary_height_m"],
         tuple(problem["wind_speeds_m_s"]),tuple(problem["wind_probabilities"]))]
    anchor_layout_value = components["layout_value"]
    anchor_yaw_gain = components["yaw_gain"]
    try:
        layout,yaw=_validate(problem,candidate(copy.deepcopy(problem)))
        value=_farm_value(problem,layout,yaw)
        layout_value = _farm_value(problem, layout, zero)
        layout_score = (layout_value-low)/max(anchor_layout_value-low,1e-9)
        yaw_control_score = (value-layout_value)/max(anchor_yaw_gain,1e-9)
        score = math.sqrt(max(0.0, layout_score) * max(0.0, yaw_control_score))
        shifted=_farm_value(problem,layout,yaw,expansion=.074,direction_shift=7.0)
        sb=_farm_value(problem,*base,expansion=.074,direction_shift=7.0)
        sr=_farm_value(problem,*ref,expansion=.074,direction_shift=7.0)
        robust=(shifted-sb)/max(sr-sb,1e-9)
        return {"name":spec[0],"split":spec[1],"valid":True,"score":round(float(score),6),"annual_value_gwh":value,
                "layout_score":round(float(layout_score),6),"yaw_control_score":round(float(yaw_control_score),6),
                "layout_value_gwh":float(layout_value),"yaw_gain_gwh":float(value-layout_value),
                "robustness_score":round(float(robust),6),"shifted_value_gwh":shifted}
    except Exception as exc:
        return {"name":spec[0],"split":spec[1],"valid":False,"score":0.0,"annual_value_gwh":0.0,
                "layout_score":0.0,"yaw_control_score":0.0,"layout_value_gwh":0.0,"yaw_gain_gwh":0.0,
                "robustness_score":0.0,"shifted_value_gwh":0.0,"reason":f"{type(exc).__name__}: {exc}"}


def evaluate(design_wind_farm):
    rows=[_score_instance(design_wind_farm,s) for s in INSTANCE_SPECS]; dev=[r for r in rows if r["split"]=="development"]; held=[r for r in rows if r["split"]=="heldout"]
    return {"combined_score":round(max(0.0,float(np.mean([r["score"] for r in dev]))),6) if all(r["valid"] for r in dev) else 0.0,"valid":float(all(r["valid"] for r in dev)),
            "feasibility_rate":float(np.mean([r["valid"] for r in dev])),"robustness_score":round(float(np.mean([r["robustness_score"] for r in dev])),6),
            "heldout_policy_score":round(float(np.mean([r["score"] for r in held])),6),"heldout_robustness_score":round(float(np.mean([r["robustness_score"] for r in held])),6),
            "heldout_feasibility_rate":float(np.mean([r["valid"] for r in held])),"per_instance":rows}
