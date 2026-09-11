import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); aggregate=json.loads((root/'aggregate.json').read_text()); plan=json.loads((root/'plan.json').read_text())
assert aggregate['bindings']==plan['bindings'] and aggregate['source_unchanged']
records=aggregate['records']; counts=0; absent=0
sha=lambda b:hashlib.sha256(b).hexdigest()
for i,r in enumerate(records):
 p=root/('%02d.full.json'%i); raw=p.read_bytes(); m=json.loads(raw)
 assert p.stat().st_mode & 0o777 == 0o600
 assert sha(raw)==r['full_file_sha256']
 assert sha(json.dumps(m,sort_keys=True,allow_nan=False,separators=(',',':')).encode())==r['full_metrics_sha256']
 assert {k:v for k,v in m.items() if type(v) in (int,float,bool)}==r['scalars']
 if not m.get('per_instance'):
  assert m['valid']==0; absent+=1; continue
 for split in ('development','heldout'):
  rows=[x for x in m['per_instance'] if x['split']==split]
  expected=28 if aggregate['task_id'].startswith('ParticlePhysics/') else 10
  assert len(rows)==expected
  offset=1/7 if expected==28 else .2
  score=max(0,(sum(x['mechanism'] for x in rows)/expected-offset)/(1-offset))
  assert abs(score-m[split+'_mechanism_score'])<1e-9
  assert sum(x['false_claim'] for x in rows)==m[split+'_false_discovery_count']
  assert sum(x['claim'] for x in rows)==m[split+'_claim_count']
  for name,value in [('correct_refusal_count',sum(x['correct_refusal'] for x in rows)),('none_correct_count',sum(x['model']=='none' for x in rows if x['kind']=='none')),('valid_world_count',sum(x['valid'] for x in rows)),('world_count',len(rows)),('experiment_units_sum',sum(x['units'] for x in rows))]:
   assert m[split+'_'+name]==value
  counts+=1
 if m['valid']==1:
  assert m['development_valid_rate']==1
if aggregate['phase']=='methods':
 assert len(records)==2*len(plan['protocol']['methods'])
 for i in range(0,len(records),2):
  a=json.loads((root/('%02d.full.json'%i)).read_text());b=json.loads((root/('%02d.full.json'%(i+1))).read_text());assert a==b
  assert a['development_valid_rate']==a['heldout_valid_rate']==1
assert root.stat().st_mode & 0o777 == 0o700
print(json.dumps({'task':aggregate['task_id'],'phase':aggregate['phase'],'source_revision':aggregate['bindings']['source_revision'],'aggregate_sha256':sha((root/'aggregate.json').read_bytes()),'raw_files_verified':len(records),'split_score_and_count_recomputations':counts,'invalid_evaluations_without_world_rows':absent,'permissions_verified':True,'model_calls':0,'oracle_calls':0,'scientific_admission':'not_assessed'},indent=2))
