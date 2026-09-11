"""Recompute every number quoted in JuntaVariableDiscovery's Task.md, TASK_CARD.yaml and
references/known_best.md, against the package's own delivered evaluator. Run:

    .venv/bin/python .research/junta/summary.py
"""
import importlib.util, math
from pathlib import Path
import numpy as np
from scipy.stats import binom, norm

ROOT=Path(__file__).resolve().parents[2]; D=ROOT/"benchmarks/ComputerScience/JuntaVariableDiscovery"
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ev=load("e",D/"verification/evaluator.py"); ref=load("r",D/"verification/reference_influence.py"); sol=load("s",D/"solution.py")
pr=load("pr",Path(__file__).parent/"probe.py")

ORIG={w["name"]:w["run_seed"] for w in ev.DEVELOPMENT_WORLDS+ev.HELDOUT_WORLDS}
def run_shift(identify, shift):
    dev=[ev._evaluate_world(identify,{**sp,"run_seed":ORIG[sp['name']]+7919*shift},"development",i) for i,sp in enumerate(ev.DEVELOPMENT_WORLDS)]
    held=[ev._evaluate_world(identify,{**sp,"run_seed":ORIG[sp['name']]+7919*shift},"heldout",i) for i,sp in enumerate(ev.HELDOUT_WORLDS)]
    ds=ev._split_summary(dev); hs=ev._split_summary(held)
    return ds["normalized_mechanism"], hs["normalized_mechanism"], sum(1 for r in dev+held if r["false_discovery"]), dev

def robust(identify, k=12):
    ds=[];hs=[];fds=[]
    for sh in range(k):
        d,h,fd,_=run_shift(identify,sh); ds.append(d);hs.append(h);fds.append(fd)
    return np.mean(ds),min(ds),max(ds),np.mean(hs),min(hs),max(hs),sum(fds)

print("="*70)
print("REFERENCE (verification/reference_influence.py): pivotal + family-wise delta=1e-3")
g=ev.evaluate(ref.identify)
print(f"  graded: dev {g['development_mechanism_score']:.4f}  held {g['heldout_mechanism_score']:.4f}  "
      f"FD {sum(1 for r in g['per_instance'] if r['false_discovery'])}  refuse {g['development_correct_refusal_rate']:.2f}  "
      f"cover {g['development_discovery_coverage']:.2f}  mean_q {g['development_mean_probes_used']:.0f}")
sup=[r['sharpness'] for r in g['per_instance'] if r['split']=='development' and r['kind']=='supported']
print(f"  supported recall range {min(sup):.3f}..{max(sup):.3f}")
r=robust(ref.identify)
print(f"  robust 12 seeds: dev {r[0]:.3f} [{r[1]:.3f},{r[2]:.3f}]  held {r[3]:.3f} [{r[4]:.3f},{r[5]:.3f}]  totalFD {r[6]}/216")

print("="*70)
print("BASELINE (solution.py): degree-one correlation")
b=ev.evaluate(sol.identify)
print(f"  dev {b['development_mechanism_score']:.4f} (raw {b['development_raw_mechanism']:.4f})  held {b['heldout_mechanism_score']:.4f}  "
      f"FD {sum(1 for r in b['per_instance'] if r['false_discovery'])}")
da=ev.evaluate(pr.S_declare_all); ra=ev.evaluate(pr.S_refuse_all)
print(f"  declare_all dev {da['development_mechanism_score']:.4f} FD {sum(1 for r in da['per_instance'] if r['false_discovery'])}; "
      f"refuse_all dev {ra['development_mechanism_score']:.4f}")

N_SUP=12*sum(1 for r in g['per_instance'] if r['kind']=='supported')   # supported world-runs over 12 seeds
def null_error(z, budget):
    """Exact chance the pivotal test at margin z names an irrelevant variable. The two answers of a
    pair see the same function value, so they disagree only through the noise and the count over
    per pairs is Binomial(per, base); the variable is named when its rate minus z observed standard
    errors clears base. Returns the per-variable rate, the union bound over the n candidates, the
    chance a supported world names any of its n - K irrelevant variables, and the chance none of
    the N_SUP supported world-runs does."""
    base=2*ev.NOISE*(1-ev.NOISE); per=max(4,int(budget*0.9)//(2*ev.N))
    k=next(k for k in range(per+1) if k/per-z*math.sqrt(max(k/per*(1-k/per),1e-9)/per)>base)
    a=binom.sf(k-1,per,base); w=1-(1-a)**(ev.N-ev.MAX_JUNTA)
    return a, ev.N*a, w, (1-w)**N_SUP
def guarantee(z, budget):
    a,u,w,p0=null_error(z,budget)
    return f"  | exact: per-variable {a:.2e}  union over n {u:.2e}  per supported world {w:.2e}  P(no FD in {N_SUP}) {p0:.2f}"

print("="*70)
print("LADDER: reference method, margin z (family-wise ref z=%.2f) and budget fraction" % norm.isf(1e-3/28))
print(f"  delta/n = {1e-3/ev.N:.2e}, normal tail at z=3: {norm.sf(3.0):.2e}")
for z in [norm.isf(1e-3/28),3.5,3.25,3.0,2.75,2.5]:
    a=robust(pr.S_pivotal_fixedz(z))
    tag=" <-REF" if abs(z-norm.isf(1e-3/28))<0.01 else (" <-CLIFF" if abs(z-2.75)<0.01 else "")
    print(f"  z={z:.3f}  dev {a[0]:.3f} [{a[1]:.3f},{a[2]:.3f}]  held {a[3]:.3f}  FD {a[6]}{tag}{guarantee(z,ev.BUDGET)}")
for frac in [0.75,0.5,0.25]:
    a=robust(pr.S_pivotal_budget(frac))
    print(f"  budget {frac:.2f} (family-wise margin)  dev {a[0]:.3f}  held {a[3]:.3f}  FD {a[6]}{guarantee(norm.isf(1e-3/28),int(ev.BUDGET*frac))}")

print("="*70)
print("SHORTCUT PROBE: methods that do NOT run the full-budget pivotal family-wise test")
refmean=robust(ref.identify)[0]
best=None
for name,fn in [("blind_declare_all",pr.S_declare_all),("blind_refuse_all",pr.S_refuse_all),
                ("blind_random_k",pr.S_random_k),("correlation_familywise",sol.identify),
                ("corr_fixed_0.02",pr.S_corr_fixed(0.02)),("corr_fixed_0.05",pr.S_corr_fixed(0.05)),
                ("pivotal_norefuse_full",pr.S_pivotal_norefuse(0.9)),
                ("pivotal_fixed_c0.02",pr.S_pivotal_fixed(0.02)),("pivotal_fixed_c0.03",pr.S_pivotal_fixed(0.03)),
                ("corr_claim_pivotal_detect",pr.S_corr_claim_pivotal_detect)]:
    a=robust(fn)
    print(f"  {name:28s} dev {a[0]:.3f}  held {a[3]:.3f}  FD {a[6]}")
    if a[6]==0 and (best is None or a[0]>best[1]): best=(name,a[0])
print(f"  reference dev {refmean:.3f}")
print(f"  BEST shortcut with 0 FD: {best[0]} dev {best[1]:.3f} = {best[1]/refmean*100:.1f}% of reference")

print("="*70)
print("DETECTABILITY kappa* (supported worlds 0; unsupported = parity size - max_junta)")
for worlds,lab in [(ev.DEVELOPMENT_WORLDS,"dev"),(ev.HELDOUT_WORLDS,"held")]:
    ks=[(sp['name'],ev.make_world(sp)['kind'][:3],round(ev.detectability(ev.make_world(sp)),1)) for sp in worlds]
    print(f"  {lab}:", ks)
