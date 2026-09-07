"""Truth-blind batch-aware reference with design-rank refusal."""
import numpy as np
def analyze_expression(problem, measure):
    rows=list(problem["initial_samples"])
    cells={tuple(x) for x in problem["available_cells"]}
    if len(cells)<3:
        return {"discoveries":[],"abstain":True,"reason_code":"not_identifiable"}
    # Balance the two missing cross-cells; choosing samples does not depend on
    # whether the hidden world actually contains a condition effect.
    targets=[cell for cell in ((0,1),(1,0)) if cell in cells]
    for i in range(problem["sample_budget"]): rows.append(measure(*targets[i % len(targets)]))
    x=np.array([[1,r["batch"],r["condition"]] for r in rows],float)
    y=np.log1p(np.array([r["counts"] for r in rows],float))
    coef=np.linalg.lstsq(x,y,rcond=None)[0][2]
    hits=[{"gene":g,"effect":float(e)} for g,e in zip(problem["gene_ids"],coef) if abs(e)>.55]
    return {"discoveries":hits,"abstain":False,"reason_code":"supported" if hits else "no_effect"}
