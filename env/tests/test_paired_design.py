"""Future-plan invariants; never spend a request or construct a campaign ledger."""

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from env import paired_design as paired
from env.analysis_api import PROTOCOL as SNAPSHOT_PROTOCOL, contract
from env.registry import load_world
from env.runner import DEFAULT_LIMITS
from env.scoring import canonical_hash


@pytest.fixture(autouse=True)
def forbid_execution_and_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("planner must never execute API, candidates, cohorts or ledgers")
    monkeypatch.setattr("socket.socket", fail)
    monkeypatch.setattr("socket.create_connection", fail)
    monkeypatch.setattr("env.campaign.run_cohort", fail)
    monkeypatch.setattr("env.campaign.run_episode", fail)
    monkeypatch.setattr("env.campaign.CampaignLedger", fail)
    monkeypatch.setattr("env.campaign.CampaignClient", fail)
    monkeypatch.setattr("env.ising_spin.world.World.run", fail)


def plan(**kwargs):
    settings = dict(factor="rounds", values=[6, 12], instances=2,
                    task_profile="mechanism_discrimination", presentation_profile="apparatus_only")
    settings.update(kwargs)
    return paired.create_paired_design("future-test", ["ising_spin"], **settings)


def rehash(design):
    for arm in design["arms"]:
        arm["manifest_sha256"] = paired._hash(design["manifests"][arm["arm"]])


def test_rounds_arms_draw_one_template_and_fix_world_panels_nonfactor_budgets(monkeypatch):
    calls, original = [], paired.create_manifest
    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)
    monkeypatch.setattr(paired, "create_manifest", spy)
    design = plan()
    assert len(calls) == 1
    assert paired.validate_design(design) == design["public_summary"]
    assert design["public_summary"]["planned_pairs"] == 2
    assert design["public_summary"]["planned_episodes"] == 4
    assert design["public_summary"]["planned_max_api_attempts"] == 2*(6+12)
    first, second = design["manifests"].values()
    assert first["source_sha256"] == second["source_sha256"]
    assert first["decoding"] == second["decoding"]
    assert first["presentation_profile"] == second["presentation_profile"]
    assert first["task_profile"] == second["task_profile"]
    assert first["analysis_contract"] is second["analysis_contract"] is None
    for count, manifest in zip((6,12), (first,second)):
        assert manifest["limits"] == dict(DEFAULT_LIMITS, rounds=count, exploration_rounds=count-2)
        assert manifest["planned_max_api_attempts"] == 2*count
    ids, keys = set(), set()
    for index, pair in enumerate(design["pair_index"]):
        for manifest in (first,second):
            row = manifest["instances"][index]
            assert row["world_seed"] not in manifest["reserved_development_world_seeds"]
            for key in ("world_seed", "panel_seed", "panel_hashes"):
                assert row[key] == pair[key]
            ids.add(row["episode_id"])
            keys.add(row["confirmation_key"])
            world, _ = load_world(row["environment"], row["world_seed"])
            for kind in ("conditions", "interventions"):
                assert canonical_hash(world.panel(row["panel_seed"], kind, manifest["limits"]["panel_count"])) == pair["panel_hashes"][kind]
    assert len(ids) == len(keys) == 4
    # Runner's existing exploration key construction produces no repeated key.
    exploration_keys = {episode + ":obs-0001" for episode in ids}
    assert len(exploration_keys) == 4
    assert "not common random numbers" in design["interpretation"]["noise"]


def test_snapshot_arms_change_only_protocol_and_derived_public_contract():
    design = plan(factor="analysis_protocol", values=["legacy", SNAPSHOT_PROTOCOL], rounds=10, closing_opportunities=3)
    first, second = design["manifests"].values()
    assert first["limits"] == second["limits"] == dict(DEFAULT_LIMITS, rounds=10, exploration_rounds=7)
    assert first["analysis_protocol"] == "legacy" and first["analysis_contract"] is None
    assert second["analysis_protocol"] == SNAPSHOT_PROTOCOL and second["analysis_contract"] == contract()
    assert paired._normalize(first, "analysis_protocol") == paired._normalize(second, "analysis_protocol")
    assert design["public_summary"]["planned_max_api_attempts"] == 40


def test_rounds_can_hold_snapshot_availability_fixed_and_request_totals_can_exceed_old_cap():
    design = plan(values=[8,16,24,32], instances=5, analysis_protocol=SNAPSHOT_PROTOCOL)
    assert design["public_summary"]["planned_max_api_attempts"] == 400
    assert design["public_summary"]["ledger_modified"] is False
    assert all(m["analysis_contract"] == contract() for m in design["manifests"].values())


@pytest.mark.parametrize("kwargs", [
    {"factor": "budget_and_snapshots"}, {"values": [6]}, {"values": [6,6]}, {"values": [2,6]},
    {"values": [6,33]}, {"values": [True,6]}, {"values": [6,"12"]}, {"values": [6,7,8,9,10]},
    {"closing_opportunities": 1}, {"closing_opportunities": True}, {"closing_opportunities": 6},
    {"rounds": 12}, {"analysis_protocol": "unknown"},
    {"factor": "analysis_protocol", "values": ["legacy", "legacy"]},
    {"factor": "analysis_protocol", "values": ["legacy", "unknown"]},
    {"factor": "analysis_protocol", "values": ["legacy", SNAPSHOT_PROTOCOL], "analysis_protocol": "legacy"},
    {"factor": "analysis_protocol", "values": ["legacy", SNAPSHOT_PROTOCOL], "rounds": True},
])
def test_invalid_or_multifactor_settings_fail_before_sampling(kwargs, monkeypatch):
    monkeypatch.setattr(paired, "create_manifest", lambda *a, **k: pytest.fail("invalid design sampled a world"))
    with pytest.raises(ValueError):
        plan(**kwargs)


@pytest.mark.parametrize("field,value", [
    ("analysis_active_seconds", 120), ("experiments", 48), ("experiment_units", 900),
    ("wall_seconds", 1800), ("panel_count", 4), ("exploration_rounds", 5),
])
def test_tampered_nonfactor_budget_rejected_even_after_manifest_rehash(field, value):
    design = plan()
    design["manifests"]["a2"]["limits"][field] = value
    rehash(design)
    with pytest.raises(ValueError):
        paired.validate_design(design)


@pytest.mark.parametrize("mutation", [
    lambda m: m["decoding"].update(temperature=.7),
    lambda m: m.update(task_profile={"name": "different"}),
    lambda m: m.update(presentation_profile={"name": "full_description"}),
    lambda m: m.update(source_sha256="f"*64),
    lambda m: m["instances"][0].update(world_seed=7),
    lambda m: m["instances"][0].update(panel_seed=3),
    lambda m: m["instances"][0]["panel_hashes"].update(conditions="a"*64),
    lambda m: m.update(analysis_protocol=SNAPSHOT_PROTOCOL, analysis_contract=contract()),
])
def test_scientific_or_interface_confound_rejected_even_after_manifest_rehash(mutation):
    design = plan()
    mutation(design["manifests"]["a2"])
    rehash(design)
    with pytest.raises(ValueError):
        paired.validate_design(design)


def test_snapshot_factor_cannot_also_change_rounds():
    design = plan(factor="analysis_protocol", values=["legacy", SNAPSHOT_PROTOCOL])
    design["manifests"]["a2"]["limits"].update(rounds=20, exploration_rounds=18)
    rehash(design)
    with pytest.raises(ValueError, match="non-factor"):
        paired.validate_design(design)


def test_reused_confirmation_key_and_pair_index_tampering_fail():
    design = plan()
    design["manifests"]["a2"]["instances"][0]["confirmation_key"] = design["manifests"]["a1"]["instances"][0]["confirmation_key"]
    rehash(design)
    with pytest.raises(ValueError, match="independent"):
        paired.validate_design(design)
    design = plan()
    design["pair_index"][0]["panel_seed"] += 1
    with pytest.raises(ValueError, match="paired world/panel"):
        paired.validate_design(design)


def test_balanced_structural_strata_stay_shared_and_private():
    design = paired.create_paired_design("balanced-future", ["microecology_causal"], factor="rounds",
        values=[8,12], instances=3, balanced_strata=["microecology_causal"])
    assert len({pair["operator_sampling_stratum"] for pair in design["pair_index"]}) == 3
    public = json.dumps(design["public_summary"])
    for word in ("seed", "stratum", "strata", "environment", "feedback", "detox"):
        assert word not in public


def test_unique_new_files_source_binding_counts_only_export_and_no_ledger(tmp_path, monkeypatch):
    design = plan()
    output = tmp_path / "new-plan"
    public = paired.write_design(design, output)
    assert set(path.name for path in output.iterdir()) == {"a1-manifest-private.json", "a2-manifest-private.json", "paired-index-private.json", "public-summary.json"}
    assert set(public) == {"protocol", "plan_only", "planned_pairs", "planned_arms", "planned_episodes", "planned_max_api_attempts", "ledger_modified"}
    assert json.loads((output/"a1-manifest-private.json").read_text()) == design["manifests"]["a1"]
    assert not list(tmp_path.rglob("*.sqlite"))
    with pytest.raises(FileExistsError):
        paired.write_design(design, output)
    monkeypatch.setattr(paired, "source_digest", lambda: "changed")
    with pytest.raises(ValueError, match="source changed"):
        paired.write_design(design, tmp_path/"not-written")
    assert not (tmp_path/"not-written").exists()


def test_source_change_during_template_sampling_prevents_freeze(monkeypatch):
    monkeypatch.setattr(paired, "source_digest", lambda: "changed")
    with pytest.raises(ValueError, match="source changed while planning"):
        plan()


def test_cli_plans_only_and_has_no_execution_or_ledger_flags(tmp_path, monkeypatch, capsys):
    output = tmp_path / "cli-plan"
    monkeypatch.setattr("sys.argv", ["paired", "--design-id", "cli-future", "--environments", "ising_spin",
        "--factor", "analysis_protocol", "--values", "legacy,"+SNAPSHOT_PROTOCOL, "--instances", "1",
        "--rounds", "8", "--output", str(output)])
    paired.main()
    result = json.loads(capsys.readouterr().out)
    assert result["planned_max_api_attempts"] == 16 and result["plan_only"] is True
    assert result == json.loads((output/"public-summary.json").read_text())
    source = Path(paired.__file__).read_text()
    ast.parse(source, feature_version=(3,8))
    tree = ast.parse(source)
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)}
    assert not (calls & {"run_cohort", "run_episode", "CampaignLedger", "CampaignClient", "CandidateProxy"})
    assert 'add_argument("--run"' not in source and 'add_argument("--ledger"' not in source
