"""Deterministic Gaussian/Jensen hybrid wake oracle for layout-yaw co-design."""
from __future__ import annotations

import copy
import math

import numpy as np


DIFFICULTY = "hard"
DIRECTIONS = np.arange(0.0, 360.0, 30.0)
_REFERENCE_CACHE = {}
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
            "wake_expansion_public":0.055,
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


def _farm_value(problem, layout, yaw, expansion=None, direction_shift=0.0, turbulence_penalty=0.0):
    expansion=float(expansion if expansion is not None else problem["wake_expansion_public"])
    rotor=float(problem["rotor_diameter_m"]); radius=rotor/2; rho=float(problem["air_density_kg_m3"])
    cp=float(problem["power_coefficient"]); ct=float(problem["thrust_coefficient"]); induction=.5*(1-math.sqrt(1-ct))
    total=0.0; load=0.0
    for d,(direction,speed,probability) in enumerate(zip(problem["wind_directions_deg"],problem["wind_speeds_m_s"],problem["wind_probabilities"])):
        theta=math.radians(float(direction)+direction_shift); down=layout[:,0]*math.cos(theta)+layout[:,1]*math.sin(theta); cross=-layout[:,0]*math.sin(theta)+layout[:,1]*math.cos(theta)
        effective=np.full(len(layout),float(speed)); order=np.argsort(down)
        for pos,j in enumerate(order):
            deficits=[]
            for i in order[:pos]:
                dx=down[j]-down[i]
                if dx<=0: continue
                yi=math.radians(float(yaw[d,i])); sigma=radius+expansion*dx
                center=cross[i]+.055*dx*math.sin(yi)
                deficit=2*induction*math.cos(yi)**2/(1+expansion*dx/radius)**2*math.exp(-.5*((cross[j]-center)/sigma)**2)
                deficits.append(deficit)
            effective[j]=speed*max(.18,1-math.sqrt(sum(x*x for x in deficits)))
        yaw_rad=np.radians(yaw[d]); power=.5*rho*math.pi*radius**2*cp*effective**3*np.cos(yaw_rad)**1.88
        power=np.minimum(power,3.6e6); total += float(probability)*float(np.sum(power))*8760/1e9
        load += float(probability)*float(np.mean((effective/np.maximum(speed,1e-9))**2*(1+.22*np.abs(yaw_rad))))
    return float(total*(1-.018*turbulence_penalty)-.20*load)


def _baseline(problem):
    layout=_grid(problem,False); yaw=np.zeros((len(DIRECTIONS),len(layout)))
    return layout,yaw


def _reference(problem):
    key=(problem["turbine_count"],problem["boundary_width_m"],problem["boundary_height_m"],
         tuple(problem["wind_speeds_m_s"]),tuple(problem["wind_probabilities"]))
    if key in _REFERENCE_CACHE:
        layout,yaw=_REFERENCE_CACHE[key]; return layout.copy(),yaw.copy()
    rng=np.random.default_rng(7201+int(problem["turbine_count"])); candidates=[_grid(problem,False),_grid(problem,True)]
    base=_grid(problem,True)
    for _ in range(180):
        trial=base+rng.normal(0,70,base.shape); trial[:,0]=np.clip(trial[:,0],40,float(problem["boundary_width_m"])-40); trial[:,1]=np.clip(trial[:,1],40,float(problem["boundary_height_m"])-40)
        try: _validate(problem,{"layout_xy_m":trial,"yaw_by_direction_deg":np.zeros((len(DIRECTIONS),len(trial)))})
        except ValueError: continue
        candidates.append(trial)
    zero=np.zeros((len(DIRECTIONS),int(problem["turbine_count"])))
    layout=max(candidates,key=lambda x:_farm_value(problem,x,zero)); yaw=zero.copy()
    # Coordinate yaw refinement. Only the public model and wind rose are used.
    for d in range(len(DIRECTIONS)):
        best=_farm_value(problem,layout,yaw)
        for j in range(len(layout)):
            old=yaw[d,j]; chosen=old
            for value in (-22.,-14.,0.,14.,22.):
                yaw[d,j]=value; q=_farm_value(problem,layout,yaw)
                if q>best: best,chosen=q,value
            yaw[d,j]=chosen
    for step_size in (80., 40., 20.):
        best = _farm_value(problem, layout, yaw)
        for j in range(len(layout)):
            for axis in range(2):
                for sign in (-1., 1.):
                    trial = layout.copy(); trial[j,axis] += sign * step_size
                    try:
                        _validate(problem, {"layout_xy_m": trial, "yaw_by_direction_deg": yaw})
                    except ValueError:
                        continue
                    value = _farm_value(problem, trial, yaw)
                    if value > best:
                        layout, best = trial, value
    _REFERENCE_CACHE[key]=(layout.copy(),yaw.copy())
    return layout,yaw


def _score_instance(candidate,spec):
    problem=_problem(spec); base=_baseline(problem); ref=_reference(problem)
    low=_farm_value(problem,*base,expansion=.061); high=_farm_value(problem,*ref,expansion=.061)
    try:
        layout,yaw=_validate(problem,candidate(copy.deepcopy(problem)))
        value=_farm_value(problem,layout,yaw,expansion=.061)
        score=(value-low)/max(high-low,1e-9)
        shifted=_farm_value(problem,layout,yaw,expansion=.074,direction_shift=7.0,turbulence_penalty=.7)
        sb=_farm_value(problem,*base,expansion=.074,direction_shift=7.0,turbulence_penalty=.7); sr=_farm_value(problem,*ref,expansion=.074,direction_shift=7.0,turbulence_penalty=.7)
        robust=(shifted-sb)/max(sr-sb,1e-9)
        return {"name":spec[0],"split":spec[1],"valid":True,"score":float(score),"annual_value_gwh":value,
                "robustness_score":float(robust),"shifted_value_gwh":shifted}
    except Exception as exc:
        return {"name":spec[0],"split":spec[1],"valid":False,"score":0.0,"annual_value_gwh":0.0,
                "robustness_score":0.0,"shifted_value_gwh":0.0,"reason":f"{type(exc).__name__}: {exc}"}


def evaluate(design_wind_farm):
    rows=[_score_instance(design_wind_farm,s) for s in INSTANCE_SPECS]; dev=[r for r in rows if r["split"]=="development"]; held=[r for r in rows if r["split"]=="heldout"]
    return {"combined_score":max(0.0,float(np.mean([r["score"] for r in dev]))) if all(r["valid"] for r in dev) else 0.0,"valid":float(all(r["valid"] for r in dev)),
            "feasibility_rate":float(np.mean([r["valid"] for r in dev])),"robustness_score":float(np.mean([r["robustness_score"] for r in dev])),
            "heldout_policy_score":float(np.mean([r["score"] for r in held])),"heldout_robustness_score":float(np.mean([r["robustness_score"] for r in held])),
            "heldout_feasibility_rate":float(np.mean([r["valid"] for r in held])),"per_instance":rows}
