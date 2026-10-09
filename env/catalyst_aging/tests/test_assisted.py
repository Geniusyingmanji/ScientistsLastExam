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
