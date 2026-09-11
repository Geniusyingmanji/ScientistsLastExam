"""Discovery-contract pins for LDMismatchFineMapping.

The public score is mechanism, normalised so that declining every world is exactly zero and so is
naming one fixed variant everywhere. An unresolved world is the unsupported case: declining it is
correct, declining everything is not; a typed world is determinable and its causal set is the
answer.

Six of these tests pin what the construction checkpoints found the hard way: that every
single-variant world carries a proxy the panel does not see, that every masked variant is below
genome-wide significance, that every world carries exactly one secondary hit in a band no
region-wide selection line separates, that the weakest of three signals is buried under proxies,
that resolvability is a likelihood gap and not a threshold, and that the rows are not free.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _sandbox_tools import skip_unless_sandbox
from sle.secure_eval import CandidateProxy

TASK = ROOT / "benchmarks/Biology/LDMismatchFineMapping"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fit(z, R, S):
    S = list(S)
    return float(z[S] @ np.linalg.solve(R[np.ix_(S, S)], z[S]))


class LDMismatchFineMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evaluator = _load(TASK / "verification/evaluator.py", "ld_mismatch_oracle")
        cls.baseline = _load(TASK / "solution.py", "ld_mismatch_baseline")
        cls.reference = _load(TASK / "verification/reference_conditional_rows.py",
                              "ld_mismatch_reference")
        cls.complete_reference = _load(TASK / "verification/reference_masking_aware.py",
                                       "ld_mismatch_complete_reference")
        cls.worlds = [cls.evaluator._world(spec)
                      for spec in cls.evaluator.DEVELOPMENT_WORLDS + cls.evaluator.HELDOUT_WORLDS]

    def test_blanket_refusal_in_both_forms_and_a_fixed_variant_all_score_zero(self):
        for submission in ({"verdict": "unresolved", "confidence": 1.0}, {"abstain": True}):
            metrics = self.evaluator.evaluate(lambda _p, _r, s=submission: dict(s))
            self.assertEqual(metrics["valid"], 1.0, submission)
            self.assertEqual(metrics["combined_score"], 0.0, submission)
            self.assertEqual(metrics["development_correct_refusal_rate"], 1.0, submission)
        for confidence in (0.9, 0.2):
            # A wrong variant is a false discovery whatever its confidence (variant 1 is causal
            # in no graded world).
            fixed = self.evaluator.evaluate(
                lambda _p, _r, c=confidence: {"verdict": "typed", "causal": [1], "effects": [0.1], "confidence": c})
            self.assertEqual(fixed["valid"], 1.0, confidence)
            self.assertEqual(fixed["combined_score"], 0.0, confidence)
            self.assertEqual(fixed["development_false_discovery_rate"], 1.0, confidence)

    def test_the_marginal_scan_is_not_enough(self):
        """The top variant by |z| with its marginal effect, never declining: right in the
        single-variant worlds and wrong everywhere else."""
        def top(problem, _r):
            j = int(np.argmax(np.abs(problem["z"])))
            return {"verdict": "typed", "causal": [j],
                    "effects": [float(problem["z"][j] * problem["standard_error"][j])], "confidence": 0.9}
        metrics = self.evaluator.evaluate(top)
        self.assertEqual(metrics["valid"], 1.0)
        self.assertLess(metrics["combined_score"], 0.4)

    def test_every_single_world_has_a_proxy_the_panel_does_not_see(self):
        """The property the single-variant worlds are built on: a genome-wide significant proxy
        at cohort r-squared 0.3 or more that the panel puts at 0.1 or less, so clumping on the
        panel reports it as a second signal."""
        ev = self.evaluator
        singles = [w for w in self.worlds if w["kind"] == "single"]
        self.assertEqual(len(singles), 4)
        for w in singles:
            j = w["causal"][0]
            R, R_ref, z = w["R"], w["R_ref"], w["z"]
            traps = [p for p in range(ev.N_SNP) if p != j
                     and R[j, p] ** 2 >= ev.TRAP_R2 and R_ref[j, p] ** 2 <= ev.TRAP_REF_R2
                     and abs(z[p]) >= ev.GENOME_WIDE_Z]
            self.assertTrue(traps, w["seed"])
            problem = ev._public_problem(w)
            claimed = self.baseline.fine_map(problem, ev._Campaign(w).oracle())["causal"]
            self.assertFalse(set(claimed) <= set(w["causal"]), (w["seed"], claimed))

    def test_every_masked_variant_is_below_genome_wide_significance(self):
        """The partner's marginal signal is hidden by the lead's through LD and an opposite sign;
        its conditional signal given the lead's exact row is in the secondary-hit band."""
        ev = self.evaluator
        masked = [w for w in self.worlds if w["kind"] == "masked"]
        self.assertEqual(len(masked), 5)
        for w in masked:
            lead, partner = sorted(w["causal"], key=lambda v: -abs(w["z"][v]))
            self.assertEqual(lead, int(np.argmax(np.abs(w["z"]))), w["seed"])
            self.assertLess(abs(w["z"][partner]), ev.GENOME_WIDE_Z, w["seed"])
            self.assertLess(w["truth_beta"][lead] * w["truth_beta"][partner], 0.0, w["seed"])
            self.assertLessEqual(abs(w["R"][lead, partner]), ev.MASK_LD[1], w["seed"])
            chi = ev._conditional_chi(w["z"], w["R"], [lead])
            self.assertEqual(partner, w["secondary"], w["seed"])
            self.assertTrue(ev.SECONDARY_CHI[0] <= chi[partner] <= ev.SECONDARY_CHI[1], w["seed"])
            # nothing else given the lead comes near the band: the partner is resolvable
            chi[w["causal"]] = -np.inf
            self.assertLess(chi.max(), ev.SECONDARY_CHI[0], w["seed"])

    def test_every_world_carries_exactly_one_secondary_hit(self):
        """In a masked world the secondary hit is the real partner, in LD with the lead. In every
        other world it is a decoy in weak LD with every causal variant, and it is the only
        non-causal variant in the band. The band straddles the plain BIC line and the Bonferroni
        line for the sixty typed variants and stays below the extended BIC penalty, so no
        region-wide selection line takes every partner without taking decoys."""
        ev = self.evaluator
        lo, hi = ev.SECONDARY_CHI
        self.assertLess(lo, np.log(ev.N_GWAS))
        self.assertLess(11.16, hi)
        self.assertLess(hi, np.log(ev.N_GWAS) + 2 * np.log(ev.N_SNP))
        for w in self.worlds:
            if w["kind"] == "masked":
                continue
            causal = w["causal"] or w["unresolved_causal"]
            chi = ev._conditional_chi(w["z"], w["R"], causal)
            if w["duplicate"] is not None:
                chi[list(w["duplicate"])] = -np.inf
            hits = [int(u) for u in np.flatnonzero(chi >= lo - ev.SECONDARY_MARGIN)]
            self.assertEqual(hits, [w["secondary"]], w["seed"])
            self.assertLessEqual(chi[w["secondary"]], hi, w["seed"])
            self.assertNotIn(w["secondary"], causal, w["seed"])
            self.assertLessEqual(np.abs(w["R"][w["secondary"], causal]).max(), ev.DECOY_LD_MAX, w["seed"])

    def test_the_weakest_of_three_signals_is_buried(self):
        ev = self.evaluator
        multi = [w for w in self.worlds if w["kind"] == "multi"]
        self.assertEqual(len(multi), 3)
        for w in multi:
            order = list(np.argsort(-np.abs(w["z"])))
            weakest = max(order.index(j) for j in w["causal"])
            self.assertGreaterEqual(weakest, ev.MULTI_WEAKEST_RANK, w["seed"])
            # rows for the six largest |z| never reach it
            self.assertGreaterEqual(weakest, ev.ROW_BUDGET, w["seed"])

    def test_resolvability_is_a_likelihood_gap(self):
        """Twice the maximised log-likelihood of a configuration under the cohort's own LD is
        z_S' R_SS^-1 z_S. Typed worlds have the truth at least RESOLVED_GAP ahead of every
        single-member swap; unresolved worlds have the pair within UNRESOLVED_GAP and far ahead of
        everything else, and the panel shows the pair as an ordinary resolvable proxy."""
        ev = self.evaluator
        for w in self.worlds:
            R, z = w["R"], w["z"]
            if w["kind"] == "unresolved":
                i, j = w["duplicate"]
                causal = w["unresolved_causal"]
                swapped = [i + j - v if v in (i, j) else v for v in causal]
                self.assertLess(abs(_fit(z, R, causal) - _fit(z, R, swapped)), ev.UNRESOLVED_GAP, w["seed"])
                self.assertGreaterEqual(abs(R[i, j]), 0.98, w["seed"])
                self.assertLessEqual(abs(w["R_ref"][i, j]), 0.9, w["seed"])
                if w["signals"] == 3:
                    # the pair is a weak signal below the proxies of the strongest: rows bought
                    # for the largest |z| never reach it
                    order = list(np.argsort(-np.abs(z)))
                    self.assertGreaterEqual(min(order.index(i), order.index(j)), ev.ROW_BUDGET, w["seed"])
                self.assertGreaterEqual(w["gap"], ev.RESOLVED_GAP, w["seed"])
                self.assertEqual(w["causal"], [])
            else:
                self.assertGreaterEqual(ev._swap_gap(z, R, w["causal"]), ev.RESOLVED_GAP, w["seed"])
                self.assertGreaterEqual(np.abs(z).max(), ev.GENOME_WIDE_Z, w["seed"])

    def test_the_panel_is_not_the_cohort(self):
        """The reference algorithm fed the panel's rows in place of the cohort's loses most of
        the score: the proxy the panel does not see becomes a second signal."""
        ev, ref = self.evaluator, self.reference

        def trusting(problem, _r):
            panel = np.asarray(problem["reference_ld"], dtype=float)
            return ref.fine_map(problem, lambda v: [float(x) for x in panel[int(v)]])

        full = ev.evaluate(ref.fine_map)["combined_score"]
        panel_only = ev.evaluate(trusting)["combined_score"]
        self.assertLess(panel_only, full - 0.35, "the panel's rows score as well as the cohort's")

    def test_the_rows_are_not_free_and_the_refusal_is_earned(self):
        ev, ref = self.evaluator, self.reference
        source = (TASK / "verification/reference_conditional_rows.py").read_text(encoding="utf-8")

        def variant(old, new):
            self.assertIn(old, source)
            namespace = {}
            exec(compile(source.replace(old, new), "reference_variant", "exec"), namespace)  # noqa: S102
            return namespace["fine_map"]

        full = ev.evaluate(ref.fine_map)["combined_score"]
        half = variant('budget = int(problem["row_budget"])', 'budget = int(problem["row_budget"]) // 2')
        self.assertLess(ev.evaluate(half)["combined_score"], full - 0.1, "half the rows score as well as all of them")
        never = variant("RESOLVE_MARGIN = 3.0", "RESOLVE_MARGIN = -1.0")
        metrics = ev.evaluate(never)
        self.assertLess(metrics["combined_score"], full - 0.25, "never declining scores as well as declining")
        self.assertEqual(metrics["development_correct_refusal_rate"], 0.0)
        # proxy rows by the largest predicted z-score go to the strongest signal's proxies and
        # never reach the weak signal's near-duplicate
        by_prediction = variant("    for s in sorted(config, key=lambda v: abs(z[v])):\n", "    for s in []:\n")
        self.assertLess(ev.evaluate(by_prediction)["combined_score"], full - 0.1, "one proxy row per modelled variant is not needed")

    def test_the_clumping_baseline_is_valid_and_scores_zero(self):
        baseline = self.evaluator.evaluate(self.baseline.fine_map)
        reference = self.evaluator.evaluate(self.reference.fine_map)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertGreater(baseline["development_false_discovery_rate"], 0.6)
        self.assertEqual(baseline["development_correct_refusal_rate"], 0.0)
        self.assertEqual(baseline["development_mean_rows_bought"], 0.0)
        self.assertGreater(reference["combined_score"], 0.5)
        self.assertLess(reference["combined_score"], 0.9)
        # The reference names every typed world and declines every unresolved one. What it
        # leaves on the table is the masked partner, which its region-wide selection line never
        # takes, and the sampling noise of the effects. If either reaches the ceiling the task
        # has stopped measuring the axis it was built around.
        self.assertEqual(reference["development_discovery_coverage"], 1.0)
        self.assertEqual(reference["development_correct_refusal_rate"], 1.0)
        self.assertEqual(reference["development_false_discovery_rate"], 0.0)
        self.assertLess(reference["development_effect_score"], 0.95)
        self.assertLessEqual(reference["development_mean_rows_bought"], self.evaluator.ROW_BUDGET)
        for row in reference["per_instance"]:
            self.assertEqual(row["abstained"], row["kind"] == "unresolved", row)
            if row["kind"] == "masked":
                self.assertAlmostEqual(row["set_f1"], 2.0 / 3.0, places=3, msg=row)

    def test_two_evaluations_are_identical(self):
        first = self.evaluator.evaluate(self.reference.fine_map)
        second = self.evaluator.evaluate(self.reference.fine_map)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    @skip_unless_sandbox("bwrap")
    def test_actual_candidate_process_and_tmpfs_reset_between_all_worlds_and_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "candidate.py"
            candidate.write_text(textwrap.dedent('''
                import os
                import numpy as np

                calls = 0

                def fine_map(problem, ld_row):
                    global calls
                    calls += 1
                    marker = "/tmp/fine-mapping-world-state"
                    if calls != 1 or os.path.exists(marker):
                        raise RuntimeError("state leaked from previous world")
                    if getattr(np, "_fine_mapping_world_seen", False):
                        raise RuntimeError("imported state leaked from previous world")
                    np._fine_mapping_world_seen = True
                    with open(marker, "w") as handle:
                        handle.write("within-world state")
                    first = ld_row(0)
                    second = ld_row(0)
                    if first != second or calls != 1:
                        raise RuntimeError("paid callback did not preserve its session")
                    with open(marker) as handle:
                        if handle.read() != "within-world state":
                            raise RuntimeError("tmpfs reset inside world")
                    return {"verdict": "unresolved", "confidence": 0.8}
            '''), encoding="utf-8")
            with CandidateProxy(candidate, "fine_map", timeout_s=90) as proxy:
                metrics = self.evaluator.evaluate(proxy)
        rows = metrics["per_instance"]
        self.assertEqual(len(rows), len(self.evaluator.DEVELOPMENT_WORLDS)
                         + len(self.evaluator.HELDOUT_WORLDS))
        self.assertEqual({r["split"] for r in rows}, {"development", "heldout"})
        for row in rows:
            self.assertTrue(row["valid"], row)
            self.assertEqual(row["rows_bought"], 1, row)

    def test_reset_failure_is_not_scored_as_an_invalid_scientific_submission(self):
        class BrokenReset:
            def reset_session(self):
                raise RuntimeError("cannot establish isolated candidate session")

            def __call__(self, _problem, _ld_row):
                raise AssertionError("candidate must not run after failed reset")

        with self.assertRaisesRegex(RuntimeError, "cannot establish isolated"):
            self.evaluator.evaluate(BrokenReset())

    def test_truth_effect_units_follow_the_accepted_phenotype_draw(self):
        signal = np.array([-2.0, -1.0, 1.0, 2.0])
        noise = np.array([-1.0, 0.0, 0.0, 1.0])
        phenotype, scale = self.evaluator._standardize_trait(signal, noise)
        expected = signal + noise
        self.assertAlmostEqual(scale, np.std(expected))
        np.testing.assert_allclose(phenotype, (expected - expected.mean()) / np.std(expected))
        self.assertGreater(abs(scale - np.sqrt(np.var(signal) + 1.0)), 0.1)
        for world in self.worlds:
            for variant, original in world["unscaled_causal_effects"].items():
                self.assertAlmostEqual(world["truth_beta"][variant] * world["phenotype_scale"], original)

    def test_complete_reference_joint_effects_match_individual_level_regression(self):
        rng = np.random.default_rng(7912)
        genotype = rng.normal(size=(200, 3))
        genotype[:, 1] += 0.8 * genotype[:, 0]
        phenotype = genotype @ np.array([0.7, -0.5, 0.2]) + rng.normal(scale=0.3, size=200)
        phenotype = (phenotype - phenotype.mean()) / phenotype.std()
        z, _, se = self.evaluator.ldsim.marginal_z(genotype, phenotype)
        R = self.evaluator.ldsim.correlation(genotype)
        estimated = self.complete_reference._joint_effects(z, se, R, [0, 1, 2], len(phenotype))
        centered = genotype - genotype.mean(axis=0)
        expected = np.linalg.lstsq(centered, phenotype, rcond=None)[0]
        np.testing.assert_allclose(estimated, expected, rtol=1e-7, atol=1e-9)
        approximate = np.linalg.solve(R, z) * se
        self.assertGreater(np.max(np.abs(approximate - expected)), 0.01)

    def test_reused_regression_statistics_match_separate_ols_with_intercepts(self):
        rng = np.random.default_rng(7951)
        genotype = rng.integers(0, 3, size=(120, 7)).astype(float)
        statistics = self.evaluator.ldsim.regression_statistics(genotype)
        for _ in range(3):
            phenotype = genotype @ rng.normal(size=7) + rng.normal(size=120) + 4.0
            z, beta, se = self.evaluator.ldsim.marginal_z(genotype, phenotype, statistics)
            for variant in range(genotype.shape[1]):
                design = np.column_stack([np.ones(len(phenotype)), genotype[:, variant]])
                coefficient = np.linalg.lstsq(design, phenotype, rcond=None)[0]
                residual = phenotype - design @ coefficient
                variance = float(residual @ residual) / (len(phenotype) - 2)
                expected_se = np.sqrt(variance * np.linalg.inv(design.T @ design)[1, 1])
                self.assertAlmostEqual(beta[variant], coefficient[1], places=12)
                self.assertAlmostEqual(se[variant], expected_se, places=12)
                self.assertAlmostEqual(z[variant], coefficient[1] / expected_se, places=10)

    def test_complete_reference_recovers_masked_partners_without_a_truth_import(self):
        source = (TASK / "verification/reference_masking_aware.py").read_text()
        self.assertNotIn("import evaluator", source)
        self.assertNotIn("import ldsim", source)
        metrics = self.evaluator.evaluate(self.complete_reference.fine_map)
        original = self.evaluator.evaluate(self.reference.fine_map)
        self.assertGreater(metrics["combined_score"], original["combined_score"] + 0.1)
        self.assertLess(metrics["combined_score"], 1.0)
        for split in ("development", "heldout"):
            self.assertEqual(metrics[split + "_false_discovery_rate"], 0.0)
            self.assertEqual(metrics[split + "_correct_refusal_rate"], 1.0)
        for row in metrics["per_instance"]:
            self.assertTrue(row["valid"])
            self.assertLessEqual(row["rows_bought"], self.evaluator.ROW_BUDGET)
            if row["kind"] == "masked":
                self.assertEqual(row["set_f1"], 1.0)

    def test_discovery_denominators_include_invalid_worlds_without_refusal_credit(self):
        candidates = [self.complete_reference.fine_map, lambda _p, _r: {"abstain": True},
                      lambda _p, _r: {}]
        for candidate in candidates:
            metrics = self.evaluator.evaluate(candidate)
            for split in ("development", "heldout"):
                rows = [r for r in metrics["per_instance"] if r["split"] == split]
                determinable = [r for r in rows if r["kind"] != "unresolved"]
                unsupported = [r for r in rows if r["kind"] == "unresolved"]
                prefix = split + "_"
                self.assertEqual(metrics[prefix + "world_count"], len(rows))
                self.assertEqual(metrics[prefix + "determinable_world_count"], len(determinable))
                self.assertEqual(metrics[prefix + "unsupported_world_count"], len(unsupported))
                for count, rate, denominator in (
                    ("false_discovery_count", "false_discovery_rate", len(rows)),
                    ("correct_refusal_count", "correct_refusal_rate", len(unsupported)),
                    ("discovery_attempt_count", "discovery_coverage", len(determinable)),
                ):
                    self.assertAlmostEqual(metrics[prefix + rate], metrics[prefix + count] / denominator)
                expected = np.clip((sum(r["mechanism_score"] for r in rows) - len(unsupported))
                                   / len(determinable), 0.0, 1.0)
                self.assertAlmostEqual(metrics[prefix + "mechanism_score"], expected)

    def test_malformed_candidates_score_zero_without_raising(self):
        n = self.evaluator.N_SNP

        def raises(_p, _r):
            raise RuntimeError("boom")

        def overspend(_p, ld_row):
            for v in range(n):
                ld_row(v)
            return {"verdict": "unresolved"}

        def patched_budget(_p, ld_row):
            ld_row.budget = 999  # a function attribute: the ledger is not reachable
            return overspend(_p, ld_row)

        def suppressed_overspend(_p, ld_row):
            try:
                overspend(_p, ld_row)
            except RuntimeError:
                pass
            return {"verdict": "unresolved"}

        typed = {"verdict": "typed", "causal": [1], "effects": [0.1]}
        shapes = {
            "raises": raises,
            "none": lambda _p, _r: None,
            "empty": lambda _p, _r: {},
            "string": lambda _p, _r: "typed",
            "verdict_bad": lambda _p, _r: {"verdict": "maybe"},
            "typed_no_causal": lambda _p, _r: {"verdict": "typed"},
            "causal_int": lambda _p, _r: {**typed, "causal": 3},
            "causal_empty": lambda _p, _r: {"verdict": "typed", "causal": [], "effects": []},
            "causal_four": lambda _p, _r: {"verdict": "typed", "causal": [0, 1, 2, 3], "effects": [0.1] * 4},
            "causal_repeat": lambda _p, _r: {"verdict": "typed", "causal": [1, 1], "effects": [0.1, 0.1]},
            "causal_range": lambda _p, _r: {**typed, "causal": [n]},
            "causal_float": lambda _p, _r: {**typed, "causal": [1.0]},
            "causal_bool": lambda _p, _r: {**typed, "causal": [True]},
            "effects_short": lambda _p, _r: {"verdict": "typed", "causal": [1, 2], "effects": [0.1]},
            "effects_nan": lambda _p, _r: {**typed, "effects": [float("nan")]},
            "effects_str": lambda _p, _r: {**typed, "effects": ["big"]},
            "confidence_nan": lambda _p, _r: {**typed, "confidence": float("nan")},
            "confidence_str": lambda _p, _r: {**typed, "confidence": "high"},
            "overspend": overspend,
            "patched_budget": patched_budget,
            "suppressed_overspend": suppressed_overspend,
            "bad_row": lambda _p, r: r(9999),
            "float_row": lambda _p, r: r(1.0),
            "bool_row": lambda _p, r: r(True),
        }
        self.assertGreaterEqual(len(shapes), 12)
        for name, candidate in shapes.items():
            metrics = self.evaluator.evaluate(candidate)
            self.assertEqual(metrics["valid"], 0.0, name)
            self.assertEqual(metrics["combined_score"], 0.0, name)
            self.assertEqual(metrics["feasibility_rate"], 0.0, name)

    def test_repeat_rows_are_free_and_the_budget_fails_closed(self):
        ev = self.evaluator
        world = self.worlds[0]
        campaign = ev._Campaign(world)
        ld_row = campaign.oracle()
        rows = [ld_row(v) for v in range(world["budget"])]
        self.assertEqual(ld_row(0), rows[0])
        self.assertEqual(campaign.spent, world["budget"])
        with self.assertRaises(RuntimeError):
            ld_row(world["budget"])
        self.assertTrue(campaign.violated)

    def test_hidden_axes_stay_out_of_the_search_view(self):
        from sle.metric_visibility import SEARCH_VISIBLE_KEYS

        for key in SEARCH_VISIBLE_KEYS:
            self.assertNotIn("heldout", key)
            self.assertNotIn("mechanism", key)
            self.assertNotIn("set_f1", key)


if __name__ == "__main__":
    unittest.main()
