"""The task generator must not emit a wrapper that runs the candidate unsandboxed.

`scripts/gen_task.py` writes each new task's `frontier_eval/run_eval.py`, the black-box entry
external harnesses call. Its template used to import the candidate and the oracle into the
same process, which is a way for candidate code to run outside the Bubblewrap sandbox
whenever anyone reaches for the convenience - the exact shape the exemplar task's wrapper
carries a comment warning against. Three submitted branches also shipped wrappers with
unrendered `{{ }}` placeholders, which fail on every evaluation, because the template is a
`.format()` string and nothing checked the rendered result.

These tests pin the properties of what the generator emits, not its wording.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _generator():
    spec = importlib.util.spec_from_file_location(
        "gen_task_under_test", REPO / "scripts" / "gen_task.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render(task="HarmonicOscillatorControl", task_id="Physics/HarmonicOscillatorControl",
            eval_timeout=300):
    return _generator().RUN_EVAL_TEMPLATE.format(
        task=task, task_id=task_id, eval_timeout=eval_timeout)


class GeneratedRunEvalTests(unittest.TestCase):
    def test_rendered_wrapper_is_valid_python(self):
        ast.parse(_render())

    def test_no_placeholder_survives_rendering(self):
        rendered = _render()
        for marker in ("{{", "}}", "{task}", "{task_id}", "{eval_timeout}"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, rendered)

    def test_wrapper_shells_out_instead_of_importing_the_candidate(self):
        rendered = _render()
        self.assertIn("subprocess.run(", rendered)
        self.assertIn('sle/frontier_eval_entrypoint.py', rendered)
        helper = (REPO / 'sle/frontier_eval_entrypoint.py').read_text()
        self.assertIn('"-m", "sle", "eval"', helper)
        for bypass in ("importlib", "exec_module", "spec_from_file_location", "exec("):
            with self.subTest(bypass=bypass):
                self.assertNotIn(bypass, rendered)

    def test_wrapper_reports_failures_instead_of_raising(self):
        rendered = _render()
        self.assertIn("result.returncode", rendered)
        self.assertIn("return 2", rendered)
        self.assertIn("stderr", rendered)
        # Candidate diagnostics and metric filtering belong to the trusted helper.
        # Launch/import failures are infrastructure errors and must not invent a score.
        helper = (REPO / "sle/frontier_eval_entrypoint.py").read_text()
        self.assertIn("search_visible_metrics", helper)

    def test_root_depth_matches_the_benchmarks_layout(self):
        """`parents[4]` must land on the repository root from the wrapper's own location."""
        match = re.search(r"parents\[(\d+)\]", _render())
        self.assertIsNotNone(match)
        depth = int(match.group(1))
        example = REPO / "benchmarks" / "Engineering" / "TrussWeightMinimization" / \
            "frontier_eval" / "run_eval.py"
        self.assertTrue(example.is_file())
        self.assertEqual(example.resolve().parents[depth], REPO)

    def test_timeout_follows_the_convention_and_can_be_overridden(self):
        module = _generator()
        default = module.DEFAULT_EVAL_TIME_SECONDS

        def timeout_for(spec):
            seconds = int(spec.get("eval_time_seconds") or default)
            return int(spec.get("eval_timeout_s") or max(300, 3 * seconds))

        # Floored at the repository's usual 300 s for quick tasks...
        self.assertEqual(timeout_for({"eval_time_seconds": 5}), 300)
        self.assertEqual(timeout_for({"eval_time_seconds": 100}), 300)
        # ...and three times the expected evaluation once that exceeds the floor, so a long
        # task does not get a wrapper timeout below its own declared cost.
        self.assertEqual(timeout_for({"eval_time_seconds": 300}), 900)
        self.assertEqual(timeout_for({"eval_time_seconds": 720}), 2160)
        # An explicit key wins, because this is a review quantity set by task difficulty.
        self.assertEqual(timeout_for({"eval_time_seconds": 30, "eval_timeout_s": 900}), 900)
        # A missing declaration falls back once, so metadata.yaml and run_eval.py cannot
        # disagree about it.
        self.assertEqual(timeout_for({}), max(300, 3 * default))

    def test_wrapper_refuses_to_run_if_copied_to_another_task(self):
        """A copied wrapper keeps its old TASK_ID and would score against the wrong oracle.

        The previous template derived everything from `__file__`, so a copy relocated itself.
        This one writes the registered id in, because `sle eval` needs the id rather than a
        path - so the mismatch has to be caught here instead of by whoever reads the numbers.
        """
        rendered = _render(task="Foo", task_id="Physics/Foo")
        self.assertIn("_expected_task", rendered)
        self.assertIn("parents[1].name", rendered)
        # Exercise it: drop the rendered wrapper into a directory named after another task.
        import subprocess
        import sys as _sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            wrong = pathlib.Path(tmp) / "benchmarks" / "Physics" / "Bar" / "frontier_eval"
            wrong.mkdir(parents=True)
            (wrong / "run_eval.py").write_text(rendered, encoding="utf-8")
            done = subprocess.run(
                [_sys.executable, str(wrong / "run_eval.py"),
                 "--candidate", "x.py", "--metrics-out", str(pathlib.Path(tmp) / "m.json")],
                capture_output=True, text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("does not name this directory", done.stderr)

    def test_generated_wrapper_writes_only_search_visible_keys(self):
        """Issue #14: the metrics file is what an external harness reads back.

        `sle eval` prints everything the evaluator returned, which for a discovery task includes
        the held-out scores, the per-instance rows and the discovery axes. Measured across the
        frozen baseline document, all 82 tasks return at least one key outside the whitelist and
        1200 in total, 444 of them `heldout_*`. This repository's own loop never sees them, but a
        harness that feeds this file back into its own loop would be selecting on the sealed
        split. Both generated and shipped wrappers delegate to the same trusted helper.
        """
        rendered = _render()
        self.assertIn("sle/frontier_eval_entrypoint.py", rendered)
        helper = (REPO / "sle/frontier_eval_entrypoint.py").read_text()
        self.assertIn("search_visible_metrics(result)", helper)
        # Imported, not restated: a second copy of the list is how two paths diverge.
        self.assertNotIn('"combined_score",\n    "valid",', rendered)

    def test_generated_wrapper_filters_a_real_metrics_dictionary(self):
        """The property, exercised end to end rather than read off the source."""
        import json
        import subprocess
        import sys as _sys
        import tempfile
        import shutil

        from sle.metric_visibility import SEARCH_VISIBLE_KEYS

        rendered = _render(task="Bar", task_id="Physics/Bar")
        leaky = {
            "combined_score": 0.5, "valid": 1.0, "raw_score": 0.5,
            "heldout_combined_score": 0.9, "development_mechanism_score": 1.0,
            "per_instance": [{"kind": "supported", "units": 3}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            wrapper = root / "benchmarks" / "Physics" / "Bar" / "frontier_eval" / "run_eval.py"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text(rendered, encoding="utf-8")
            # `sle` must be importable from the fake root, and the subprocess the wrapper shells
            # out to is replaced by a stub that prints the leaky dictionary `sle eval` would.
            (root / "sle").mkdir()
            (root / "sle" / "__init__.py").write_text("", encoding="utf-8")
            shutil.copy(REPO / "sle" / "metric_visibility.py", root / "sle" / "metric_visibility.py")
            shutil.copy(REPO / "sle" / "frontier_eval_entrypoint.py", root / "sle" / "frontier_eval_entrypoint.py")
            (root / "sle" / "__main__.py").write_text(
                "import json, sys\nprint(json.dumps(%r))\n" % (leaky,), encoding="utf-8")
            candidate = root / "candidate.py"
            candidate.write_text("", encoding="utf-8")
            out = root / "metrics.json"
            done = subprocess.run(
                [_sys.executable, str(wrapper), "--candidate", str(candidate),
                 "--metrics-out", str(out), "--timeout", "30"],
                capture_output=True, text=True, timeout=120, cwd=str(root))
            self.assertEqual(done.returncode, 0, done.stderr)
            # Read inside the block: the directory goes away when it closes.
            written = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(set(written) - set(SEARCH_VISIBLE_KEYS), set())
        self.assertEqual(written["combined_score"], 0.5)
        for hidden in ("heldout_combined_score", "development_mechanism_score", "per_instance"):
            with self.subTest(key=hidden):
                self.assertNotIn(hidden, written)
        self.assertNotIn("heldout", done.stdout)
    def test_no_shipped_wrapper_loads_the_candidate_in_process(self):
        """A wrapper that imports the candidate puts it in the oracle's own address space.

        `frontier_eval/run_eval.py` is what external harnesses call through `eval_command.txt`,
        and the oracle is imported into that process. A wrapper that also imports the candidate
        there gives candidate code the oracle module: the hidden worlds, the sealed split, and
        the scoring functions, with no sandbox and no seccomp filter in between. It can read the
        answers or replace the scorer.

        Two wrapper shapes are legitimate and must keep passing. Sixty-eight shell out to
        `python -m sle eval`, which runs the candidate in Bubblewrap behind a typed JSON-RPC
        boundary. Thirteen import the oracle here but reach the candidate through
        `sle.secure_eval.CandidateProxy`, which is the same sandbox by another route. What this
        rejects is the third shape: `importlib` against the candidate path.

        `Physics/CriticalPhenomenaLab` was the last one, and it was the only wrapper in the tree
        without a `parents[...]` root, which is how it survived the migration that moved the
        others. A candidate run through it could reach `evaluator.DEVELOPMENT_SPECS`,
        `evaluator.VALIDATION_SPECS` and `evaluator.SEALED_SIZES`.
        """
        offenders = []
        for path in sorted((REPO / "benchmarks").glob("*/*/frontier_eval/run_eval.py")):
            text = path.read_text(encoding="utf-8")
            markers = [m for m in ("exec_module", "spec_from_file_location", "importlib")
                       if m in text]
            if markers:
                offenders.append("%s: %s" % (path.relative_to(REPO), ", ".join(markers)))
        self.assertEqual(offenders, [])

    def test_every_shipped_wrapper_uses_shared_entrypoint(self):
        """The migration covers the entire registry, including formerly direct/proxy wrappers."""
        strays = []
        for path in sorted((REPO / "benchmarks").glob("*/*/frontier_eval/run_eval.py")):
            text = path.read_text(encoding="utf-8")
            # Match on the argv the shape needs, not on one formatting of it: several wrappers
            # spread the list across lines, so a literal '"-m", "sle", "eval"' misses them.
            if "sle/frontier_eval_entrypoint.py" not in text or "subprocess.run" not in text:
                strays.append(str(path.relative_to(REPO)))
        self.assertEqual(strays, [])

    def test_no_shipped_wrapper_carries_an_unrendered_placeholder(self):
        offenders = []
        for path in sorted((REPO / "benchmarks").glob("*/*/frontier_eval/run_eval.py")):
            text = path.read_text(encoding="utf-8")
            if "{{" in text or "}}" in text:
                offenders.append(str(path.relative_to(REPO)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
