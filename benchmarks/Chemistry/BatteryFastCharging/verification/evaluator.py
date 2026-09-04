from __future__ import annotations
import numpy as np

INVALID=-1e18
DEV=[(.12,20,.038,1.00),(.28,31,.052,.91),(.08,10,.046,1.07),(.34,36,.058,.94),(.20,27,.064,.98)]
TEST=[(.17,4,.061,1.04),(.11,40,.047,.89),(.30,25,.069,1.10),(.23,33,.056,.96)]
DT=.06; STEPS=16

def _simulate(policy, s, latent):
    soc,temp,res,capacity=s; ambient=temp; fade=0.; max_temp=temp; delivered=0.; polarization=0.
    r_mult, heat_mult, kinetics = latent
    for current in policy:
        current=float(current)
        if not np.isfinite(current) or current<0 or current>3.0: return None
        # Nonlinear OCV plus an unobserved, slowly relaxing polarization state.
        ocv=3.00+1.04*soc+0.09*np.tanh(7.0*(soc-.72))
        voltage=ocv+(res*r_mult)*current+polarization
        if voltage>4.25: return None
        temp += DT*(20.0*heat_mult*res*current*current-.16*(temp-ambient))
        if temp>47: return None
        eta=max(.72, .997-.018*current-.006*max(0,temp-29)-.010*(1.0-kinetics)*current)
        ds=min(1-soc, eta*current*DT/capacity); soc+=ds; delivered+=ds
        fade += DT*.0025*current*current*np.exp(max(0,temp-24)/22)*(1.0+.6*max(0,soc-.65))
        polarization=.78*polarization+.030*current/kinetics
        max_temp=max(max_temp,temp)
    completion=max(0., soc-.72)
    utility=delivered+0.35*completion-3.2*fade-.025*max(0,max_temp-36)**1.25
    return utility, soc, max_temp, fade

def _reference(problem):
    # A reproducible conservative CC-CV-like reference, not a claimed global optimum.
    r=problem["internal_resistance"]
    early=np.clip(1.08-.010*(problem["ambient_celsius"]-25)-4.0*(r-.05), .74, 1.16)
    return np.array([early]*5+[.82*early]*4+[.58*early]*4+[.30*early]*3,float)

LATENT=[(.92,.88,1.08),(1.0,1.0,1.0),(1.12,1.17,.91)]

def _evaluate(policy_fn, worlds):
    vals=[]; feasible=[]; details=[]
    for s in worlds:
        p={"time_steps":STEPS,"dt_hours":DT,"initial_soc":s[0],"ambient_celsius":s[1],"internal_resistance":s[2],"relative_capacity":s[3],"max_current_c":3.0,"max_voltage":4.25,"max_temperature_celsius":47.0,"target_soc":.80}
        try: policy=np.asarray(policy_fn(p),float)
        except Exception: policy=np.array([])
        # The true cell differs mildly from its public nominal parameters.  A policy
        # is valid only when it is safe for every latent member of this cell family.
        outcomes=[_simulate(policy,s,z) for z in LATENT] if policy.shape==(STEPS,) else [None]
        bases=[_simulate(np.full(STEPS,.5),s,z)[0] for z in LATENT]
        refs=[_simulate(_reference(p),s,z)[0] for z in LATENT]
        if any(x is None for x in outcomes): vals.append(-1.0); feasible.append(0.); details.append(None)
        else:
            ratios=[(x[0]-b)/max(1e-9,r-b) for x,b,r in zip(outcomes,bases,refs)]
            # Lower-tail utility prevents a schedule that only succeeds on the easy cell.
            vals.append(.55*min(ratios)+.45*float(np.mean(ratios))); feasible.append(1.); details.append(outcomes)
    return float(np.mean(vals)),float(np.mean(feasible)),details

def evaluate(candidate):
    dev,feas,details=_evaluate(candidate,DEV); held,held_feas,_=_evaluate(candidate,TEST)
    return {"combined_score":float(np.clip(dev,-1.0,1.0)),"valid":float(feas==1.0),"feasibility_rate":feas,"heldout_score":float(np.clip(held,-1.0,1.0)),"heldout_feasibility_rate":held_feas}
