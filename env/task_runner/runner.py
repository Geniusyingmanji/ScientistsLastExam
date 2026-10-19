"""Operator CLI. Never executes candidate code in the trusted Python process."""
import argparse, hashlib, json, math, os, re, shutil, subprocess, uuid
from pathlib import Path

PACKAGES=Path(__file__).parent/'packages'

def read(p): return json.loads(Path(p).read_text())
def write(p,x):
    with Path(p).open('x') as f: json.dump(x,f,indent=2,allow_nan=False)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def regular(p):
    if p.is_symlink() or not p.is_file(): raise ValueError(f'not a regular file: {p.name}')

def prepare(task, root, seed, panels):
    from env.discovery_layers.protocol import contract
    from env.discovery_layers.episode import LayeredEpisode
    if task not in ('ecology','oscillator'): raise ValueError('unknown task')
    package=PACKAGES/task; manifest=read(package/'manifest.json')
    if not isinstance(panels,list) or not panels: raise ValueError('nonempty panel list required')
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    os.chmod(root,0o700)
    for n in ('workspace','workspace/output','public','private'): (root/n).mkdir()
    shutil.copyfile(package/'instruction.md',root/'workspace/instruction.md')
    write(root/'workspace/delivery.json',{k:manifest[k] for k in ('required_outputs','optional_outputs','prediction_interface')})
    shutil.copyfile(Path(__file__).parents[1]/'discovery_layers/mcp_client.py',root/'public/mcp_client.py')
    # Validate without running experiments; temporary episode is retained as preflight evidence.
    ep=LayeredEpisode(task,seed,root/'private/validation',budget=manifest['attempt_budget'])
    for spec in panels: ep.base.validate_spec(spec)
    write(root/'workspace/apparatus.json',ep.call('describe'))
    write(root/'private/instance.json',{'seed':seed,'panels':panels,'task':task})
    write(root/'private/judge-contract.json',contract(task))
    shutil.copyfile(Path(__file__).parents[1]/'discovery_layers/JUDGE_CONTRACT.md',root/'private/JUDGE_CONTRACT.md')
    write(root/'manifest.json',dict(manifest,package_files={p.name:sha(p) for p in package.iterdir() if p.is_file()},instance_sha256=sha(root/'private/instance.json'),judge_sha256=sha(root/'private/JUDGE_CONTRACT.md')))
    return root

def serve(root,port):
    from env.discovery_layers.episode import LayeredEpisode
    from env.microecology_context.matrix_service import serve as http
    root=Path(root);m=read(root/'manifest.json');i=read(root/'private/instance.json')
    if sha(root/'private/instance.json')!=m['instance_sha256']: raise ValueError('instance modified')
    ep=LayeredEpisode(m['environment'],i['seed'],root/'private/laboratory',budget=m['attempt_budget'])
    http(ep,port).serve_forever()

def seal(root):
    root=Path(root);m=read(root/'manifest.json');out=root/'workspace/output'
    submission=read(root/'private/laboratory/submission.json')
    for name in m['required_outputs']: regular(out/name)
    allowed=set(m['required_outputs']+m['optional_outputs'])
    files=list(out.iterdir())
    if any(p.name not in allowed for p in files): raise ValueError('undeclared deliverable')
    for p in files: regular(p)
    if sha(out/'model.py')!=submission['declared_model_sha256']: raise ValueError('model seal mismatch')
    if read(out/'claims.json')!=submission['submission']: raise ValueError('claim seal mismatch')
    target=root/'sealed';target.mkdir(exist_ok=False)
    for p in files: shutil.copyfile(p,target/p.name)
    write(root/'seal.json',{'files':{p.name:sha(p) for p in target.iterdir()},'submission_sha256':sha(root/'private/laboratory/submission.json')})

def predict(root,image,timeout=180):
    root=Path(root).resolve();seal_record=read(root/'seal.json')
    if not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}',image): raise ValueError('digest-pinned image required')
    for name,digest in seal_record['files'].items():
        regular(root/'sealed'/name)
        if sha(root/'sealed'/name)!=digest: raise ValueError('sealed artifact changed')
    if shutil.which('docker') is None: raise RuntimeError('Docker unavailable; no unisolated fallback')
    run=root/'prediction';run.mkdir(exist_ok=False)
    queries=read(root/'private/instance.json')['panels'];write(run/'queries.json',queries)
    (run/'executor.py').write_text('''import sys,json,os
sys.path.insert(0,"/candidate")
os.chdir("/candidate")
import model
queries=json.load(open("/queries.json"));result=[]
for spec in queries:
 try:
  import numpy as np
  result.append({"prediction":np.asarray(model.predict(spec),dtype=float).tolist()})
 except Exception as e:result.append({"error":type(e).__name__})
json.dump(result,open("/output/predictions.json","w"),allow_nan=False)
''')
    output=run/'output';output.mkdir();os.chmod(output,0o777)
    name='sle-predict-'+uuid.uuid4().hex
    command=['docker','run','--name',name,'--rm','--network','none','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64','--memory','2g','--cpus','1','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
      '-v',f'{root}/sealed:/candidate:ro','-v',f'{run}/queries.json:/queries.json:ro','-v',f'{run}/executor.py:/executor.py:ro','-v',f'{output}:/output:rw',image,'python','/executor.py']
    receipt={'image':image,'network':'none','status':'execution_error'}
    try:
        with (run/'stdout').open('x') as stdout,(run/'stderr').open('x') as stderr:
            p=subprocess.run(command,stdout=stdout,stderr=stderr,timeout=timeout)
        receipt.update(status='completed' if p.returncode==0 else 'failed',returncode=p.returncode)
    except subprocess.TimeoutExpired:receipt['status']='timeout'
    finally:
        subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
        write(run/'receipt.json',receipt)
    return receipt

def evaluate(root):
    import numpy as np
    root=Path(root);m=read(root/'manifest.json');inst=read(root/'private/instance.json')
    if sha(root/'private/instance.json')!=m['instance_sha256']:raise ValueError('instance modified')
    receipt=read(root/'prediction/receipt.json')
    if receipt['status']!='completed': raise ValueError('execution failed; scientific judgment unavailable')
    path=root/'prediction/output/predictions.json';regular(path)
    if path.stat().st_size>10_000_000:raise ValueError('oversized predictions')
    predictions=read(path)
    if not isinstance(predictions,list) or len(predictions)!=len(inst['panels']):raise ValueError('prediction count mismatch')
    if m['environment']=='ecology':
        from env.microecology_context.world import World
        from env.microecology_context.direct_kernel import DirectKernel
        w=World(inst['seed'],'fixed');w.kernel=DirectKernel(inst['seed'],'three_body')
        truth=lambda s:w.run(s,clean=True)['values']
    else:
        from env.coupled_oscillators.world import World
        w=World(inst['seed']);truth=lambda s:w.run(s,noise_key=None)['values']
    rows=[]
    for spec,pred in zip(inst['panels'],predictions):
        target=truth(spec);row={'spec':spec,'target':target,'prediction':pred}
        try:
            a=np.asarray(pred['prediction'],dtype=float);b=np.asarray(target)
            if a.shape!=b.shape or not np.isfinite(a).all():raise ValueError('invalid array')
            row['rmse_by_channel']=np.sqrt(np.mean((a-b)**2,axis=0)).tolist()
        except (ValueError,TypeError,KeyError):row['failed']=True
        rows.append(row)
    write(root/'numeric-evaluation.json',{'rows':rows,'prediction_sha256':sha(path),'layer_score':None,'judge_status':'pending','scope':'trajectory metrics only; effect panels and independent layered judge remain separate'})

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('--task',choices=['ecology','oscillator'],required=True);a.add_argument('--seed',type=int,required=True);a.add_argument('--panels',required=True)
    for name in ('serve','seal','predict','evaluate'):sub.add_parser(name)
    for a in sub.choices.values():a.add_argument('--root',required=True)
    sub.choices['serve'].add_argument('--port',type=int,required=True)
    sub.choices['predict'].add_argument('--image',required=True)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.task,a.root,a.seed,read(a.panels))
    elif a.action=='serve':serve(a.root,a.port)
    elif a.action=='seal':seal(a.root)
    elif a.action=='predict':predict(a.root,a.image)
    else:evaluate(a.root)
if __name__=='__main__':main()
