"""Two drivers write runs into one tree at different depths, and both must be read.

`run_cohort.sh` writes `runs/<cohort>/<name>/`, one level down. `batch_evolve.py` nests by task,
algorithm, mode and seed: `runs/<cohort>/<Task>/<algorithm>/<mode>/seed_0/`. The readers globbed a
fixed depth, so they found the first and found *nothing* in the second - which does not look like
an unrecognised layout, it looks like a cohort that was never run. A whole paired sweep would have
reported as absent evidence.

The cohort key matters as much as the depth. It has to keep a paired sweep together: `normal` and
`selection_blind` in one cohort is what makes them comparable, and keying on the run's parent
directory would file each mode separately and leave nothing paired.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        "layout_%s" % name, ROOT / "scripts" / ("%s.py" % name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_run(directory: Path, task: str, mode: str, seed: int, scores: list[float]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "run_manifest.json").write_text(json.dumps({
        "task_id": task, "feedback_mode": mode, "seed": seed,
        "algorithm": "greedy_rewrite",
        "task_package_sha256": "a" * 64,
        "llm_condition": {"model": "test-model"},
    }), encoding="utf-8")
    (directory / "trajectory.jsonl").write_text(
        "".join(json.dumps({"step": index, "score": score, "best_score": score, "valid": True,
                            "oracle_calls": index + 1, "budget_units": index + 1}) + "\n"
                for index, score in enumerate(scores)), encoding="utf-8")


class RunLayoutTests(unittest.TestCase):
    TASK = "Optics/DiffractionGratingDesign"

    def _tree(self, root: Path) -> None:
        # Flat, as run_cohort.sh writes it.
        _write_run(root / "flatcohort" / "grating_normal_s0",
                   self.TASK, "normal", 0, [0.1, 0.2, 0.3])
        _write_run(root / "flatcohort" / "grating_selection_blind_s0",
                   self.TASK, "selection_blind", 0, [0.1, 0.15, 0.2])
        # Nested, as batch_evolve.py writes it.
        base = root / "nestedcohort" / "Optics__DiffractionGratingDesign" / "greedy_rewrite"
        _write_run(base / "normal" / "seed_0", self.TASK, "normal", 0, [0.1, 0.3, 0.5])
        _write_run(base / "selection_blind" / "seed_0",
                   self.TASK, "selection_blind", 0, [0.1, 0.12, 0.14])

    def test_both_layouts_are_collected(self):
        module = _load("report_admission_criterion")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._tree(root)
            found = module.collect(root)
        cohorts = {key[1] for key in found}
        self.assertIn("flatcohort", cohorts)
        self.assertIn(
            "nestedcohort", cohorts,
            "the nested layout was not collected, so a paired sweep written by batch_evolve.py "
            "would report as evidence that does not exist")

    def test_a_paired_sweep_stays_one_cohort_so_its_arms_are_comparable(self):
        module = _load("report_admission_criterion")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._tree(root)
            found = module.collect(root)
        for key, modes in found.items():
            self.assertEqual(
                {"normal", "selection_blind"}, set(modes),
                "cohort %r holds only %s - the arms were split across cohorts and nothing pairs"
                % (key[1], sorted(modes)))

    def test_the_cross_model_reader_sees_both_layouts_too(self):
        module = _load("report_cross_model")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._tree(root)
            runs = module.read_runs(root)
        self.assertEqual(len(runs), 4, "expected every run in both layouts, got %d" % len(runs))


if __name__ == "__main__":
    unittest.main()
