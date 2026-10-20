import hashlib,json
import pytest
from env.discovery_layers.judge import grade,MODULES
from env.discovery_layers.three_stage import contract

def fixture(tmp_path):
    root=tmp_path/'evidence';root.mkdir();(root/'report.txt').write_text('observable evidence')
    (root/'evidence_manifest.json').write_text(json.dumps({'report.txt':hashlib.sha256((root/'report.txt').read_bytes()).hexdigest()}))
    c=contract('ecology');d={'review_independence':'same-family','acceptance_status':'provisional'}
    for group in ['result','process']:
        rows=[]
        for l,cs in c[group]['criteria'].items():
            for k in cs:
                row=dict(level=l,criterion=k,score=60,reason='partial recovery',evidence=['report.txt'])
                if l=='laws':row['modules']=[dict(id=m,score=60,reason='partial recovery',evidence=['report.txt']) for m in MODULES['ecology']]
                rows.append(row)
        d[group+'_decisions']=rows
    p=tmp_path/'decisions.json';p.write_text(json.dumps(d));return root,p,d

def test_evidence_bound_separate_scores_and_no_overwrite(tmp_path):
    r,p,d=fixture(tmp_path);out=tmp_path/'score.json'
    v=grade('ecology',r,p,out,retrospective=True)
    assert v['result']['weighted_score']==60 and v['combined_score'] is None
    with pytest.raises(FileExistsError):grade('ecology',r,p,out,retrospective=True)
    (r/'report.txt').write_text('changed')
    with pytest.raises(ValueError,match='evidence changed'):grade('ecology',r,p,tmp_path/'new.json',retrospective=True)

def test_cannot_omit_hard_module_or_invent_evidence(tmp_path):
    r,p,d=fixture(tmp_path)
    law=next(x for x in d['result_decisions'] if x['level']=='laws');law['modules'].pop();p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='fixed scientific modules'):grade('ecology',r,p,tmp_path/'score.json',retrospective=True)
    d['result_decisions'][0]['evidence']=['absent.txt'];p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='unmanifested'):grade('ecology',r,p,tmp_path/'score.json',retrospective=True)

def test_historical_run_cannot_be_called_prospective(tmp_path):
    r,p,d=fixture(tmp_path)
    with pytest.raises(ValueError,match='frozen three-stage'):grade('ecology',r,p,tmp_path/'score.json')
