"""Unregistered prototype implementing the trusted operator World contract."""
import numpy as np
from env.prototype_history import real, integer, times, schedule, observe, baseline
from .kernel import predict


class World:
    name='adaptive_signaling';version='adaptive_signaling-0.1.0';axis_field='times'
    channels=('reporter_deviation',);scales=(2.,);noise_std=(.002,)
    operator_strata=('feedforward','feedback')

    def __init__(self,seed):
        self._seed=integer(seed,'seed');rng=np.random.default_rng(seed)
        self._family=self.operator_strata[seed%2]
        self._parameters=np.array([rng.uniform(.25,.8),rng.uniform(.8,1.8),rng.uniform(.7,1.5)])

    def operator_stratum(self): return self._family

    def describe(self):
        return {'name':self.name,'version':self.version,'channels':list(self.channels),'scales':list(self.scales),'noise_std':list(self.noise_std),
                'research_prompt':'Study a freshly prepared signal-responsive instrument. Build accounts of its response to stimulus histories and test their limits under auxiliary-state manipulation.',
                'units':'Dimensionless stimulus and reporter deviation; time in instrument units. Reporter deviation may be negative.',
                'semantics':['Every experiment starts with baseline internal states and a zero reporter. Stimulus is piecewise constant; a segment applies at its at time.',
                'At reset_at an auxiliary internal state is multiplied by retained_fraction. The reporter is not directly reset. Reset does not change future stimulus. Segments and reset occur before a same-time readout.',
                'The device is fixed across experiments. Additive independent Gaussian readout noise has standard deviation 0.002, without clipping; no process noise.',
                'Controls after the last requested time have no effect on earlier readings. Finite input/output observations need not uniquely identify an internal mechanism.'],
                'schema':{'times':'1..49 strictly increasing values in [0,12]','stimulus':'1..4 segments {at:[0,12],level:[0,2]}, first at=0, strictly increasing','reset_at':'[0,12]','retained_fraction':'[0,1]; 1 is no intervention'},
                'cost':'8 + 2*number of times + number of stimulus segments','examples':[self.example()]}

    @staticmethod
    def example(): return {'times':[0.,.5,1.,2.,4.,8.,12.],'stimulus':[{'at':0.,'level':1.}],'reset_at':3.,'retained_fraction':1.}

    def validate(self,spec):
        if not isinstance(spec,dict) or set(spec)!={'times','stimulus','reset_at','retained_fraction'}: raise ValueError('expected times, stimulus, reset_at, retained_fraction')
        return {'times':times(spec['times']),'stimulus':schedule(spec['stimulus'],'level',2),'reset_at':real(spec['reset_at'],0,12,'reset_at'),'retained_fraction':real(spec['retained_fraction'],0,1,'retained_fraction')}

    def cost(self,spec):
        s=self.validate(spec);return 8+2*len(s['times'])+len(s['stimulus'])

    def run(self,spec,*,noise_key=None):
        s=self.validate(spec);return observe(self._seed,s,predict(self._family,self._parameters,s),self.channels,self.noise_std,noise_key)

    def panel(self,panel_seed,kind,count=8):
        seed=integer(panel_seed,'panel_seed');count=integer(count,'count')
        if not 1<=count<=64 or kind not in ('development','conditions','interventions'): raise ValueError('invalid panel kind/count')
        rng=np.random.default_rng(seed);out=[]
        for _ in range(count):
            s=self.example();s['times']=np.linspace(.2,12,25).tolist();s['stimulus']=[{'at':0.,'level':float(rng.uniform(.3,1.8))},{'at':float(rng.uniform(3,6)),'level':float(rng.uniform(.2,1.8))}];s['reset_at']=float(rng.uniform(2,8));s['retained_fraction']=float(rng.uniform(0,.7)) if kind=='interventions' else 1.;out.append(self.validate(s))
        return out
