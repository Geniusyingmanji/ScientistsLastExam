"""Weak baseline: ignore batch and call large marginal differences discoveries."""
import numpy as np
def analyze_expression(problem, measure):
    rows=problem["initial_samples"]
    a=np.mean([r["counts"] for r in rows if r["condition"]==0],axis=0)
    b=np.mean([r["counts"] for r in rows if r["condition"]==1],axis=0)
    effect=np.log1p(b)-np.log1p(a)
    hits=[{"gene":g,"effect":float(e)} for g,e in zip(problem["gene_ids"],effect) if abs(e)>.45]
    return {"discoveries":hits,"abstain":False,"reason_code":"supported"}
