"""Run fixed data-free compatibility fixtures in the unmodified candidate sandbox."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from sle.secure_eval import CandidateProxy, sanitized_candidate_failure
from sle.algorithms.common import runtime_source_sha256
BASE='2660c38a413fb7281d0e7012a6446eb384a934d1'
RUNTIME='8159a99d54894dd304e3ac48956cd05d4389f12a041f5d5d86a2c079641c2c86'
CANDIDATE=Path(__file__).with_name('candidate.py')
PRIVATE=Path('/home/azureuser/workspace-gzy/zyf/sle-pr30-micro-private-20260911')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==BASE
assert runtime_source_sha256()==RUNTIME
assert not PRIVATE.exists()
PRIVATE.mkdir(mode=0o700)
report={'schema_version':1,'scope':'data-free two-variable LP engineering compatibility, no task package or oracle imported',
        'runtime_head':BASE,'runtime_source_sha256':RUNTIME,'python':sys.version,
        'candidate_sha256':hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
        'task_evaluations':0,'model_calls':0,'rows':[]}
CASES=['import_only','python_thread','linprog_default','linprog_threads_one','direct_threads_one','direct_serial_minmax']
for case in CASES:
    for repeat in range(1,3):
        row={'case':case,'repeat':repeat,'checkpoints':[]}
        def checkpoint(label):
            assert label in ('candidate_entered','solver_entered','solver_returned')
            row['checkpoints'].append(label)
            return None
        proxy=None
        started=time.monotonic()
        try:
            proxy=CandidateProxy(CANDIDATE,'micro',timeout_s=15,memory_mb=4096)
            row['result']=proxy(case,checkpoint)
            row['status']='returned'
        except Exception as exc:
            row['status']='failed'
            row['failure_kind']=sanitized_candidate_failure(exc)['candidate_failure_kind']
            row['exception_type']=type(exc).__name__
            detail={'error':str(exc),'worker_returncode':proxy.proc.poll() if proxy and proxy.proc else None}
            private=PRIVATE/('%s_%d.json'%(case,repeat))
            private.write_text(json.dumps(detail,sort_keys=True,indent=2)+'\n')
            private.chmod(0o600)
            row['private_diagnostic_sha256']=hashlib.sha256(private.read_bytes()).hexdigest()
            row['worker_returncode']=detail['worker_returncode']
        finally:
            if proxy: proxy.close(kill=True)
        row['seconds']=time.monotonic()-started
        report['rows'].append(row)
        print(json.dumps(row,sort_keys=True),flush=True)
report['runtime_unchanged']=runtime_source_sha256()==RUNTIME
report['candidate_unchanged']=hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()==report['candidate_sha256']
Path(__file__).with_name('results.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
