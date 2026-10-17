import json
import pytest
from env.microecology_context.matrix_episode import MatrixEpisode
from env.microecology_context.matrix_submission import audit, validate_submission

def test_prospective_and_posthoc_are_separate(tmp_path):
    e=MatrixEpisode(17101,'three_body',tmp_path)
    spec={'initial':{'C':.2},'times':[0]}
    e.call('register_prediction',experiment_id='future',spec=spec,prediction=[0,0,0,.2,0,0,0,0,0],model_sha256='a'*64)
    e.call('experiment',experiment_id='future',spec=spec)
    e.call('experiment',experiment_id='posthoc',spec=spec)
    journal=[json.loads(x) for x in (tmp_path/'prospective.jsonl').read_text().splitlines()]
    observations=[json.loads(x) for x in (tmp_path/'observations.jsonl').read_text().splitlines()]
    sub={'claims':[dict(id='c',cell='law/counterfactual',statement='Scoped claim',scope='one time point',alternatives=[],evidence=['future','posthoc','missing'])]}
    result=audit(sub,['law/counterfactual'],journal,observations)
    assert result['claims'][0]['prospective_evidence']==['future']
    assert result['claims'][0]['missing_evidence']==['missing']
    assert result['claims'][0]['scientific_verdict'] is None
    assert result['evidence']['future']['observation_rmse']>=0
    assert not result['evidence']['posthoc']['prospective']
    observations[0]['response']['receipt']='bad'
    with pytest.raises(ValueError,match='receipt'):audit(sub,['law/counterfactual'],journal,observations)

def test_inapplicable_and_duplicate_claims_rejected():
    c=dict(id='c',cell='structure/mechanism',statement='x',scope='x',alternatives=[],evidence=[])
    with pytest.raises(ValueError):validate_submission({'claims':[c]},['law/deduction'])
    with pytest.raises(ValueError):validate_submission({'claims':[c,c]},['structure/mechanism'])
