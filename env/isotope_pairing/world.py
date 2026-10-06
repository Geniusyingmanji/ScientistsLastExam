import numpy as np
from env.prototype_history import integer,observe
from .kernel import predict
from .eligibility import validate_spec

class World:
    name='isotope_pairing';version='isotope_pairing-0.1.0';axis_field='times'
    channels=('unlabeled','single_label','double_label');scales=(1.,1.,1.);noise_std=(.002,.002,.002)
    def __init__(self,seed):
        self._seed=integer(seed,'seed');r=np.random.default_rng(seed)
        self._rate=r.uniform(.3,1.5);self._scrambling=r.uniform(0,1)
    @staticmethod
    def example():return {'times':[0.,1.,3.,6.,12.],'source':[{'at':0.,'fractions':[.5,0.,0.,.5]}]}
    def describe(self):
        return dict(name=self.name,version=self.version,channels=list(self.channels),scales=list(self.scales),noise_std=list(self.noise_std),
          research_prompt='Investigate how source labeling recipes and their history determine product labeling. Test competing explanations and predict fresh recipes.',
          semantics=['Synthetic two-position labeling apparatus; dimensionless time. Each query resets the product pool to entirely unlabeled.',
          'Source fractions are in order 00,10,01,11, sum to one, and replace the recipe at the stated time. Recipe changes do not instantaneously replace product. Total source concentration and product pool size are constant.',
          'Readouts are product mass fractions with zero, one or two labels; positions within singly labeled product are not resolved.',
          'Independent Gaussian measurement errors of standard deviation .002 per channel, no clipping or process noise. Measured fractions need not sum exactly to one.'],
          schema={'times':'1..49 strictly increasing in [0,12]','source':'1..4 segments, first at=0; each {at, fractions:[00,10,01,11]}'},examples=[self.example()])
    def validate(self,s):
        return validate_spec(s)
    def cost(self,s):
        s=self.validate(s);return 8+3*len(s['times'])+len(s['source'])
    def run(self,s,*,noise_key=None):
        s=self.validate(s);return observe(self._seed,s,predict(self._rate,self._scrambling,s),self.channels,self.noise_std,noise_key)
    def panel(self,panel_seed,kind,count=8):
        r=np.random.default_rng(integer(panel_seed,'panel_seed'));count=integer(count,'count')
        if kind not in ('development','conditions','interventions') or not 1<=count<=64:raise ValueError('invalid panel')
        out=[]
        for _ in range(count):
            s={'times':np.linspace(0,12,25).tolist(),'source':[{'at':0.,'fractions':r.dirichlet(np.ones(4)).tolist()}]}
            if kind=='interventions':s['source'].append({'at':3.,'fractions':[1.,0.,0.,0.]})
            out.append(self.validate(s))
        return out


def baseline(records,spec):
    if not records:return [[1.,0.,0.] for _ in spec['times']]
    def f(s):return np.array([next(x['fractions'] for x in reversed(s['source']) if x['at']<=t) for t in np.linspace(0,12,25)])
    row=min(records,key=lambda x:np.sum((f(x['spec'])-f(spec))**2));y=np.asarray(row['observation']['values'])
    return np.array([np.interp(spec['times'],row['observation']['axis'],y[:,j]) for j in range(3)]).T.tolist()
