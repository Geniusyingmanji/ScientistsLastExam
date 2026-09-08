"""Reconstruct public SorterHunter networks; this is a lookup/replication probe.

Bert Dobbelaere, MIT license. Attribution, source commits and SHA-256 hashes:
../references/reference_sources.json and ../references/SorterHunter-LICENSE.txt.
This program is NOT a truth-blind search reference or evidence of model difficulty.
Run: python verification/reference_reconstruction.py 13
"""
from pathlib import Path
import argparse
import json


def build_network(n: int):
    paths = sorted((Path(__file__).parent / "data").glob(f"Sort_{n}_*.json"))
    if len(paths) != 1:
        raise ValueError("unsupported network size")
    data = json.loads(paths[0].read_text())
    return [list(pair) for pair in data["nw"]]


def export_source():
    """Single-file public-data candidate suitable for the isolated RPC worker."""
    data = {n: build_network(n) for n in range(13, 18)}
    license_text = (Path(__file__).resolve().parents[1] / "references/SorterHunter-LICENSE.txt").read_text()
    notice = "# Public SorterHunter reconstruction; not an original search result.\n"
    notice += "".join("# " + line + "\n" for line in license_text.splitlines())
    return notice + "NETWORKS = " + repr(data) + "\n\ndef build_network(n):\n    return [list(pair) for pair in NETWORKS[n]]\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", nargs="?", type=int)
    parser.add_argument("--export", type=Path, help="write a self-contained reference candidate")
    args = parser.parse_args()
    if (args.n is None) == (args.export is None):
        parser.error("give n or --export PATH, exclusively")
    if args.export is not None:
        args.export.write_text(export_source(), encoding="utf-8")
    else:
        print(json.dumps(build_network(args.n)))
