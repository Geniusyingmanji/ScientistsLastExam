"""Quota handoff regressions using invented private records; no network or API."""
import copy
import json

import pytest

from scripts.continue_observational_pilot import PARENT_FILES, ledger, parent_snapshot
from sle.scientific_episode import digest


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value))


@pytest.fixture
def campaign(tmp_path):
    directory = tmp_path.resolve() / "campaign"
    directory.mkdir(mode=0o700)
    write_json(directory / "campaign.json", {"episodes": 3, "max_steps": 32, "fixture": True})
    write_json(directory / "provider_failure.json", {"draw": 1, "reason": "fixture timeout"})
    write_json(directory / "model-01.started.json", {"slot": 1, "plan_sha256": "original"})
    write_json(directory / "model-01/episode.json", {"status": "budget_exhausted", "fixture": True})
    write_json(directory / "model-01/completed.json", {
        "status": "budget_exhausted", "transport_attempts": 1})
    (directory / "model-01/transport.jsonl").write_text(
        json.dumps({"kind": "request_started", "attempt": 1}) + "\n" +
        json.dumps({"kind": "request_failed", "attempt": 1, "error_type": "TimeoutError"}) + "\n")
    plan = {"parent": parent_snapshot(directory), "remaining_slots": [2, 3],
            "max_steps": 32, "total_episode_quota": 3, "fixture": True}
    return directory, plan


def register(campaign):
    directory, plan = campaign
    assert ledger(directory, {"operation": "register", "plan": plan}) == {"plan_sha256": digest(plan)}
    return directory, plan


def operation(campaign, name, slot, **extra):
    directory, plan = campaign
    return ledger(directory, {"operation": name, "slot": slot, "plan_sha256": digest(plan), **extra})


def receipt(status="completed", transport_problem=False):
    return {"at": "2026-09-20T00:00:00+00:00", "status": status,
            "transport_attempts": 1, "transport_problem": transport_problem,
            "usage": {"calls": 1, "total_tokens": 12},
            "usage_scope": "Mock parsed response only.",
            "files": {name: "a" * 64 for name in ("episode.json", "transport.jsonl", "completed.json")}}


def test_original_records_remain_byte_identical_through_two_remaining_slots(campaign):
    directory, plan = campaign
    before = {name: (directory / name).read_bytes() for name in PARENT_FILES}
    assert ledger(directory, {"operation": "describe"})["started_slots"] == ["model-01.started.json"]
    register(campaign)
    register(campaign)  # Identical registration is harmless and does not mint slots.
    for number in (2, 3):
        assert operation(campaign, "claim", number) == {"claimed_slot": number, "plan_sha256": digest(plan)}
        assert operation(campaign, "finish", number, receipt=receipt()) == {"recorded_slot": number}
    assert {name: (directory / name).read_bytes() for name in PARENT_FILES} == before
    assert ledger(directory, {"operation": "describe"})["started_slots"] == [
        "model-01.started.json", "model-02.started.json", "model-03.started.json"]


@pytest.mark.parametrize("number", [0, 1, 4, True, 2.0, "2"])
def test_only_exact_original_slots_two_and_three_are_claimable(campaign, number):
    register(campaign)
    with pytest.raises(ValueError, match="only original slots"):
        operation(campaign, "claim", number)
    assert not (campaign[0] / "model-02.started.json").exists()
    assert not (campaign[0] / "model-04.started.json").exists()


def test_interrupted_claim_cannot_be_claimed_again(campaign):
    register(campaign)
    operation(campaign, "claim", 2)
    original = (campaign[0] / "model-02.started.json").read_bytes()
    with pytest.raises(FileExistsError):
        operation(campaign, "claim", 2)
    assert (campaign[0] / "model-02.started.json").read_bytes() == original


def test_unknown_operation_has_no_effect(campaign):
    register(campaign)
    before = {path.relative_to(campaign[0]): path.read_bytes()
              for path in campaign[0].rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="unknown ledger operation"):
        operation(campaign, "grant_extra_draw", 2)
    after = {path.relative_to(campaign[0]): path.read_bytes()
             for path in campaign[0].rglob("*") if path.is_file()}
    assert after == before


@pytest.mark.parametrize("second_started", [False, True])
def test_third_slot_requires_second_completion(campaign, second_started):
    register(campaign)
    if second_started:
        operation(campaign, "claim", 2)
    with pytest.raises((ValueError, FileNotFoundError)):
        operation(campaign, "claim", 3)
    assert not (campaign[0] / "model-03.started.json").exists()


@pytest.mark.parametrize("status,transport_error", [
    ("budget_exhausted", True), ("completed", True), ("model_error", False),
])
def test_prior_transport_or_model_error_prevents_third_slot(campaign, status, transport_error):
    register(campaign)
    operation(campaign, "claim", 2)
    operation(campaign, "finish", 2, receipt=receipt(status, transport_error))
    with pytest.raises(ValueError, match="unresolved continuation failure"):
        operation(campaign, "claim", 3)
    assert not (campaign[0] / "model-03.started.json").exists()


def test_completion_cannot_be_recorded_before_claim_or_overwritten(campaign):
    register(campaign)
    with pytest.raises((ValueError, FileNotFoundError)):
        operation(campaign, "finish", 2, receipt=receipt())
    operation(campaign, "claim", 2)
    operation(campaign, "finish", 2, receipt=receipt())
    path = campaign[0] / "model-02.continuation-completed.json"
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        operation(campaign, "finish", 2, receipt=receipt("model_error", True))
    assert path.read_bytes() == original


@pytest.mark.parametrize("name", PARENT_FILES)
def test_parent_archive_tamper_blocks_claim(campaign, name):
    register(campaign)
    path = campaign[0] / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError):
        operation(campaign, "claim", 2)
    assert not (campaign[0] / "model-02.started.json").exists()


def test_registered_plan_cannot_be_changed_or_claimed_under_other_digest(campaign):
    register(campaign)
    directory, plan = campaign
    changed = copy.deepcopy(plan)
    changed["fixture"] = "changed"
    with pytest.raises(ValueError, match="immutable continuation differs"):
        ledger(directory, {"operation": "register", "plan": changed})
    with pytest.raises(ValueError, match="identity changed"):
        ledger(directory, {"operation": "claim", "slot": 2, "plan_sha256": "b" * 64})
    assert not (directory / "model-02.started.json").exists()


@pytest.mark.parametrize("field,value", [
    ("remaining_slots", [2, 3, 4]), ("max_steps", 33), ("total_episode_quota", 4),
])
def test_registration_cannot_expand_budget(campaign, field, value):
    directory, plan = campaign
    changed = copy.deepcopy(plan)
    changed[field] = value
    with pytest.raises(ValueError, match="retain original evidence and quota"):
        ledger(directory, {"operation": "register", "plan": changed})
    assert not (directory / "continuation-plan.json").exists()


@pytest.mark.parametrize("slot", [2, 3, 4])
def test_registration_refuses_existing_unreconciled_extra_slot(campaign, slot):
    directory, plan = campaign
    marker = directory / ("model-%02d.started.json" % slot)
    write_json(marker, {"slot": slot, "plan_sha256": "other-source"})
    original = marker.read_bytes()
    with pytest.raises(ValueError, match="unreconciled slot"):
        ledger(directory, {"operation": "register", "plan": plan})
    assert marker.read_bytes() == original
    assert not (directory / "continuation-plan.json").exists()


@pytest.mark.parametrize("bad_receipt", [
    {"transport_problem": False},
    dict(receipt(), status="unknown"),
    dict(receipt(), transport_attempts=33),
    dict(receipt(), transport_attempts=True),
    dict(receipt(), files={"episode.json": "not-a-hash"}),
])
def test_malformed_completion_cannot_unlock_third_slot(campaign, bad_receipt):
    register(campaign)
    operation(campaign, "claim", 2)
    with pytest.raises(ValueError):
        operation(campaign, "finish", 2, receipt=bad_receipt)
    assert not (campaign[0] / "model-02.continuation-completed.json").exists()
