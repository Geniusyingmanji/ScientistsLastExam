import pytest
from env.electrical_impedance.reference_records import pool_same_apparatus
from env.electrical_impedance.protocol import CHANNELS
from env.electrical_impedance.port_reference import port_reference, ReferenceFailure

def record(freq,values,source=500):
 return {'spec':{'frequencies_hz':freq,'source_ohm':source,'load_ohm':5000,'amplitude_v':1},'observation':{'axis':freq,'channels':list(CHANNELS),'values':values,'receipt':'metadata'}}

def test_all_rows_pooled_and_compatible():
 r=pool_same_apparatus([record([2,10],[[.5,0],[.4,0]]),record([2],[[.7,0]])])
 assert r['counts']==[2,1] and r['record']['observation']['values'][0]==[.6,0]
 assert len(port_reference([r['record']],r['record']['spec']))==2

def test_mixed_apparatus_not_silently_selected():
 with pytest.raises(ReferenceFailure):pool_same_apparatus([record([2],[[.5,0]]),record([2],[[.5,0]],1000)])
 with pytest.raises(ReferenceFailure):pool_same_apparatus([])

def test_both_comparators_use_all_repeat_measurements():
 from env.electrical_impedance.reference_records import compare_pooled
 a=record([2,10],[[.5,0],[.4,0]])
 b=record([2,10],[[.7,0],[.6,0]])
 out=compare_pooled([a,b],a['spec'])
 assert out['pooling']['counts']==[2,2]
 for method in out['methods'].values():
  assert method['error'] is None
  assert method['prediction'][0][0]==pytest.approx(.6)
  assert method['prediction'][1][0]==pytest.approx(.5)
 # The caller's records, including receipt metadata, remain unchanged.
 assert a['observation']['values'][0][0]==.5
