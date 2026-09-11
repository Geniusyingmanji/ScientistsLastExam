import numpy as np, math
from scipy.stats import norm
import eng

def _pivotal(query, n, vars_, per, rng):
    """Estimate influence of each var in vars_ with `per` pivotal samples; return (est, se)."""
    est={}; se={}
    for i in vars_:
        X=rng.integers(0,2,size=(per,n)); X2=X.copy(); X2[:,i]^=1
        y1=query(X); y2=query(X2)
        d=float(np.mean(y1!=y2))              # observed disagreement
        # d = Inf*(1-2eta)^0 ... two noisy labels: P(disagree)=Inf*(1-2q)+(1-Inf)*2q(1-q)... approx
        est[i]=d; se[i]=math.sqrt(max(d*(1-d),1e-9)/per)
    return est,se

def reference(problem, query, cfg=None):
    cfg=cfg or {}; delta=cfg.get('delta',1e-3); n=problem['n']; K=problem['max_junta']; eta=problem['noise_rate']; B=problem['budget']
    rng=np.random.default_rng(cfg.get('seed',12345))
    base=2*eta*(1-eta)                       # disagreement floor for an irrelevant var
    per=max(4,int(B*cfg.get('frac',0.9))//(2*n))
    est,se=_pivotal(query,n,range(n),per,rng)
    z=norm.isf(delta/n)
    # junta-distance refuse: influence above the floor for more than K variables
    signif=[i for i in range(n) if est[i]-z*se[i]>base]
    if len(signif)>K: return {'verdict':'no_junta','confidence':0.9}
    relevant=sorted(signif)
    return {'verdict':'junta','relevant':relevant,'confidence':0.6}

def correlation(problem, query, cfg=None):
    cfg=cfg or {}; delta=cfg.get('delta',1e-3); n=problem['n']; K=problem['max_junta']; B=problem['budget']
    rng=np.random.default_rng(999)
    M=B  # one query per sample
    X=rng.integers(0,2,size=(M,n)); Y=(2*query(X)-1).astype(float)
    chi=(2*X-1).astype(float)
    coef=(chi*Y[:,None]).mean(0)               # degree-1 Fourier coefficients
    z=norm.isf(delta/n); claims=[]
    for i in range(n):
        se=math.sqrt(max(1-coef[i]**2,1e-9)/M)
        if abs(coef[i])-z*se>0: claims.append(i)
    if len(claims)>K: return {'verdict':'no_junta','confidence':0.5}
    return {'verdict':'junta','relevant':sorted(claims),'confidence':0.5}

def declare_all(problem, query, cfg=None):
    n=problem['n']; K=problem['max_junta']
    return {'verdict':'junta','relevant':list(range(min(K,n))),'confidence':0.5}

def score(sub, world):
    R=world['R'] if world['kind']=='supported' else None
    unsup=world['kind']=='unsupported'
    v=sub.get('verdict'); refused = v in (None,'no_junta') or sub.get('abstain') is True
    if refused: return (1.0 if unsup else 0.0),('refuse',False)
    rel=set(int(i) for i in sub.get('relevant',[]))
    if unsup: return 0.0,('claim_on_unsup',True)
    # FD: any claimed var with true influence 0 (not in R)
    for i in rel:
        if i not in world['R']: return -1.0,('false_var',True)
    recall=len(rel & world['R'])/len(world['R'])
    return recall,('ok',False)

def evalworld(solver,spec,cfg=None):
    w=eng.make_world(spec); b=eng.Bench(w,spec['run_seed']); q=b.oracle()
    prob={'n':w['n'],'max_junta':eng.K,'noise_rate':eng.ETA,'budget':eng.BUDGET}
    sub=solver(prob,q,cfg)
    if b.violated: sub={'verdict':'invalid'}
    sc,(why,fd)=score(sub,w)
    return sc,why,fd,b.used,w['kind']

WORLDS=[dict(name=f'sup{k}',seed=300+k,run_seed=440000+k) for k in range(7)]+[
    dict(name='bp0',seed=360,run_seed=441000,fault='bigparity',size=14),
    dict(name='bp1',seed=361,run_seed=441001,fault='bigparity',size=15),
    dict(name='bp2',seed=362,run_seed=441002,fault='bigparity',size=16),
    dict(name='bp3',seed=363,run_seed=441003,fault='bigparity',size=17),
    dict(name='bp4',seed=364,run_seed=441004,fault='bigparity',size=18),
]

def summ(solver,cfg=None):
    rows=[evalworld(solver,sp,cfg) for sp in WORLDS]
    raw=np.mean([r[0] for r in rows]); nun=sum(1 for r in rows if r[4]=='unsupported'); n=len(rows)
    aa=nun/n; norm_=max(0.0,(raw-aa)/(1-aa)); fd=sum(1 for r in rows if r[2])
    sup=[r for r in rows if r[4]=='supported']
    return dict(norm=round(norm_,3),raw=round(raw,3),fd=fd,supmean=round(np.mean([r[0] for r in sup]),3)),rows

if __name__=='__main__':
    for name,solver in [('reference',reference),('correlation',correlation),('declare_all',declare_all)]:
        s,rows=summ(solver)
        print(name,s)
        if name=='reference':
            for r,sp in zip(rows,WORLDS):
                if r[2] or (r[4]=='unsupported' and r[1]!='refuse'): print('   problem',sp['name'],r)

def reference_adaptive(problem, query, cfg=None):
    cfg=cfg or {}; delta=cfg.get('delta',1e-3); n=problem['n']; K=problem['max_junta']; eta=problem['noise_rate']; B=problem['budget']
    rng=np.random.default_rng(cfg.get('seed',12345))
    base=2*eta*(1-eta); z=norm.isf(delta/n)
    per0=max(4,int(B*cfg.get('init',0.4))//(2*n))
    est={}; cnt={}
    for i in range(n):
        X=rng.integers(0,2,size=(per0,n)); X2=X.copy(); X2[:,i]^=1
        est[i]=float(np.mean(query(X)!=query(X2))); cnt[i]=per0
    used=per0*n*2
    for _ in range(cfg.get('rounds',8)):
        rem=B-used
        if rem<2*n: break
        active=[i for i in range(n) if not((est[i]-z*math.sqrt(max(est[i]*(1-est[i]),1e-9)/cnt[i])>base) or
                                             (est[i]+z*math.sqrt(max(est[i]*(1-est[i]),1e-9)/cnt[i])<base))]
        if not active: break
        active.sort(key=lambda i: abs(est[i]-base))
        batch=max(4, rem//(2*len(active)))
        for i in active:
            if used+2*batch>B: batch=(B-used)//2
            if batch<1: break
            X=rng.integers(0,2,size=(batch,n)); X2=X.copy(); X2[:,i]^=1
            d=float(np.mean(query(X)!=query(X2)))
            est[i]=(est[i]*cnt[i]+d*batch)/(cnt[i]+batch); cnt[i]+=batch; used+=2*batch
    signif=[i for i in range(n) if est[i]-z*math.sqrt(max(est[i]*(1-est[i]),1e-9)/cnt[i])>base]
    if len(signif)>K: return {'verdict':'no_junta','confidence':0.9}
    return {'verdict':'junta','relevant':sorted(signif),'confidence':0.6}

def reference_frac(problem, query, cfg=None):
    c=dict(cfg or {}); return reference(problem, query, c)
