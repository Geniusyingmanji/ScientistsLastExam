"""Deterministic marker-count mixture oracle with alias and library-inadequacy worlds."""
from __future__ import annotations
import numpy as np

TAXA=[f"t{i}" for i in range(8)]; MARKERS=[f"m{i}" for i in range(16)]; BUDGET=2
PANEL_MARKERS={0:(0,1,2,3),1:(4,5,6,15),2:(7,8,9,10),3:(11,12,13,14),4:(0,5,10,15)}
SPECS=(("supported",31),("alias",32),("out_of_library",33),("supported",34),("alias",35),("supported",36),
       ("out_of_library",71),("supported",72),("alias",73))
DEV=range(6); HELD=range(6,9)

def _reference():
    rng=np.random.default_rng(8801); a=rng.uniform(.05,1,(len(MARKERS),len(TAXA)))
    a[:,1]=a[:,0]                         # an exactly unresolvable strain pair
    a[15,:]=0.0                           # sentinel marker for detectable library inadequacy
    return a/np.maximum(a.sum(axis=0,keepdims=True),1e-12)
REF=_reference()

def _truth(kind,seed):
    rng=np.random.default_rng(seed)
    count = int(rng.integers(2, 5))
    if kind == "alias":
        ids = [0] + sorted(rng.choice(np.arange(2, 8), count-1, replace=False))
    else:
        ids = sorted(rng.choice(np.arange(2, 8), count, replace=False))
    # A continuous simplex draw, with every true component above the reporting
    # threshold. No rounded grid or repeated fixed abundance is an oracle target.
    abundance = .10 + (1 - .10*count) * rng.dirichlet(np.ones(count)*2)

    probs=REF[:,ids]@abundance
    if kind=="out_of_library": probs=.72*probs; probs[15]=.28
    probs=probs/probs.sum()
    return ids,abundance,probs

def _counts(kind,seed,panel,call):
    ids,abundance,probs=_truth(kind,seed); mask=np.isin(np.arange(len(MARKERS)),PANEL_MARKERS[panel])
    q=probs*mask; q=q/q.sum(); rng=np.random.default_rng((seed,panel,call,41))
    return {"panel_id":panel,"read_count":400,"marker_counts":rng.multinomial(400,q).tolist()}

class _Sequencer:
    def __init__(self,kind,seed): self.kind=kind; self.seed=seed; self.calls=0; self.violated=False
    def __call__(self,panel_id):
        if self.calls>=BUDGET: self.violated=True; raise RuntimeError("read budget exhausted")
        if isinstance(panel_id,bool) or panel_id not in (1,2,3,4): raise ValueError("invalid panel")
        self.calls+=1; return _counts(self.kind,self.seed,int(panel_id),self.calls)

def _problem(kind,seed):
    return {"taxon_ids":TAXA,"marker_ids":MARKERS,"reference_profiles":REF.tolist(),
            "initial_observation":_counts(kind,seed,0,0),"available_panels":[1,2,3,4],
            "panel_markers":{p:[MARKERS[i] for i in ids] for p,ids in PANEL_MARKERS.items()},
            "panel_budget":BUDGET,"minimum_reported_abundance":.08,"abundance_tolerance":.025,
            "known_alias_groups":[["t0","t1"]]}

def _parse(out,problem):
    if not isinstance(out,dict) or set(out)!={"taxa","ambiguous_groups","abstain"}: return None
    if not isinstance(out["abstain"],bool) or not isinstance(out["taxa"],list) or not isinstance(out["ambiguous_groups"],list): return None
    taxa={}
    for row in out["taxa"]:
        if not isinstance(row,dict) or set(row)!={"taxon","abundance"} or row["taxon"] not in TAXA or row["taxon"] in taxa: return None
        try: value=float(row["abundance"])
        except Exception: return None
        if not np.isfinite(value) or not 0<=value<=1: return None
        taxa[row["taxon"]]=value
    groups=[]; allowed={frozenset(x) for x in problem["known_alias_groups"]}
    for group in out["ambiguous_groups"]:
        if not isinstance(group,list) or len(group)<2 or len(set(group))!=len(group) or any(x not in TAXA for x in group): return None
        value=frozenset(group)
        if value not in allowed or value in groups or value&set(taxa): return None
        groups.append(value)
    if out["abstain"] and (taxa or groups): return None
    return taxa,groups,out["abstain"]

def evaluate(assign_composition):
    rows=[]
    for kind,seed in SPECS:
        seq=_Sequencer(kind,seed)
        problem=_problem(kind,seed)
        try: parsed=_parse(assign_composition(problem,seq),problem)
        except Exception: parsed=None
        valid=parsed is not None and not seq.violated; taxa,groups,abstain=parsed if valid else ({},[],False)
        ids,ab,_=_truth(kind,seed); truth={TAXA[i]:float(x) for i,x in zip(ids,ab)}
        if kind=="alias":
            alias_ok = frozenset(("t0", "t1")) in groups
            identifiable = set(truth) - {"t0", "t1"}
            abundance_quality = sum(
                max(0.0, 1.0-abs(taxa[t]-truth[t])/problem["abundance_tolerance"])
                for t in sorted(identifiable & set(taxa))
            ) / len(identifiable)
            false = len(set(taxa)-identifiable)
            correct_claims = int(alias_ok) + len(identifiable & set(taxa))
            precision = correct_claims / max(1, correct_claims+false)
            mechanism = (.5*alias_ok + .5*abundance_quality)*precision
            refusal = float(alias_ok)
        elif kind=="out_of_library":
            mechanism=0.0; false=len(taxa)+len(groups); refusal=float(abstain)
        else:
            common=set(taxa)&set(truth); precision=len(common)/max(1,len(taxa)+len(groups)); recall=len(common)/len(truth)
            setscore=2*precision*recall/max(1e-12,precision+recall)
            abundance=1-np.mean([min(1,abs(taxa[x]-truth[x])/problem["abundance_tolerance"]) for x in sorted(common)]) if common else 0
            mechanism=.7*setscore+.3*abundance; false=len(set(taxa)-set(truth))+len(groups); refusal=0.0
        scientific=mechanism if kind!="out_of_library" else refusal
        rows.append({"kind":kind,"valid":valid,"mechanism":mechanism,"false":false,"claimed":len(taxa)+len(groups),
                     "refusal":refusal,"coverage":float(bool(taxa) or bool(groups)),"scientific":scientific})
    dev=[rows[i] for i in DEV]; held=[rows[i] for i in HELD]; floor=sum(r["kind"]=="out_of_library" for r in dev)/len(dev)
    raw=float(np.mean([r["scientific"] for r in dev])); combined=max(0,(raw-floor)/(1-floor))
    metrics = {"combined_score": float(combined), "valid": 1.0,
               "feasibility_rate": float(np.mean([r["valid"] for r in dev])),
               "per_world": rows}
    for prefix, panel in (("development", dev), ("heldout", held)):
        aliases = [r for r in panel if r["kind"] == "alias"]
        library = [r for r in panel if r["kind"] == "out_of_library"]
        supported = [r for r in panel if r["kind"] == "supported"]
        false = sum(r["false"] for r in panel)
        claims = sum(r["claimed"] for r in panel)
        metrics.update({
            f"{prefix}_mechanism_score": float(np.mean([r["mechanism"] for r in panel if r["kind"] != "out_of_library"])),
            f"{prefix}_false_discovery_rate": false / max(1, claims),
            f"{prefix}_false_discovery_count": false,
            f"{prefix}_claim_count": claims,
            f"{prefix}_alias_resolution_rate": float(np.mean([r["refusal"] for r in aliases])),
            f"{prefix}_alias_world_count": len(aliases),
            f"{prefix}_correct_refusal_rate": float(np.mean([r["refusal"] for r in library])),
            f"{prefix}_refusal_world_count": len(library),
            f"{prefix}_discovery_coverage": float(np.mean([r["coverage"] for r in supported])),
        })
    held_floor = sum(r["kind"] == "out_of_library" for r in held) / len(held)
    held_raw = float(np.mean([r["scientific"] for r in held]))
    metrics["heldout_scientific_score"] = max(0.0, (held_raw-held_floor)/(1-held_floor))
    if not all(row["valid"] for row in rows):
        metrics["valid"] = 0.0
        metrics["combined_score"] = 0.0
        for key in tuple(metrics):
            if key.startswith("heldout_") and "score" in key:
                metrics[key] = 0.0
    return metrics
