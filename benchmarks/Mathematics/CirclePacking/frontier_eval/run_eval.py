from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
INVALID = -1e18; TASK_DIR = Path(__file__).resolve().parent.parent
def _load(p, n):
    s=importlib.util.spec_from_file_location("c",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return getattr(m,n)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--candidate",required=True); ap.add_argument("--metrics-out",required=True); args=ap.parse_args()
    metrics={"combined_score":INVALID,"valid":0.0}
    try:
        sys.path.insert(0,str(TASK_DIR/"verification")); import evaluator as o
        f=_load(Path(args.candidate).resolve(),"pack_circles"); r=o.evaluate(f); metrics.update(r); metrics["raw_score"]=r.get("combined_score")
    except Exception as e: metrics["error_message"]=f"{type(e).__name__}: {e}"
    Path(args.metrics_out).write_text(json.dumps(metrics,indent=2,default=str)); print(json.dumps({k:metrics.get(k) for k in ("combined_score","valid")})); return 0
if __name__=="__main__": raise SystemExit(main())
