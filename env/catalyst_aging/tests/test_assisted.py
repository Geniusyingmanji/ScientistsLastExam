from types import SimpleNamespace
import pytest
from env.catalyst_aging.assisted import Assistance
from env.catalyst_aging.export_check import digest
from env.catalyst_aging.world import World
from env.analysis_api import ModelSnapshots


def test_initial_debit_and_validated_snapshot(tmp_path):
    w=World(0);spec={'events':[{'kind':'blank'}],'event_indices':[1]}
    records=[{'id':'obs-%04d'%(i+1),'spec':spec,'cost':1,'observation':w.run(spec)} for i in range(6)]
    support=Assistance(records)
    copied=support.initialize(w,{'initial_records_sha256':digest(records)},{'experiments':48,'experiment_units':800})
    assert len(copied)==6 and sum(r['cost'] for r in copied)==6
    store=ModelSnapshots(tmp_path/'models');receipt=store.save_model('fit','v1',{},'def predict(spec): return [[0.]]')
    ref={k:receipt[k] for k in ('name','version','sha256')}
    specs=support.public_data()['validation_specs']
    predictions=[[[0.]]*len(s['event_indices']) for s in specs]
    action={'model_snapshot':ref,'analysis_predictions':predictions}
    predict=lambda path,spec,seconds:[[0.]]*len(spec['event_indices'])
    analysis=SimpleNamespace(remaining=180.)
    result=support.validate_export(action,store,analysis,predict,tmp_path)
    assert result['passed'] and analysis.remaining<180
    submission={'model_snapshot':ref,'claims':[],'explanation':'fixture'}
    source=store.resolve_submission(submission)[0]['predictor_code']
    assert support.require_submission(submission,source)
    assert result['visible_residuals_by_kind']['blank']['count']==6
    assert result['structural_terminal_differences']==[0.,0.]
    action['analysis_predictions']=[[[1.]]*len(s['event_indices']) for s in specs]
    assert not support.validate_export(action,store,analysis,predict,tmp_path)['passed']
    with pytest.raises(ValueError):support.require_submission(submission,source)
    with pytest.raises(ValueError):support.validate_export(action,store,analysis,predict,tmp_path)


def test_assisted_linux_closure(tmp_path):
    import sys, shutil, json
    if sys.platform!='linux' or not shutil.which('bwrap'):
        pytest.skip('Linux+bwrap required')
    from env.runner import DEFAULT_LIMITS
    from env.analysis_api import PROTOCOL
    from env.catalyst_aging import matched_driver, matched_scoring as scoring
    from env.tests.test_pilot_protocol import FakeClient
    w=World(0)
    spec={'events':[{'kind':'blank'}],'event_indices':[1]}
    records=[{'id':'obs-%04d'%(i+1),'spec':spec,'cost':1,'observation':w.run(spec)} for i in range(6)]
    inst=dict(episode_id='assisted-engineering',environment=w.name,world_seed=0,panel_seed=21,
              confirmation_key='engineering',scoring_protocol=scoring.PROTOCOL,analysis_protocol=PROTOCOL,
              assisted_protocol='catalyst-assisted-export-0.1',initial_records=records,initial_records_sha256=digest(records))
    code="def predict(spec):\n return [[1.5 if spec['events'][i-1]['kind']=='standard' else 0.] for i in spec['event_indices']]"
    class Client(FakeClient):
        def __init__(self):super().__init__([])
        def complete(self,prompt,system=None):
            p=json.loads(prompt);self.prompts.append(p)
            assert 'additionally permits the validate_export' in system
            if len(self.prompts)==1:
                action={'analyze':{'code':"result=save_model('fixture','v1',{},"+repr(code)+")"}}
            elif len(self.prompts)==2:
                receipt=p['recent_results'][-1]['analysis']['result']
                self.ref={k:receipt[k] for k in ('name','version','sha256')}
                specs=p['assisted_public_data']['validation_specs']
                predictions=[[[1.5 if s['events'][i-1]['kind']=='standard' else 0.] for i in s['event_indices']] for s in specs]
                action={'validate_export':{'model_snapshot':self.ref,'analysis_predictions':predictions}}
            else:action={'submit':{'model_snapshot':self.ref,'claims':[],'explanation':'engineering'}}
            return json.dumps(dict(note='engineering',**action))
    limits=dict(DEFAULT_LIMITS,rounds=3,exploration_rounds=2,panel_count=1,wall_seconds=240,verification_reserve_seconds=30)
    report=matched_driver.run_assisted_episode(inst,limits,tmp_path,Client())
    assert report['status']=='completed',report['stop_reason']
    assert report['history'][1]['export_validation']['passed']
    assert len(report['records'])==6
