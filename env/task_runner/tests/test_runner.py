import hashlib,json
import pytest
from env.task_runner.runner import prepare,seal,predict,read

@pytest.mark.parametrize('task',['ecology','oscillator'])
def test_public_boundary_and_seal(task,tmp_path):
    root=tmp_path/'attempt';spec={'times':[0,.1]}
    if task=='ecology':spec['initial']={'A':.1}
    prepare(task,root,900001,[spec])
    assert not (root/'workspace/instance.json').exists()
    assert 'seed' not in read(root/'workspace/apparatus.json')
    with pytest.raises(FileExistsError):prepare(task,root,900001,[spec])
    out=root/'workspace/output';(out/'model.py').write_text('def predict(spec): return []\n')
    (out/'claims.json').write_text('{"claims":[]}');(out/'report.md').write_text('Incomplete scoped discovery')
    lab=root/'private/laboratory';lab.mkdir()
    (lab/'submission.json').write_text(json.dumps({'declared_model_sha256':hashlib.sha256((out/'model.py').read_bytes()).hexdigest(),'submission':{'claims':[]}}))
    seal(root);assert (root/'seal.json').exists()
    (root/'sealed/model.py').write_text('changed')
    with pytest.raises(ValueError,match='sealed artifact changed'):predict(root,'runtime@sha256:'+'a'*64)

def test_missing_submission_is_not_repaired(tmp_path):
    root=tmp_path/'attempt';prepare('oscillator',root,900002,[{'times':[0,.1]}])
    with pytest.raises(FileNotFoundError):seal(root)
    assert not (root/'sealed').exists()
