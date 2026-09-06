"""Shared thin CLI used by task-local frontier_eval/run_eval.py wrappers."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

def run(task_id: str, root: Path, timeout: float = 300.0) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--candidate",required=True); parser.add_argument("--metrics-out",required=True); parser.add_argument("--timeout",type=float,default=timeout)
    args=parser.parse_args(); metrics={"combined_score":-1e18,"valid":0.0}
    try:
        done=subprocess.run([sys.executable,"-m","sle","eval","--task",task_id,"--allow-uncertified",
            "--candidate",str(Path(args.candidate).resolve()),"--timeout",str(args.timeout)],
            cwd=str(root),capture_output=True,text=True,timeout=args.timeout+120,env={**os.environ,"PYTHONPATH":str(root)})
        if done.returncode: raise RuntimeError("sle eval failed")
        metrics.update(json.loads(done.stdout)); metrics.setdefault("raw_score",metrics.get("combined_score"))
    except Exception as exc:
        metrics["error_message"]=type(exc).__name__
    Path(args.metrics_out).write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    print(json.dumps({k:metrics.get(k) for k in ("combined_score","valid")})); return 0
