import pytest
from env.catalyst_aging.export_check import compare_export,require_validated_submission

REF={'name':'fit','version':'v1','sha256':'a'*64}
SPECS=[{'events':[{'kind':'blank'}],'event_indices':[1]}]


def test_export_binding_and_behavior():
    receipt=compare_export(REF,'source',SPECS,[[[1.]]],[[[1.]]])
    submission={'model_snapshot':dict(REF),'claims':[],'explanation':'fixture'}
    assert require_validated_submission(submission,'source',receipt)
    with pytest.raises(ValueError): require_validated_submission(submission,'changed',receipt)
    with pytest.raises(ValueError): require_validated_submission(dict(submission,predictor_code='source'),'source',receipt)
    submission['model_snapshot']['version']='v2'
    with pytest.raises(ValueError): require_validated_submission(submission,'source',receipt)
    assert receipt['snapshot']==REF


@pytest.mark.parametrize('output',[[[2.]],[[float('nan')]],[[1.,2.]],[]])
def test_invalid_or_changed_predictions_fail(output):
    receipt=compare_export(REF,'source',SPECS,[[[1.]]],[output])
    assert not receipt['passed']
    with pytest.raises(ValueError):
        require_validated_submission({'model_snapshot':REF,'claims':[],'explanation':'x'},'source',receipt)
