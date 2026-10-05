import copy
import importlib.util
import json
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[1]/'docs/reports/render_model_comparison.py'
spec=importlib.util.spec_from_file_location('comparison_report',path)
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)


def fixtures():
    a=json.loads((path.parent/'sle-unified12-20261004/data.json').read_text())
    for e in a['episodes']:
        e.update(score=50.,condition_score=50.,intervention_score=50.,claim_score=50.,
                 status='completed',completed=True,infrastructure_failure=None,settled=True)
    b=copy.deepcopy(a);b['model']='deepseek-v4-pro-0813'
    b['comparison']={'reference_manifest_sha256':a['manifest_sha256']}
    for e in b['episodes']:
        e.update(score=60.,condition_score=60.,intervention_score=60.,claim_score=60.)
    return a,b


def test_constant_cluster_difference_has_exact_interval_and_all_pairs():
    a,b=fixtures();d=report.compare(a,b)
    assert d['ready'] and d['delta']==10
    assert d['paired_cluster_bootstrap_95']==[10,10]
    assert len(d['worlds'])==12
    assert all(w['cluster_deltas']==[10,10,10] for w in d['worlds'])
    assert all(w['wins_ties_losses']==[6,0,0] for w in d['worlds'])
    assert d['matched_noinfra_delta']==10
    assert '同一批科学世界' in report.render(d)


def test_pending_is_not_zero_and_macro_waits_for_all_runs():
    a,b=fixtures();e=b['episodes'][0]
    e.update(settled=False,completed=False,status='running',score=None,
             condition_score=None,intervention_score=None,claim_score=None)
    d=report.compare(a,b)
    assert not d['ready'] and d['delta'] is None and d['paired_cluster_bootstrap_95'] is None
    assert d['candidate']['score'] is None and d['candidate']['settled']==71
    assert d['worlds'][0]['delta'] is None


def test_infra_pair_remains_zero_primary_but_is_removed_only_from_sensitivity():
    a,b=fixtures();e=b['episodes'][0]
    e.update(completed=False,status='failed',score=0.,condition_score=0.,intervention_score=0.,claim_score=0.,infrastructure_failure='api')
    d=report.compare(a,b)
    assert d['delta']==pytest.approx(10-60/72)
    assert d['matched_noinfra_delta']==10
    assert d['candidate']['infrastructure_failures']==1


@pytest.mark.parametrize('change',['budget','binding','slots','noise_id'])
def test_unpaired_comparisons_rejected(change):
    a,b=fixtures()
    if change=='budget':b['limits']['rounds']=32
    elif change=='binding':b['comparison']['reference_manifest_sha256']='different'
    elif change=='slots':b['episodes'][0]=copy.deepcopy(b['episodes'][1])
    else:b['episodes'][0]['episode_id']='new-noise-key'
    with pytest.raises(ValueError):report.compare(a,b)


def test_stopped_first_wave_does_not_become_zero_full_macro():
    a,b=fixtures();b['status']='stopped_infrastructure'
    for e in b['episodes']:
        closed=e['instance_index']==1 and e['repeat_index']==1
        e.update(settled=closed,completed=False,status='failed' if closed else 'pending',
                 score=0. if closed else None,condition_score=0. if closed else None,
                 intervention_score=0. if closed else None,claim_score=0. if closed else None,
                 infrastructure_failure='deadline' if closed else None)
    d=report.compare(a,b)
    assert d['candidate']['settled']==12 and d['candidate']['score'] is None
    assert d['delta'] is None and d['paired_cluster_bootstrap_95'] is None
    assert all(w['candidate']['score'] is None for w in d['worlds'])
    assert '不计算72次总分' in report.render(d)


@pytest.mark.parametrize("cap,profile", [(16000,"extended-output-v1"),(32000,"extended-output-32k-v1")])
def test_extended_budget_is_labeled_and_cannot_hide_other_budget_changes(cap,profile):
    a,b=fixtures()
    b['limits']['wall_seconds']=14400
    b['decoding']={'max_output_tokens':cap,'timeout_seconds':900}
    b['comparison']['budget_change']={
        'profile':profile,'equal_budget':False,
        'fields':{'max_output_tokens':{'reference':8000,'candidate':cap},
                  'timeout_seconds':{'reference':180,'candidate':900},
                  'wall_seconds':{'reference':3600,'candidate':14400}}}
    d=report.compare(a,b)
    assert d['equal_budget'] is False
    text=report.render(d,data_href='deepseek-extended-data.json')
    assert '不是等预算模型排名' in text and format(cap, ',') in text
    assert '同样的世界、面板、提示、评分与预算' not in text
    assert '共同外部预算下的系统比较' not in text
    assert 'href="deepseek-extended-data.json"' in text
    b['limits']['experiments']=96
    with pytest.raises(ValueError,match='Undeclared extended'):
        report.compare(a,b)
