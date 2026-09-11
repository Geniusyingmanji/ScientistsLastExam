import numpy as np, math
from scipy.stats import norm

N=28; K=12; ETA=0.10; BUDGET=20000

def make_world(spec):
    rng=np.random.default_rng(spec['seed']); n=N
    idx=rng.permutation(n)
    world={'n':n,'kind':'supported','fault':''}
    fault=spec.get('fault')
    if fault=='bigparity':
        vars_=list(idx[:spec.get('size',K+4)])
        def f(X):
            X=np.atleast_2d(X); return np.bitwise_xor.reduce(X[:,vars_],axis=1).astype(int)
        world['R']=set(vars_); world['kind']='unsupported'; world['fault']=fault
    elif fault=='addmany':
        vars_=list(idx[:spec.get('size',K+3)]); w=np.ones(len(vars_))
        def f(X):
            X=np.atleast_2d(X); s=(X[:,vars_]*2-1)@w; return (s>0).astype(int)
        world['R']=set(vars_); world['kind']='unsupported'; world['fault']=fault
    else:
        sel=int(idx[0]); add=list(idx[1:5]); wts=np.array(spec.get('wts',[3.0,2.0,1.2,0.7]))
        par=list(idx[5:8]); gc=list(idx[8:10]); gp=list(idx[10:12])
        R=set([sel])|set(add)|set(par)|set(gc)|set(gp)
        def f(X):
            X=np.atleast_2d(X); g=((X[:,add]*2-1)@wts>0).astype(int)
            p=np.bitwise_xor.reduce(X[:,par],axis=1)
            gate=(X[:,gc].sum(1)==len(gc)); gpb=np.bitwise_xor.reduce(X[:,gp],axis=1)&gate.astype(int)
            return np.where(X[:,sel]==0,g,p^gpb).astype(int)
        world['R']=R
    world['f']=f
    return world

def influence(world,i,M=300000,seed=1):
    rng=np.random.default_rng(seed); X=rng.integers(0,2,size=(M,world['n'])); Y=world['f'](X); X2=X.copy(); X2[:,i]^=1
    return float(np.mean(world['f'](X2)!=Y))

class Bench:
    def __init__(self,world,run_seed):
        self.world=world; self.budget=BUDGET; self.used=0; self.violated=False
        self.rng=np.random.default_rng(run_seed)
    def oracle(self):
        st=self; w=self.world
        def query(X):
            X=np.asarray(X)
            if X.ndim!=2 or X.shape[1]!=w['n']: raise ValueError('X must be k x n binary')
            if not np.isin(X,[0,1]).all(): raise ValueError('binary only')
            k=X.shape[0]
            if st.used+k>st.budget: st.violated=True; raise RuntimeError('budget exhausted')
            st.used+=k
            y=w['f'](X); flip=st.rng.random(k)<ETA
            return (y^flip.astype(int)).astype(int)
        return query
    def public(self):
        return {'n':w_n(self),'max_junta':K,'noise_rate':ETA,'budget':BUDGET}
def w_n(b): return b.world['n']
