"""Trusted sandbox entry point."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from sle.frontier_eval_entrypoint import run
EVAL_TIMEOUT_S = 300

if __name__ == "__main__":
    raise SystemExit(run("StructuralBiology/ProteinDistanceGeometry", ROOT, timeout=EVAL_TIMEOUT_S))
