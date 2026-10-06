import pytest
from env.isotope_pairing.development_metrics import fixture_manifest, score_fixtures


def test_binding_and_no_assigned_value_credit():
    m = fixture_manifest()
    targets = {e['id']: [[0., 0., 0.] for _ in e['spec']['times']] for e in m['entries']}
    predictions = {k: [[999., 999., 999.]] + [[1., 1., 1.] for _ in v[1:]] for k, v in targets.items()}
    r = score_fixtures(predictions, targets, design_sha256=m['design_sha256'])
    assert [r['axes'][a]['experiments'] for a in ('new_recipe', 'new_history', 'ambiguity_control')] == [2, 2, 1]
    assert all(v['mean_experiment_rmse'] == pytest.approx(1.) for v in r['axes'].values())
    assert r['overall_score'] is None and r['structural_holdout'] is False
    with pytest.raises(ValueError):
        score_fixtures(predictions, targets, design_sha256='wrong')
    predictions.pop(next(iter(predictions)))
    with pytest.raises(ValueError):
        score_fixtures(predictions, targets, design_sha256=m['design_sha256'])


def test_manifest_is_detached():
    m = fixture_manifest()
    m['entries'][0]['spec']['times'][0] = 7
    assert fixture_manifest()['entries'][0]['spec']['times'][0] == 0
