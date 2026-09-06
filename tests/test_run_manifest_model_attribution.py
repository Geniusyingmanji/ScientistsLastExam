"""A run must be attributable to the model that produced it, not only reproducible.

The manifest has always carried `llm_condition_sha256`, which binds the searcher condition and
detects drift. A hash cannot be read back, so it cannot answer "which model produced this run",
and it cannot confirm that a comparison across runs held the model fixed. This was not
hypothetical: a paired experiment in this repository was analysed for some time before the model
behind it could be identified at all.

These tests pin the readable descriptor beside the hash, and pin the two properties that make it
safe to add: it must not write credentials to disk, and it must not invalidate the resume of a
run recorded before the field existed.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sle.algorithms import common


class _Config:
    wire = "responses"
    base_url = "http://proxy.internal:9877/v1?access_token=SUPERSECRET"
    model = "gpt-5.5"
    max_output_tokens = 8000
    temperature = None
    reasoning_effort = "low"
    timeout_seconds = 900
    extra_headers = {"Authorization": "Bearer SUPERSECRET"}
    input_cost_per_million = None
    output_cost_per_million = None


class _Client:
    config = _Config()


class RunManifestModelAttributionTests(unittest.TestCase):
    def test_descriptor_names_the_model_and_its_decoding_condition(self):
        descriptor = common.llm_condition_descriptor(_Client())
        self.assertEqual(descriptor["model"], "gpt-5.5")
        self.assertEqual(descriptor["wire"], "responses")
        self.assertEqual(descriptor["reasoning_effort"], "low")
        self.assertEqual(descriptor["max_output_tokens"], 8000)
        self.assertEqual(descriptor["timeout_seconds"], 900)
        self.assertFalse(descriptor["chat_reasoning_fallback"])
        self.assertFalse(descriptor["server_side_seed_control"])
        self.assertEqual(
            descriptor["endpoint_sha256"],
            "d3bdaecabc50dadbfd9a8e477c2708be23914bac0ad13d2977d2af5adf732a1d",
        )

    def test_descriptor_never_writes_a_credential_to_disk(self):
        descriptor = common.llm_condition_descriptor(_Client())
        self.assertNotIn("SUPERSECRET", json.dumps(descriptor))
        # The host is kept because it distinguishes proxies; the query string is not.
        self.assertEqual(descriptor["base_url_host"], "proxy.internal:9877")
        self.assertNotIn("base_url", descriptor)

    def test_descriptor_degrades_rather_than_raising_without_a_config(self):
        class Bare:
            pass

        self.assertEqual(
            common.llm_condition_descriptor(Bare()), {"client_type": "Bare"}
        )

    def test_default_false_stream_flag_preserves_the_legacy_condition_hash(self):
        class ExplicitFalse(_Config):
            stream = False

        class Streaming(_Config):
            stream = True

        class FalseClient:
            config = ExplicitFalse()

        class StreamClient:
            config = Streaming()

        self.assertEqual(
            common.llm_condition_sha256(_Client()),
            common.llm_condition_sha256(FalseClient()),
        )
        self.assertEqual(
            common.llm_condition_sha256(_Client()),
            "bfa30402d45305dd5504080f44c793c444fa4268dfe7bfce840c32c24d6da842",
        )
        self.assertNotEqual(
            common.llm_condition_sha256(_Client()),
            common.llm_condition_sha256(StreamClient()),
        )

    def test_wire_and_reasoning_budget_changes_have_distinct_condition_hashes(self):
        class ChangedChatField(_Config):
            chat_max_tokens_field = "max_completion_tokens"

        class ChangedAnthropicVersion(_Config):
            anthropic_version = "2099-01-01"

        class ThinkingBudget(_Config):
            thinking_budget_tokens = 4000

        hashes = {common.llm_condition_sha256(_Client())}
        for config in (ChangedChatField, ChangedAnthropicVersion, ThinkingBudget):
            client = type("Client", (), {"config": config()})()
            hashes.add(common.llm_condition_sha256(client))
        self.assertEqual(len(hashes), 4)

    def test_malformed_base_url_does_not_break_a_run(self):
        class Odd(_Config):
            base_url = "::not a url::"

        class OddClient:
            config = Odd()

        descriptor = common.llm_condition_descriptor(OddClient())
        self.assertEqual(descriptor["model"], "gpt-5.5")

    def test_resume_still_matches_a_manifest_written_before_the_field_existed(self):
        """The descriptor is documentation; `llm_condition_sha256` is what binds the run."""
        client = _Client()
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with patch.object(common, "task_contract_sha256", return_value="a" * 64), \
                 patch.object(common, "task_package_sha256", return_value="b" * 64), \
                 patch.object(common, "runtime_source_sha256", return_value="c" * 64):
                written = common.ensure_run_manifest(
                    workdir, spec=_Spec(), llm=client, algorithm="greedy_rewrite",
                    seed=0, feedback_mode="normal", resume=False,
                )
                self.assertIn("llm_condition", written)

                # Simulate a manifest recorded before the descriptor existed.
                path = workdir / "run_manifest.json"
                legacy = json.loads(path.read_text(encoding="utf-8"))
                legacy.pop("llm_condition")
                path.write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8")

                common.ensure_run_manifest(
                    workdir, spec=_Spec(), llm=client, algorithm="greedy_rewrite",
                    seed=0, feedback_mode="normal", resume=True,
                )

    def test_resume_still_rejects_a_changed_binding_condition(self):
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            with patch.object(common, "task_contract_sha256", return_value="a" * 64), \
                 patch.object(common, "task_package_sha256", return_value="b" * 64), \
                 patch.object(common, "runtime_source_sha256", return_value="c" * 64):
                common.ensure_run_manifest(
                    workdir, spec=_Spec(), llm=_Client(), algorithm="greedy_rewrite",
                    seed=0, feedback_mode="normal", resume=False,
                )
                with self.assertRaises(ValueError):
                    common.ensure_run_manifest(
                        workdir, spec=_Spec(), llm=_Client(), algorithm="greedy_rewrite",
                        seed=1, feedback_mode="normal", resume=True,
                    )


class _Spec:
    task_id = "Chemistry/Example"


if __name__ == "__main__":
    unittest.main()
