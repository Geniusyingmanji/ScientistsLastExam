"""An anchor copied out of a table nobody here can re-derive is an anchor that can be silently wrong.

`CirclePacking` normalises its score against the smallest known square side for each N, taken from
Packomania. One of the three numbers is wrong: it records 7.6274 for N=13, while `4 + 2*sqrt(3) =
7.4641` is a construction anyone can write down, and a recorded model run reached a verified valid
7.4632466. The score built on that anchor read 1.4406 - a new world record from a single proposal -
and the task was reclassified as saturated on the strength of it.

Nothing in the repository could have caught that, because the number is a literal. Every other
anchor here is either recomputed by the evaluator or shipped as a runnable reference, so it can be
checked by running it.

This does not forbid literal anchors - a published record is a legitimate thing to normalise
against, and re-deriving Packomania is not the job of a benchmark. It keeps the set of tasks that
depend on one small and deliberate, so that adding another is a decision somebody makes rather than
a line that slips in.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import list_tasks  # noqa: E402

ANCHOR_KEYS = re.compile(
    r"(best_known|best_side|record|reference_value|known_best|literature|published_|"
    r"target_record|optimum|sota)", re.IGNORECASE)

# Tasks that legitimately normalise against a published record, each one a deliberate choice.
# Adding to this list means accepting that the number cannot be checked by running anything here,
# so it needs a source in the task's `references/known_best.md` and a human who has read it.
# `sota` joined the pattern on 2026-09-03. Until then seven tasks normalised against `sota_ref`
# literals the guard never saw - five arriving in one PR, two (MatrixMultiplicationRank, CapSet)
# certified and present all along. The same review caught one of the five off by one:
# Superpermutation's n=8 anchor read 46204 where OEIS A180632 and Egan record 46205. A key name
# the pattern does not match is a literal nothing checks, which is the CirclePacking failure with
# a different spelling.
DECLARED_EXTERNAL_ANCHORS = {
    "AtmosphericChemistry/MethaneSourceAttribution",
    "Turbulence/WallClosureDiscovery",
    "Exoplanets/TransmissionSpectrumSpecies",
    "DiscreteGeometry/SpherePackingCertificate",
    "QuantumFoundations/BellBoundCertificate",
    "InformationTheory/ShannonCapacityCertificate",
    "Mathematics/NonlinearCodeRecords",
    "Optimization/CirclePacking",
    "Algorithm/MatrixMultiplicationRank",
    "Mathematics/CapSet",
    "Mathematics/CapSetFrontier",
    "Mathematics/KissingNumber",
    "Mathematics/NarrowAdmissibleTuple",
    "Mathematics/RamseyLowerBound",
    "Mathematics/Superpermutation",
    "Mathematics/ZarankiewiczMatrix",
    "Mathematics/DegreeDiameterGraph",
    "Mathematics/VanDerWaerdenColoring",
    "Mathematics/SchurPartition",
    "Mathematics/ErdosMinimumOverlap",
    "Mathematics/HeilbronnTrianglePacking",
    "Algorithm/TensorRank555",
    "Superconductivity/SuperconductorTcRecord",
}


def _hardcoded_anchors(source: str) -> list[tuple[str, float, int]]:
    """Anchor-shaped keys whose value is a numeric literal in the evaluator."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                        and ANCHOR_KEYS.search(key.value)
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, (int, float))
                        and not isinstance(value.value, bool)):
                    found.append((key.value, value.value, key.lineno))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                name = getattr(target, "id", "")
                if (name and ANCHOR_KEYS.search(name)
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, (int, float))
                        and not isinstance(node.value.value, bool)):
                    found.append((name, node.value.value, node.lineno))
    return found


class ExternalAnchorTests(unittest.TestCase):
    def test_only_declared_tasks_normalise_against_an_uncheckable_number(self):
        offenders = []
        for spec in list_tasks(None):
            path = spec.task_dir / "verification" / "evaluator.py"
            if not path.is_file():
                continue
            anchors = _hardcoded_anchors(path.read_text(encoding="utf-8"))
            # A literal zero is a failure-branch placeholder, not a record to normalise against.
            anchors = [row for row in anchors if row[1] != 0]
            if anchors and spec.task_id not in DECLARED_EXTERNAL_ANCHORS:
                offenders.append("%s: %s" % (spec.task_id, ", ".join(
                    "%s=%s at line %d" % row for row in anchors[:3])))
        self.assertEqual(
            offenders, [],
            "these tasks normalise against a numeric literal that nothing here can re-derive; "
            "either recompute the anchor, ship a runnable reference, or add the task to "
            "DECLARED_EXTERNAL_ANCHORS with a source in its references/known_best.md:\n"
            + "\n".join(offenders))

    def test_every_literal_anchor_is_recorded_with_a_source(self):
        """`references/anchors.json` is the ledger: one entry per literal, each with a source URL
        and the derivation from that source, and the evaluator's literal must match it.

        Two anchors were wrong in one review cycle - 7.6274 that Packomania never listed and 46204
        that OEIS records as 46205 - and both were plain numbers nobody could check by running
        anything. A ledger does not make a number true, but it makes it a claim with an address,
        and the match makes an evaluator edit that drifts from the ledger a test failure."""
        for task in sorted(DECLARED_EXTERNAL_ANCHORS):
            spec = next(s for s in list_tasks(None) if s.task_id == task)
            ledger_path = spec.task_dir / "references" / "anchors.json"
            self.assertTrue(ledger_path.is_file(),
                            "%s declares literal anchors but ships no references/anchors.json" % task)
            entries = (json.loads(ledger_path.read_text(encoding="utf-8")).get("anchors") or [])
            self.assertTrue(entries, "%s: anchors.json lists nothing" % task)
            for entry in entries:
                self.assertTrue(str(entry.get("source_url", "")).startswith("http"),
                                "%s: anchor %r has no source_url" % (task, entry.get("name")))
                self.assertTrue(entry.get("derivation"),
                                "%s: anchor %r has no derivation" % (task, entry.get("name")))
            values = [float(e["value"]) for e in entries]
            source = (spec.task_dir / "verification" / "evaluator.py").read_text(encoding="utf-8")
            for name, value, line in [r for r in _hardcoded_anchors(source) if r[1] != 0]:
                self.assertTrue(
                    any(abs(float(value) - v) <= 1e-9 * max(1.0, abs(v)) for v in values),
                    "%s: evaluator literal %s=%s (line %d) is not in references/anchors.json - "
                    "the ledger or the evaluator moved without the other" % (task, name, value, line))

    def test_a_declared_external_anchor_ships_its_source(self):
        for task in DECLARED_EXTERNAL_ANCHORS:
            spec = next(s for s in list_tasks(None) if s.task_id == task)
            record = spec.task_dir / "references" / "known_best.md"
            self.assertTrue(record.is_file(), "%s has no references/known_best.md" % task)
            text = record.read_text(encoding="utf-8")
            self.assertTrue(
                re.search(r"(source|Packomania|proven optimal|reference)", text, re.IGNORECASE),
                "%s normalises against a published record without naming where it came from"
                % task)


if __name__ == "__main__":
    unittest.main()
