"""The admission report decides which tasks this benchmark can claim, so its rules are pinned.

Four defects were found in it by inspection rather than by test, and each one changed what the
report said about the inventory:

  * runs were identified by directory name, which invented a task called "b20" out of a
    budget-sweep cohort and split one task's evidence across fictitious names;
  * open-loop seeds were not pooled across cohorts, which would have made a seeding pass useless
    because the new cohort and the old one each stayed below the confidence threshold;
  * one row was emitted per (task, cohort), so a pooled saturation verdict was counted once per
    cohort and 52 tasks were reported as 93 rows;
  * the judged cohort was picked by seed count, so a task was judged on a cohort holding a single
    budget and the verdict read "gap grows with budget, +0.1345 at 3 to +0.1345 at 3".

Each of those is a test below.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "report_admission_criterion.py"
    spec = importlib.util.spec_from_file_location("admission_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def write_run(root: Path, cohort: str, dirname: str, task: str, mode: str, seed: int,
              scores: list[float], write_manifest: bool = True) -> None:
    workdir = root / cohort / dirname
    workdir.mkdir(parents=True)
    if write_manifest:
        (workdir / "run_manifest.json").write_text(json.dumps({
            "task_id": task, "feedback_mode": mode, "seed": seed,
        }), encoding="utf-8")
    lines = [json.dumps({"step": 0, "valid": True, "score": 0.0})]
    for index, score in enumerate(scores, start=1):
        lines.append(json.dumps({"step": index, "valid": True, "score": score}))
    (workdir / "trajectory.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


class RunIdentityTests(unittest.TestCase):
    def test_task_comes_from_the_manifest_not_the_directory_name(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "crossover", "b20_normal_s0", "Astro/LowThrust", "normal", 0, [0.1])
            found = MODULE.collect(root)
            self.assertEqual(list(found), [("Astro/LowThrust", "crossover")])

    def test_a_run_without_a_manifest_is_skipped_rather_than_guessed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run(root, "c", "Some_normal_s0", "T/X", "normal", 0, [0.1],
                      write_manifest=False)
            self.assertEqual(MODULE.collect(root), {})


class PoolingTests(unittest.TestCase):
    def test_open_loop_seeds_pool_across_cohorts_for_saturation(self):
        """Saturation is one-armed, so a seed in a new cohort counts toward the same task."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            climb = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
            write_run(root, "saturation", "a", "T/X", "selection_blind", 0, climb)
            write_run(root, "screen3", "b", "T/X", "selection_blind", 1, climb)
            write_run(root, "screen3", "c", "T/X", "selection_blind", 2, climb)
            report = self.run_report(root)
            row = report["rows"][0]
            self.assertEqual(row["pooled_open_loop_seeds"], 3)
            self.assertEqual(row["confidence"], "measured")

    def test_one_row_per_task_however_many_cohorts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            climb = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
            for cohort, seed in (("saturation", 0), ("screen3", 1), ("other", 2)):
                write_run(root, cohort, "w", "T/X", "selection_blind", seed, climb)
            report = self.run_report(root)
            self.assertEqual(len(report["rows"]), 1)
            self.assertEqual(report["distinct_task_count"], 1)

    @staticmethod
    def run_report(root: Path) -> dict:
        with TemporaryDirectory() as out:
            target = Path(out) / "report.json"
            import contextlib
            import io

            with contextlib.redirect_stdout(io.StringIO()):
                MODULE.main(["--runs", str(root), "--output", str(target)])
            return json.loads(target.read_text(encoding="utf-8"))


def _sat(*, seeds, median, final, is_floor=False, saturated=False, marginal=False):
    return {
        "seeds": seeds,
        "median_second_half_gain": median,
        "mean_second_half_gain": median,
        "max_second_half_gain": median,
        "mean_final": final,
        "is_floor": is_floor,
        "saturated": saturated,
        "marginal": marginal,
    }


class VerdictTests(unittest.TestCase):
    """Condition 1 requires the control to SATURATE, not to keep climbing.

    An earlier version had this backwards, and the inversion silently disqualified every task
    that actually passed: a task whose control is exhausted while its feedback arm keeps pulling
    ahead is the ideal case, and it was being reported as having no headroom.
    """

    EXHAUSTED = dict(seeds=6, median=0.0, final=0.62, saturated=True)

    def test_an_exhausted_control_with_a_growing_gap_measures_iteration(self):
        gaps = [
            {"budget": 3, "n": 6, "mean": 0.02, "stderr": 0.01, "wins": 4, "losses": 2},
            {"budget": 12, "n": 6, "mean": 0.13, "stderr": 0.04, "wins": 5, "losses": 1},
        ]
        state, why = MODULE.verdict(_sat(**self.EXHAUSTED), gaps)
        self.assertEqual(state, "measures_iteration")
        self.assertIn("control exhausted", why)

    def test_a_climbing_control_is_not_admissible_however_good_the_gap(self):
        """Best-of-N has not run out, so the gap depends on the budget that was picked."""
        climbing = _sat(seeds=6, median=0.18, final=0.97)
        gaps = [
            {"budget": 3, "n": 6, "mean": 0.02, "stderr": 0.01, "wins": 4, "losses": 2},
            {"budget": 12, "n": 6, "mean": 0.31, "stderr": 0.04, "wins": 6, "losses": 0},
        ]
        state, why = MODULE.verdict(climbing, gaps)
        self.assertEqual(state, "control_not_exhausted")
        self.assertIn("depends on the budget", why)

    def test_a_single_budget_cannot_produce_a_trend_verdict(self):
        gaps = [{"budget": 3, "n": 8, "mean": 0.1345, "stderr": 0.03, "wins": 8, "losses": 0}]
        state, why = MODULE.verdict(_sat(**self.EXHAUSTED), gaps)
        self.assertEqual(state, "gap_at_one_budget")
        self.assertIn("single point", why)

    def test_a_closing_gap_is_a_crossover_not_a_pass(self):
        gaps = [
            {"budget": 3, "n": 8, "mean": 0.19, "stderr": 0.05, "wins": 6, "losses": 2},
            {"budget": 12, "n": 8, "mean": 0.02, "stderr": 0.05, "wins": 4, "losses": 4},
        ]
        self.assertEqual(
            MODULE.verdict(_sat(**self.EXHAUSTED), gaps)[0], "crossover_in_range")

    def test_a_negative_gap_means_feedback_is_harmful(self):
        gaps = [
            {"budget": 3, "n": 4, "mean": -0.29, "stderr": 0.11, "wins": 1, "losses": 3},
            {"budget": 12, "n": 4, "mean": -0.37, "stderr": 0.08, "wins": 0, "losses": 4},
        ]
        state, why = MODULE.verdict(_sat(**self.EXHAUSTED), gaps)
        self.assertEqual(state, "feedback_harmful")
        self.assertIn("does worse", why)

    def test_an_exhausted_control_with_no_feedback_arm_is_the_pairing_queue(self):
        self.assertEqual(
            MODULE.verdict(_sat(**self.EXHAUSTED), [])[0], "exhausted_unpaired")

    def test_drift_near_the_ceiling_counts_as_exhausted(self):
        """A control creeping by 0.0025 at 0.9991 has run out in every sense that matters."""
        sat = _sat(seeds=6, median=0.0025, final=0.9991, marginal=True)
        self.assertEqual(MODULE.verdict(sat, [])[0], "exhausted_unpaired")

    def test_a_thin_screen_is_not_a_verdict(self):
        state, why = MODULE.verdict(_sat(seeds=1, median=0.41, final=0.41), [])
        self.assertEqual(state, "thin_screen")
        self.assertIn("1 open-loop seed", why)

    def test_a_floor_is_distinguished_from_an_exhausted_control(self):
        floor = _sat(seeds=4, median=0.0, final=0.0, is_floor=True, saturated=True)
        flat = _sat(seeds=4, median=0.0, final=0.87, saturated=True)
        self.assertEqual(MODULE.verdict(floor, [])[0], "floor")
        self.assertEqual(MODULE.verdict(flat, [])[0], "exhausted_unpaired")


class SaturationTests(unittest.TestCase):
    def test_saturation_is_judged_on_the_median_seed_not_the_mean(self):
        """One climbing seed among flat ones must not read as headroom.

        Best-so-far curves are monotone, so a second-half gain is never negative and the mean
        over seeds can only rise as seeds are added. Judging on the mean made adding seeds move
        tasks one way only: 17 of 52 in this inventory went from "no headroom" toward "headroom"
        and none came back.
        """
        flat = [0.5] * 12
        climbs = [0.1 * i for i in range(1, 13)]
        sat = MODULE.saturation({0: flat, 1: flat, 2: climbs})
        self.assertTrue(sat["saturated"], "median of two flat seeds and one climber is flat")
        self.assertGreater(sat["mean_second_half_gain"], 0.0)
        self.assertGreater(sat["max_second_half_gain"], 0.0)

    def test_a_majority_climbing_still_counts_as_headroom(self):
        flat = [0.5] * 12
        climbs = [0.1 * i for i in range(1, 13)]
        sat = MODULE.saturation({0: climbs, 1: climbs, 2: flat})
        self.assertFalse(sat["saturated"])


    def test_a_control_that_never_leaves_zero_is_a_floor(self):
        sat = MODULE.saturation({0: [0.0] * 12, 1: [0.0] * 12})
        self.assertTrue(sat["is_floor"])

    def test_curves_shorter_than_six_proposals_are_not_judged(self):
        self.assertIsNone(MODULE.saturation({0: [0.1, 0.2, 0.3]}))


if __name__ == "__main__":
    unittest.main()
