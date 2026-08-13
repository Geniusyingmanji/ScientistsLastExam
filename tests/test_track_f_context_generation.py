from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/generate_track_f_confirmation_contexts.py"
SPEC = importlib.util.spec_from_file_location(
    "track_f_context_generation_for_test", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrackFContextGenerationTests(unittest.TestCase):
    ROOT_ENTROPY = "42" * 32

    def test_seed_derivation_is_deterministic_and_domain_separated(self):
        first = MODULE.derive_master_seed(
            self.ROOT_ENTROPY, "DynamicalSystems/ActiveLawDiscovery", 0
        )
        self.assertEqual(
            first,
            MODULE.derive_master_seed(
                self.ROOT_ENTROPY, "DynamicalSystems/ActiveLawDiscovery", 0
            ),
        )
        values = {
            MODULE.derive_master_seed(self.ROOT_ENTROPY, task, replicate)
            for task in MODULE.SUPPORTED_TASKS
            for replicate in (0, 1)
        }
        self.assertEqual(len(values), 4)
        self.assertTrue(all(0 <= value < 2**63 for value in values))

    def test_private_manifest_and_public_commitment_are_separated(self):
        clean = {
            "git_available": True,
            "git_revision": "a" * 40,
            "source_tree_dirty": False,
            "source_changes": [],
            "source_scope": ["sle", "scripts", "tests", "benchmarks"],
            "command": ["test"],
        }
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            MODULE, "source_provenance", return_value=clean
        ):
            root = Path(temporary)
            private_path = root / "secrets" / "contexts.json"
            public_path = root / "nested" / "commitment.json"
            private, public = MODULE.generate(
                cohort_id="test-cohort",
                tasks=["DynamicalSystems/ActiveLawDiscovery"],
                replicates=[0, 1],
                root_entropy_hex=self.ROOT_ENTROPY,
                private_output=private_path,
                public_output=public_path,
                command=["test"],
            )
            private_bytes = private_path.read_bytes()
            public_text = public_path.read_text(encoding="utf-8")
            public_disk = json.loads(public_text)

            self.assertEqual(public_disk, public)
            self.assertEqual(private["root_entropy_hex"], self.ROOT_ENTROPY)
            self.assertEqual(len(private["blocks"]), 2)
            self.assertEqual(public["block_count"], 2)
            self.assertEqual(
                public["private_manifest_utf8_bytes"], len(private_bytes)
            )
            self.assertEqual(private_path.stat().st_mode & 0o777, 0o600)
            for forbidden in (
                self.ROOT_ENTROPY,
                "root_entropy_hex",
                "master_seed",
                '"worlds"',
                '"shifts"',
                '"anchors"',
            ):
                self.assertNotIn(forbidden, public_text)
            for block in public["blocks"]:
                self.assertEqual(
                    set(block),
                    {
                        "task", "replicate_id", "panel_id", "generator",
                        "world_count", "context_sha256", "context_utf8_bytes",
                    },
                )
                private_block = next(
                    value for value in private["blocks"]
                    if value["task"] == block["task"]
                    and value["replicate_id"] == block["replicate_id"]
                )
                self.assertEqual(
                    private_block["context_sha256"], block["context_sha256"]
                )

    def test_dirty_source_and_bad_entropy_fail_closed(self):
        dirty = {
            "git_available": True,
            "git_revision": "a" * 40,
            "source_tree_dirty": True,
            "source_changes": [" M benchmarks/task.py"],
        }
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            MODULE, "source_provenance", return_value=dirty
        ):
            root = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "clean source"):
                MODULE.generate(
                    cohort_id="dirty",
                    tasks=["DynamicalSystems/ActiveLawDiscovery"],
                    replicates=[0],
                    root_entropy_hex=self.ROOT_ENTROPY,
                    private_output=root / "private.json",
                    public_output=root / "public.json",
                )
        for invalid in ("", "AA" * 32, "0" * 63, "z" * 64):
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "entropy"
                path.write_text(invalid, encoding="utf-8")
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    MODULE._root_entropy(path)

    def test_main_refuses_to_overwrite_either_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private_path = root / "private.json"
            public_path = root / "public.json"
            private_path.write_text("occupied", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "overwrite"):
                MODULE.main([
                    "--cohort-id", "test",
                    "--tasks", "DynamicalSystems/ActiveLawDiscovery",
                    "--replicates", "0",
                    "--private-output", str(private_path),
                    "--public-output", str(public_path),
                ])


if __name__ == "__main__":
    unittest.main()
