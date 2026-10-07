import pytest
from env.runner import DEFAULT_LIMITS
from env.tests.test_pilot_protocol import FakeClient, FakeAnalysis
from env.isotope_pairing.model_driver import run_model_episode
from env.isotope_pairing.campaign_scoring import PROTOCOL


def test_scripted_episode_without_api(tmp_path):
    instance=dict(episode_id='isotope-plumbing', environment='isotope_pairing',
                  world_seed=0, panel_seed=1, confirmation_key='development-only',
                  scoring_protocol=PROTOCOL)
    client=FakeClient([{'note':'Engineering fixture', 'submit': {'predictor_code': 'def predict(spec): return []',
                       'claims': [], 'explanation': 'Engineering fixture only.'}}])
    limits=dict(DEFAULT_LIMITS, rounds=1, panel_count=1, wall_seconds=60,
                verification_reserve_seconds=0)
    report=run_model_episode(instance,limits,tmp_path,client,
        analysis_factory=FakeAnalysis,
        predict_fn=lambda path,spec,seconds: [[1.,0.,0.] for t in spec['times']])
    assert report['status']=='completed',report.get('stop_reason')
    assert report['subscores']['claims']==0
    assert all(row['valid'] for rows in report['panels'].values() for row in rows)
    assert len(client.prompts)==1


def test_requires_explicit_protocol(tmp_path):
    with pytest.raises(ValueError,match='protocol'):
        run_model_episode({},DEFAULT_LIMITS,tmp_path,None)


# Engineering fixture only: real isolation, no paid model calls.
def test_linux_isolated_episode(tmp_path):
    import shutil
    import sys
    if sys.platform != 'linux' or shutil.which('bwrap') is None:
        pytest.skip('Requires Linux and bubblewrap; skip does not satisfy admission')
    from env.isotope_pairing.world import World
    from env.scoring import canonical_hash
    from env.analysis_api import PROTOCOL as ANALYSIS_PROTOCOL
    from env.isotope_pairing.campaign_scoring import generate_panel
    world=World(0)
    spec={'times':[0.,1.,3.], 'source':[{'at':0.,'fractions':[.5,0.,0.,.5]}]}
    instance=dict(episode_id='isotope-native-smoke',environment='isotope_pairing',
        world_seed=0,panel_seed=1,confirmation_key='development-only',
        scoring_protocol=PROTOCOL,analysis_protocol=ANALYSIS_PROTOCOL)
    instance['panel_hashes']={kind:canonical_hash(generate_panel(world,1,kind,1))
                            for kind in ('conditions','interventions')}
    client=FakeClient([
        {'note':'Engineering observation','experiments':[spec]},
        {'note':'Read public observations in isolation','analyze':{'code':
         "result = {'rows': len(records[0]['observation']['values'])}"}},
        {'note':'Freeze engineering fixture','submit':{
         'predictor_code':"import numpy as np\ndef predict(spec):\n    return np.asarray([[1.,0.,0.] for t in spec['times']])\n",
         'claims':[], 'explanation':'Engineering fixture, not a scientific reference.'}}])
    limits=dict(DEFAULT_LIMITS,rounds=3,exploration_rounds=2,panel_count=1,
        experiment_units=30000,analysis_active_seconds=60,wall_seconds=180,
        verification_reserve_seconds=30)
    report=run_model_episode(instance,limits,tmp_path,client)
    assert report['status']=='completed',report.get('stop_reason')
    assert report['history'][1]['analysis']['ok']
    assert report['history'][1]['analysis']['result']['rows']==3
    assert all(row['valid'] for rows in report['panels'].values() for row in rows)
    assert len(client.prompts)==3
