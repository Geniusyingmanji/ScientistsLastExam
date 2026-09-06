"""Weak valid regular-grid, zero-yaw baseline."""
import math
import numpy as np


def design_wind_farm(problem):
    n=int(problem["turbine_count"]); width=float(problem["boundary_width_m"]); height=float(problem["boundary_height_m"])
    cols=int(math.ceil(math.sqrt(n*width/height))); rows=int(math.ceil(n/cols))
    xs=np.linspace(180,width-180,cols); ys=np.linspace(180,height-180,rows); layout=[]
    for y in ys:
        for x in xs:
            if len(layout)<n: layout.append([float(x),float(y)])
    yaw=np.zeros((len(problem["wind_directions_deg"]),n))
    return {"layout_xy_m":layout,"yaw_by_direction_deg":yaw.tolist()}
