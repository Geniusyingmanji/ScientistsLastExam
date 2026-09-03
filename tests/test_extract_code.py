"""Pin code extraction for truncated hy3 streams.

The searcher is told to return one fenced Python block. On this host hy3-ioa has
hit max_output_tokens with the fence still open, and the old parser treated that
as `no_code` even when a `def` was already on the page. A closed fence still
wins; an unclosed fence is only recovered when it looks like a program.
"""
from __future__ import annotations

import unittest

from sle.algorithms.evolve import extract_code


class ExtractCodeTests(unittest.TestCase):
    def test_a_closed_fence_is_taken(self):
        text = "note\n```python\ndef discover_phases(problem, synthesize):\n    return {}\n```\n"
        self.assertEqual(
            extract_code(text),
            "def discover_phases(problem, synthesize):\n    return {}",
        )

    def test_an_unclosed_fence_that_defines_the_entrypoint_is_recovered(self):
        text = (
            "I will rewrite the program.\n"
            "```python\n"
            "def discover_phases(problem, synthesize):\n"
            "    return {'abstain': True}\n"
        )
        code = extract_code(text)
        self.assertEqual(
            code,
            "def discover_phases(problem, synthesize):\n    return {'abstain': True}",
        )
        compile(code, "<candidate>", "exec")

    def test_prose_without_a_program_is_not_a_candidate(self):
        self.assertIsNone(extract_code("Here is my plan for the phase diagram."))

    def test_a_closed_fence_wins_over_trailing_prose(self):
        text = "```python\ndef f():\n    return 1\n```\nand then more talk"
        self.assertEqual(extract_code(text), "def f():\n    return 1")


if __name__ == "__main__":
    unittest.main()
