"""Fixed review probe: five-date interpolation, unweighted mean, constant uncertainty."""
import numpy as np

def cheap(grid,catalog,lab,budget,n=5,std=.15,chi_gate=4.,coherence_gate=.35,edge=1):
    empty={'temperature_mean':[],'temperature_std':[],'age_offsets_years':[],
           'abstain':True,'confidence':.1}
    chi=np.mean([((np.asarray(r['calibration_proxy_values'])-r['sensitivity']*
             np.asarray(r['calibration_temperature_c']))/r['calibration_noise_std'])**2 for r in catalog])
    if chi>chi_gate:return empty
    curves=[];signals=[];used=0
    for row in catalog:
        nominal=np.asarray(row['nominal_age_years']);cost=1+int(np.ceil(n/5))
        if used+cost<=budget:
            indices=np.linspace(edge,len(nominal)-1-edge,n,dtype=int)
            response=lab(int(row['proxy_index']),indices);used+=response['budget_cost']
            curve=np.interp(nominal,nominal[indices],np.maximum.accumulate(response['dated_age_years']))
        else:curve=nominal
        curve=np.maximum.accumulate(np.clip(curve,grid[0],grid[-1]));curves.append(curve)
        signals.append(np.interp(grid,curve,np.asarray(row['values'])/row['sensitivity']))
    matrix=np.asarray(signals);mean=matrix.mean(axis=0)
    if np.mean((matrix-mean)**2)>coherence_gate:return empty
    return {'temperature_mean':mean,'temperature_std':np.full_like(mean,std),
            'sample_ages_years':curves,'abstain':False,'confidence':.8}


def reconstruct_climate(*args):
    return cheap(*args,n=5,std=.3,chi_gate=1.5,coherence_gate=.2,edge=0)
