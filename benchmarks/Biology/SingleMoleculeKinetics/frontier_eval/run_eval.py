"""Trusted sandbox entry point."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from sle.frontier_eval_entrypoint import run
if __name__ == "__main__":
    raise SystemExit(run("Biophysics/SingleMoleculeKinetics", ROOT))
