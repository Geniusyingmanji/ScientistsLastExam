"""Bounded operator development confirmation; no candidate/model calls."""
import hashlib,json,math,os,platform,time
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import linprog
from scipy.stats import norm
from .kernel import travel_times


def run(directory):
    root=Path(directory);root.mkdir(mode=0o700)
    def save(name,value):
        data=json.dumps(value,sort_keys=True,indent=2,allow_nan=False).encode()
        with (root/name).open('xb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        return hashlib.sha256(data).hexdigest()
    def event(name,**values):
        with (root/'events.jsonl').open('a') as f:
            f.write(json.dumps(dict(event=name,utc=time.time(),**values))+'\n');f.flush();os.fsync(f.fileno())
    xs=[0.,.1,.25,.5,1.,2.,4.]
    fixtures=[{'name':'layered','h':[.5,1.5],'v':[1.,3.],'noise_seed':22007},
              {'name':'homogeneous_control','h':[math.sqrt(5)],'v':[math.sqrt(5)],'noise_seed':22008}]
    plan={'scope':'Exposed development confirmation; new noise, not new structures or hidden instances.',
          'fixtures':fixtures,'offsets':xs,'noise_sd':.001,'family_alpha':.05,
          'bands':'Bonferroni over all14 observations','parameter_bounds':[[.01,100],[.01,100]],
          'kernel_calls_cap':2,'lp_calls_cap':2,'lp_maxiter':1000,'no_retries':True,
          'decision':'LP status2 means numerical family inconsistency; status0 feasible; other status unresolved.'}
    sources={}
    for path in [Path(__file__),Path(__file__).with_name('kernel.py')]:
        data=path.read_bytes();sources[path.name]=hashlib.sha256(data).hexdigest()
        (root/path.name).write_bytes(data)
    plan_hash=save('plan.json',plan)
    save('runtime.json',{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'sources':sources})
    event('frozen',plan_sha256=plan_hash)
    eps=float(norm.ppf(1-.05/(2*14))*.001);A=np.column_stack([np.ones(7),np.array(xs)**2]);results=[]
    for fixture in fixtures:
        name=fixture['name'];event('kernel_attempt',fixture=name)
        clean=travel_times(fixture['h'],fixture['v'],xs)
        y=np.array(clean['times'])+np.random.default_rng(fixture['noise_seed']).normal(0,.001,7)
        save(name+'-observations.json',{'values':y.tolist(),'clean':clean})
        b=np.concatenate([(y+eps)**2,-np.maximum(0,y-eps)**2]);aa=np.vstack([A,-A])
        save(name+'-lp-input.json',{'c':[0.,0.],'A_ub':aa.tolist(),'b_ub':b.tolist(),'bounds':plan['parameter_bounds'],'method':'highs','maxiter':1000,'band_half_width':eps})
        event('lp_attempt',fixture=name)
        result=linprog([0.,0.],A_ub=aa,b_ub=b,bounds=plan['parameter_bounds'],method='highs',options={'maxiter':1000})
        row={'fixture':name,'status':int(result.status),'message':result.message,'iterations':int(result.nit),'parameters':None if result.x is None else result.x.tolist()}
        if result.success:row['max_time_band_violation']=float(np.max(np.abs(np.sqrt(A@result.x)-y)-eps))
        save(name+'-lp-result.json',row);results.append(row);event('fixture_completed',fixture=name,status=row['status'])
        if result.status not in (0,2):break
    save('summary.json',{'results':results,'model_calls':0,'scope':plan['scope']});event('completed')
    return [{'fixture':r['fixture'],'status':r['status']} for r in results]


if __name__=='__main__':
    import sys
    print(json.dumps(run(sys.argv[1])))
