import shutil
import sys
import numpy as np
import pytest
from env.runner import DEFAULT_LIMITS
from env.tests.test_pilot_protocol import FakeClient
from env.retention_capacity import order_scoring as s, order_driver
from env.retention_capacity.world import World
from env.retention_capacity.order_task import validate_pair, score
from env.scoring import canonical_hash


def test_panel_pairing_and_pooling():
    w = World(0)
    left, right = [s.generate_panel(w, 21, k, 3) for k in ('conditions', 'interventions')]
    reports = {'conditions': [], 'interventions': []}
    predictions, targets = [], []
    for i, (a, b) in enumerate(zip(left, right)):
        validate_pair(w, {'left': a, 'right': b})
        target = [w.run(x)['values'][0][0] for x in (a,b)]
        pred = [target[0] + .01*i, target[1] - .02*i]
        predictions.append(pred); targets.append(target)
        for j, (k,x) in enumerate(zip(reports, (a,b))):
            reports[k].append({'index': i, 'prediction_values': [[pred[j]]], 'clean_truth': w.run(x)})
    result = s.aggregate_episode(reports, {})
    assert result['score'] == score(predictions, targets)['score']
    assert set(result['subscores']) == {'absolute','order'}
    assert s.verify_claims(w, [], 'unused')['claims'] == []
    with pytest.raises(ValueError): s.validate_submission({'claims':[{}]},w,[])
    assert 'every omitted claim slot' not in s.CANDIDATE_SYSTEM


def test_order_real_linux_pipeline(tmp_path):
    if sys.platform != 'linux' or not shutil.which('bwrap'):
        pytest.skip('Linux+bwrap required')
    from env.analysis_api import PROTOCOL
    w = World(0)
    inst = dict(episode_id='order-engineering-smoke',environment=w.name,world_seed=0,panel_seed=21,
                confirmation_key='engineering-only',scoring_protocol=s.PROTOCOL,analysis_protocol=PROTOCOL)
    inst['panel_hashes'] = {k: canonical_hash(s.generate_panel(w,21,k,2)) for k in ('conditions','interventions')}
    client = FakeClient([
        {'note':'fixture', 'experiments':[w.example()]},
        {'note':'fixture', 'analyze':{'code':"result={'rows':len(records[0]['observation']['values'])}"}},
        {'note':'fixture', 'submit':{'predictor_code':"import numpy as np\ndef predict(spec): return np.zeros((len(spec['times']),1))",'claims':[],'explanation':'Engineering fixture, no science claim.'}}])
    limits = dict(DEFAULT_LIMITS,rounds=3,exploration_rounds=2,panel_count=2,wall_seconds=180,verification_reserve_seconds=30)
    report = order_driver.run_model_episode(inst,limits,tmp_path,client)
    assert report['status']=='completed',report['stop_reason']
    assert report['history'][1]['analysis']['ok']
    assert set(report['subscores']) == {'absolute','order'}
    assert report['score'] == s.aggregate_episode(report['panels'],{})['score']
