"""Profile/manifest checks with no network, World trajectories or candidate execution."""
from copy import deepcopy
import importlib
import json
import sys

import pytest

from env import campaign, research_runner
from env.analysis_api import ModelSnapshots
from env.evidence_packet import build_packet
from env.presentation_profiles import present_problem
from env.prospective import ProspectiveSession
from env.registry import ENVIRONMENTS, load_world
from env.scoring import canonical_hash, score_contract
from env.task_profiles import get_task_profile


NEW_PROFILES = ("model_revision", "boundary_mapping")
OLD_PROFILES = ("open_discovery", "mechanism_discrimination", "regime_transfer")


@pytest.fixture(autouse=True)
def no_external_or_numerical_execution(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("profile tests must not run network, World trajectories or candidate code")
    monkeypatch.setattr("socket.socket", fail)
    monkeypatch.setattr("socket.create_connection", fail)
    for name in ENVIRONMENTS:
        world_class = importlib.import_module("env." + name + ".world").World
        monkeypatch.setattr(world_class, "run", fail)
    # Freeze validates public configuration only. Parallel unrelated development
    # must not turn this profile test into a source-tree stability measurement.
    monkeypatch.setattr(campaign, "source_digest", lambda: "profile-fixture-source")
    monkeypatch.setattr(research_runner, "source_digest", lambda: "profile-fixture-source")


def test_old_profile_and_research_scientific_content_changes_only_catalog_revision():
    batch = {"open_discovery": "132268525661759a2e4afce129eca887c2a8b4648d61285413d10cb0e23574cd",
             "mechanism_discrimination": "b5ff3552cac27dce130a4c07bcbf445ae4c9df7a30eacd07152407bc37d5a121",
             "regime_transfer": "7da95fcc61f5fe8752a484d77cb99d4c4c33437db815ef105c18075a68e87e99"}
    research = {"open_discovery": "46da014c0e68fec1dd78ed32e5eaef015c35a26f54f046df2b518da9ce4e103d",
                "mechanism_discrimination": "3fe2d40b069a1ae35b711b79c9b85b577216028ee55a474c87954cd043d7b40e",
                "regime_transfer": "f89d56ca5291fb153cc955f9e018d83bea0542d86d90361d31c2ed0a879d8225"}
    for name in OLD_PROFILES:
        for profile, expected in ((get_task_profile(name), batch[name]),
                                  (research_runner._research_profile(name, "pattern_formation"), research[name])):
            assert profile["version"] == name + "-0.1.0"
            assert profile.pop("catalog_version") == "scientific-task-profiles-0.1.6"
            # Only the explicit later-world applicability additions are normalized.
            profile["applicable_environments"].remove("electrical_impedance")
            profile["applicable_environments"].remove("spin_echo")
            assert canonical_hash(profile) == expected
    contract = score_contract()
    assert contract["claim_eligibility"]["protocol"] == "public-claim-eligibility-0.9"
    contract["claim_eligibility"].pop("spin_echo_rule")
    contract["claim_eligibility"]["minimum_lag"].pop("spin_echo")
    assert set(contract["claim_eligibility"].pop("frequency_rules")) == {"electrical_impedance"}
    contract["claim_eligibility"]["protocol"] = "public-claim-eligibility-0.7"
    assert canonical_hash(contract) == "665c0b8946b72e302e1ee250a671148677681a694f0c2fd3cda610d419c5adda"


def test_revision_requires_actual_earlier_evidence_and_fresh_prospective_check():
    profile = get_task_profile("model_revision")
    items = {item["id"]: item for item in profile["evidence_requirements"]}
    assert items["original_prediction"]["timing"] == "before_original_result"
    assert items["observed_limitation_and_diagnosis"]["timing"] == "before_revision"
    assert "experiment_records" in items["observed_limitation_and_diagnosis"]["sources"]
    for name in ("documented_revision", "fresh_revision_prediction"):
        assert items[name]["timing"] == "before_revision_test_result"
    assert items["revision_test_and_assessment"]["count_unit"] == "observed_prospective_revision_test"
    assert "conditions excluded from its construction" in profile["success_semantics"]["positive_finding_requires"]
    assert "unchanged original" in profile["success_semantics"]["positive_finding_requires"]
    outcomes = profile["success_semantics"]["allowed_conclusions"]
    assert {"revision_failed", "revision_inconclusive", "no_supported_limitation_to_revise",
            "revision_untested_budget_limited"} <= set(outcomes)


def test_boundary_requires_fixed_criterion_domain_and_both_sides_for_positive_claim():
    profile = get_task_profile("boundary_mapping")
    items = {item["id"]: item for item in profile["evidence_requirements"]}
    for name in ("fixed_model_and_criterion", "ordered_control_domain", "boundary_search_design"):
        assert items[name]["timing"] == "before_boundary_observations"
    assert items["prospective_mapping_predictions"]["timing"] == "before_each_mapping_result"
    positive = profile["success_semantics"]["positive_finding_requires"]
    assert "both adequate and failed" in positive and "transition bracket or region" in positive
    assert "sampling resolution and unmeasured gaps" in positive
    limits = profile["scientific_scope"]["does_not_establish"]
    assert "one successful transfer establishes an empirical boundary" in limits
    assert "one failure locates a complete domain boundary" in limits
    assert {"boundary_not_found_within_tested_domain", "boundary_inconclusive",
            "boundary_search_budget_limited"} <= set(profile["success_semantics"]["allowed_conclusions"])


@pytest.mark.parametrize("name", NEW_PROFILES)
def test_limited_conclusions_do_not_add_submission_fields_or_automatic_success(name):
    profile = get_task_profile(name)
    semantics = profile["success_semantics"]
    assert semantics["missing_evidence_status"] == "not_demonstrated"
    assert not semantics["automatic_checklist_verdict"] and not semantics["automatic_depth_certification"]
    assert "entirely inconclusive or budget-limited" in semantics["inconclusive_policy"]
    assert "does not declare an incomplete checklist complete" in semantics["inconclusive_policy"]
    assert profile["submission_contract"]["fields"] == ["predictor_code", "claims", "explanation"]
    assert profile["submission_contract"]["additional_required_fields"] == []
    for private in ("Swift", "Hamiltonian", "golden mechanism", "positive_r0", "anchored_forcing"):
        assert private not in profile["public_prompt"]


@pytest.mark.parametrize("name", NEW_PROFILES)
def test_real_batch_cli_freeze_selects_new_full_description_profile(tmp_path, monkeypatch, capsys, name):
    from env.__main__ import main
    path = tmp_path / (name + ".json")
    monkeypatch.setattr(sys, "argv", ["env", "freeze", "--cohort", "profile-freeze", "--environments",
        "pattern_formation", "--instances", "1", "--rounds", "4", "--exploration-rounds", "2",
        "--task-profile", name, "--presentation-profile", "full_description", "--output", str(path)])
    main()
    manifest = json.loads(path.read_text())
    assert manifest["task_profile"] == get_task_profile(name)
    assert manifest["instances"][0]["task_profile"] == name
    assert manifest["presentation_profile"]["name"] == "full_description"
    world, _ = load_world("pattern_formation", manifest["instances"][0]["world_seed"])
    public = world.describe()
    public.update(task_profile=get_task_profile(name), score_contract=score_contract())
    assert present_problem(public) == public
    assert "episodes" in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("name", NEW_PROFILES)
def test_research_cli_freeze_publishes_task_and_existing_wire_finish_contract(tmp_path, capsys, name):
    path = tmp_path / (name + ".json")
    assert research_runner._main(["freeze", "--episode", "research-profile-freeze", "--environment",
        "pattern_formation", "--seed", "7", "--profile", name, "--output", str(path)]) == 0
    manifest = json.loads(path.read_text())
    research_runner.validate_manifest(manifest)
    profile = manifest["profile"]
    assert profile["name"] == name
    assert profile["evidence_requirements"] == get_task_profile(name)["evidence_requirements"]
    assert profile["submission_contract"] == {"action": "finish", "fields": ["explanation", "evidence_ids", "test_ids"],
                                                "minimum_completed_prospective_tests": 1}
    prompt = profile["public_prompt"]
    assert "not a new preregistration wire profile" in prompt
    assert "preregister.profile as mechanism_discrimination or regime_transfer" in prompt
    assert "does not bypass the existing finish requirement" in prompt
    assert "predictor_code, claims and explanation" not in prompt
    assert manifest["limits"] == research_runner.DEFAULT_LIMITS
    assert manifest["score"] is None and not manifest["automatic_depth_certification"]
    assert json.loads(capsys.readouterr().out)["model_requests"] == 0


@pytest.mark.parametrize("name", NEW_PROFILES)
@pytest.mark.parametrize("environment", ["coupled_oscillators", "ising_spin"])
def test_new_apparatus_combination_rejected_before_freeze_and_direct_projection(monkeypatch, name, environment):
    world, _ = load_world(environment, 7)
    public = world.describe()
    public.update(task_profile=get_task_profile(name), score_contract=score_contract())
    with pytest.raises(ValueError, match="task profile is not audited"):
        present_problem(public, "apparatus_only", environment=environment)
    monkeypatch.setattr(campaign, "load_world", lambda *a: pytest.fail("reject unaudited combination before instance selection"))
    with pytest.raises(ValueError, match="task profile is not audited"):
        campaign.create_manifest("unaudited-task", [environment], instances=1,
                                 task_profile=name, presentation_profile="apparatus_only")


@pytest.mark.parametrize("name", OLD_PROFILES)
@pytest.mark.parametrize("environment", ["coupled_oscillators", "ising_spin"])
def test_existing_apparatus_profile_combinations_still_freeze(name, environment):
    manifest = campaign.create_manifest("prior-task", [environment], instances=1,
                                        task_profile=name, presentation_profile="apparatus_only")
    assert manifest["task_profile"]["name"] == name
    public = load_world(environment, 7)[0].describe()
    public.update(task_profile=manifest["task_profile"], score_contract=score_contract())
    projected = present_problem(public, "apparatus_only", environment=environment)
    assert "applicable_environments" not in projected["task_profile"]
    assert environment not in json.dumps(projected)


@pytest.mark.parametrize("name", NEW_PROFILES)
def test_snapshot_preregistration_binding_and_inconclusive_finish_are_compatible(tmp_path, name):
    # Only parse and bind inert source; these callbacks must never be invoked.
    def fail(*args, **kwargs):
        pytest.fail("validation must not execute a predictor or observe a world")
    store = ModelSnapshots(tmp_path / "snapshots")
    code = "raise RuntimeError('candidate must stay inert')\ndef predict(spec):\n    return [[MODEL['a']] for t in spec['times']]\n"
    rivals = []
    for label, a in (("original", 1.), ("alternative", 2.)):
        receipt = store.save_model(label, "v1", {"a": a}, code)
        rivals.append({"id": label, "model_snapshot": {k: receipt[k] for k in ("name", "version", "sha256")},
                       "rationale": "Inert public-account fixture.", "evidence_ids": ["obs-1"], "tolerance": .01})
    request = {"profile": "regime_transfer", "scope": "Profile compatibility only.", "rivals": rivals,
               "experiments": [{"id": "target", "role": "target", "spec": {"drive": 2., "times": [2.]}}],
               "readout": [{"experiment_id": "target", "row": 0, "channel": "y", "weight": 1.}],
               "replicates": 4, "revision_of": None, "change_note": ""}
    resolved, bindings = research_runner._resolve_rivals(request, store)
    assert len(bindings) == 2 and request["rivals"][0].get("model_snapshot")
    public = {"environment": "prospective_fixture", "world_version": "fixture-1", "axis_field": "times",
              "channels": ["y"], "scales": [1.], "noise_std": [.01], "noise_mean_bias_bound": [0.]}
    session = ProspectiveSession(public, validate_spec=deepcopy, predict=fail, observe=fail,
                                 persist=fail, runtime_id="profile-validation")
    session._ingest([{"id": "obs-1", "spec": {"drive": 1., "times": [1.]},
                      "observation": {"axis": [1.], "channels": ["y"], "values": [[1.]]}}])
    assert session._request(resolved)["profile"] == "regime_transfer"
    with pytest.raises(ValueError, match="unsupported prospective profile"):
        session._request(dict(resolved, profile=name))
    final = {"explanation": "All completed comparisons are inconclusive; budget limits remain.",
             "evidence_ids": ["obs-1"], "test_ids": ["test-1"]}
    assert research_runner._final(final, [{"id": "obs-1"}], [{"test_id": "test-1", "outcome": "inconclusive"}]) == final
    with pytest.raises(ValueError, match="test_ids"):
        research_runner._final(dict(final, test_ids=[]), [{"id": "obs-1"}], [])


@pytest.mark.parametrize("name", NEW_PROFILES)
def test_public_evidence_packet_retains_scientific_task_identity(name):
    report = {"environment": "pattern_formation", "task_profile": name, "rounds": [], "history": [], "records": [],
              "private_parameters": "OPERATOR_CANARY"}
    packet = build_packet(report)
    assert packet["task_profile"] == name and "OPERATOR_CANARY" not in json.dumps(packet)
    assert "task_profile" not in build_packet(dict(report, task_profile="unreviewed-task"))
