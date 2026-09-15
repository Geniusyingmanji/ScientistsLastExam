import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();private=Path(sys.argv[2]).resolve();baseline_path=Path(sys.argv[3]).resolve();output=Path(sys.argv[4]).resolve();sys.path.insert(0,str(root))
from sle.metric_visibility import search_visible_metrics
from sle.provenance import finalize_report_trust,source_provenance
plan=json.loads((private/'plan.json').read_text());execution=json.loads((private/'execution.json').read_text());baseline=json.loads(baseline_path.read_text());current=source_provenance(root)
assert execution['complete'] and execution['actual_wrapper_calls']==len(execution['tasks'])==len(plan['tasks'])==86
assert execution['plan_sha256']==hashlib.sha256((private/'plan.json').read_bytes()).hexdigest()
assert plan['source_provenance']['source_tree_dirty'] is False and current['source_tree_dirty'] is False
assert baseline['trusted_evidence'] is True and baseline['environment']['python']==plan['python']
scopes=['sle','benchmarks','requirements-upstream.txt'];revision=plan['source_provenance']['git_revision']
for target in [baseline['source_provenance']['git_revision'],'HEAD']:
 assert not subprocess.check_output(['git','-c','core.commitGraph=false','diff','--name-only',revision,target,'--',*scopes],cwd=root,text=True).strip()
old={r['task']:r for r in baseline['tasks']};assert len(old)==len(baseline['tasks'])==86
assert set(old)=={r['task'] for r in plan['tasks']}=={r['task'] for r in execution['tasks']}
rows=[]
for p,r in zip(plan['tasks'],execution['tasks']):
 assert p['task']==r['task'];b=old[r['task']];assert p['candidate_sha256']==b['candidate_sha256']==r.get('candidate_sha256')
 expected=search_visible_metrics(b['runs'][0]['metrics']);expected.setdefault('raw_score',expected['combined_score']);actual=r.get('metrics')
 try:stdout=json.loads(r.get('stdout',''))
 except (TypeError,ValueError):stdout=None
 passed=r.get('returncode')==0 and not r.get('stderr') and actual==expected and stdout==actual
 rows.append({'task':r['task'],'candidate_sha256':p['candidate_sha256'],'returncode':r.get('returncode'),'public_metrics':search_visible_metrics(actual) if isinstance(actual,dict) else None,'expected_public_metrics':expected,'passed':passed})
report={'schema_version':1,'evidence_scope':'PUBLIC_WRAPPER_BASELINE_REPLAY_ONLY','source_provenance':{k:v for k,v in plan['source_provenance'].items() if k!='command'},'baseline':str(baseline_path.relative_to(root)),'baseline_sha256':hashlib.sha256(baseline_path.read_bytes()).hexdigest(),'inventory_count':len(rows),'passed_count':sum(r['passed'] for r in rows),'tasks':rows,'execution_strategy':'All 86 source-bound wrapper calls frozen in advance; two workers; compared with independently collected baseline after both completed.','plan_sha256':execution['plan_sha256'],'private_execution_sha256':hashlib.sha256((private/'execution.json').read_bytes()).hexdigest(),'export_source_revision':current['git_revision'],'source_compatibility':{'scope':scopes,'changed_paths':[]},'actual_wrapper_calls':86,'model_calls':0}
finalize_report_trust(report,report['passed_count']==86)
with output.open('x') as h:json.dump(report,h,indent=2,allow_nan=False);h.write('\n')
print(json.dumps({'passed':report['passed'],'count':report['passed_count'],'total':86}))
assert report['passed']
