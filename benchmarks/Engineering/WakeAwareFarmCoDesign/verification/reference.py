"""Standalone public-model witness. No oracle imports or hidden instance access.

The public model is reproduced here; independent high-fidelity validation is pending.
"""
import math
import numpy as np

_REFERENCE_CACHE={}
RANDOM_LAYOUT_STARTS = 12
LAYOUT_REFINEMENT_STEPS_M = (120.0, 60.0, 30.0)
ALTERNATIONS = 1
YAW_GRID_DEG = (-25.0, -15.0, -7.5, 0.0, 7.5, 15.0, 25.0)
LAYOUT_PASSES_PER_SCALE = 2

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
    return float(sum(_direction_value(problem,layout,yaw[d],d,expansion,direction_shift)
                     for d in range(len(problem["wind_directions_deg"]))))

def _refine_yaw(problem, layout, yaw):
    for d in range(len(problem["wind_directions_deg"])):
        best=_direction_value(problem,layout,yaw[d],d)
        for j in range(len(layout)):
            chosen=float(yaw[d,j])
            for value in YAW_GRID_DEG:
                yaw[d,j]=value; quality=_direction_value(problem,layout,yaw[d],d)
                if quality>best+1e-12: best,chosen=quality,value
            yaw[d,j]=chosen
    return yaw

def _refine_layout(problem, layout, yaw):
    for step_size in LAYOUT_REFINEMENT_STEPS_M:
        for _ in range(LAYOUT_PASSES_PER_SCALE):
            improved=False; best=_farm_value(problem,layout,yaw)
            for j in range(len(layout)):
                for axis in range(2):
                    for sign in (-1.,1.):
                        trial=layout.copy(); trial[j,axis]+=sign*step_size
                        try: _validate(problem,{"layout_xy_m":trial,"yaw_by_direction_deg":yaw})
                        except ValueError: continue
                        quality=_farm_value(problem,trial,yaw)
                        if quality>best+1e-12: layout,best,improved=trial,quality,True
            if not improved: break
    return layout

def _reference(problem):
    key=(problem["turbine_count"],problem["boundary_width_m"],problem["boundary_height_m"],
         tuple(problem["wind_speeds_m_s"]),tuple(problem["wind_probabilities"]))
    if key in _REFERENCE_CACHE:
        layout,yaw=_REFERENCE_CACHE[key]; return layout.copy(),yaw.copy()
    rng=np.random.default_rng(7201+int(problem["turbine_count"])); candidates=[_grid(problem,False),_grid(problem,True)]
    base=_grid(problem,True)
    for _ in range(RANDOM_LAYOUT_STARTS):
        trial=base+rng.normal(0,70,base.shape); trial[:,0]=np.clip(trial[:,0],40,float(problem["boundary_width_m"])-40); trial[:,1]=np.clip(trial[:,1],40,float(problem["boundary_height_m"])-40)
        try: _validate(problem,{"layout_xy_m":trial,"yaw_by_direction_deg":np.zeros((len(problem["wind_directions_deg"]),len(trial)))})
        except ValueError: continue
        candidates.append(trial)
    zero=np.zeros((len(problem["wind_directions_deg"]),int(problem["turbine_count"])))
    layout=max(candidates,key=lambda x:_farm_value(problem,x,zero)); yaw=zero.copy()
    for _ in range(ALTERNATIONS):
        yaw=_refine_yaw(problem,layout,yaw)
        layout=_refine_layout(problem,layout,yaw)
    yaw=_refine_yaw(problem,layout,yaw)
    _REFERENCE_CACHE[key]=(layout.copy(),yaw.copy())
    return layout,yaw

def design_wind_farm(problem):
    layout,yaw=_reference(problem)
    return {"layout_xy_m":layout.tolist(),"yaw_by_direction_deg":yaw.tolist()}
