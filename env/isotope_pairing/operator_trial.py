"""Local operator-only integration smoke path, NOT a sandbox or registered runner.

A receipt holds raw observations and must stay private. Single-use, no retries.
A generated random namespace avoids replaying measurement keys between trials.
"""
import copy,hashlib,json,os,uuid
from .eligibility import validate_spec,contrast_eligibility,CHANNELS
from .evidence import record
from .noise_contract import contrast_uncertainty
from env.prototype_history import real

class Trial:
    def __init__(self,control,treatment,row,channel,interval,replicates=8,budget=4096):
        a=validate_spec(control);b=validate_spec(treatment)
        if not contrast_eligibility(a,b,row,channel)['eligible']:raise ValueError('contrast is not eligible')
        if not isinstance(interval,list) or len(interval)!=2:raise ValueError('interval requires two bounds')
        low,high=[real(v,-1,1,'effect bound') for v in interval]
        if low>high:raise ValueError('interval bounds reversed')
        uncertainty=contrast_uncertainty(replicates)
        if type(budget) is not int or budget<=0:raise ValueError('budget must be positive integer')
        units=replicates*sum(8+3*len(s['times'])+len(s['source']) for s in (a,b))
        if units>budget:raise ValueError('insufficient experiment budget')
        self._plan={'control':a,'treatment':b,'row':row,'channel':channel,'interval':[low,high],'replicates':replicates,'budget':budget,'reserved_units':units,'uncertainty':uncertainty}
        self._hash=hashlib.sha256(json.dumps(self._plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self._used=False;self._namespace=uuid.uuid4().hex;self.attempted_calls=0;self.charged_units=0
    @property
    def plan(self):return copy.deepcopy(self._plan)
    def run(self,world,journal_path=None):
        if journal_path is None:
            return self._run(world,lambda event: None)
        # Exclusive creation prevents overwriting an earlier attempt or symlink.
        fd=os.open(journal_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:
            def emit(event):
                stream.write(json.dumps(event,allow_nan=False,sort_keys=True)+'\n')
                stream.flush();os.fsync(stream.fileno())
            emit({'event':'frozen','plan_sha256':self._hash,'plan':self.plan})
            try:
                result=self._run(world,emit)
                emit({'event':'completed','result':result})
                return result
            except Exception as exc:
                emit({'event':'failed','exception_type':type(exc).__name__,
                      'attempted_calls':self.attempted_calls,'charged_units':self.charged_units})
                raise

    def _run(self,world,emit):
        if self._used:raise RuntimeError('trial is single-use, including after failure')
        if world.name!='isotope_pairing' or world.version!='isotope_pairing-0.1.0':raise ValueError('unsupported world version')
        for arm in ('control','treatment'):
            s=self._plan[arm]
            if world.cost(s)!=8+3*len(s['times'])+len(s['source']):raise ValueError('cost contract mismatch')
        self._used=True;p=self._plan;records=[];values={}
        for arm in ('control','treatment'):
            values[arm]=[]
            for i in range(p['replicates']):
                s=copy.deepcopy(p[arm]);self.attempted_calls+=1;self.charged_units+=world.cost(s)
                key=self._namespace+':'+arm+':'+str(i)
                emit({'event':'attempt','arm':arm,'replicate':i,'noise_key':key,'attempted_calls':self.attempted_calls,'charged_units':self.charged_units})
                obs=world.run(s,noise_key=key)
                receipt=record(s,obs);records.append(receipt)
                emit({'event':'observation','arm':arm,'replicate':i,'record':receipt})
                values[arm].append(obs['values'][p['row']][CHANNELS.index(p['channel'])])
        delta=sum(values['treatment'])/p['replicates']-sum(values['control'])/p['replicates']
        h=p['uncertainty']['half_width'];lo,hi=p['interval']
        verdict='inconclusive'
        if delta+h<lo or delta-h>hi:verdict='incompatible'
        elif lo<=delta-h and delta+h<=hi:verdict='compatible_at_declared_precision'
        return {'schema':'isotope-operator-trial-1','plan_sha256':self._hash,'plan':self.plan,'attempted_calls':self.attempted_calls,'charged_units':self.charged_units,'observed_mean_difference':delta,'measurement_interval':[delta-h,delta+h],'verdict':verdict,'mechanism_certified':False,'records':records}
