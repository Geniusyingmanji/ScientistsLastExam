import pytest
from env.microecology_context.matrix_rubric import RUBRIC, summarize_review


def test_partial_review_not_zero_and_no_cross_cell_credit():
    c=[{'id':'law','cell':'law/deduction'}]
    d={'cell':'law/deduction','criterion':RUBRIC['law/deduction'][0],
       'supported':True,'reason':'Reviewer verified equation','claim_ids':['law'],'evidence':['archive/report:law']}
    out=summarize_review(c,[d],('law/deduction',))
    assert out['cells']['law/deduction']['score'] is None
    assert out['cells']['structure/deduction']['max_score'] is None
    with pytest.raises(ValueError):summarize_review(c,[dict(d,cell='structure/deduction',criterion=RUBRIC['structure/deduction'][0])])
    with pytest.raises(ValueError):summarize_review(c,[d,d])
    with pytest.raises(ValueError):summarize_review(c,[dict(d,evidence=[])])


def test_explicit_negative_review_and_cell_denominator():
    ds=[{'cell':'law/deduction','criterion':k,'supported':False,
         'reason':'No supporting submission','claim_ids':[],'evidence':[]} for k in RUBRIC['law/deduction']]
    out=summarize_review([],ds)
    assert out['cells']['law/deduction']['score']==0
    assert out['cells']['law/mechanism']['score'] is None
    assert out['overall_score'] is None
