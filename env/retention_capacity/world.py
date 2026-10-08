"""Fresh preparations; load is public control, interior storage is unobserved."""
import numpy as np
from env.prototype_history import integer,real,times,schedule,observe
from .kernel import predict


class World:
    name='retention_capacity';version='retention_capacity-0.1.0';axis_field='times'
    channels=('recovered_fraction',);scales=(1.,);noise_std=(.002,)
    operator_strata=('storage_capacity','outlet_capacity')
    def __init__(self,seed):
        self._seed=integer(seed,'seed');rng=np.random.default_rng(seed)
        self._family=self.operator_strata[seed%2]
        self._parameters=np.array([rng.uniform(.7,1.3),rng.uniform(.3,.9),rng.uniform(.15,.5),rng.uniform(.4,1.4)])
    def describe(self):
        return {'name':self.name,'version':self.version,'channels':list(self.channels),'scales':list(self.scales),'noise_std':list(self.noise_std),
                'research_prompt':'Study how injected tracer amount and flow history jointly affect recovery. Build transferable predictions and test competing explanations.',
                'semantics':['Each experiment prepares a fresh identical cartridge and injects load units at time zero; no later injection. Only cumulative recovered mass divided by injected load is observed.',
                             'Time and flow use instrument units. Piecewise-constant nonnegative flow; zero stops imposed flow. A segment applies at its time, while internal states remain continuous.',
                             'No tracer destruction. Independent additive Gaussian readout error SD0.002, no clipping and no process noise. Interior quantities and mechanism are not observable.'],
                'schema':{'load':'finite [0.1,3]','times':'1..49 increasing readings [0,12]','flow':'1..4 segments {at,rate}, start0, increasing at in[0,12], rate[0,3]'},
                'cost':'8+2*number of times+number of flow segments','examples':[self.example()]}
    @staticmethod
    def example():return {'load':1.,'times':[0.,.5,1.,2.,4.,8.,12.],'flow':[{'at':0.,'rate':1.}]}
    def validate(self,spec):
        if not isinstance(spec,dict) or set(spec)!={'load','times','flow'}:raise ValueError('expected exactly load,times,flow')
        return {'load':real(spec['load'],.1,3,'load'),'times':times(spec['times']),'flow':schedule(spec['flow'],'rate',3)}
    def cost(self,spec):
        s=self.validate(spec);return 8+2*len(s['times'])+len(s['flow'])
    def run(self,spec,*,noise_key=None):
        s=self.validate(spec);return observe(self._seed,s,predict(self._family,self._parameters,s),self.channels,self.noise_std,noise_key)
    def panel(self,panel_seed,kind,count=8):
        seed=integer(panel_seed,'panel_seed');count=integer(count,'count')
        if kind not in ('development','conditions','interventions') or not 1<=count<=64:raise ValueError('invalid panel kind/count')
        rng=np.random.default_rng(seed);out=[]
        for _ in range(count):
            s=self.example();s['load']=float(rng.uniform(.1,3));s['times']=np.linspace(.2,12,25).tolist();s['flow'][0]['rate']=float(rng.uniform(.3,2.5))
            if kind=='interventions':s['flow'] += [{'at':float(rng.uniform(1,3)),'rate':0.},{'at':float(rng.uniform(4,6)),'rate':float(rng.uniform(.3,2.5))}]
            out.append(self.validate(s))
        return out


def baseline(records,spec):
    """Nearest public load and sampled flow history, then time interpolation."""
    if not records:return [[0.] for _ in spec['times']]
    def feature(s):return np.array([s['load']]+[next(r['rate'] for r in reversed(s['flow']) if r['at']<=t) for t in np.linspace(0,12,25)])
    target=feature(spec);r=min(records,key=lambda r:float(np.sum((feature(r['spec'])-target)**2)))
    return [[float(np.interp(t,r['observation']['axis'],np.asarray(r['observation']['values'])[:,0]))] for t in spec['times']]
