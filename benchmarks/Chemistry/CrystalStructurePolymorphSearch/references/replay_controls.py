"""Replay the fixed controls in one fresh Linux process.

Run twice from a clean checkout, with separate private output directories:
    python references/replay_controls.py <repository-root> <private-pass-directory>

Uses the canonical CandidateProxy and validates complete metrics. Anchors are
recomputed once per process; only that trusted oracle cache is reused. This
comparison runner does not replace check_task_contribution.py or model admission.
"""
import hashlib, importlib.util, json, os, platform, resource, signal, subprocess, sys, time, traceback
from pathlib import Path
if sys.platform != "linux":
 raise SystemExit("requires Linux and the canonical pinned candidate runtime")
if len(sys.argv) != 3:
 raise SystemExit("usage: replay_controls.py <repository-root> <private-pass-directory>")
root=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve()
if out == root or root in out.parents:
 raise SystemExit("full metrics must be outside the repository")
if out.exists() and any(out.iterdir()):
 raise SystemExit("refuse to overwrite or resume an existing output directory")
if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True).strip():
 raise SystemExit("freeze a clean source revision before replay")
out.mkdir(parents=True,exist_ok=True); os.chmod(out,0o700)
os.chdir(root); sys.path.insert(0,str(root))
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
 os.environ[variable] = "1"
import numpy, scipy
from sle.secure_eval import CandidateProxy, CandidateError, sanitized_candidate_failure, validate_metrics
from sle.runtime_identity import current_runtime_descriptor, task_runtime_distributions
task=root/'benchmarks/Chemistry/CrystalStructurePolymorphSearch'
sp=importlib.util.spec_from_file_location('csp_comparison',task/'verification/evaluator.py'); e=importlib.util.module_from_spec(sp); sp.loader.exec_module(e)
meta={'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'dirty':subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True),'runtime':current_runtime_descriptor(task_runtime_distributions(task)),'platform':platform.platform(),'numpy':numpy.__version__,'scipy':scipy.__version__,'timeout_s':300,'seed_selection':'fixed in candidate source before measurement; no heldout selection','cpu_accounting_limit':'reaped-child accounting is not verified total candidate-subtree CPU','sandbox':'canonical CandidateProxy + validate_metrics; shared trusted anchor cache within pass; separate process per pass'}
(out/'environment.json').write_text(json.dumps(meta,indent=2))
start=time.monotonic(); anchors=e._anchors(); (out/'anchors.json').write_text(json.dumps({'anchors':anchors,'wall_seconds':time.monotonic()-start},indent=2)); print('anchors_ready',time.monotonic()-start,flush=True)
paths=['verification/shortcut_record_replay.py','verification/shortcut_cubic.py','verification/shortcut_cubic24.py','verification/shortcut_anisotropic24.py','verification/shortcut_restarts24.py','verification/ablation_energy_only.py','solution.py','verification/reference_multistart.py']
class EvaluationTimeout(RuntimeError):
 pass
def timeout(signum, frame): raise EvaluationTimeout('300 second trusted evaluation supervision')
signal.signal(signal.SIGALRM,timeout)
outcomes = []
for rel in paths:
 p=task/rel; dest=out/(p.stem+'.json')
 if dest.exists(): raise RuntimeError('refuse overwrite')
 start=time.monotonic(); parent=resource.getrusage(resource.RUSAGE_SELF); child=resource.getrusage(resource.RUSAGE_CHILDREN)
 signal.alarm(300)
 try:
  with CandidateProxy(p,'search_crystals',300) as candidate:
   metrics=e.evaluate(candidate)
   if candidate.failure is not None: raise candidate.failure
  metrics=validate_metrics(metrics,'uncapped')
 except (CandidateError, TimeoutError) as exc:
  metrics=sanitized_candidate_failure(exc)
 except Exception as exc:
  metrics={'infrastructure_failure':True,'exception':repr(exc),'traceback':traceback.format_exc()}
 finally: signal.alarm(0)
 endp=resource.getrusage(resource.RUSAGE_SELF); endc=resource.getrusage(resource.RUSAGE_CHILDREN)
 row={'candidate':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'wall_seconds':time.monotonic()-start,'trusted_cpu_seconds':endp.ru_utime+endp.ru_stime-parent.ru_utime-parent.ru_stime,'reaped_children_cpu_seconds':endc.ru_utime+endc.ru_stime-child.ru_utime-child.ru_stime,'metrics':metrics}
 outcomes.append(metrics)
 dest.write_text(json.dumps(row,indent=2)); print(p.stem,row['wall_seconds'],metrics.get('combined_score'),metrics.get('valid'),flush=True)

if any(m.get("infrastructure_failure") for m in outcomes):
 raise SystemExit(2)
if any(m.get("valid") != 1.0 for m in outcomes):
 raise SystemExit(1)
print("Replay complete; this is not an admission or difficulty decision.")
