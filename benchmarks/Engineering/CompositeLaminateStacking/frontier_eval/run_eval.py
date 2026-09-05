"""Secure black-box wrapper for CompositeLaminateStacking."""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

TASK_ID = "AerospaceStructures/CompositeLaminateStacking"
ROOT = Path(__file__).resolve().parents[4]
INVALID = -1e18


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--candidate",required=True); parser.add_argument("--metrics-out",required=True); parser.add_argument("--timeout",type=float,default=300)
    args=parser.parse_args(); metrics={"combined_score":INVALID,"valid":0.0}
    try:
        done=subprocess.run([sys.executable,"-m","sle","eval","--task",TASK_ID,"--allow-uncertified","--candidate",str(Path(args.candidate).resolve()),"--timeout",str(args.timeout)],cwd=str(ROOT),capture_output=True,text=True,timeout=args.timeout+120,env={**os.environ,"PYTHONPATH":str(ROOT)})
        if done.returncode != 0: raise RuntimeError("sle eval exited %d: %s" % (done.returncode,(done.stderr or "")[-500:]))
        result=json.loads(done.stdout); metrics.update(result); metrics.setdefault("raw_score",result.get("combined_score"))
    except Exception as exc:
        metrics["error_message"]="%s: %s" % (type(exc).__name__,exc)
    Path(args.metrics_out).write_text(json.dumps(metrics,indent=2,default=str),encoding="utf-8")
    print(json.dumps({k:metrics.get(k) for k in ("combined_score","valid")})); return 0


if __name__ == "__main__": raise SystemExit(main())
