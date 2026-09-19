from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from sle.evaluate import canonical_trusted_context, evaluate_candidate
from sle.metric_visibility import search_visible_metrics
from sle.registry import find_task
from _sandbox_tools import skip_unless_sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACTIVE = _load(
    "benchmarks/Mathematics/ActiveLawDiscovery/verification/evaluator.py",
    "track_f_active_law_oracle",
)


def _active_context(seed: int = 782347234) -> dict:
    return {
        "schema_version": 1,
        "purpose": "fresh_confirmation",
        "task_id": "DynamicalSystems/ActiveLawDiscovery",
        "generator": "active_law_fresh_v1",
        "panel_id": "track-f-test-active",
        "master_seed": seed,
        "world_count": 7,
    }


class ActiveLawConfirmationTests(unittest.TestCase):
    def test_panel_is_deterministic_balanced_and_answer_disjoint(self):
        first = ACTIVE._confirmation_specs(_active_context())
        second = ACTIVE._confirmation_specs(_active_context())
        other = ACTIVE._confirmation_specs(_active_context(782347235))
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 7)
        self.assertEqual(
            sorted(spec[3] for spec in first),
            ["in_library"] * 5 + ["misspecified", "null"],
        )
        self.assertEqual(
            sorted(spec[1] for spec in first if spec[3] == "in_library"),
            list(range(5)),
        )
        self.assertTrue(
            {spec[0] for spec in first}.isdisjoint(ACTIVE._STATIC_WORLD_SEEDS)
        )
        audit = ACTIVE.audit_confirmation_context(_active_context())
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["static_seed_overlap_count"], 0)

    def test_baseline_and_exact_oracle_calibrate_fresh_panel(self):
        context = _active_context()

        def abstain(n_states, term_names, experiment, _budget):
            experiment(np.zeros(n_states), np.zeros(8), 8)
            shape = (len(term_names), n_states)
            return {
                "coefficients": np.zeros(shape),
                "support": np.zeros(shape),
                "confidence": 0.0,
                "abstain": True,
            }

        specs = iter(ACTIVE._confirmation_specs(context))

        def exact(n_states, term_names, experiment, _budget):
            spec = next(specs)
            experiment(np.zeros(n_states), np.zeros(8), 8)
            world = ACTIVE._world(spec)
            support = np.abs(world["coefficients"]) > 0.0
            return {
                "coefficients": world["coefficients"],
                "support": support,
                "confidence": 1.0,
                "abstain": world["kind"] != "in_library",
            }

        baseline = ACTIVE.evaluate_with_context(abstain, context)
        reference = ACTIVE.evaluate_with_context(exact, context)
        self.assertEqual(baseline["valid"], 1.0)
        self.assertEqual(baseline["combined_score"], 0.0)
        self.assertEqual(reference["valid"], 1.0)
        self.assertAlmostEqual(reference["combined_score"], 1.0)
        self.assertEqual(reference["confirmation_false_discoveries"], 0)
        self.assertEqual(reference["confirmation_correct_abstentions"], 2)

    def test_invalid_or_tampered_context_fails_closed(self):
        for field, value in (
            ("task_id", "Optics/DiffractionGratingDesign"),
            ("generator", "active_law_fresh_v2"),
            ("world_count", 8),
            ("master_seed", -1),
        ):
            context = _active_context()
            context[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    ACTIVE._validate_confirmation_context(context)

    @skip_unless_sandbox("bwrap")  # exercises the candidate sandbox; skipped only where none can exist
    def test_secure_baseline_binds_context_and_seals_science_axes(self):
        spec = find_task(
            "DynamicalSystems/ActiveLawDiscovery", include_uncertified=True
        )
        context = _active_context()
        result = evaluate_candidate(
            spec,
            spec.initial_program_path,
            timeout_s=90,
            trusted_context=context,
        )
        expected = hashlib.sha256(canonical_trusted_context(context)).hexdigest()
        self.assertEqual(result["valid"], 1.0, result)
        self.assertEqual(result["combined_score"], 0.0)
        self.assertEqual(result["trusted_context_sha256"], expected)
        self.assertEqual(result["candidate_instance_call_count"], 7)
        visible = search_visible_metrics(result)
        self.assertNotIn("per_confirmation_world", visible)
        self.assertNotIn("confirmation_false_discoveries", visible)




if __name__ == "__main__":
    unittest.main()
