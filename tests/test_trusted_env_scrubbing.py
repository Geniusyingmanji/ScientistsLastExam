"""A contributor's evaluator must not be handed the parent's credentials.

`verification/evaluator.py` runs in the trusted parent, not the candidate sandbox, because it
holds the hidden worlds and must not be reachable from candidate code. That places external
contributor code in a process that inherits whatever the operator's shell carries - and the
repository's own LLM configuration is documented as living in environment variables
(`api_key: ${ANTHROPIC_API_KEY}`), so a search or calibration run has a key in scope.

`sle/upstream_evaluator.py` already dropped credential-shaped variables before evaluating. The
main path in `sle/evaluate.py` did not, so `sle eval`, every cohort run and every calibration
handed the full environment through. No evaluator in the tree reads any environment variable at
all, so removing them costs nothing.

These tests pin the property rather than the wording, and check that both call sites share one
list so they cannot drift apart again.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sle.evaluate import CREDENTIAL_MARKERS, without_credentials


class TrustedEnvironmentScrubbingTests(unittest.TestCase):
    def test_credential_shaped_names_are_dropped(self):
        environment = {
            "ANTHROPIC_API_KEY": "sk-secret",
            "OPENAI_API_KEY": "sk-other",
            "AUTHORIZATION": "Bearer abc",
            "GH_TOKEN": "ghp_xyz",
            "CLAUDE_CODE_MESSAGING_TOKEN": "t",
            "api_key_lowercase": "also secret",
            "DB_PASSWORD": "password",
            "AWS_SECRET_ACCESS_KEY": "credential",
            "SERVICE_CREDENTIAL": "credential",
        }
        scrubbed = without_credentials(dict(environment))
        self.assertEqual(scrubbed, {})

    def test_everything_else_survives(self):
        environment = {
            "PATH": "/usr/bin",
            "HOME": "/home/runner",
            "OMP_NUM_THREADS": "1",
            "PYTHONHASHSEED": "0",
            "SLE_REQUIRE_FROZEN_INVENTORY": "1",
            "KEYBOARD_LAYOUT": "us",  # contains KEY but is not API_KEY
        }
        self.assertEqual(without_credentials(dict(environment)), environment)

    def test_matching_is_case_insensitive_and_substring(self):
        for name in ("MY_API_KEY_2", "x-authorization", "SomeToken", "TOKEN"):
            with self.subTest(name=name):
                self.assertEqual(without_credentials({name: "v"}), {})

    def test_the_trusted_child_environment_is_scrubbed(self):
        """The property that matters: what `evaluate_candidate` hands the driver.

        Asserted at the boundary by intercepting the Popen call, so it covers the real
        composition of the child environment rather than the helper in isolation.
        """
        import sle.evaluate as evaluate_module
        from sle.registry import find_task

        captured = {}

        class FakePopen:
            def __init__(self, *args, **kwargs):
                captured["env"] = kwargs.get("env")
                raise RuntimeError("stop here: the environment is what this test is about")

        spec = find_task("LennardJonesCluster", include_uncertified=True)
        secrets = {"ANTHROPIC_API_KEY": "sk-must-not-pass", "GH_TOKEN": "ghp-must-not-pass"}
        runtime = evaluate_module.TrustedRuntime(
            executable="/usr/bin/python3",
            descriptor={"fingerprint_sha256": "a" * 64},
        )
        with patch.dict(os.environ, secrets, clear=False), \
             patch.object(evaluate_module, "resolve_trusted_runtime", return_value=runtime), \
             patch.object(evaluate_module.subprocess, "Popen", FakePopen):
            with self.assertRaises(RuntimeError):
                evaluate_module.evaluate_candidate(
                    spec, spec.initial_program_path, timeout_s=5)

        self.assertIsNotNone(captured.get("env"), "Popen was never reached")
        child = captured["env"]
        for name in secrets:
            with self.subTest(name=name):
                self.assertNotIn(name, child)
        # The thread pins the trusted path sets are still there, so this did not just empty it.
        self.assertEqual(child.get("OMP_NUM_THREADS"), "1")
        self.assertIn("PATH", child)

    def test_both_call_sites_share_one_marker_list(self):
        """A second copy of the list is how the two paths diverged in the first place."""
        import pathlib
        source = (pathlib.Path(__file__).resolve().parents[1]
                  / "sle" / "upstream_evaluator.py").read_text(encoding="utf-8")
        self.assertIn("CREDENTIAL_MARKERS", source)
        self.assertNotIn('("API_KEY", "AUTHORIZATION", "TOKEN")', source)
        from sle.frontier_eval_entrypoint import SENSITIVE_MARKERS
        self.assertEqual(CREDENTIAL_MARKERS, SENSITIVE_MARKERS)


if __name__ == "__main__":
    unittest.main()
