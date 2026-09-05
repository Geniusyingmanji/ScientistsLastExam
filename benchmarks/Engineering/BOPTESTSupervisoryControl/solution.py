"""Weak valid occupied/unoccupied rule controller."""
import numpy as np


def make_hvac_controller(problem):
    del problem
    def step(observation):
        temp=np.asarray(observation["zone_temperature_c"],dtype=float); occ=np.asarray(observation["occupancy"],dtype=float)
        heat=np.where(occ>0,np.clip(4.2*(21.6-temp),0,18),np.clip(2.0*(17.0-temp),0,18))
        cool=np.where(occ>0,np.clip(4.2*(temp-24.4),0,18),np.clip(2.0*(temp-29.0),0,18))
        vent=np.clip(.25+.025*occ,.15,1.55)
        return {"heating_kw":heat.tolist(),"cooling_kw":cool.tolist(),"ventilation_ach":vent.tolist()}
    return step
