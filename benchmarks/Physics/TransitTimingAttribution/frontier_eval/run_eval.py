from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
INVALID=-1e18
TASK_DIR=Path(__file__).resolve().parent.parent
def _load(path,name):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True); ap.add_argument('--metrics-out',required=True); args=ap.parse_args()
    m={'combined_score':INVALID,'valid':0.0}
    try:
        o=_load(TASK_DIR/'verification'/'evaluator.py','oracle'); c=_load(Path(args.candidate).resolve(),'candidate')
        r=o.evaluate(c.attribute_ttv); m.update(r); m['raw_score']=r.get('combined_score')
    except Exception as e: m['error_message']=f'{type(e).__name__}: {e}'
    Path(args.metrics_out).write_text(json.dumps(m,indent=2,default=str)); print(json.dumps({k:m.get(k) for k in ('combined_score','valid')})); return 0
if __name__=='__main__': raise SystemExit(main())
