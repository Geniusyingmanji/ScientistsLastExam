import hashlib,json,stat,subprocess
from pathlib import Path
root=Path('/home/azureuser/workspace-gzy/zyf/sle-pr72-audit-20260911')
private=Path('/home/azureuser/workspace-gzy/zyf/sle-pr72-private-20260911')
public=root/'.research/pr72_shortcut_review_2026-09-11.json'
report=json.loads(public.read_text())
def digest(x):
    if not isinstance(x,bytes): x=json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(x).hexdigest()
assert report['status']=='completed'
assert report['planned_evaluations']==report['attempted_evaluations']==report['completed_evaluations']==8
assert report['all_repeats_identical'] and report['all_worlds_valid']
assert stat.S_IMODE(private.stat().st_mode)==0o700
assert len(list(private.glob('*.json')))==8
assert 'per_instance' not in [k for r in report['candidates'].values() for run in r['runs'] for k in run['metrics']]
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==report['integration_head']
assert digest((root/'.research/audit_pr72_shortcuts_2026-09-11.py').read_bytes())==report['driver_sha256']
validation={'schema_version':1,'scope':'read-only verification of all eight saved evaluations; no additional evaluate_candidate call',
            'source_integration_head':report['integration_head'],'task_head':report['task_head'],
            'report_file_sha256':digest(public.read_bytes()),'private_directory_mode':'0700','evaluations_verified':0,
            'world_records_verified':0,'per_candidate':{},'additional_evaluations':0}
for name,record in report['candidates'].items():
    assert len(record['runs'])==2
    assert digest((root/record['source_path']).read_bytes())==record['candidate_sha256']==report['candidate_plan_sha256'][name]
    metrics_runs=[]
    for run in record['runs']:
        path=private/('%s_%d.json'%(name,run['repeat']))
        assert stat.S_IMODE(path.stat().st_mode)==0o600
        metrics=json.loads(path.read_text()); metrics_runs.append(metrics)
        assert digest(path.read_bytes())==run['full_metrics_file_sha256']
        assert digest(metrics)==run['full_metrics_sha256']
        assert digest(metrics['per_instance'])==run['per_instance_sha256']
        assert len(metrics['per_instance'])==56
        assert metrics['valid']==1 and not metrics.get('infrastructure_failure')
        expected_scalars={k:v for k,v in metrics.items() if type(v) in (int,float)}
        assert expected_scalars==run['metrics']
        for split in ('development','heldout'):
            rows=[r for r in metrics['per_instance'] if r['split']==split]
            assert len(rows)==28
            assert sum(r['kind'] in ('contact','q2') for r in rows)==20
            assert sum(r['kind']=='none' for r in rows)==4
            assert sum(r['kind']=='unsupported' for r in rows)==4
            units=12 if name in ('reference','fixed_mass_57_8') else 1
            assert all(r['units']==units and r['valid'] for r in rows)
            assert run['denominators'][split]['charged_experiment_units_sum']==28*units
            assert metrics[split+'_mechanism_score']==round(max(0.0,(sum(r['mechanism'] for r in rows)/28-1/7)/(1-1/7)),10)
            assert run['denominators'][split]['mechanism_utility_sum']==sum(r['mechanism'] for r in rows)
        validation['evaluations_verified']+=1
        validation['world_records_verified']+=len(metrics['per_instance'])
    assert metrics_runs[0]==metrics_runs[1]
    validation['per_candidate'][name]={'saved_full_metrics_repeat_identical':True,'source_sha256':record['candidate_sha256'],
        'valid_worlds':112,'charged_experiment_units_two_runs':sum(r['units'] for m in metrics_runs for r in m['per_instance'])}
validation['fixed_probe_comparisons']={}
for name in ('fixed_mass_57_8','published_four_way_probe'):
    comparisons={}
    for split in ('development','heldout'):
        ref=report['candidates']['reference']['runs'][0]['metrics'][split+'_mechanism_score']
        score=report['candidates'][name]['runs'][0]['metrics'][split+'_mechanism_score']
        comparisons[split]={'score':score,'reference':ref,'score_to_reference_ratio':score/ref,'absolute_gap_below_reference':ref-score}
        if name=='published_four_way_probe':
            comparisons[split]['previously_declared_fixed_probe_gate_passed']=score<.7*ref and ref-score>.15
    validation['fixed_probe_comparisons'][name]=comparisons
validation['passed']=True
validation['scientific_admission']='not_assessed'
validation['full_private_metrics_file_mode']='0600'
output=root/'.research/pr72_shortcut_validation_2026-09-11.json'
output.write_text(json.dumps(validation,sort_keys=True,indent=2,allow_nan=False)+'\n')
print(json.dumps(validation,sort_keys=True,indent=2))
