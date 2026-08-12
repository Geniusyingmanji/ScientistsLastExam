"""Tests for scripts/run_cohort.sh, the cohort runner.

This script exists because two ad-hoc drivers deleted each other's output and three runs vanished
from a thirty-six run comparison without anything reporting a failure. Its guarantees are worth
testing directly rather than trusting to review:

    a completed run is one with a manifest, not one with a long enough trajectory
    two drivers that collide on a run serialise instead of racing
    a lock left behind by a dead driver does not block the run forever
    a run that fails is reported, not silently skipped

The real runner is invoked, with a fake `python3` earlier on PATH standing in for
`frontier_science run`. That keeps the shell logic under test - argument parsing, locking, the
completion check - rather than a reimplementation of it.
"""
from __future__ import annotations

import json
import os
import subprocess
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "run_cohort.sh"


class CohortRunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.calls = self.tmp / "calls.txt"

    def fake_python(self, body: str) -> None:
        """Install a `python3` that stands in for the run command."""
        (self.bin / "python3").write_text(
            "#!/usr/bin/env bash\n" + textwrap.dedent(body), encoding="utf-8")
        (self.bin / "python3").chmod(0o755)

    def run_script(self, *args: str, root: Path | None = None, timeout: int = 60):
        env = dict(os.environ)
        env["PATH"] = "%s:%s" % (self.bin, env["PATH"])
        # The runner resolves its tree from its own location, so it is copied into the sandbox.
        home = root or self.tmp / "repo"
        (home / "scripts").mkdir(parents=True, exist_ok=True)
        (home / "scripts" / "run_cohort.sh").write_text(
            SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
        return subprocess.run(
            ["bash", str(home / "scripts" / "run_cohort.sh"), *args],
            capture_output=True, text=True, env=env, timeout=timeout, cwd=str(home))

    # -- completion ----------------------------------------------------------------------------

    def test_a_run_without_a_manifest_is_not_treated_as_finished(self):
        """The old guard accepted a long trajectory, which is exactly what a clobbered run has."""
        home = self.tmp / "repo"
        stale = home / "runs" / "c" / "t_normal_s0"
        stale.mkdir(parents=True)
        (stale / "trajectory.jsonl").write_text("\n".join(
            json.dumps({"step": i, "valid": True, "score": 0.1}) for i in range(20)),
            encoding="utf-8")
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            mkdir -p "$out"; echo '{}' > "$out/run_manifest.json"
        ''')
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("done  t normal s0", result.stdout)
        self.assertTrue((stale / "run_manifest.json").is_file())

    def test_a_completed_run_is_skipped_on_resume(self):
        home = self.tmp / "repo"
        for mode in ("normal", "selection_blind"):
            done = home / "runs" / "c" / ("t_%s_s0" % mode)
            done.mkdir(parents=True)
            (done / "run_manifest.json").write_text("{}", encoding="utf-8")
        self.fake_python('echo "SHOULD NOT RUN" >> "%s"; exit 1' % self.calls)
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("already complete", result.stdout)
        self.assertFalse(self.calls.exists())
        self.assertIn("all runs have a manifest", result.stdout)

    # -- failure reporting ---------------------------------------------------------------------

    def test_a_failing_run_is_reported_rather_than_passing_silently(self):
        self.fake_python('echo "boom" >&2; exit 3')
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("FAIL  t normal s0", result.stdout)
        self.assertIn("MISSING t normal s0", result.stdout)
        self.assertIn("2 run(s) missing a manifest", result.stdout)

    def test_a_run_that_exits_zero_without_a_manifest_still_counts_as_failed(self):
        """Exit status alone is not the contract; the manifest is."""
        self.fake_python("exit 0")
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("FAIL  t normal s0", result.stdout)

    # -- locking -------------------------------------------------------------------------------

    def test_a_second_driver_does_not_enter_a_run_another_holds(self):
        home = self.tmp / "repo"
        (home / "scripts").mkdir(parents=True)
        # Both arms, so that anything running at all is a lock failure rather than the other arm
        # doing its job. A first version locked only `normal` and read the `selection_blind` run
        # as a breach.
        for mode in ("normal", "selection_blind"):
            lock = home / ".locks" / "c" / ("t_%s_s0" % mode)
            lock.mkdir(parents=True)
            # A pid that is alive: this test process.
            (lock / "pid").write_text(str(os.getpid()), encoding="utf-8")
        self.fake_python('echo ran >> "%s"; exit 1' % self.calls)
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0",
                                 "--only-missing", "T/t:t")
        self.assertIn("busy  t normal s0", result.stdout)
        self.assertIn("busy  t selection_blind s0", result.stdout)
        self.assertFalse(self.calls.exists())

    def test_a_lock_left_by_a_dead_driver_is_taken_over(self):
        """Otherwise a killed driver blocks that run permanently."""
        home = self.tmp / "repo"
        (home / "scripts").mkdir(parents=True)
        lock = home / ".locks" / "c" / "t_normal_s0"
        lock.mkdir(parents=True)
        # A pid that cannot be running: 0 is not a valid process to signal here, and a very high
        # pid would risk colliding with a real one.
        (lock / "pid").write_text("999999", encoding="utf-8")
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            mkdir -p "$out"; echo '{}' > "$out/run_manifest.json"
        ''')
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0",
                                 "--only-missing", "T/t:t")
        self.assertIn("stale t normal s0", result.stdout)
        self.assertIn("done  t normal s0", result.stdout)

    def test_the_lock_is_released_when_the_run_finishes(self):
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            mkdir -p "$out"; echo '{}' > "$out/run_manifest.json"
        ''')
        self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertFalse((self.tmp / "repo" / ".locks" / "c" / "t_normal_s0").exists())

    def test_locks_are_not_written_where_the_run_globs_will_find_them(self):
        """Reports glob runs/*/*; a lock directory there reads as a run with no manifest."""
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            sleep 0.3
            mkdir -p "$out"; echo '{}' > "$out/run_manifest.json"
        ''')
        self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        strays = [p.name for p in (self.tmp / "repo" / "runs" / "c").iterdir()
                  if "lock" in p.name]
        self.assertEqual(strays, [])

    # -- pairing -------------------------------------------------------------------------------

    def test_both_arms_of_a_seed_are_run(self):
        """A gap needs the same seed in both arms; running one is worse than running neither."""
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; --feedback-mode) mode="$arg" ;; esac
              prev="$arg"
            done
            echo "$mode" >> "%s"
            mkdir -p "$out"; echo '{}' > "$out/run_manifest.json"
        ''' % self.calls)
        self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0,1", "T/t:t")
        modes = sorted(self.calls.read_text(encoding="utf-8").split())
        self.assertEqual(modes, ["normal", "normal", "selection_blind", "selection_blind"])


if __name__ == "__main__":
    unittest.main()
