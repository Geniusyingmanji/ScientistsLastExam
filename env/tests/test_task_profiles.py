"""Pure catalog tests: no World, runner, transport, model API or hidden data."""

import ast
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from env.task_profiles import (APPLICABLE_ENVIRONMENTS, DEFAULT_TASK_PROFILE,
                               TASK_PROFILE_CATALOG_VERSION, TASK_PROFILE_NAMES,
                               get_task_profile, list_task_profiles)


def test_task_profiles_stable_identity_default_and_applicability():
    assert DEFAULT_TASK_PROFILE == "open_discovery"
    assert TASK_PROFILE_NAMES == ("open_discovery", "mechanism_discrimination", "regime_transfer")
    assert TASK_PROFILE_CATALOG_VERSION == "scientific-task-profiles-0.1.0"
    assert APPLICABLE_ENVIRONMENTS == (
        "microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
        "gene_regulation", "ising_spin", "hysteresis_material",
    )
    assert get_task_profile() == get_task_profile("open_discovery")
    assert [p["name"] for p in list_task_profiles()] == list(TASK_PROFILE_NAMES)
    for environment in APPLICABLE_ENVIRONMENTS:
        assert list_task_profiles(environment) == list_task_profiles()
        for name in TASK_PROFILE_NAMES:
            profile = get_task_profile(name, environment)
            assert profile["version"] == name + "-0.1.0"
            assert profile["applicable_environments"] == list(APPLICABLE_ENVIRONMENTS)


def test_task_profiles_are_json_safe_defensive_copies():
    original = list_task_profiles()
    encoded = json.dumps(original, allow_nan=False)
    assert json.loads(encoded) == original
    returned = get_task_profile()
    returned["evidence_requirements"][0]["sources"].append("private_source")
    returned["applicable_environments"].clear()
    returned["success_semantics"]["automatic_depth_certification"] = True
    returned["public_prompt"] = "modified"
    listing = list_task_profiles()
    listing[1]["scientific_scope"]["does_not_establish"].clear()
    assert list_task_profiles() == original


def test_task_profiles_have_reviewable_evidence_without_scoring_changes():
    allowed_sources = {"research_notes", "explanation", "experiment_records", "analysis_records", "frozen_predictor"}
    allowed_timings = {"by_final_submission", "before_discriminating_result", "before_transfer_result"}
    for profile in list_task_profiles():
        ids = [item["id"] for item in profile["evidence_requirements"]]
        assert len(ids) == len(set(ids))
        assert len(ids) >= 4
        for item in profile["evidence_requirements"]:
            assert item["required"] is True
            assert isinstance(item["minimum_count"], int) and item["minimum_count"] >= 1
            assert item["count_unit"] and item["description"]
            assert set(item["sources"]) <= allowed_sources
            assert item["timing"] in allowed_timings
            assert item["assessment"] == "separate_scientific_evidence_review"
        semantics = profile["success_semantics"]
        assert semantics["unreviewed_status"] == "requires_evidence_review"
        assert semantics["missing_evidence_status"] == "not_demonstrated"
        assert semantics["prediction_score_effect"] == "none"
        assert semantics["automatic_checklist_verdict"] is False
        assert semantics["automatic_depth_certification"] is False
        assert semantics["numerical_claim_verification_certifies_mechanism"] is False
        assert profile["scientific_scope"]["hidden_reference_required"] is False
        assert profile["submission_contract"]["fields"] == ["predictor_code", "claims", "explanation"]
        assert profile["submission_contract"]["additional_required_fields"] == []


def test_task_profiles_require_distinct_scientific_workflows():
    open_profile = get_task_profile("open_discovery")
    discrimination = get_task_profile("mechanism_discrimination")
    transfer = get_task_profile("regime_transfer")
    discriminate_items = {item["id"]: item for item in discrimination["evidence_requirements"]}
    transfer_items = {item["id"]: item for item in transfer["evidence_requirements"]}
    assert discriminate_items["competing_mechanisms"]["minimum_count"] == 2
    assert discriminate_items["discriminating_prediction"]["timing"] == "before_discriminating_result"
    assert "identifiability_limits" in discriminate_items
    assert transfer_items["source_and_target_regimes"]["minimum_count"] == 2
    assert transfer_items["source_and_target_observations"]["minimum_count"] == 2
    assert transfer_items["prospective_target_prediction"]["timing"] == "before_transfer_result"
    assert "Independent fits" in transfer["public_prompt"]
    assert "identifiability" in discrimination["public_prompt"]
    assert all(item["timing"] == "by_final_submission" for item in open_profile["evidence_requirements"])
    assert len({p["public_prompt"] for p in list_task_profiles()}) == 3
    assert len({p["scientific_scope"]["primary_measure"] for p in list_task_profiles()}) == 3


@pytest.mark.parametrize("name", [None, True, 1, [], {}, "", "unknown", "OPEN_DISCOVERY"])
def test_task_profiles_reject_unknown_or_malformed_names(name):
    with pytest.raises(ValueError, match="unknown task profile"):
        get_task_profile(name)


@pytest.mark.parametrize("environment", [True, 1, [], {}, "", "unknown", "reaction"])
def test_task_profiles_reject_unknown_or_malformed_environment(environment):
    with pytest.raises(ValueError, match="not applicable"):
        get_task_profile(environment=environment)
    with pytest.raises(ValueError, match="not applicable"):
        list_task_profiles(environment=environment)


def test_task_profiles_have_no_private_imports_io_or_api_calls():
    path = Path(__file__).resolve().parents[1] / "task_profiles.py"
    source = path.read_text()
    tree = ast.parse(source, feature_version=(3, 8))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert len(imports) == 1
    assert isinstance(imports[0], ast.ImportFrom) and imports[0].module == "copy"
    assert [name.name for name in imports[0].names] == ["deepcopy"]
    forbidden_keys = {"world_seed", "panel_seed", "confirmation_key", "api_key", "hidden_parameters",
                      "golden_mechanism", "ground_truth", "model_client", "private_recipe"}

    def visit(value):
        if isinstance(value, dict):
            assert not (set(value) & forbidden_keys)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for profile in list_task_profiles():
        visit(profile)

    # Once loaded, every catalog operation works with all file and network
    # access blocked. No model client or environment instance is constructed.
    with patch("builtins.open", side_effect=AssertionError("unexpected file access")), \
         patch("pathlib.Path.read_text", side_effect=AssertionError("unexpected file access")), \
         patch("socket.socket", side_effect=AssertionError("unexpected network access")):
        for environment in APPLICABLE_ENVIRONMENTS:
            assert len(list_task_profiles(environment)) == 3
