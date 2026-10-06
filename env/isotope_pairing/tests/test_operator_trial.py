from copy import deepcopy
import pytest
from env.isotope_pairing.world import World
from env.isotope_pairing.operator_trial import Trial

def specs():
    a=World.example();b=deepcopy(a);b['source'][0]['fractions']=[0.,.5,.5,0.]
    return a,b

def test_freeze_observe_accounting_and_no_replay():
    a,b=specs();t=Trial(a,b,3,'double_label',[-1.,1.],replicates=2)
    a['source'][0]['fractions'][0]=0
    p=t.plan;p['interval'][0]=0
    r=t.run(World(100))
    assert r['plan']['interval']==[-1.,1.]
    assert r['attempted_calls']==4 and r['charged_units']==96
    assert len(r['records'])==4 and r['mechanism_certified'] is False
    with pytest.raises(RuntimeError):t.run(World(100))

def test_invalid_or_overbudget_makes_no_observations():
    a,b=specs()
    with pytest.raises(ValueError):Trial(a,b,0,'double_label',[-1.,1.])
    with pytest.raises(ValueError):Trial(a,b,3,'double_label',[-1.,1.],budget=1)

def test_failed_call_is_charged_and_cannot_retry():
    class Broken(World):
        def run(self,*args,**kwargs):raise RuntimeError('test failure')
    a,b=specs();t=Trial(a,b,3,'double_label',[-1.,1.],replicates=2)
    with pytest.raises(RuntimeError):t.run(Broken(100))
    assert t.attempted_calls==1 and t.charged_units==24
    with pytest.raises(RuntimeError):t.run(World(100))

def test_private_journal_retains_partial_failure(tmp_path):
    import json,stat
    class SecondFails(World):
        calls=0
        def run(self,*args,**kwargs):
            self.calls+=1
            if self.calls==2:raise RuntimeError('sensitive diagnostic not copied into journal')
            return super().run(*args,**kwargs)
    a,b=specs();t=Trial(a,b,3,'double_label',[-1.,1.],replicates=2);p=tmp_path/'trial.jsonl'
    with pytest.raises(RuntimeError):t.run(SecondFails(100),p)
    events=[json.loads(x) for x in p.read_text().splitlines()]
    assert [x['event'] for x in events]==['frozen','attempt','observation','attempt','failed']
    assert events[-1]['charged_units']==48 and events[-1]['attempted_calls']==2
    assert 'sensitive diagnostic' not in p.read_text()
    assert stat.S_IMODE(p.stat().st_mode)==0o600
    saved=p.read_bytes()
    with pytest.raises(FileExistsError):Trial(a,b,3,'double_label',[-1.,1.]).run(World(100),p)
    assert p.read_bytes()==saved
