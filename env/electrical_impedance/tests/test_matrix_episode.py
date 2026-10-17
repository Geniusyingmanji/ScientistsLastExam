import pytest
from env.electrical_impedance.matrix_episode import MatrixEpisode
from env.electrical_impedance.protocol import example


def test_noisy_prospective_and_budget(tmp_path):
    e=MatrixEpisode(17201,tmp_path,budget=29,max_attempts=3);s=example()
    e.call('register_prediction',experiment_id='x',spec=s,prediction=[0.]*16,model_sha256='a'*64)
    r=e.call('experiment',experiment_id='x',spec=s)
    assert len(r['values'])==8 and r['remaining_units']==1
    assert 'error' in e.call('experiment',experiment_id='bad',spec=s)
    with pytest.raises(ValueError):e.call('experiment',experiment_id='over',spec=s)
    with pytest.raises(FileExistsError):MatrixEpisode(17201,tmp_path)


def test_invalid_counts_and_late_prediction_rejected(tmp_path):
    e=MatrixEpisode(17201,tmp_path)
    r=e.call('experiment',experiment_id='x',spec={})
    assert r['remaining_units']==279 and r['remaining_attempts']==15
    with pytest.raises(ValueError):e.call('register_prediction',experiment_id='x',spec=example(),prediction=[0.]*16,model_sha256='a'*64)
    with pytest.raises(ValueError):e.call('clean',spec=example())
