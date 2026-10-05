"""Unregistered transport prototype; each request prepares a new unit pulse."""
import numpy as np
from env.prototype_history import integer, times, schedule, observe, baseline
from .kernel import predict


class World:
    name='retention_transport';version='retention_transport-0.1.0';axis_field='times'
    channels=('recovered_fraction',);scales=(1.,);noise_std=(.002,)
    operator_strata=('exchange','parallel')

    def __init__(self,seed):
        self._seed=integer(seed,'seed');rng=np.random.default_rng(seed);self._family=self.operator_strata[seed%2]
        self._parameters=np.array([rng.uniform(.7,1.3),rng.uniform(.3,.9),rng.uniform(.15,.5)]) if self._family=='exchange' else np.array([rng.uniform(1.2,2.),rng.uniform(.12,.4),rng.uniform(.35,.75)])

    def operator_stratum(self): return self._family

    def describe(self):
        return {'name':self.name,'version':self.version,'channels':list(self.channels),'scales':list(self.scales),'noise_std':list(self.noise_std),
                'research_prompt':'Study passage of a tracer through a sealed transport cartridge. Explain recovery curves and test transfer of your account to altered flow histories.',
                'units':'Time and nonnegative flow in instrument units; recovered fraction normalized to the injected unit tracer mass.',
                'semantics':['Each call prepares a fresh cartridge in the same fixed instance and injects unit tracer mass at time zero. No tracer is initially recovered. There is no ongoing injection.',
                'Flow is piecewise constant and nonnegative. A zero rate pauses imposed flow. A segment applies at its at time before same-time observation. Only total recovered tracer is measured; interior compartments are inaccessible.',
                'Readout errors are independent additive Gaussian with standard deviation 0.002, without clipping. There is no process noise. Clean mass recovery is between zero and one; noisy measurements may fall outside this range.',
                'No chemical destruction occurs. A finite recovery trace does not uniquely determine internal geometry or asymptotic recovery. Controls after the last reading cannot affect that reading.'],
                'schema':{'times':'1..49 strictly increasing values in [0,12]','flow':'1..4 segments {at:[0,12],rate:[0,3]}, first at=0, strictly increasing'},
                'cost':'8 + 2*number of times + number of flow segments','examples':[self.example()]}

    @staticmethod
    def example(): return {'times':[0.,.5,1.,2.,4.,8.,12.],'flow':[{'at':0.,'rate':1.}]}

    def validate(self,spec):
        if not isinstance(spec,dict) or set(spec)!={'times','flow'}: raise ValueError('expected exactly times and flow')
        return {'times':times(spec['times']),'flow':schedule(spec['flow'],'rate',3)}

    def cost(self,spec):
        s=self.validate(spec);return 8+2*len(s['times'])+len(s['flow'])

    def run(self,spec,*,noise_key=None):
        s=self.validate(spec);return observe(self._seed,s,predict(self._family,self._parameters,s),self.channels,self.noise_std,noise_key)

    def panel(self,panel_seed,kind,count=8):
        seed=integer(panel_seed,'panel_seed');count=integer(count,'count')
        if not 1<=count<=64 or kind not in ('development','conditions','interventions'): raise ValueError('invalid panel kind/count')
        rng=np.random.default_rng(seed);out=[]
        for _ in range(count):
            s=self.example();s['times']=np.linspace(.2,12,25).tolist();s['flow']=[{'at':0.,'rate':float(rng.uniform(.4,2.5))}]
            if kind=='interventions': s['flow'] += [{'at':float(rng.uniform(1,3)),'rate':0.},{'at':float(rng.uniform(4,7)),'rate':float(rng.uniform(.4,2.5))}]
            out.append(self.validate(s))
        return out
