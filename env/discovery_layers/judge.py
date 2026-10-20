"""Evidence-bound semantic grading. Never imports or executes candidate artifacts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from .three_stage import contract, review

MODULES = {'ecology': {'a_uptake','b_uptake','c_basal','c_context','allocation','turnover'},
           'oscillator': {'connections','springs','mass_damping'}}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def evidence_path(root, name):
    if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('evidence must be relative and contained')
    p=root/name
    if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root.resolve()):
        raise ValueError('missing or unsafe evidence')
    return p

def grade(environment, evidence, decisions, output, *, retrospective=False):
    root=Path(evidence).resolve(); destination=Path(output)
    if destination.exists(): raise FileExistsError('assessment outputs are append-only')
    manifest_path=root/'evidence_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if not isinstance(manifest,dict) or not manifest: raise ValueError('evidence manifest required')
    for name,expected in manifest.items():
        if digest(evidence_path(root,name))!=expected: raise ValueError('evidence changed: '+name)
    if 'candidate/model.py' in manifest and 'private/submission.json' in manifest:
        submission=json.loads((root/'private/submission.json').read_text())
        if digest(root/'candidate/model.py')!=submission['declared_model_sha256']:
            raise ValueError('candidate does not match submitted model')
    judge_path=Path(decisions); data=json.loads(judge_path.read_text())
    if data.get('review_independence')!='same-family' or data.get('acceptance_status')!='provisional':
        raise ValueError('explicit reviewer provenance required')
    frozen=contract(environment)
    def refs(row):
        if not row.get('evidence'):raise ValueError('evidence required')
        for name in row['evidence']:
            if name not in manifest and name!='evidence_manifest.json':raise ValueError('unmanifested evidence')
            evidence_path(root,name)
    for row in data['result_decisions']+data['process_decisions']:
        refs(row)
    for row in data['result_decisions']:
        if row['level']!='laws':continue
        modules=row.get('modules',[])
        if len(modules)!=len(MODULES[environment]) or {m['id'] for m in modules}!=MODULES[environment]:
            raise ValueError('all fixed scientific modules required')
        for m in modules:
            s=m['score']
            if isinstance(s,bool) or not isinstance(s,(int,float)) or not math.isfinite(s) or not 0<=s<=100 or not m.get('reason'):
                raise ValueError('invalid module judgment')
            refs(m)
        if not math.isclose(row['score'],sum(m['score'] for m in modules)/len(modules),abs_tol=1e-8):
            raise ValueError('module aggregation mismatch')
    result=review(frozen,data['result_decisions'],data['process_decisions'])
    result.update(assessment_type='retrospective_supplement' if retrospective else 'prospective',
        original_results_modified=False, evidence_manifest_sha256=digest(manifest_path),
        reviewer_sha256=digest(judge_path), rubric_sha256=digest(Path(__file__).with_name('THREE_STAGE_JUDGE.md')),
        contract=frozen, decisions=data,
        limitations=['Semantic judgments are same-family/provisional, not mechanically verified truth.']+data.get('limitations',[]))
    if not retrospective:
        # Bind new-task assessments to a contract frozen before its run.
        saved=root/'judge-contract.json'
        if 'judge-contract.json' not in manifest or json.loads(saved.read_text())!=frozen:
            raise ValueError('prospective run requires its frozen three-stage contract')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--environment',required=True,choices=MODULES)
    p.add_argument('--evidence',required=True);p.add_argument('--decisions',required=True);p.add_argument('--output',required=True)
    p.add_argument('--retrospective',action='store_true');a=p.parse_args()
    r=grade(a.environment,a.evidence,a.decisions,a.output,retrospective=a.retrospective)
    print(json.dumps({k:r[k] for k in ['assessment_type','result','process','combined_score']},ensure_ascii=False))
if __name__=='__main__':main()
