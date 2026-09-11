"""Shortcut probe for JuntaVariableDiscovery: strategies that do not contain the reference's
full-budget pivotal test with a family-wise refusal. Reports the best over the graded seed and a
few re-drawn run seeds, with false-discovery counts. Recomputes against the DELIVERED evaluator."""
import importlib.util, math, json, sys
from pathlib import Path
import numpy as np
from scipy.stats import norm

ROOT=Path(__file__).resolve().parents[2]; D=ROOT/"benchmarks/ComputerScience/JuntaVariableDiscovery"
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ev=load("e",D/"verification/evaluator.py"); ref=load("r",D/"verification/reference_influence.py"); sol=load("s",D/"solution.py")

def pivotal_counts(problem, query, frac):
    n=problem["n"]; B=problem["budget"]; rng=np.random.default_rng(12345)
    per=max(4,int(B*frac)//(2*n)); dis=[]
    for i in range(n):
        X=rng.integers(0,2,size=(per,n)); X2=X.copy(); X2[:,i]^=1
        dis.append(float(np.mean(query(X)!=query(X2))))
    return np.array(dis), per

def S_declare_all(p,q): return {"verdict":"junta","relevant":list(range(min(p["max_junta_size"],p["n"])))}
def S_refuse_all(p,q): return {"verdict":"no_junta"}
def S_random_k(p,q):
    rng=np.random.default_rng(7); return {"verdict":"junta","relevant":sorted(rng.choice(p["n"],p["max_junta_size"],replace=False).tolist())}

def S_correlation(margin):
    def f(p,q):
        c=dict(sol.DELTA.__class__() if False else {}); return sol.identify(p,q)  # baseline is delta family-wise
    return f
def S_corr_fixed(thr):
    def f(p,q):
        n=p["n"]; B=p["budget"]; K=p["max_junta_size"]; rng=np.random.default_rng(999)
        X=rng.integers(0,2,size=(B,n)); Y=(2*q(X)-1).astype(float); chi=(2*X-1).astype(float)
        coef=(chi*Y[:,None]).mean(0); claims=[i for i in range(n) if abs(coef[i])>thr]
        if len(claims)>K: return {"verdict":"no_junta"}
        return {"verdict":"junta","relevant":sorted(claims)}
    return f

def S_pivotal_norefuse(frac):
    def f(p,q):
        n=p["n"]; K=p["max_junta_size"]; eta=p["noise_rate"]; flr=2*eta*(1-eta)
        dis,per=pivotal_counts(p,q,frac); z=norm.isf(p["budget"] and 1e-3/n)
        sig=[i for i in range(n) if dis[i]-z*math.sqrt(max(dis[i]*(1-dis[i]),1e-9)/per)>flr]
        return {"verdict":"junta","relevant":sorted(sig[:K])}  # never declines; truncates to K
    return f

def S_pivotal_fixed(c, frac=0.9):
    def f(p,q):
        n=p["n"]; K=p["max_junta_size"]; eta=p["noise_rate"]; flr=2*eta*(1-eta)
        dis,per=pivotal_counts(p,q,frac); sig=[i for i in range(n) if dis[i]>flr+c]
        if len(sig)>K: return {"verdict":"no_junta"}
        return {"verdict":"junta","relevant":sorted(sig)}
    return f

def S_pivotal_budget(frac):
    def f(p,q):
        pp=dict(p); pp["budget"]=int(p["budget"]*frac); return ref.identify(pp,q)
    return f

def S_corr_claim_pivotal_detect(p,q):
    # claims from correlation, refusal test from a cheap pivotal pass at quarter budget
    n=p["n"]; K=p["max_junta_size"]; eta=p["noise_rate"]; flr=2*eta*(1-eta)
    rng=np.random.default_rng(999)
    half=p["budget"]//2
    X=rng.integers(0,2,size=(half,n)); Y=(2*q(X)-1).astype(float); chi=(2*X-1).astype(float)
    coef=(chi*Y[:,None]).mean(0); z=norm.isf(1e-3/n)
    claims=[i for i in range(n) if abs(coef[i])-z*math.sqrt(max(1-coef[i]**2,1e-9)/half)>0]
    dis,per=pivotal_counts({**p,"budget":p["budget"]-half},q,1.0)
    sig=[i for i in range(n) if dis[i]-z*math.sqrt(max(dis[i]*(1-dis[i]),1e-9)/per)>flr]
    if len(sig)>K: return {"verdict":"no_junta"}
    return {"verdict":"junta","relevant":sorted(claims)}

STRATS={
 "blind_declare_all":S_declare_all, "blind_refuse_all":S_refuse_all, "blind_random_k":S_random_k,
 "correlation_familywise":sol.identify,
 "corr_fixed_0.02":S_corr_fixed(0.02), "corr_fixed_0.05":S_corr_fixed(0.05),
 "pivotal_norefuse_full":S_pivotal_norefuse(0.9),
 "pivotal_fixed_c0.01":S_pivotal_fixed(0.01), "pivotal_fixed_c0.02":S_pivotal_fixed(0.02), "pivotal_fixed_c0.03":S_pivotal_fixed(0.03),
 "pivotal_budget_0.5":S_pivotal_budget(0.5), "pivotal_budget_0.25":S_pivotal_budget(0.25), "pivotal_budget_0.75":S_pivotal_budget(0.75),
 "corr_claim_pivotal_detect":S_corr_claim_pivotal_detect,
}

def run_shift(identify, shift):
    orig={w["name"]:w["run_seed"] for w in ev.DEVELOPMENT_WORLDS+ev.HELDOUT_WORLDS}
    dev=[ev._evaluate_world(identify,{**sp,"run_seed":orig[sp['name']]+7919*shift},"development",i) for i,sp in enumerate(ev.DEVELOPMENT_WORLDS)]
    held=[ev._evaluate_world(identify,{**sp,"run_seed":orig[sp['name']]+7919*shift},"heldout",i) for i,sp in enumerate(ev.HELDOUT_WORLDS)]
    ds=ev._split_summary(dev); hs=ev._split_summary(held)
    fd=sum(1 for r in dev+held if r["false_discovery"])
    return ds["normalized_mechanism"], hs["normalized_mechanism"], fd

if __name__=="__main__":
    shifts=[0,1,2,3]
    rows=[]
    for name,fn in STRATS.items():
        ds=[];hs=[];fds=[]
        for sh in shifts:
            d,h,fd=run_shift(fn,sh); ds.append(d);hs.append(h);fds.append(fd)
        rows.append((name, np.mean(ds), np.mean(hs), sum(fds)))
        print(f"{name:28s} dev {np.mean(ds):.3f}  held {np.mean(hs):.3f}  FD {sum(fds)} (over {len(shifts)} seeds)")
    best=max(rows, key=lambda r: r[1])
    refd=[];
    for sh in shifts: refd.append(run_shift(ref.identify,sh)[0])
    print(f"\nreference dev {np.mean(refd):.3f}")
    print(f"BEST shortcut: {best[0]} dev {best[1]:.3f} held {best[2]:.3f} FD {best[3]}  =>  {best[1]/np.mean(refd)*100:.1f}% of reference")

def S_pivotal_fixedz(z, frac=0.9):
    """The reference's pivotal test but with a fixed confidence level z instead of the
    family-wise quantile norm.isf(delta/n): a cheaper statistical choice, not a smaller budget."""
    def f(p,q):
        n=p["n"]; K=p["max_junta_size"]; eta=p["noise_rate"]; flr=2*eta*(1-eta)
        dis,per=pivotal_counts(p,q,frac)
        sig=[i for i in range(n) if dis[i]-z*math.sqrt(max(dis[i]*(1-dis[i]),1e-9)/per)>flr]
        if len(sig)>K: return {"verdict":"no_junta"}
        return {"verdict":"junta","relevant":sorted(sig)}
    return f
