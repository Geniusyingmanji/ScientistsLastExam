"""Frozen RNA-count evidence oracle with batch confounding and charged follow-up samples."""
from __future__ import annotations
import numpy as np

GENES=[f"g{i:02d}" for i in range(24)]
SPECS=(
    ("supported",101),("null",102),("confounded",103),("supported",104),
    ("null",105),("supported",106),("supported",201),("confounded",202),("null",203),
)
DEV=range(6); HELD=range(6,9); BUDGET=4

def _truth(kind, seed):
    rng=np.random.default_rng(seed)
    effects=np.zeros(len(GENES))
    if kind=="supported":
        chosen=np.sort(rng.choice(len(GENES),4,replace=False)); effects[chosen]=rng.choice([-1,1],4)*rng.uniform(.8,1.25,4)
    batch=rng.normal(0,.5,len(GENES)); base=rng.uniform(3.2,5.0,len(GENES))
    return effects,batch,base

def _row(kind,seed,batch,condition,replicate):
    effects,be,base=_truth(kind,seed)
    eta=base+be*batch+effects*condition
    rng=np.random.default_rng((seed,batch,condition,replicate,991))
    mean=np.exp(eta); dispersion=.12
    counts=rng.negative_binomial(1/dispersion,(1/dispersion)/(1/dispersion+mean))
    return {"batch":batch,"condition":condition,"library_size":1.0,
            "counts":[int(x) for x in counts]}

def _initial(kind,seed):
    # Recruitment layout carries identifiability information, never an effect label.
    # All worlds start with the same confounded observations; follow-ups can resolve
    # condition effects only when a cross-cell is available.
    cells=[(0,0),(1,1)]
    return [_row(kind,seed,b,c,r) for b,c in cells for r in range(2)]

class _Lab:
    def __init__(self,kind,seed): self.kind=kind; self.seed=seed; self.calls=0; self.violated=False
    @property
    def available(self): return [[0,0],[1,1]] if self.kind=="confounded" else [[0,0],[0,1],[1,0],[1,1]]
    def __call__(self,batch,condition):
        if self.calls>=BUDGET: self.violated=True; raise RuntimeError("sample budget exhausted")
        if [batch,condition] not in self.available: raise ValueError("unavailable batch-condition cell")
        self.calls+=1
        return _row(self.kind,self.seed,int(batch),int(condition),100+self.calls)

def _problem(kind,seed,lab):
    return {"gene_ids":GENES,"initial_samples":_initial(kind,seed),"available_cells":lab.available,
            "sample_budget":BUDGET,"effect_scale":"natural_log_fold_change",
            "valid_reason_codes":["supported","not_identifiable","no_effect"]}

def _parse(out):
    if not isinstance(out,dict) or set(out)!={"discoveries","abstain","reason_code"}: return None
    if not isinstance(out["abstain"],bool) or out["reason_code"] not in {"supported","not_identifiable","no_effect"}: return None
    if not isinstance(out["discoveries"],list): return None
    found={}
    for row in out["discoveries"]:
        if not isinstance(row,dict) or set(row)!={"gene","effect"}: return None
        if row["gene"] not in GENES or row["gene"] in found: return None
        try: value=float(row["effect"])
        except Exception: return None
        if not np.isfinite(value) or abs(value)>5: return None
        found[row["gene"]]=value
    if out["abstain"] and found: return None
    return found,out["abstain"],out["reason_code"]

def _score_world(kind,seed,parsed,valid):
    found,abstain,reason=parsed if valid else ({},False,"")
    effects=_truth(kind,seed)[0]; true={GENES[i] for i,x in enumerate(effects) if x}
    claimed=set(found); tp=len(true&claimed); fp=len(claimed-true); fn=len(true-claimed)
    f1=2*tp/max(1,2*tp+fp+fn)
    effect_quality=(sum(max(0.0,1.0-abs(found[g]-effects[GENES.index(g)])/.75)
                        for g in sorted(true&claimed))/max(1,len(true)))
    mechanism=.7*f1+.3*effect_quality
    correct_refusal=float(kind=="confounded" and abstain and reason=="not_identifiable")
    if not valid:
        scientific=mechanism=correct_refusal=0.0
    elif kind=="supported":
        scientific=mechanism if not abstain and reason=="supported" else 0.0
    elif kind=="confounded":
        scientific=correct_refusal
    else:
        scientific=float(not claimed and not abstain and reason=="no_effect")
    return {"kind":kind,"valid":valid,"mechanism":mechanism,"false_positive":fp,
            "claimed":len(claimed),"refusal":correct_refusal,"coverage":float(bool(claimed)),
            "scientific":scientific}

def _baseline_output(problem):
    rows=problem["initial_samples"]
    a=np.mean([r["counts"] for r in rows if r["condition"]==0],axis=0)
    b=np.mean([r["counts"] for r in rows if r["condition"]==1],axis=0)
    effect=np.log1p(b)-np.log1p(a)
    hits={g:float(e) for g,e in zip(problem["gene_ids"],effect) if abs(e)>.45}
    return hits,False,"supported"

def evaluate(analyze_expression):
    rows=[]
    for kind,seed in SPECS:
        lab=_Lab(kind,seed)
        try: parsed=_parse(analyze_expression(_problem(kind,seed,lab),lab))
        except Exception: parsed=None
        valid=parsed is not None and not lab.violated
        row=_score_world(kind,seed,parsed,valid); row["calls"]=lab.calls; rows.append(row)
    dev=[rows[i] for i in DEV]; held=[rows[i] for i in HELD]
    abstain_floor=sum(r["kind"]=="confounded" for r in dev)/len(dev)
    baseline_raw=float(np.mean([_score_world(kind,seed,_baseline_output(_problem(kind,seed,_Lab(kind,seed))),True)["scientific"]
                                for kind,seed in SPECS[:6]]))
    # A layout-only policy can correctly refuse confounding and deny every effect.
    # Normalize above that entire no-discovery policy, not just blanket abstention.
    no_discovery_floor=sum(r["kind"]!="supported" for r in dev)/len(dev)
    floor=max(abstain_floor,baseline_raw,no_discovery_floor)
    raw=float(np.mean([r["scientific"] for r in dev])); combined=max(0.0,(raw-floor)/(1-floor))
    unsupported=[r for r in dev if r["kind"]!="supported"]
    return {"combined_score":combined,"valid":1.0 if all(r["valid"] for r in dev) else 0.0,
            "feasibility_rate":float(np.mean([r["valid"] for r in dev])),
            "development_mechanism_score":float(np.mean([r["mechanism"] for r in dev if r["kind"]=="supported"])),
            "development_false_discovery_rate":sum(r["false_positive"] for r in unsupported)/max(1,sum(r["claimed"] for r in unsupported)),
            "development_false_discovery_count":sum(r["false_positive"] for r in unsupported),
            "development_unsupported_claim_count":sum(r["claimed"] for r in unsupported),
            "development_correct_refusal_rate":float(np.mean([r["refusal"] for r in dev if r["kind"]=="confounded"])),
            "development_discovery_coverage":float(np.mean([r["coverage"] for r in dev if r["kind"]=="supported"])),
            "heldout_scientific_score":float(np.mean([r["scientific"] for r in held])),"per_world":rows}
