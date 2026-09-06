"""Short reference proofs. Lengths are the score-1 anchors."""
from copy import deepcopy

# Loaded from the same compiled Hilbert terms as solution.py, without padding.
import json
from pathlib import Path

def build_proofs(problem):
    path = Path(__file__).with_name("short_proofs.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = {
        "identity": raw["I"],
        "conjunction_swap": raw["swap"],
        "packed_composition": raw["comp"],
        "modus_ponens_closed": raw["eval"],
    }
    return {name: deepcopy(proof) for name, proof in mapping.items()}
