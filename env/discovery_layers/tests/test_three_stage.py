import pytest
from env.discovery_layers.three_stage import contract,review

def decisions(c,score):
    return [dict(level=l,criterion=k,score=score,reason='scoped recovery',evidence=['trusted:1']) for l,cs in c['criteria'].items() for k in cs]

def test_separate_scientific_and_process_scores():
    c=contract('ecology');r=review(c,decisions(c['result'],60),decisions(c['process'],90))
    assert r['result']['weighted_score']==60
    assert r['process']['weighted_score']==90
    assert r['combined_score'] is None
    assert review(c,[],decisions(c['process'],90))['result']['weighted_score'] is None

def test_duplicates_cannot_inflate_score():
    c=contract('oscillator');d=decisions(c['result'],50)
    with pytest.raises(ValueError):review(c,d+d[:1],[])
