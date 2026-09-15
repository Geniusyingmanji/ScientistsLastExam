import concurrent.futures,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();os.umask(0o077);assert platform.system()=='Linux' and root not in out.parents;out.mkdir(mode=0o700,exist_ok=False);os.chdir(root);sys.path.insert(0,str(root))
from sle.registry import list_tasks
from sle.provenance import source_provenance
from sle.algorithms.common import runtime_source_sha256

def save(path,obj):
 with path.open('x') as h:json.dump(obj,h,indent=2,allow_nan=False);h.write('\n')
 path.chmod(0o600)
prov=source_provenance(root);assert prov.get('source_tree_dirty') is False
specs=list_tasks(None);plan={'source_provenance':prov,'runtime_source_sha256':runtime_source_sha256(),'python':sys.version,'timeout_s':300,'workers':2,'model_calls':0,'tasks':[{'task':s.task_id,'candidate_sha256':hashlib.sha256(s.initial_program_path.read_bytes()).hexdigest()} for s in specs]};save(out/'plan.json',plan)
def run(item):
 i,s=item;cell=out/str(i);cell.mkdir(mode=0o700);m=cell/'metrics.json';before=time.monotonic()
 try:
  result=subprocess.run([sys.executable,str(s.task_dir/'frontier_eval/run_eval.py'),'--candidate',str(s.initial_program_path),'--metrics-out',str(m),'--timeout','300'],capture_output=True,text=True,timeout=480)
  receipt={'task':s.task_id,'candidate_sha256':plan['tasks'][i]['candidate_sha256'],'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'metrics':json.loads(m.read_text()) if m.exists() else None}
 except Exception as e:receipt={'task':s.task_id,'failure_kind':type(e).__name__}
 receipt['elapsed_seconds']=time.monotonic()-before;save(cell/'receipt.json',receipt)
 print(json.dumps({'index':i+1,'task':s.task_id,'returncode':receipt.get('returncode'),'failure_kind':receipt.get('failure_kind'),'elapsed_seconds':receipt['elapsed_seconds']}),flush=True)
 return receipt
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,enumerate(specs)))
save(out/'execution.json',{'plan_sha256':hashlib.sha256((out/'plan.json').read_bytes()).hexdigest(),'source_provenance':prov,'actual_wrapper_calls':len(rows),'tasks':rows,'complete':True})
