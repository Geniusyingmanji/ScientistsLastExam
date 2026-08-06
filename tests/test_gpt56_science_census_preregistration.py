from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/build_gpt56_science_census_preregistration.py"
)
SPEC = importlib.util.spec_from_file_location("gpt56_science_census_builder", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GPT56ScienceCensusPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort, cls.preregistration = MODULE.build_documents()

    def test_complete_admitted_census_is_frozen(self):
        rows = self.cohort["tasks"]
        self.assertEqual(len(rows), 50)
        self.assertEqual(len({row["task"] for row in rows}), 50)
        self.assertEqual(
            self.cohort["selection"]["admitted_status_counts"],
            {"candidate": 43, "certified": 7},
        )
        self.assertEqual(
            len(self.cohort["selection"]["excluded_tasks"]), 9
        )

    def test_execution_contract_matches_manifest_exactly(self):
        self.assertEqual(
            MODULE.validate_documents(self.cohort, self.preregistration), []
        )

    def test_model_condition_matches_pilot(self):
        model = self.preregistration["model_condition"]
        self.assertEqual(model["model"], "gpt-5.6-sol")
        self.assertEqual(model["reasoning_effort"], "low")
        self.assertEqual(model["max_output_tokens"], 16000)
        self.assertEqual(
            model["llm_condition_sha256"],
            MODULE.EXPECTED_PILOT_CONDITION_SHA256,
        )

    def test_budget_one_does_not_claim_self_evolution(self):
        self.assertEqual(self.preregistration["design"]["proposal_budget"], 1)
        self.assertIn(
            "cannot establish",
            self.preregistration["predeclared_descriptive_gates"][
                "self_evolving_fit"
            ],
        )

    def test_failure_policy_separates_protocol_and_science(self):
        bands = self.preregistration["primary_outcomes"]["difficulty_bands"]
        self.assertIn("do not call this scientific difficulty", bands["protocol_blocked"])
        self.assertIn("valid proposal", bands["executable_floor"])


if __name__ == "__main__":
    unittest.main()
