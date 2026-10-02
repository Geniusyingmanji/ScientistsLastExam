"""Presentation smoke tests: no model API, campaign or numerical score changes."""

import ast
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from env.claim_semantics import claim_eligibility, policy_description
from env.presentation_profiles import (
    APPARATUS_ENVIRONMENTS, DEFAULT_PRESENTATION_PROFILE,
    PRESENTATION_CATALOG_VERSION, PRESENTATION_PROFILE_NAMES,
    get_presentation_profile, leakage_boundary, present_problem, present_system,
)
from env.registry import ENVIRONMENTS, load_world
from env.runner import DEFAULT_LIMITS, SYSTEM
from env.scoring import canonical_hash, score_contract
from env.task_profiles import get_task_profile


def assembled_problem(world, task="open_discovery"):
    result = world.describe()
    result["task_profile"] = get_task_profile(task, world.name)
    result["score_contract"] = score_contract()
    result["submission_contract"] = {
        "entrypoint": "predict(spec)",
        "returns": "values array only; exact public channel order",
        "claim_count": "0..3", "claim_replicates_per_arm": 8,
    }
    return result


def test_presentation_catalog_is_separate_opt_in_and_operator_only():
    assert DEFAULT_PRESENTATION_PROFILE == "full_description"
    assert PRESENTATION_PROFILE_NAMES == ("full_description", "apparatus_only")
    assert PRESENTATION_CATALOG_VERSION == "presentation-profiles-0.1.0"
    assert APPARATUS_ENVIRONMENTS == ("coupled_oscillators", "ising_spin")
    for name in PRESENTATION_PROFILE_NAMES:
        profile = get_presentation_profile(name)
        assert profile["operator_only"] is True
        assert profile["world_request_observation_and_scoring_changes"] is False
        assert profile["task_profile_override"] is None
        assert profile["default_enabled"] == (name == "full_description")
        assert json.loads(json.dumps(profile, allow_nan=False)) == profile
    boundary = leakage_boundary()
    assert boundary["operator_only"] is True
    assert len(boundary["retained"]) >= 6 and len(boundary["withheld"]) >= 7
    assert any("actuator laws" in text for text in boundary["residual_information"])
    assert any("baselines" in text for text in boundary["residual_information"])
    boundary["retained"].clear()
    assert leakage_boundary()["retained"]


@pytest.mark.parametrize("environment", ENVIRONMENTS)
@pytest.mark.parametrize("task", ["open_discovery", "mechanism_discrimination", "regime_transfer"])
def test_default_preserves_every_current_environment_and_task_exactly(environment, task):
    world, _ = load_world(environment, 17)
    original = assembled_problem(world, task)
    encoded = json.dumps(original, sort_keys=True, separators=(",", ":"), allow_nan=False)
    projected = present_problem(original)
    assert json.dumps(projected, sort_keys=True, separators=(",", ":"), allow_nan=False) == encoded
    assert projected is not original
    assert projected["task_profile"] is not original["task_profile"]
    assert projected["score_contract"] is not original["score_contract"]
    assert present_system(SYSTEM) == SYSTEM
    projected["task_profile"]["name"] = "modified"
    assert original["task_profile"]["name"] == task


def test_full_description_preserves_custom_world_extensions_without_new_restrictions():
    info = {"name": "linear-test", "extra": {"untouched": [1, 2]}, "new_contract": True}
    assert present_problem(info, environment="linear-test") == info
    assert present_system("custom system") == "custom system"


@pytest.mark.parametrize("environment", APPARATUS_ENVIRONMENTS)
@pytest.mark.parametrize("task", ["open_discovery", "mechanism_discrimination", "regime_transfer"])
def test_apparatus_public_problem_removes_family_routes_and_preserves_measurements(environment, task):
    world, _ = load_world(environment, 23)
    original = assembled_problem(world, task)
    before = deepcopy(original)
    projected = present_problem(original, "apparatus_only", environment=environment)
    assert original == before
    assert projected["name"] == "apparatus"
    assert projected["version"] == "apparatus-interface-0.1.0"
    assert projected["axis_field"] == world.axis_field
    for key in ("nodes", "channels", "channel_units", "scales", "noise_std"):
        assert projected[key] == original[key]
    assert projected["task_profile"] == {key: value for key, value in original["task_profile"].items() if key != "applicable_environments"}
    assert projected["submission_contract"] == original["submission_contract"]
    for key in original["score_contract"]:
        if key != "claim_eligibility":
            assert projected["score_contract"][key] == original["score_contract"][key]
    assert "claim_eligibility" in projected["score_contract"]
    assert "episode_limits" in projected["budget"]
    encoded = json.dumps(projected, allow_nan=False).lower()
    # Regression checks supplement the manually stated information boundary;
    # a keyword test alone would not establish model-family concealment.
    forbidden = [
        "coupled_oscillators", "ising_spin", "microecology", "reaction_kinetics",
        "heat_transport", "gene_regulation", "physical_family", "candidate_family",
        "hamiltonian", "boltzmann", "gibbs", "ising", "spring", "viscous",
        "unknown_ranges", "higher-order", "nonlinear", "connected graph",
        "susceptibility", "frustrat", "enumerat", "matrix exponential",
        "k_ij", "j_ij", "intrinsic_drag", "grounding_stiffness",
        "world_seed", "panel_seed", "confirmation_key", "operator_only",
    ]
    for term in forbidden:
        assert term not in encoded
    assert json.loads(json.dumps(projected, allow_nan=False)) == projected
    projected["scales"][0] = 999
    assert present_problem(original, "apparatus_only")["scales"][0] == original["scales"][0]


@pytest.mark.parametrize("environment", APPARATUS_ENVIRONMENTS)
def test_apparatus_examples_use_unchanged_legal_specs_and_observations(environment):
    world, _ = load_world(environment, 7)
    public = present_problem(world.describe(), "apparatus_only")
    required = public["experiment_schema"]["required"]
    assert required == [world.axis_field]
    for index, spec in enumerate(public["examples"]):
        assert set(required) <= set(spec)
        canonical = world.validate(spec)
        before = world.run(canonical, noise_key="public-example-%d" % index)
        repeated_public = present_problem(world.describe(), "apparatus_only")
        after = world.run(repeated_public["examples"][index], noise_key="public-example-%d" % index)
        assert before == after
        assert before["channels"] == public["channels"]
        assert before["axis"] == canonical[world.axis_field]
        assert len(before["values"]) == len(canonical[world.axis_field])
        assert all(len(row) == len(public["channels"]) for row in before["values"])


def test_mechanical_apparatus_retains_full_operational_range_and_known_actuators():
    world, _ = load_world("coupled_oscillators", 1)
    public = present_problem(world.describe(), "apparatus_only")
    schema = public["experiment_schema"]
    assert schema["times"]["length"] == [1, 241]
    assert schema["times"]["range"] == [0, 24]
    assert schema["cut_edges"]["max_length"] == 6
    assert schema["clamp"]["max_length"] == 4
    assert public["apparatus_calibration"]["unloaded_mass_kg"] == [1] * 4
    for key, bounds in (("initial_position", [-1, 1]), ("initial_velocity", [-2, 2]), ("mass_add", [0, 3]), ("damping_add", [0, 2])):
        assert schema[key]["range"] == bounds
        assert schema[key]["default"] == [0] * 4
        for endpoint in bounds:
            world.validate({"times": [0, 24], key: [endpoint] * 4})
        with pytest.raises(ValueError):
            world.validate({"times": [0], key: [bounds[1] + 0.01] * 4})
    assert "-damping_add_i*v_i" in schema["damping_add"]["action"]
    assert "amplitude*sin" in schema["drive"]["calibration"]
    assert schema["drive"]["amplitude"]["range"] == [-2, 2]
    assert schema["drive"]["frequency"]["range"] == [0, 2]
    assert world.cost({"times": [0]}) == public["cost"]["range"][0]
    assert world.cost({"times": [i / 10 for i in range(241)]}) == public["cost"]["range"][1]
    with pytest.raises(ValueError):
        world.validate({"times": [0], "clamp": ["A"], "initial_position": [1, 0, 0, 0]})
    with pytest.raises(ValueError):
        world.validate({"times": [0], "clamp": ["A"], "drive": {"node": "A", "amplitude": 1, "frequency": 1, "phase": 0}})


def test_binary_apparatus_retains_ensemble_axis_raw_moments_and_control_calibration():
    world, _ = load_world("ising_spin", 1)
    public = present_problem(world.describe(), "apparatus_only")
    schema = public["experiment_schema"]
    assert schema["temperatures"]["length"] == [1, 32]
    assert schema["temperatures"]["range"] == [0.35, 6]
    assert schema["external_field"]["range"] == [-2, 2]
    assert schema["external_field"]["default"] == [0] * 6
    assert "-external_field_i*s_i" in schema["external_field"]["calibration"]
    assert schema["clamp"]["max_length"] == 6
    assert schema["suppress_bonds"]["max_length"] == 15
    assert schema["suppress_bonds"]["fraction"]["range"] == [0, 1]
    assert "not covariance" in public["channel_definitions"]["c_LEFT_RIGHT"]
    assert "not a cooling trajectory" in public["apparatus_calibration"]["reset"]
    assert "preserving its sign" in schema["suppress_bonds"]["action"]
    world.validate({"temperatures": [0.35, 6], "external_field": [-2, 2] * 3, "clamp": {"A": -1, "F": 1}})
    assert world.cost({"temperatures": [1]}) == public["cost"]["range"][0]
    assert world.cost({"temperatures": [0.35 + i * 0.1 for i in range(32)]}) == public["cost"]["range"][1]
    for invalid in (0, 1.0, True):
        with pytest.raises(ValueError):
            world.validate({"temperatures": [1], "clamp": {"A": invalid}})


def test_scoped_claim_documentation_preserves_existing_eligibility_decisions():
    common = policy_description()
    for environment in APPARATUS_ENVIRONMENTS:
        world, _ = load_world(environment, 0)
        projected = present_problem(assembled_problem(world), "apparatus_only")
        rule = projected["score_contract"]["claim_eligibility"]
        assert rule["protocol"] == common["protocol"]
        assert rule["reason_codes"] == common["reason_codes"]
        assert rule["absolute_coordinate_tolerance"] == common["absolute_coordinate_tolerance"]
        if environment == "coupled_oscillators":
            assert rule["minimum_lag"] == common["minimum_lag"][environment]
            assert rule["readout_rule"] == common["oscillator_rule"]
            control = world.validate({"times": [0.24, 0.25, 1]})
            treatment = world.validate({"times": [0.24, 0.25, 1], "clamp": ["A"]})
            assert not claim_eligibility(environment, control, treatment, {"row": 0, "channel": "x_B"}, world.axis_field)["eligible"]
            assert claim_eligibility(environment, control, treatment, {"row": 1, "channel": "x_B"}, world.axis_field)["eligible"]
            assert not claim_eligibility(environment, control, treatment, {"row": 2, "channel": "x_A"}, world.axis_field)["eligible"]
        else:
            assert rule["minimum_lag"] is None
            assert rule["readout_rule"] == common["ising_rule"]
            control = world.validate({"temperatures": [0.5]})
            treatment = world.validate({"temperatures": [1.5], "clamp": {"A": 1, "B": -1}})
            assert claim_eligibility(environment, control, treatment, {"row": 0, "channel": "m_C"}, world.axis_field)["eligible"]
            assert not claim_eligibility(environment, control, treatment, {"row": 0, "channel": "c_A_B"}, world.axis_field)["eligible"]


def test_apparatus_system_prompt_preserves_action_and_submission_protocol():
    projected = present_system(SYSTEM, "apparatus_only")
    assert "equilibrium spin systems" not in projected
    assert "after t=0" not in projected
    assert "apparatus's public claim_eligibility" in projected
    before, _, after = SYSTEM.partition("Row is zero-based")
    suffix = after[after.index("Read the full score contract."):]
    assert projected.startswith(before)
    assert projected.endswith(suffix)
    assert "eight fresh" in projected
    assert "numpy/scipy" in projected
    assert "predict(spec)" in projected
    assert "up to 3" in projected
    assert 'records[0]["observation"]["values"]' in projected
    assert "candidate's line number" in projected


@pytest.mark.parametrize("profile", [None, True, 1, [], {}, "", "unknown", "open_discovery"])
def test_presentation_rejects_invalid_profile_without_repurposing_task_names(profile):
    with pytest.raises(ValueError, match="unknown presentation profile"):
        get_presentation_profile(profile)
    with pytest.raises(ValueError, match="unknown presentation profile"):
        present_problem({}, profile)
    with pytest.raises(ValueError, match="unknown presentation profile"):
        present_system(SYSTEM, profile)


@pytest.mark.parametrize("environment", [True, 2, [], {}, "", "unknown", "heat_transport"])
def test_apparatus_rejects_unsupported_or_malformed_environment(environment):
    world, _ = load_world("ising_spin", 0)
    with pytest.raises(ValueError, match="not audited"):
        present_problem(world.describe(), "apparatus_only", environment=environment)
    with pytest.raises(ValueError, match="not audited"):
        get_presentation_profile("apparatus_only", environment)


@pytest.mark.parametrize("location", ["unknown_top", "physical_family", "version", "channel", "noise", "task_profile", "score_contract", "submission_contract"])
def test_apparatus_fails_closed_on_unreviewed_source_or_attachment_changes(location):
    world, _ = load_world("ising_spin", 7)
    source = assembled_problem(world)
    secret = "UNREVIEWED_PRIVATE_MECHANISM_CANARY"
    if location == "unknown_top":
        source["new_mechanism"] = secret
    elif location == "physical_family":
        source["physical_family"]["new_hint"] = secret
    elif location == "version":
        source["version"] = "new-version"
    elif location == "channel":
        source["channels"][0] = secret
    elif location == "noise":
        source["noise_std"][0] = 1
    else:
        source[location]["new_hint"] = secret
    with pytest.raises(ValueError, match="audit") as failure:
        present_problem(source, "apparatus_only")
    assert secret not in str(failure.value)
    # The opt-in guard never becomes a new restriction on existing behavior.
    assert present_problem(source) == source


def test_apparatus_requires_matching_identity_and_finite_bounded_public_json():
    world, _ = load_world("ising_spin", 0)
    with pytest.raises(ValueError, match="identity"):
        present_problem(world.describe(), "apparatus_only", environment="coupled_oscillators")
    for info in (None, [], 1):
        with pytest.raises(ValueError, match="object"):
            present_problem(info)
    for value in (float("nan"), "x" * 128001, object()):
        info = world.describe()
        info["extra"] = value
        with pytest.raises(ValueError, match="bounded finite JSON"):
            present_problem(info, "apparatus_only")
    for system in (SYSTEM + " changed", "\ud800"):
        with pytest.raises(ValueError, match="requires an audit"):
            present_system(system, "apparatus_only")
    with pytest.raises(ValueError, match="text"):
        present_system(None)


def test_apparatus_projection_does_not_read_worlds_files_network_or_private_parameters():
    prepared = []
    for environment in APPARATUS_ENVIRONMENTS:
        world, _ = load_world(environment, 38)
        prepared.append((world, assembled_problem(world)))
    with patch("builtins.open", side_effect=AssertionError("unexpected file access")), \
         patch("pathlib.Path.read_text", side_effect=AssertionError("unexpected file access")), \
         patch("socket.socket", side_effect=AssertionError("unexpected network access")):
        for world, info in prepared:
            with patch.object(type(world), "__init__", side_effect=AssertionError("unexpected world creation")), \
                 patch.object(type(world), "describe", side_effect=AssertionError("unexpected world access")), \
                 patch.object(type(world), "run", side_effect=AssertionError("unexpected experiment")), \
                 patch.object(type(world), "panel", side_effect=AssertionError("unexpected private panel")):
                result = present_problem(info, "apparatus_only")
                assert result["name"] == "apparatus"
                assert present_system(SYSTEM, "apparatus_only")
                assert get_presentation_profile("apparatus_only")["operator_only"] is True
    source = Path(__file__).resolve().parents[1] / "presentation_profiles.py"
    tree = ast.parse(source.read_text(), feature_version=(3, 8))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    assert set(imports) == {"copy", "hashlib", "json", "math"}


def test_no_api_smoke_builds_both_complete_prompt_envelopes_without_budget_changes():
    for environment in APPARATUS_ENVIRONMENTS:
        world, _ = load_world(environment, 24)
        budget = {"experiments_remaining": 32, "units_remaining": 800, "analysis_active_seconds_remaining": 60, "wall_seconds_remaining": 810}
        full = {"problem": assembled_problem(world, "mechanism_discrimination"), "limits": deepcopy(DEFAULT_LIMITS), "budget": budget}
        original = deepcopy(full)
        apparatus = deepcopy(full)
        apparatus["problem"] = present_problem(full["problem"], "apparatus_only")
        system = present_system(SYSTEM, "apparatus_only")
        assert full == original
        assert apparatus["limits"] == full["limits"]
        assert apparatus["budget"] == full["budget"]
        encoded = json.dumps(apparatus, allow_nan=False)
        assert len(encoded) < 260000
        assert environment not in encoded
        assert "Ising" not in encoded + system
        # No API request or runner/campaign execution is made by this smoke test.
        # Actual wiring must send this projection to BOTH public consumers.


@pytest.mark.parametrize("environment,task,expected", [
    ("coupled_oscillators", "open_discovery", "631fa8859a85b21dc6614efaa2edc5f61471b3722db1620f9cf7aa0c6b8f2fdb"),
    ("coupled_oscillators", "mechanism_discrimination", "6655146d68f03d6a6b493347af5ce35139ec20f15ef8b4ef2c6eac38f3bc6293"),
    ("coupled_oscillators", "regime_transfer", "b870706743a4d827e5aec5fc1b70f9d1cb07bfe92a4ad65defef48ce3731e3cc"),
    ("ising_spin", "open_discovery", "448f20035fc9d7643451010b729095248ec935ebceb372c053beec310984a178"),
    ("ising_spin", "mechanism_discrimination", "bbbda8bee9c93cf642851b3cb086ad9a7c329e5a173a8f3fea952f0abfd90d39"),
    ("ising_spin", "regime_transfer", "6fcb14f1d991cd08c979c0567e3b81eec93da18cc87688d7a74720e808eda5c9"),
])
def test_eighth_world_registration_preserves_prior_apparatus_scientific_content(environment, task, expected):
    # Fingerprints captured BEFORE microecology_causal registration. Only the
    # catalog/policy revision strings are omitted; all scientific text, task
    # instructions, noise, controls, scales and projected scoring rules remain.
    world, _ = load_world(environment, 7)
    projected = present_problem(assembled_problem(world, task), "apparatus_only")
    del projected["task_profile"]["catalog_version"]
    del projected["score_contract"]["claim_eligibility"]["protocol"]
    assert canonical_hash(projected) == expected
    assert "microecology_causal" not in json.dumps(projected)
