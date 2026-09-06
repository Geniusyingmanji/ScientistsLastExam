"""Truth-blind exhaustive small-cardinality knockout witness."""
import itertools
import numpy as np
from scipy.optimize import linprog

def _utility(p, ko):
    ids=p["reaction_ids"]; bounds=list(zip(p["lower_bounds"],p["upper_bounds"]))
    for x in ko: bounds[ids.index(x)]=(0.0,0.0)
    s=np.asarray(p["stoichiometric_matrix"]); c=np.zeros(len(ids)); c[ids.index(p["biomass_reaction"])]=-1
    g=linprog(c,A_eq=s,b_eq=np.zeros(s.shape[0]),bounds=bounds,method="highs")
    if not g.success or g.x[ids.index(p["biomass_reaction"])]<p["minimum_growth"]: return 0.0
    c[:]=0; c[ids.index(p["product_reaction"])]=1
    a=np.zeros((1,len(ids))); a[0,ids.index(p["biomass_reaction"])]=-1
    q=linprog(c,A_eq=s,b_eq=np.zeros(s.shape[0]),A_ub=a,
              b_ub=[-(g.x[ids.index(p["biomass_reaction"])]-p["growth_optimality_tolerance"])],
              bounds=bounds,method="highs")
    return 0.0 if not q.success else max(0.0,q.x[ids.index(p["product_reaction"])])*g.x[ids.index(p["biomass_reaction"])]/(1+0.08*len(ko))

def design_strain(problem):
    allowed=problem["allowed_reaction_knockouts"]
    choices=[c for k in range(problem["maximum_knockouts"]+1) for c in itertools.combinations(allowed,k)]
    return {"reaction_knockouts": list(max(choices,key=lambda c:_utility(problem,c)))}
