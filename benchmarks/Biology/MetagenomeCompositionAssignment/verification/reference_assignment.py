"""Truth-blind panel-likelihood mixture and residual/alias reference."""
import numpy as np
from scipy.optimize import minimize


def assign_composition(problem, sequence):
    a=np.asarray(problem["reference_profiles"],float)
    marker_index={name:i for i,name in enumerate(problem["marker_ids"])}

    def information(panel):
        indices=[marker_index[name] for name in problem["panel_markers"][panel]]
        conditioned=a[indices,:]/np.maximum(a[indices,:].sum(axis=0,keepdims=True),1e-12)
        distances=[np.linalg.norm(conditioned[:,i]-conditioned[:,j])
                   for i in range(a.shape[1]) for j in range(i)]
        return float(np.mean(distances))

    sentinel_panel=next(p for p in problem["available_panels"]
                        if problem["marker_ids"][-1] in problem["panel_markers"][p])
    remaining=[p for p in problem["available_panels"] if p!=sentinel_panel]
    chosen=[sentinel_panel,max(remaining,key=information)]
    observations=[problem["initial_observation"]]+[sequence(p) for p in chosen]
    empirical={}
    for panel in {o["panel_id"] for o in observations}:
        counts=np.sum([np.asarray(o["marker_counts"],float) for o in observations
                       if o["panel_id"]==panel],axis=0)
        empirical[panel]=counts/max(1,counts.sum())

    def loss(weights):
        total=0.0
        for panel,y in empirical.items():
            allowed=set(problem["panel_markers"][panel])
            mask=np.array([name in allowed for name in problem["marker_ids"]])
            predicted=(a@weights)*mask
            predicted=predicted/max(1e-12,predicted.sum())
            total+=float(np.sum((predicted-y)**2))
        return total

    fit=minimize(loss,np.ones(a.shape[1])/a.shape[1],method="SLSQP",
                 bounds=[(0.0,1.0)]*a.shape[1],
                 constraints={"type":"eq","fun":lambda weights: weights.sum()-1.0},
                 options={"maxiter":500,"ftol":1e-12})
    coef=fit.x
    if empirical[0][-1]>.12 or not fit.success or loss(coef)>.02:
        return {"taxa":[],"ambiguous_groups":[],"abstain":True}
    rows=[]; groups=[]
    for j,x in enumerate(coef):
        if x<problem["minimum_reported_abundance"]: continue
        if j in (0,1):
            if not groups: groups.append(["t0","t1"])
        else: rows.append({"taxon":problem["taxon_ids"][j],"abundance":float(x)})
    return {"taxa":rows,"ambiguous_groups":groups,"abstain":False}
