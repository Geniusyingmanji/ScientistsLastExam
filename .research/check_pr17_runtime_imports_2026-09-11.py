"""Two fixed data-free import probes; no oracle imports or task evaluations."""
import hashlib, importlib.metadata, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from sle.secure_eval import CandidateProxy, read_candidate_packages
from sle.algorithms.common import runtime_source_sha256
base='''def probe():
    import numpy, scipy, sysconfig
    try:
        import pymatching
    except ImportError:
        anchor_visible = False
    else:
        anchor_visible = True
    return {"numpy": numpy.__version__, "scipy": scipy.__version__, "soabi": sysconfig.get_config_var("SOABI"), "reference_anchor_visible": anchor_visible}
'''
qutip='''def probe():
    import qutip, packaging
    return {"qutip": qutip.__version__, "packaging": packaging.__version__}
'''
rows=[]
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary)
 for name,source,task in [('base',base,root/'empty-task'),('qutip',qutip,Path('benchmarks/Physics/HamiltonianLearning'))]:
  candidate=root/(name+'.py'); candidate.write_text(source)
  row={'name':name,'candidate_sha256':hashlib.sha256(source.encode()).hexdigest()}
  try:
   packages=read_candidate_packages(task)
   row['preflight']='passed'
   row['trusted_distribution_versions']={p:importlib.metadata.version(p) for p in (('numpy','scipy') if name=='base' else ('qutip','packaging'))}
   with CandidateProxy(candidate,'probe',timeout_s=40,packages=packages) as worker:
    row['observed']=worker()
   row['status']='passed' if all(row['observed'][p]==v for p,v in row['trusted_distribution_versions'].items()) else 'version_binding_mismatch'
   if name=='base' and row['observed']['reference_anchor_visible']: row['status']='reference_anchor_exposed'
  except Exception as error:
   row['status']='failed'; row['error_class']=type(error).__name__
  rows.append(row)
report={'schema_version':1,'scope':'TWO_FIXED_DATA_FREE_CANDIDATE_RPC_IMPORT_PROBES','source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'runtime_source_sha256':runtime_source_sha256(),'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scientific_evaluate_candidate_calls':0,'model_draws':0,'rows':rows}
Path('/tmp/sle-pr17-runtime-micro-20260911.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
