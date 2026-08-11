#!/usr/bin/env python3
"""Audit every task against the standards this benchmark claims for itself.

Three things were asked of a task when this inventory was designed: a real scientific grounding,
a fit with the iterative-self-improvement question, and an evaluation that can actually measure
either. `scripts/audit_tasks.py` checks that a task card is well formed and
`scripts/audit_task_maturity.py` checks that its evidence is current and bound. Neither asks
whether the task is any good, and that is what this reports.

Each standard below is mechanically checkable from the task package. None of them is a judgement
call dressed up as a metric, and none is a proxy for difficulty:

  oracle_is_community      the evaluator imports a domain toolkit (RDKit, Stim, PySCF, ...) rather
                           than reimplementing the science in NumPy. An author reimplementation
                           means a score measures agreement with that author's code.
  anchor_recomputed        the reference value is recomputed by the oracle at evaluation time
                           rather than pasted in as a constant. A pasted constant cannot be
                           checked and silently rots against library versions.
  has_reference_record     `references/known_best.md` exists. Required for uncapped scoring,
                           where a score above 1.0 is a claim about the state of the art.
  has_sealed_split         the evaluator holds regimes back from the development score, so a
                           candidate tuned to what it can see loses ground on what it cannot.
  declares_shortcuts       `known_shortcuts` is present and specific, not empty boilerplate.
  cites_literature         the card carries resolvable citations (DOI or arXiv), not a prose
                           gesture at "the literature".
  states_invariants        the card lists properties the oracle must satisfy, which is what makes
                           an independent reimplementation checkable.
  difficulty_parameterized the task exposes a difficulty level or generates instances
                           procedurally, so saturating it does not retire it.
  domain_reviewed          an external domain expert has signed off. Nothing in this inventory
                           has yet.

The report is per task and per standard. It deliberately does not produce a single score: these
are different kinds of defect and averaging them would hide whichever one matters.

Usage:
    python scripts/audit_benchmark_standards.py --output /tmp/standards.json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from frontier_science.registry import list_tasks  # noqa: E402

# Domain toolkits whose presence means the oracle is not a private reimplementation. NumPy and
# SciPy are excluded on purpose: they are numerical infrastructure, not scientific authority.
COMMUNITY_PACKAGES = {
    "rdkit", "stim", "pymatching", "pyscf", "ase", "biopython", "Bio", "openmm", "mdtraj",
    "vienna", "RNA", "cobra", "astropy", "scikit-bio", "skbio", "pysam", "gpaw", "quspin",
    "qutip", "qiskit", "cirq", "openbabel", "pybel", "networkx", "sympy", "pymatgen",
    "spglib", "phonopy", "lammps", "gromacs", "obspy", "cartopy", "metpy", "xarray",
}

STANDARDS = (
    "oracle_is_community",
    "anchor_recomputed",
    "has_reference_record",
    "has_sealed_split",
    "declares_shortcuts",
    "cites_literature",
    "states_invariants",
    "difficulty_parameterized",
    "domain_reviewed",
)

CITATION = re.compile(r"(doi:|10\.\d{4,}/|arxiv[:/]|\d{4}\.\d{4,5})", re.IGNORECASE)


def imported_modules(source: str) -> set[str]:
    """Top-level module names actually imported, from the parse tree rather than by substring.

    Substring matching is what made an earlier scan report every evaluator as using ASE: the
    letters appear in "case", "base" and "database".
    """
    names: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            # `importlib.import_module("rdkit")` and `__import__("stim")`
            target = node.func
            label = getattr(target, "attr", None) or getattr(target, "id", None)
            if label in {"import_module", "__import__"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.add(first.value.split(".")[0])
    return names


def evaluator_sources(task_dir: Path) -> str:
    parts = []
    for path in sorted((task_dir / "verification").glob("*.py")):
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(parts)


def check(task_dir: Path, card: dict) -> dict[str, bool | None]:
    evaluator = task_dir / "verification" / "evaluator.py"
    source = evaluator.read_text(encoding="utf-8") if evaluator.is_file() else ""
    all_source = evaluator_sources(task_dir)
    modules = imported_modules(all_source)

    review = card.get("review") or {}
    normalization = card.get("normalization") or {}
    shortcuts = str(card.get("known_shortcuts") or "").strip()
    citations = card.get("citations") or []
    invariants = card.get("invariants") or []

    citation_text = json.dumps(citations)
    reference_text = " ".join(str(normalization.get(key, "")) for key in
                              ("reference", "baseline", "score", "measured_anchors"))

    return {
        "oracle_is_community": bool(modules & COMMUNITY_PACKAGES),
        # A recomputed anchor is one the evaluator derives while scoring. The signals are a
        # reference implementation shipped under verification/, or normalization prose that says
        # the reference is measured rather than quoted.
        "anchor_recomputed": bool(
            len(list((task_dir / "verification").glob("*.py"))) > 1
            or re.search(r"recomput|measured|at evaluation time|per run",
                         reference_text, re.IGNORECASE)
        ),
        "has_reference_record": (task_dir / "references" / "known_best.md").is_file(),
        "has_sealed_split": bool(
            re.search(r"\bSEALED_|\bsealed_|heldout|held_out|validation_specs|VALIDATION_",
                      source)
        ),
        "declares_shortcuts": len(shortcuts) >= 80,
        "cites_literature": bool(CITATION.search(citation_text)),
        "states_invariants": len(invariants) >= 2,
        "difficulty_parameterized": bool(
            re.search(r"^DIFFICULTY\s*=", source, re.MULTILINE)
            or re.search(r"_LADDER\b|def _regimes\(|_at_difficulty\(", source)
        ),
        # Every value in this inventory starts with "pending_external", and 17 of them append a
        # field name - `pending_external_photovoltaics`. An exact-match exclusion let those
        # through and reported 28% reviewed when the true figure is zero.
        "domain_reviewed": bool(
            (value := str(review.get("domain", "")).strip())
            and not value.startswith(("pending", "none", "todo", "planned"))
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--show", default="all", choices=["all", "failing"])
    args = ap.parse_args(argv)

    rows = []
    for spec in list_tasks(None):
        card_path = spec.task_dir / "TASK_CARD.yaml"
        try:
            card = yaml.safe_load(card_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            card = {}
        result = check(spec.task_dir, card)
        rows.append({
            "task": spec.task_id,
            "score_mode": str(spec.metadata.get("score_mode", "clipped")),
            "scientific_role": str(spec.metadata.get("scientific_role", "")),
            "standards": result,
            "met": sum(1 for value in result.values() if value),
        })
    rows.sort(key=lambda r: (-r["met"], r["task"]))

    header = "".join("%-4s" % s[:3] for s in STANDARDS)
    print("%-36s %-9s %s met" % ("task", "score", header))
    print("-" * (36 + 10 + len(header) + 4))
    for row in rows:
        if args.show == "failing" and row["met"] == len(STANDARDS):
            continue
        cells = "".join(
            "%-4s" % ("yes" if row["standards"][s] else " . ") for s in STANDARDS)
        print("%-36s %-9s %s %d" % (
            row["task"].split("/")[-1][:36], row["score_mode"], cells, row["met"]))

    print()
    print("legend:", ", ".join("%s=%s" % (s[:3], s) for s in STANDARDS))
    print()
    totals = Counter()
    for row in rows:
        for standard, value in row["standards"].items():
            if value:
                totals[standard] += 1
    print("inventory of %d tasks, how many meet each standard:" % len(rows))
    for standard in STANDARDS:
        count = totals[standard]
        print("  %-26s %3d / %d  (%3.0f%%)"
              % (standard, count, len(rows), 100.0 * count / len(rows)))

    uncapped_without_record = [
        row["task"] for row in rows
        if row["score_mode"] == "uncapped" and not row["standards"]["has_reference_record"]
    ]
    if uncapped_without_record:
        print()
        print("uncapped scoring with no reference record (a score above 1.0 would be a claim "
              "with nothing behind it):")
        for name in uncapped_without_record:
            print("   ", name)

    Path(args.output).write_text(json.dumps({
        "schema_version": 1,
        "note": "standards are reported separately on purpose; averaging them would hide "
                "whichever defect matters for a given use",
        "standards": list(STANDARDS),
        "task_count": len(rows),
        "met_counts": {s: totals[s] for s in STANDARDS},
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print()
    print("report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
