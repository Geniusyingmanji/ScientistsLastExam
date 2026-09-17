"""A reference at its own ceiling is a task with nothing left to win, and nothing checks it.

The canary audit feeds each oracle degenerate candidates and asks whether any earns credit - the
bottom of a task. The shortcut contract asks whether a cheap candidate reaches the reference - a
margin a task owner declares. Neither asks whether the declared reference is already the maximum
the task's own contract admits, which is the shape the maintainer found by hand in five reviews:
a trivial strategy that ties such a reference measures exactly what the reference measures, which
is nothing about a searcher.

Two of those five are reproduced here as full regression tests, because they are the strongest
form of the claim - a task-specific trivial strategy that ties the reference exactly. The other
three are covered by the inventory test, since their trivial strategy is not expressible as a
generic probe (their references are at the ceiling, which the audit measures directly).
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sle.registry import find_task, list_tasks  # noqa: E402
from scripts.saturation_audit import (  # noqa: E402
    AT_CEILING_DECLARED,
    AT_CEILING_UNDECLARED,
    HEADROOM,
    MIGRATION,
    NOT_MEASURED,
    audit_task,
    declares_ceiling,
    declares_saturation,
    reference_path,
)

# The flagged set, resolved once. Re-measuring every task would cost one full oracle evaluation
# each - minutes, dominated by the flagship contracts - and would run for every reviewer. The
# tests below measure exactly the tasks whose status is in question, and the word test covers the
# rest of the inventory cheaply. Measured scores were produced by `scripts/saturation_audit.py`.
FLAGGED = (
    "CausalDiscovery/SurvivorshipConfoundedDesign",
    "Gravitation/PTAHellingsDowns",
    "MaterialsScience/QuinaryConvexHull",
    "Oceanography/AMOCTippingRefusal",
    "ParticlePhysics/LookElsewhereAnomaly",
)


def _load(name: str, path: Path):
    module_spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


class SaturationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(MIGRATION.read_text(encoding="utf-8"))["tasks"]

    def test_each_pinned_task_measures_at_the_ceiling_and_is_undeclared(self):
        """The measured verdict each inventory entry claims, re-derived rather than trusted.

        A task whose reference hardens below the ceiling, or whose card starts declaring the
        verdict, stops being flagged here and has to leave the inventory - so the two cannot drift.
        """
        for task_id in FLAGGED:
            with self.subTest(task=task_id):
                spec = find_task(task_id, include_uncertified=True)
                row = audit_task(spec)
                self.assertEqual(row["status"], AT_CEILING_UNDECLARED, row)
                self.assertGreaterEqual(row["combined_score"], 1.0 - 0.01)
                self.assertIsNone(declares_saturation(spec))
                self.assertIn(task_id, self.inventory)
                self.assertEqual(
                    self.inventory[task_id]["measured_combined_score"], row["combined_score"])

    def test_a_denial_or_an_unknown_is_not_a_declaration(self):
        """The classifier must read an affirmation, not a substring.

        The first version of this test did not exist and the classifier matched "saturat" as a
        substring: adversarial review measured that "not_saturated", "unsaturated",
        "not_saturated_pending_review", "desaturated" and "saturation_unknown" all counted as
        declarations, which would move a task out of the defect inventory (at_ceiling_undeclared)
        into at_ceiling_declared and silently empty it. A card that DENIES saturation, or says it
        is unknown, is the exact opposite of declaring it.
        """
        from scripts.saturation_audit import _declares  # noqa: PLC0415
        for status in ("not_saturated", "unsaturated", "not_saturated_pending_review",
                       "desaturated", "saturation_unknown", "not_tested", "", "pending"):
            with self.subTest(status=status):
                self.assertFalse(_declares(status), status)
        for status in ("saturated", "saturated_for_current_frontier",
                       "Saturated_For_Current_Frontier"):
            with self.subTest(status=status):
                self.assertTrue(_declares(status), status)

    def test_the_inventory_is_exactly_the_flagged_set_with_no_stale_entries(self):
        """Listing is not a pass - the policy says so in as many words.

        Every entry must correspond to a real task and carry a reason, and the inventory must not
        grow a name no test measures: an unmeasured entry is a task quietly added, which is the
        failure mode this pin exists to catch.
        """
        self.assertEqual(sorted(self.inventory), sorted(FLAGGED))
        for task_id, record in self.inventory.items():
            self.assertEqual(record["status"], "pending", task_id)
            self.assertTrue(record.get("reason"), task_id)
            find_task(task_id, include_uncertified=True)

    def test_the_cheap_word_test_is_broader_than_the_structured_one(self):
        """The trigger over-approximates deliberately, and never under-approximates.

        `--declared-only` exists so a reviewer can re-measure only what changed without paying for
        a full sweep. It has to err toward including a task: all five flagged tasks carry the
        ceiling sentence in prose while their structured status says nothing, so a word test that
        only matched the structured field would miss exactly the gap this audit closes.
        """
        for spec in list_tasks(None):
            with self.subTest(task=spec.task_id):
                if declares_saturation(spec) is not None:
                    self.assertTrue(declares_ceiling(spec), spec.task_id)
        for task_id in FLAGGED:
            with self.subTest(flagged=task_id):
                spec = find_task(task_id, include_uncertified=True)
                self.assertTrue(declares_ceiling(spec), task_id)
                self.assertIsNone(declares_saturation(spec), task_id)

    def test_a_structured_declaration_is_what_separates_honest_from_silent(self):
        """A prose sentence is not a field a reader can act on.

        Five of the six cards at the ceiling carry the sentence "The reference sits at the scoring
        ceiling this contract admits" in `known_best.md` while `long_horizon.status` still reads
        `not_tested`. That gap is the defect: nothing that reads the tree can tell an on-ramp from
        a hard task. A card that records the verdict structurally is classified separately and is
        not an inventory entry.
        """
        honest = find_task("SystemsBiology/EnzymeKineticsLaw", include_uncertified=True)
        self.assertIn("saturat", (declares_saturation(honest) or "").lower())
        self.assertNotIn(honest.task_id, self.inventory)
        row = audit_task(honest)
        self.assertEqual(row["status"], AT_CEILING_DECLARED)

    def test_an_unmeasured_reference_is_never_a_pass(self):
        """Thirty-nine tasks keep the reference inside the evaluator, where nothing can score it.

        Those tasks have no submitable reference file, and the audit must say so rather than call
        them healthy - a check that fails open is worse than no check. The three shapes are
        checked directly rather than by sweeping the inventory, which would cost an oracle
        evaluation per task.
        """
        # An evaluator-internal reference: nothing submitable to score.
        internal = find_task("PopulationGenetics/DemographicSFS", include_uncertified=True)
        row = audit_task(internal)
        self.assertEqual(row["status"], NOT_MEASURED)
        self.assertIn("evaluator-internal", row["detail"])
        # More than one reference-named candidate: the audit refuses to guess.
        ambiguous = find_task(
            "QuantumErrorCorrection/QuantumErrorDecoder", include_uncertified=True)
        self.assertEqual(audit_task(ambiguous)["status"], NOT_MEASURED)
        # Unmeasured statuses are distinct from the two verdicts, so neither can be read as one.
        self.assertNotEqual(NOT_MEASURED, AT_CEILING_DECLARED)
        self.assertNotEqual(NOT_MEASURED, HEADROOM)
        self.assertNotEqual(NOT_MEASURED, AT_CEILING_UNDECLARED)

    def test_an_uncapped_task_is_not_compared_to_a_normalised_ceiling(self):
        """1.0 is only a ceiling where the contract clips to one.

        An uncapped task's maximum is a number the task does not publish, and one shipped
        reference already scores above 1.0. No submitable reference on an uncapped task may
        receive a ceiling verdict, whether the reason recorded is the score mode or an oracle
        that would not import on this host - both are unmeasured, and neither is a pass.
        """
        uncapped = [spec for spec in list_tasks(None)
                    if str(spec.metadata.get("score_mode")) == "uncapped"
                    and reference_path(spec) is not None]
        self.assertTrue(uncapped, "expected uncapped tasks that ship a reference")
        reasons = []
        for spec in uncapped:
            with self.subTest(task=spec.task_id):
                row = audit_task(spec)
                self.assertEqual(row["status"], NOT_MEASURED)
                reasons.append(row["detail"])
        # At least one was reached far enough to be refused for its score mode rather than for a
        # missing dependency, so the refusal is about the ceiling and not only about the host.
        self.assertTrue(any("uncapped" in detail for detail in reasons), reasons)

    def test_the_reference_lookup_refuses_to_guess_between_candidates(self):
        """A task with two reference-named files is reported unmeasured, not silently mis-scored.

        Four tasks in the tree ship more than one candidate exposing the entrypoint - a reference
        and an ablation. Choosing one arbitrarily would report the ablation's saturation as the
        task's, which is the error this refusal exists to prevent.
        """
        spec = find_task("QuantumErrorCorrection/QuantumErrorDecoder", include_uncertified=True)
        self.assertIsNone(reference_path(spec))
        self.assertEqual(audit_task(spec)["status"], NOT_MEASURED)

    def test_the_two_reproducible_trivial_strategies_tie_their_references(self):
        """The task-specific claims, executed rather than asserted in prose.

        `PTAHellingsDowns`: `frontier_eval/metadata.yaml:12` says the reference publishes
        Hellings-Downs only when it "uniquely" beats monopole, dipole and uncorrelated, but the
        oracle's `_metrics` tests `kind ==` and nothing else. A four-kernel argmin with no margin
        at all therefore reaches the same 1.0.

        `AMOCTippingRefusal`: the reference spends its probe budget on a hysteresis test; a
        zero-probe constant-year heuristic gated on the historical endpoint reaches the same 1.0,
        so the probes buy nothing.
        """
        # --- PTAHellingsDowns -------------------------------------------------------------
        pta = find_task("Gravitation/PTAHellingsDowns", include_uncertified=True)
        oracle = _load("sat_pta_oracle", pta.task_dir / "verification/evaluator.py")
        reference = _load("sat_pta_ref", pta.task_dir / "verification/reference_kernel.py")
        pta_reference = oracle.evaluate(reference.interpret_correlations)

        def _orf_hd(theta):
            x = 0.5 * (1.0 - math.cos(theta))
            x = min(1.0, max(x, 1e-15))
            return 0.5 - 0.25 * x + 1.5 * x * math.log(x)

        def no_margin_argmin(problem, bootstrap):
            del bootstrap
            theta = [float(t) for t in problem["theta_rad"]]
            rho = [float(r) for r in problem["rho"]]
            templates = {
                "hellings_downs": [_orf_hd(t) for t in theta],
                "monopole": [1.0] * len(theta),
                "dipole": [math.cos(t) for t in theta],
                "uncorrelated": [0.0] * len(theta),
            }
            sse = {name: sum((a - b) ** 2 for a, b in zip(rho, pred))
                   for name, pred in templates.items()}
            best = min(sse, key=lambda key: sse[key])
            if best != "hellings_downs":
                return {"abstain": True, "confidence": 0.5}
            return {"abstain": False, "kernel": "hellings_downs", "confidence": 0.5}

        pta_trivial = oracle.evaluate(no_margin_argmin)
        self.assertEqual(pta_trivial["combined_score"], pta_reference["combined_score"])
        self.assertAlmostEqual(pta_reference["combined_score"], 1.0)

        # --- AMOCTippingRefusal -----------------------------------------------------------
        amoc = find_task("Oceanography/AMOCTippingRefusal", include_uncertified=True)
        oracle = _load("sat_amoc_oracle", amoc.task_dir / "verification/evaluator.py")
        reference = _load("sat_amoc_ref", amoc.task_dir / "verification/reference_probe.py")
        amoc_reference = oracle.evaluate(reference.interpret_amoc)

        def constant_year(problem, probe):
            del probe
            if float(list(problem["historical_amoc"])[-1]) > 0.3:
                return {"abstain": False, "has_tipping": True,
                        "collapse_year": 2098.0, "confidence": 0.8}
            return {"abstain": True, "confidence": 0.5}

        amoc_trivial = oracle.evaluate(constant_year)
        self.assertEqual(amoc_trivial["combined_score"], amoc_reference["combined_score"])
        self.assertAlmostEqual(amoc_reference["combined_score"], 1.0)

    def test_the_dropped_replicate_gate_is_worth_half_of_quinary_convex_hull(self):
        """The reference at 1.0 is only interesting if the work is separable from the tie.

        `QuinaryConvexHull`'s reference replicates energies and refuses a catalog that does not
        reproduce; removing just that gate drops the hull computation from 1.0 to 0.5. The gate is
        therefore half the score, and a strategy that ties the witness is not automatically
        equivalent to it - which is why the audit reports the observation rather than a verdict.
        """
        spec = find_task("MaterialsScience/QuinaryConvexHull", include_uncertified=True)
        oracle = _load("sat_qh_oracle", spec.task_dir / "verification/evaluator.py")
        reference = _load("sat_qh_ref", spec.task_dir / "verification/reference_hull.py")
        self.assertAlmostEqual(
            oracle.evaluate(reference.recover_hull)["combined_score"], 1.0)

        def hull_only(problem, relax):
            catalog = list(problem["catalog"])
            n_atoms = int(problem["n_atoms"])
            elements = list(problem["elements"])
            budget = int(problem["relax_budget_calls"])

            def composition(name):
                counts = []
                rest = name
                for element in elements:
                    rest = rest[len(element):]
                    digits = ""
                    while rest and rest[0].isdigit():
                        digits += rest[0]
                        rest = rest[1:]
                    counts.append(int(digits))
                return np.array(counts, dtype=float) / float(n_atoms)

            unaries = [n for n in catalog if float(np.max(composition(n))) >= 1 - 1e-12]
            others = [n for n in catalog if n not in unaries]
            energies = {}
            for name in unaries + others:
                if len(energies) >= budget:
                    break
                try:
                    energies[name] = float(relax(name))
                except Exception:
                    break
            names = [n for n in catalog if n in energies]
            comps = np.vstack([composition(n) for n in names])
            evec = np.array([energies[n] for n in names])
            points = np.column_stack([comps[:, :4], evec])
            hull = ConvexHull(points)
            lower = hull.simplices[hull.equations[:, -2] < -1e-10]
            vertices = set(int(i) for i in lower.ravel())
            claimed = [n for i, n in enumerate(names) if i in vertices and n not in unaries]
            return {"abstain": False, "stable": claimed, "confidence": 0.88}

        self.assertAlmostEqual(
            oracle.evaluate(hull_only)["combined_score"], 0.5, places=6)


if __name__ == "__main__":
    unittest.main()
