"""Tests for scripts/run_cohort.sh, the cohort runner.

This script exists because two ad-hoc drivers deleted each other's output and three runs vanished
from a thirty-six run comparison without anything reporting a failure. Its guarantees are worth
testing directly rather than trusting to review:

    a completed run is one with a manifest, not one with a long enough trajectory
    two drivers that collide on a run serialise instead of racing
    a lock left behind by a dead driver does not block the run forever
    a run that fails is reported, not silently skipped

The real runner is invoked, with a fake `python3` earlier on PATH standing in for
`sle run`. That keeps the shell logic under test - argument parsing, locking, the
completion check - rather than a reimplementation of it.
"""
from __future__ import annotations

import json
import os
import sys
import subprocess
import textwrap
import time
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
        """Install a `python3` that stands in for the run command.

        Only the run command. The runner also calls `python3 - ... <<PY` to decide whether a cell
        is already complete, and that check must reach a real interpreter: an earlier version of
        the runner spelled it `python` so this shim would not catch it, which held on machines
        with a `python` alias and broke on the benchmark host, which has none. The shim now hands
        any heredoc invocation (first argument `-`) to the interpreter running this test suite.
        """
        (self.bin / "python3").write_text(
            "#!/usr/bin/env bash\n"
            + 'if [[ "${1:-}" == "-" ]]; then exec "%s" "$@"; fi\n' % sys.executable
            + textwrap.dedent('''
                for fake_arg in "$@"; do
                  case "$fake_prev" in
                    --task) fake_task="$fake_arg" ;;
                    --feedback-mode) fake_mode="$fake_arg" ;;
                    --seed) fake_seed="$fake_arg" ;;
                    --algorithm) fake_algorithm="$fake_arg" ;;
                    --budget) fake_budget="$fake_arg" ;;
                    --workdir) fake_out="$fake_arg" ;;
                  esac
                  fake_prev="$fake_arg"
                done
            ''') + textwrap.dedent(body) + textwrap.dedent('''
                if [[ -f "$fake_out/run_manifest.json" && -f "$fake_out/summary.json" ]]; then
                  printf '{"task_id":"%s","feedback_mode":"%s","seed":%s,"algorithm":"%s"}\n' \
                    "$fake_task" "$fake_mode" "$fake_seed" "$fake_algorithm" \
                    > "$fake_out/run_manifest.json"
                  printf '{"task_id":"%s","feedback_mode":"%s","seed":%s,"algorithm":"%s","budget":%s}\n' \
                    "$fake_task" "$fake_mode" "$fake_seed" "$fake_algorithm" "$fake_budget" \
                    > "$fake_out/summary.json"
                fi
            '''), encoding="utf-8")
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

    def start_prepared_script(self, home: Path, *args: str):
        env = dict(os.environ)
        env["PATH"] = "%s:%s" % (self.bin, env["PATH"])
        (home / "scripts").mkdir(parents=True, exist_ok=True)
        (home / "scripts" / "run_cohort.sh").write_text(
            SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
        return subprocess.Popen(
            ["bash", str(home / "scripts" / "run_cohort.sh"), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=str(home),
        )

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
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''')
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("done  t normal s0", result.stdout)
        self.assertTrue((stale / "run_manifest.json").is_file())

    def test_a_completed_run_is_skipped_on_resume(self):
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''')
        first = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t"
        )
        self.assertEqual(first.returncode, 0, first.stdout)
        self.fake_python('echo "SHOULD NOT RUN" >> "%s"; exit 1' % self.calls)
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("already complete", result.stdout)
        self.assertFalse(self.calls.exists())
        self.assertIn("all runs have terminal artifacts", result.stdout)

    def test_completed_run_with_a_different_budget_is_a_conflict_not_a_skip(self):
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''')
        first = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0", "--budget", "3",
            "T/t:t",
        )
        self.assertEqual(first.returncode, 0, first.stdout)
        second = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0", "--budget", "12",
            "T/t:t",
        )
        self.assertNotEqual(second.returncode, 0, second.stdout)
        self.assertIn("CONFLICT t normal s0", second.stdout)
        self.assertNotIn("already complete", second.stdout)

    def test_completed_run_is_rejected_after_its_task_binding_changes(self):
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''')
        home = self.tmp / "repo"
        first = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0",
            "--modes", "normal", "T/t:t", root=home,
        )
        self.assertEqual(first.returncode, 0, first.stdout)
        manifest_path = home / "runs/c/t_normal_s0/run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({
            "llm_condition_sha256": "condition-v1",
            "task_contract_sha256": "contract-v1",
            "task_package_sha256": "package-v1",
            "runtime_source_sha256": "runtime-v1",
        })
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        (home / "sle/algorithms").mkdir(parents=True)
        for init in (home / "sle/__init__.py", home / "sle/algorithms/__init__.py"):
            init.write_text("", encoding="utf-8")
        (home / "sle/config.py").write_text(
            "def load_llm_client(_path): return object()\n", encoding="utf-8")
        (home / "sle/registry.py").write_text(
            "def find_task(_task, include_uncertified=False): return object()\n",
            encoding="utf-8",
        )
        common = home / "sle/algorithms/common.py"
        common.write_text(textwrap.dedent('''
            def llm_condition_sha256(_client): return "condition-v1"
            def task_contract_sha256(_spec): return "contract-v1"
            def task_package_sha256(_spec): return "package-v1"
            def runtime_source_sha256(): return "runtime-v1"
        '''), encoding="utf-8")

        self.fake_python('echo "SHOULD NOT RUN" >> "%s"; exit 1' % self.calls)
        unchanged = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0",
            "--modes", "normal", "T/t:t", root=home,
        )
        self.assertEqual(unchanged.returncode, 0, unchanged.stdout)
        self.assertIn("already complete", unchanged.stdout)

        common.write_text(common.read_text(encoding="utf-8").replace(
            'return "package-v1"', 'return "package-version-two"'
        ), encoding="utf-8")
        changed = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0",
            "--modes", "normal", "T/t:t", root=home,
        )
        self.assertNotEqual(changed.returncode, 0, changed.stdout)
        self.assertIn("CONFLICT t normal s0", changed.stdout)
        self.assertFalse(self.calls.exists())

    # -- failure reporting ---------------------------------------------------------------------

    def test_a_failing_run_is_reported_rather_than_passing_silently(self):
        self.fake_python('echo "boom" >&2; exit 3')
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("FAIL  t normal s0", result.stdout)
        self.assertIn("INCOMPLETE t normal s0", result.stdout)
        self.assertIn("2 run(s) incomplete", result.stdout)

    def test_a_run_that_exits_zero_without_a_manifest_still_counts_as_failed(self):
        """Exit status alone is not the contract; the manifest is."""
        self.fake_python("exit 0")
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        self.assertIn("FAIL  t normal s0", result.stdout)

    def test_a_manifest_written_before_failure_is_not_complete_or_skipped(self):
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            echo called >> "%s"
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            exit 3
        ''' % self.calls)
        first = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t"
        )
        second = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t"
        )
        self.assertNotEqual(first.returncode, 0, first.stdout)
        self.assertNotEqual(second.returncode, 0, second.stdout)
        self.assertNotIn("already complete", second.stdout)
        self.assertEqual(len(self.calls.read_text(encoding="utf-8").splitlines()), 4)

    # -- locking -------------------------------------------------------------------------------

    def test_a_second_driver_does_not_enter_a_run_another_holds(self):
        home = self.tmp / "repo"
        lock_holders = []
        for mode in ("normal", "selection_blind"):
            lock = home / ".locks" / "c" / ("t_%s_s0.lock" % mode)
            lock.parent.mkdir(parents=True, exist_ok=True)
            holder = subprocess.Popen(["flock", str(lock), "sleep", "2"])
            lock_holders.append(holder)
        def stop_holders():
            for process in lock_holders:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)

        self.addCleanup(stop_holders)
        time.sleep(0.1)
        self.fake_python('echo ran >> "%s"; exit 1' % self.calls)
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0",
                                 "--only-missing", "T/t:t")
        self.assertIn("busy  t normal s0", result.stdout)
        self.assertIn("busy  t selection_blind s0", result.stdout)
        self.assertFalse(self.calls.exists())

    def test_an_unlocked_file_left_by_a_dead_driver_does_not_block_the_run(self):
        home = self.tmp / "repo"
        (home / "scripts").mkdir(parents=True)
        lock = home / ".locks" / "c" / "t_normal_s0.lock"
        lock.parent.mkdir(parents=True)
        lock.touch()
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''')
        result = self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0",
                                 "--only-missing", "T/t:t")
        self.assertIn("done  t normal s0", result.stdout)

    def test_two_drivers_from_empty_lock_state_execute_each_cell_once(self):
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            echo "$fake_mode" >> "%s"
            sleep 1
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''' % self.calls)
        home = self.tmp / "repo"
        args = ("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        first = self.start_prepared_script(home, *args)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.calls.exists() and len(
                self.calls.read_text(encoding="utf-8").splitlines()
            ) == 2:
                break
            time.sleep(0.01)
        second = self.start_prepared_script(home, *args)
        first_stdout, _ = first.communicate(timeout=60)
        second_stdout, _ = second.communicate(timeout=60)
        self.assertEqual(first.returncode, 0, first_stdout)
        self.assertEqual(second.returncode, 0, second_stdout)
        self.assertEqual(
            sorted(self.calls.read_text(encoding="utf-8").splitlines()),
            ["normal", "selection_blind"],
        )

    def test_two_drivers_with_old_unlocked_files_execute_each_cell_once(self):
        home = self.tmp / "repo"
        lock_root = home / ".locks" / "c"
        lock_root.mkdir(parents=True)
        for mode in ("normal", "selection_blind"):
            (lock_root / ("t_%s_s0.lock" % mode)).touch()
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            echo "$fake_mode" >> "%s"
            sleep 0.3
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''' % self.calls)
        args = ("--cohort", "c", "--config", "x.yaml", "--seeds", "0", "T/t:t")
        first = self.start_prepared_script(home, *args)
        second = self.start_prepared_script(home, *args)
        first.communicate(timeout=60)
        second.communicate(timeout=60)
        self.assertEqual(
            sorted(self.calls.read_text(encoding="utf-8").splitlines()),
            ["normal", "selection_blind"],
        )

    def test_locks_are_not_written_where_the_run_globs_will_find_them(self):
        """Reports glob runs/*/*; a lock directory there reads as a run with no manifest."""
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; esac
              prev="$arg"
            done
            sleep 0.3
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
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
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''' % self.calls)
        self.run_script("--cohort", "c", "--config", "x.yaml", "--seeds", "0,1", "T/t:t")
        modes = sorted(self.calls.read_text(encoding="utf-8").split())
        self.assertEqual(modes, ["normal", "normal", "selection_blind", "selection_blind"])

    def test_modes_flag_runs_only_the_requested_arm(self):
        """Wave-1 open-loop scans must not also launch unpaired normal runs."""
        self.fake_python('''
            for arg in "$@"; do
              case "$prev" in --workdir) out="$arg" ;; --feedback-mode) mode="$arg" ;; esac
              prev="$arg"
            done
            echo "$mode" >> "%s"
            mkdir -p "$out"
            echo '{}' > "$out/run_manifest.json"
            echo '{}' > "$out/summary.json"
        ''' % self.calls)
        result = self.run_script(
            "--cohort", "c", "--config", "x.yaml", "--seeds", "0,1",
            "--modes", "selection_blind", "T/t:t")
        modes = sorted(self.calls.read_text(encoding="utf-8").split())
        self.assertEqual(modes, ["selection_blind", "selection_blind"])
        self.assertIn("all runs have terminal artifacts", result.stdout)


if __name__ == "__main__":
    unittest.main()
