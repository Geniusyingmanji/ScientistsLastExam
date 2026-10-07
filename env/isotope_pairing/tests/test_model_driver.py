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
