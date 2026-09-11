"""Authoritative self-check: import the DELIVERED evaluator and reference/baseline, recompute every
number over the real 18 worlds, plus run-seed robustness, headroom and the best shortcut."""
import sys, math, importlib.util
from pathlib import Path
import numpy as np
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "benchmarks/ComputerScience/JuntaVariableDiscovery"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

ev = load("junta_eval", D / "verification/evaluator.py")
ref = load("junta_ref", D / "verification/reference_influence.py")
base = load("junta_sol", D / "solution.py")

# ---- solver variants for the difficulty ladder ------------------------------------------------
def make_reference(delta):
    def identify(problem, query):
        n=problem["n"]; K=problem["max_junta_size"]; eta=problem["noise_rate"]; B=problem["budget"]
        rng=np.random.default_rng(12345); flr=2*eta*(1-eta)
        per=max(4,int(B*0.9)//(2*n)); z=norm.isf(delta/n); sig=[]
        for i in range(n):
            X=rng.integers(0,2,size=(per,n)); X2=X.copy(); X2[:,i]^=1
            d=float(np.mean(query(X)!=query(X2))); se=math.sqrt(max(d*(1-d),1e-9)/per)
            if d-z*se>flr: sig.append(i)
        if len(sig)>K: return {"verdict":"no_junta"}
        return {"verdict":"junta","relevant":sorted(sig)}
    return identify

def half_budget(problem, query):
    problem=dict(problem); problem["budget"]=problem["budget"]//2
    return ref.identify(problem, query)

def declare_all(problem, query):
    return {"verdict":"junta","relevant":list(range(min(problem["max_junta_size"],problem["n"])))}

def refuse_all(problem, query):
    return {"verdict":"no_junta"}

def adaptive(delta):
    def identify(problem, query):
        n=problem["n"]; K=problem["max_junta_size"]; eta=problem["noise_rate"]; B=problem["budget"]
        rng=np.random.default_rng(12345); flr=2*eta*(1-eta); z=norm.isf(delta/n)
        per0=max(4,int(B*0.4)//(2*n)); est={}; cnt={}
        for i in range(n):
            X=rng.integers(0,2,size=(per0,n)); X2=X.copy(); X2[:,i]^=1
            est[i]=float(np.mean(query(X)!=query(X2))); cnt[i]=per0
        used=per0*n*2
        for _ in range(8):
            rem=B-used
            if rem<2*n: break
            act=[i for i in range(n) if not((est[i]-z*math.sqrt(max(est[i]*(1-est[i]),1e-9)/cnt[i])>flr) or
                                             (est[i]+z*math.sqrt(max(est[i]*(1-est[i]),1e-9)/cnt[i])<flr))]
            if not act: break
            act.sort(key=lambda i: abs(est[i]-flr)); b=max(4, rem//(2*len(act)))
            for i in act:
                if used+2*b>B: b=(B-used)//2
                if b<1: break
                X=rng.integers(0,2,size=(b,n)); X2=X.copy(); X2[:,i]^=1
                d=float(np.mean(query(X)!=query(X2)))
                est[i]=(est[i]*cnt[i]+d*b)/(cnt[i]+b); cnt[i]+=b; used+=2*b
        sig=[i for i in range(n) if est[i]-z*math.sqrt(max(est[i]*(1-est[i]),1e-9)/cnt[i])>flr]
        if len(sig)>K: return {"verdict":"no_junta"}
        return {"verdict":"junta","relevant":sorted(sig)}
    return identify

# ---- run one full evaluate() and pull the axes ------------------------------------------------
def run(identify):
    r=ev.evaluate(identify)
    fd=sum(1 for row in r["per_instance"] if row["false_discovery"])
    return r, fd

def line(name, r, fd):
    print(f"{name:24s} dev={r['development_mechanism_score']:.3f} (raw {r['development_raw_mechanism']:.3f}) "
          f"held={r['heldout_mechanism_score']:.3f} FD={fd} "
          f"refuse_dev={r['development_correct_refusal_rate']:.2f} cover={r['development_discovery_coverage']:.2f}")

# ---- robustness over run-seed shifts ----------------------------------------------------------
def shifted_specs(worlds, shift):
    return tuple({**w, "run_seed": w["run_seed"]+shift*7919} for w in worlds)

def run_shift(identify, shift):
    dev=[ev._evaluate_world(identify, sp, "development", i) for i,sp in enumerate(shifted_specs(ev.DEVELOPMENT_WORLDS,shift))]
    held=[ev._evaluate_world(identify, sp, "heldout", i) for i,sp in enumerate(shifted_specs(ev.HELDOUT_WORLDS,shift))]
    ds=ev._split_summary(dev); hs=ev._split_summary(held)
    fd=sum(1 for row in dev+held if row["false_discovery"])
    return ds["normalized_mechanism"], hs["normalized_mechanism"], fd

if __name__=="__main__":
    print("=== graded seed (delivered worlds) ===")
    for name, idf in [("reference d1e-3", ref.identify),
                      ("baseline correlation", base.identify),
                      ("declare_all", declare_all),
                      ("refuse_all", refuse_all),
                      ("half-budget", half_budget),
                      ("adaptive d1e-3", adaptive(1e-3)),
                      ("headroom ref d1e-2", make_reference(1e-2)),
                      ("headroom adaptive d1e-2", adaptive(1e-2))]:
        r,fd=run(idf); line(name,r,fd)

    print("\n=== robustness: reference over 12 run-seed shifts ===")
    devs=[]; helds=[]; fds=[]
    for sh in range(12):
        d,h,fd=run_shift(ref.identify, sh); devs.append(d); helds.append(h); fds.append(fd)
    print(f"reference  dev mean {np.mean(devs):.3f} [{min(devs):.3f},{max(devs):.3f}]  "
          f"held mean {np.mean(helds):.3f} [{min(helds):.3f},{max(helds):.3f}]  total FD {sum(fds)} over {12} shifts")

    print("\n=== robustness: best shortcut (half-budget) over 12 shifts ===")
    sd=[]; sh_=[]; sfd=[]
    for sh in range(12):
        d,h,fd=run_shift(half_budget, sh); sd.append(d); sh_.append(h); sfd.append(fd)
    print(f"half-budget dev mean {np.mean(sd):.3f} [{min(sd):.3f},{max(sd):.3f}]  held mean {np.mean(sh_):.3f}  total FD {sum(sfd)}")
    print(f"\nshortcut/reference ratio dev = {np.mean(sd)/np.mean(devs)*100:.1f}%")
