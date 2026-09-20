#!/usr/bin/env python3
"""Prepare a private, unassessed scientific-review template without any API call."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sle.discovery_review_packet import prepare_review_packet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = prepare_review_packet(args.episode, args.output_dir)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        # Do not print input contents or exception text from private reports.
        print("Review preparation failed; use a valid evidence report and a fresh private output directory.", file=sys.stderr)
        return 2
    print(json.dumps({"review_template": str(output), "scientific_review": "unassessed",
                      "source_modified": False, "model_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
