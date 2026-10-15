"""Public experiment validation and trusted execution; prototype, not registered."""
import copy,hashlib,json,math
import numpy as np
from .kernel import Kernel,POOLS

# Fixed apparatus IDs are not semantic chemical identities in candidate material.
CHANNELS=('substrate','A','B','C','m1','m2','m3','m4','residue')

def number(x,lo,hi):
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not lo<=x<=hi:
        raise ValueError('value outside public range')
    return float(x)

def validate(spec):
    if not isinstance(spec,dict) or set(spec)-{'initial','times','temperature','events'} or not {'initial','times'}<=set(spec):
        raise ValueError('expected initial and times; optional temperature and events')
    initial=spec['initial']
    if not isinstance(initial,dict) or set(initial)-set(CHANNELS):raise ValueError('unknown initial channel')
    initial={k:number(initial.get(k,0),0,5 if k=='substrate' else 1 if k in ('A','B','C') else 2) for k in CHANNELS}
    times=spec['times']
    if not isinstance(times,list) or not 1<=len(times)<=25:raise ValueError('1..25 times required')
    times=[number(t,0,48) for t in times]
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('times must increase')
    temp=number(spec.get('temperature',30),20,40)
    events=spec.get('events',[])
    if not isinstance(events,list) or len(events)>8:raise ValueError('at most8 events')
    previous=0;out=[];added=0
    for e in events:
        if not isinstance(e,dict) or 'time' not in e:raise ValueError('invalid event')
        at=number(e['time'],previous,times[-1]);previous=at
        if set(e)=={'time','temperature'}:e={'time':at,'temperature':number(e['temperature'],20,40)}
        elif set(e) in ({'time','channel','add'},{'time','channel','remove'}):
            if e['channel'] not in CHANNELS:raise ValueError('unknown channel')
            op='add' if 'add' in e else 'remove';v=number(e[op],0,2 if op=='add' else 1)
            if op=='add':added+=v
            e={'time':at,'channel':e['channel'],op:v}
        else:raise ValueError('invalid event keys')
        out.append(e)
    if added>8:raise ValueError('total addition exceeds8')
    return dict(initial=initial,times=times,temperature=temp,events=out)

class World:
    def __init__(self,seed,family):self.seed=seed;self.kernel=Kernel(seed,family);self.calls=0
    def run(self,spec,*,clean=False,method='DOP853'):
        s=validate(spec);z=np.array([s['initial'][k] for k in CHANNELS]+[0.]);temp=s['temperature'];time=0.;i=0;rows=[]
        for t in s['times']:
            while i<len(s['events']) and s['events'][i]['time']<=t:
                e=s['events'][i];z=self.kernel.advance(z,e['time']-time,temp,method);time=e['time']
                if 'temperature' in e:temp=e['temperature']
                else:
                    j=CHANNELS.index(e['channel'])
                    if 'add' in e:z[j]+=e['add']
                    else:z[j]*=1-e['remove']
                i+=1
            z=self.kernel.advance(z,t-time,temp,method);time=t;rows.append(z[:9].tolist())
        values=np.array(rows)
        if not clean:
            key=hashlib.sha256((str(self.seed)+':'+str(self.calls)).encode()).digest()
            values=np.maximum(0,values+np.random.default_rng(int.from_bytes(key[:8],'big')).normal(0,.002,values.shape))
            self.calls+=1
        return {'times':s['times'],'channels':list(CHANNELS),'values':values.tolist()}
