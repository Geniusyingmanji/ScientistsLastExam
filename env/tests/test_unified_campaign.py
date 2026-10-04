"""Frozen denominator and public export checks, with no model/network calls."""
import json

import pytest

from env import unified_campaign as campaign
from env import unified_panels


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    class Stub:
        pass
    monkeypatch.setattr(campaign, "load_world", lambda name, seed: (Stub(), None))
    monkeypatch.setattr(unified_panels, "generate_panel", lambda world, seed, kind, count: [{"kind":kind}]*count)
    exclusions = tmp_path/"exclude.json"
    exclusions.write_text(json.dumps({"seeds":[1,2,3], "coverage":"test"}))
    root = tmp_path/"run"
    campaign.freeze(root, exclusions, "test-source-commit")
    return root


def test_freeze_balanced_clusters_and_shared_panels(frozen):
    manifest = campaign.load_manifest(frozen)
    assert len(manifest["instances"]) == 72
    assert manifest["planned_max_api_attempts"] == 1152
    seeds = set()
    for name in campaign.ENVIRONMENTS:
        rows = [r for r in manifest["instances"] if r["environment"] == name]
        assert len(rows) == 6
        for cluster in (1,2,3):
            a,b = [r for r in rows if r["instance_index"] == cluster]
            assert a["world_seed"] == b["world_seed"]
            assert a["panel_hashes"] == b["panel_hashes"]
            assert a["confirmation_key"] != b["confirmation_key"]
            seeds.add(a["world_seed"])
    assert len(seeds) == 36
    assert not seeds.intersection({1,2,3,7,46,1439,8743})
    assert campaign.export(frozen)["total_score"] is None


def test_failure_zero_pending_and_allowlist(frozen):
    manifest = campaign.load_manifest(frozen)
    for index,item in enumerate(manifest["instances"]):
        directory=frozen/"episodes"/item["episode_id"]
        directory.mkdir()
        report={"status":"completed", "score":80, "subscores":{"conditions":80,"interventions":80,"claims":80},
                "model_completed":True,"private_world_seed":"DO_NOT_EXPORT", "records":[{"credential":"SECRET"}],
                "rounds":[{"response":"RAW MODEL PRIVATE"}]}
        if index==0:
            report.update(status="failed",score=None,subscores=None,model_completed=False,infrastructure_failure="api_transport_or_provider")
        campaign.write(directory/"report.json",report)
        if index<71:
            campaign.write(directory/"closed.json",{})
    assert campaign.export(frozen)["total_score"] is None
    last=manifest["instances"][-1]
    campaign.write(frozen/"episodes"/last["episode_id"]/"closed.json",{})
    data=campaign.export(frozen)
    assert data["total_score"] == pytest.approx(80*71/72)
    row=data["by_environment"][manifest["instances"][0]["environment"]]
    assert row["score_mean"] == pytest.approx(80*5/6)
    assert row["model_only_score_mean"] == 80
    assert row["infrastructure_failures"] == 1
    encoded=json.dumps(data)
    assert all(value not in encoded for value in ("DO_NOT_EXPORT","SECRET","RAW MODEL PRIVATE","confirmation_key","world_seed","panel_seed"))


def test_modified_manifest_rejected(frozen):
    path=frozen/"manifest-private.json"
    value=json.loads(path.read_text())
    value["limits"]["rounds"]=32
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        campaign.load_manifest(frozen)
