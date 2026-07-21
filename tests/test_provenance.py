from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_science.algorithms.abmcts_backend import TREEQUEST_COMMIT, TREEQUEST_VERSION
from frontier_science.algorithms.openevolve_backend import OPENEVOLVE_COMMIT, OPENEVOLVE_VERSION
from frontier_science.algorithms.shinkaevolve_backend import SHINKA_COMMIT, SHINKA_VERSION
from frontier_science.provenance import source_provenance


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_upstream_smokes.py"
SPEC = importlib.util.spec_from_file_location("merge_upstream_smokes_for_test", SCRIPT)
MERGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MERGE)


class SourceProvenanceTests(unittest.TestCase):
    def test_clean_and_dirty_source_are_distinguished(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frontier_science").mkdir()
            source = root / "frontier_science" / "x.py"
            source.write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "frontier_science/x.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)

            clean = source_provenance(root, command=["fixture"])
            self.assertTrue(clean["git_available"])
            self.assertFalse(clean["source_tree_dirty"])
            self.assertEqual(clean["command"], ["fixture"])

            source.write_text("x = 2\n", encoding="utf-8")
            dirty = source_provenance(root)
            self.assertTrue(dirty["source_tree_dirty"])
            self.assertTrue(any("frontier_science/x.py" in row for row in dirty["source_changes"]))


class MergeUpstreamSmokeTests(unittest.TestCase):
    def _child(self, backend, upstream, distribution, revision="abc", dirty=False):
        return {
            "schema_version": 1,
            "trust_status": "TRUSTED_SECURE_EVAL",
            "evidence_scope": "UPSTREAM_BASELINE_SMOKE_ONLY",
            "source_provenance": {
                "git_available": True,
                "git_revision": revision,
                "source_tree_dirty": dirty,
            },
            "execution_passed": True,
            "trusted_evidence": not dirty,
            "passed": True,
            "backends": [{
                "backend": backend,
                "status": "passed",
                "trajectory_schema_version": 2,
                "budget_units": 1,
                "oracle_calls": 1,
                "upstream": upstream,
                "installed_distribution": distribution,
                "expected_sealed_metric": "robustness_score",
                "sealed_metric_retained_in_trusted_trace": True,
                "sealed_metric_absent_from_search_state": True,
            }],
        }

    def _paths(self, root):
        children = [
            self._child("openevolve", {
                "name": "openevolve", "version": OPENEVOLVE_VERSION,
                "commit": OPENEVOLVE_COMMIT,
            }, {"package": "openevolve", "version": OPENEVOLVE_VERSION}),
            self._child(
                "abmcts", {"name": "treequest", "version": TREEQUEST_VERSION,
                           "commit": TREEQUEST_COMMIT},
                {"package": "treequest", "version": TREEQUEST_VERSION},
            ),
            self._child(
                "shinkaevolve", {"name": "shinkaevolve", "version": SHINKA_VERSION,
                                 "commit": SHINKA_COMMIT},
                {"package": "shinka-evolve", "version": SHINKA_VERSION, "direct_url": {
                    "vcs_info": {"commit_id": SHINKA_COMMIT},
                }},
            ),
        ]
        paths = []
        for index, child in enumerate(children):
            path = root / ("child_%d.json" % index)
            path.write_text(json.dumps(child), encoding="utf-8")
            paths.append(path)
        return paths

    def test_merge_requires_complete_clean_pinned_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(Path(tmp))
            clean = {"git_available": True, "git_revision": "abc",
                     "source_tree_dirty": False}
            with patch.object(MERGE, "source_provenance", return_value=clean):
                report = MERGE.merge_reports(paths)
            self.assertTrue(report["passed"], report["issues"])

    def test_merge_rejects_missing_or_dirty_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(Path(tmp))
            child = json.loads(paths[0].read_text(encoding="utf-8"))
            child["source_provenance"]["source_tree_dirty"] = True
            paths[0].write_text(json.dumps(child), encoding="utf-8")
            clean = {"git_available": True, "git_revision": "abc",
                     "source_tree_dirty": False}
            with patch.object(MERGE, "source_provenance", return_value=clean):
                report = MERGE.merge_reports(paths[:2])
            self.assertFalse(report["passed"])
            self.assertTrue(any("exactly one" in issue for issue in report["issues"]))
            self.assertTrue(any("clean source" in issue for issue in report["issues"]))

    def test_merge_rejects_metric_sealing_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(Path(tmp))
            child = json.loads(paths[1].read_text(encoding="utf-8"))
            child["backends"][0]["sealed_metric_absent_from_search_state"] = False
            paths[1].write_text(json.dumps(child), encoding="utf-8")
            clean = {"git_available": True, "git_revision": "abc",
                     "source_tree_dirty": False}
            with patch.object(MERGE, "source_provenance", return_value=clean):
                report = MERGE.merge_reports(paths)
            self.assertFalse(report["execution_passed"])
            self.assertTrue(any("metric sealing" in issue for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
