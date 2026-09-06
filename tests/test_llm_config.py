"""LLM configuration must resolve required environment references fail closed."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sle.config import load_llm_client
from sle.llm import LLMConfig


class LLMConfigTests(unittest.TestCase):
    def test_missing_environment_reference_is_rejected_before_network_use(self):
        variable = "SLE_TEST_REQUIRED_API_KEY"
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "llm.yaml"
            config.write_text(f"api_key: ${{{variable}}}\n", encoding="utf-8")
            with (
                patch.dict(os.environ, {}, clear=False),
                patch("urllib.request.urlopen") as urlopen,
            ):
                os.environ.pop(variable, None)
                with self.assertRaises(ValueError) as caught:
                    load_llm_client(str(config))

        self.assertEqual(
            str(caught.exception),
            f"required environment variable {variable} is missing or empty",
        )
        urlopen.assert_not_called()

    def test_empty_environment_reference_is_rejected_without_config_values(self):
        variable = "SLE_TEST_EMPTY_BASE_URL"
        with (
            patch.dict(os.environ, {variable: ""}),
            self.assertRaises(ValueError) as caught,
        ):
            LLMConfig.from_dict(
                {"base_url": f"${{{variable}}}", "api_key": "literal-private-value"}
            )

        message = str(caught.exception)
        self.assertEqual(
            message,
            f"required environment variable {variable} is missing or empty",
        )
        self.assertNotIn("literal-private-value", message)
        self.assertNotIn("${", message)

    def test_literal_config_values_remain_supported(self):
        config = LLMConfig.from_dict(
            {
                "base_url": "https://literal.invalid/v1",
                "api_key": "literal-test-key",
                "model": "literal-test-model",
            }
        )

        self.assertEqual(config.base_url, "https://literal.invalid/v1")
        self.assertEqual(config.api_key, "literal-test-key")
        self.assertEqual(config.model, "literal-test-model")


if __name__ == "__main__":
    unittest.main()
