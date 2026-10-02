"""Operator exclusion invariants using inert fake worlds only; no experiments."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
import sys

import pytest

from env import campaign, paired_design as paired, seed_exclusions as exclusions
from env import registry


def corpus(mapping=None):
    return {"protocol": exclusions.PROTOCOL, "environments": {"ising_spin": [901, 903]} if mapping is None else mapping}


class InertWorld:
    operator_strata = ("even", "odd")

    def __init__(self, seed):
        self.seed = seed

    def operator_stratum(self):
        return self.operator_strata[self.seed % 2]

    def panel(self, seed, kind, count):
        return [{"fixture": True, "world": self.seed, "panel": seed, "kind": kind, "index": i} for i in range(count)]


@pytest.fixture(autouse=True)
def inert_only(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        pytest.fail("inert exclusion tests must not execute a world, network, ledger or candidate")

    def fake_world(name, seed):
        calls.append((name, seed))
        return InertWorld(seed), forbidden

    monkeypatch.setattr(campaign, "load_world", fake_world)
    monkeypatch.setattr(registry, "load_world", forbidden)
    monkeypatch.setattr(campaign, "CampaignLedger", forbidden)
    monkeypatch.setattr(campaign, "CampaignClient", forbidden)
    monkeypatch.setattr(campaign, "run_episode", forbidden)
    monkeypatch.setattr(campaign, "_run_one", forbidden)
    monkeypatch.setattr(campaign.concurrent.futures, "ProcessPoolExecutor", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("socket.socket.connect", forbidden)
    monkeypatch.setattr(campaign, "source_digest", lambda: "a" * 64)
    monkeypatch.setattr(paired, "source_digest", lambda: "a" * 64)
    monkeypatch.setattr(campaign.time, "time", lambda: 1000.0)
    seeds, tokens = itertools.count(100), itertools.count(1)
    monkeypatch.setattr(campaign.secrets, "randbelow", lambda bound: next(seeds))
    monkeypatch.setattr(campaign.secrets, "token_hex", lambda size: "%032x" % next(tokens))
    return calls


def manifest(value=None, **kwargs):
    return campaign.create_manifest("fixture", ["ising_spin"], instances=2,
                                    seed_exclusions=value, **kwargs)


def design(value=None):
    return paired.create_paired_design("fixture", ["ising_spin"], factor="rounds", values=[6, 12],
                                       instances=2, seed_exclusions=value)


@pytest.mark.parametrize("mapping", [
    {"unknown": []}, {"ising_spin": [True]}, {"ising_spin": [1.0]}, {"ising_spin": ["1"]},
    {"ising_spin": [None]}, {"ising_spin": [-1]}, {"ising_spin": [2**31]},
    {"ising_spin": [2, 1]}, {"ising_spin": [1, 1]}, {"ising_spin": {}}, {"ising_spin": ()},
])
def test_reject_invalid_seed_maps(mapping):
    with pytest.raises(ValueError):
        exclusions.validate_exclusions(corpus(mapping))


@pytest.mark.parametrize("text", [
    '{"protocol":"sle-seed-exclusions-0.1","protocol":"sle-seed-exclusions-0.1","environments":{}}',
    '{"protocol":"sle-seed-exclusions-0.1","environments":{"ising_spin":[],"ising_spin":[]}}',
    '{"protocol":"sle-seed-exclusions-0.1","environments":{"ising_spin":[NaN]}}',
    '{"protocol":"sle-seed-exclusions-0.1","environments":{"ising_spin":[Infinity]}}',
    '[]', 'null', '{', '{"protocol":"unknown","environments":{}}',
    '{"protocol":"sle-seed-exclusions-0.1","environments":{},"extra":0}',
])
def test_strict_json_rejections(text):
    with pytest.raises(ValueError):
        exclusions.parse_exclusions(text)


def test_bounds_and_canonical_copy():
    value = corpus({"spin_echo": [0, 2**31-1], "ising_spin": [1]})
    reversed_keys = corpus(deepcopy(dict(reversed(list(value["environments"].items())))))
    assert exclusions.exclusion_hash(value) == exclusions.exclusion_hash(reversed_keys)
    binding = exclusions.exclusion_binding(value)
    value["environments"]["spin_echo"].append(12)
    assert binding["seed_exclusions"]["environments"]["spin_echo"] == [0, 2**31-1]
    assert exclusions.public_summary(reversed_keys) == {"protocol": exclusions.PROTOCOL,
        "environment_count": 2, "seed_count": 3, "sha256": binding["seed_exclusions_sha256"]}


def test_limits_and_invalid_utf8(tmp_path):
    with pytest.raises(ValueError):
        exclusions.validate_exclusions(corpus({"ising_spin": list(range(exclusions.MAX_SEEDS_PER_WORLD+1))}))
    with pytest.raises(ValueError):
        exclusions.validate_exclusions(corpus({name: list(range(exclusions.MAX_SEEDS_PER_WORLD))
                                              for name in registry.ENVIRONMENTS[:5]}))
    with pytest.raises(ValueError):
        exclusions.parse_exclusions(" " * (exclusions.MAX_JSON_BYTES+1))
    path = tmp_path / "invalid.json"
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        exclusions.load_exclusions(path)
    with pytest.raises(ValueError, match="regular"):
        exclusions.load_exclusions(tmp_path)


def test_oversized_file_rejected_before_read(tmp_path, monkeypatch):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * (exclusions.MAX_JSON_BYTES+1))
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("oversized file opened"))
    with pytest.raises(ValueError, match="byte bound"):
        exclusions.load_exclusions(path)


def test_default_legacy_shape_and_random_sequence(monkeypatch, inert_only):
    # Legacy sequence includes reserved draws, a duplicate across rows, and panel seeds.
    stream = iter([7, 100, 201, 100, 46, 102, 203])
    draws = []
    def draw(bound):
        value = next(stream)
        draws.append(value)
        return value
    monkeypatch.setattr(campaign.secrets, "randbelow", draw)
    result = manifest()
    assert result["protocol"] == "sle-pilot-cohort-0.4"
    assert set(result) == {"protocol", "cohort", "created_unix", "analysis_protocol", "analysis_contract",
        "presentation_profile", "sampling_policy", "task_profile", "runtime", "source_sha256", "score_contract",
        "limits", "reserved_development_world_seeds", "environments", "instances", "planned_max_api_attempts",
        "requested_model", "decoding", "discovery_depth"}
    assert [(r["world_seed"], r["panel_seed"]) for r in result["instances"]] == [(100, 201), (102, 203)]
    assert draws == [7, 100, 201, 100, 46, 102, 203]
    assert inert_only == [("ising_spin", 100), ("ising_spin", 102)]
    assert all(set(r) == {"episode_id", "cohort", "environment", "world_seed", "panel_seed", "confirmation_key",
                         "task_profile", "presentation_profile", "analysis_protocol", "panel_hashes"}
               for r in result["instances"])
    assert exclusions.validate_manifest_binding(result) is None


def test_explicit_empty_is_versioned_and_unused_registered_world_allowed():
    for value in (corpus({}), corpus({"spin_echo": [100]})):
        result = manifest(value)
        assert result["protocol"] == exclusions.COHORT_PROTOCOL
        assert exclusions.validate_manifest_binding(result) == value
        assert all(row["seed_exclusions_sha256"] == exclusions.exclusion_hash(value) for row in result["instances"])


def test_excludes_every_balanced_redraw(monkeypatch, inert_only):
    # First requested stratum is even; 101 is wrong, 104 is excluded, 106 is accepted.
    stream = iter([7, 100, 101, 999, 104, 106, 108, 998, 110, 111])
    monkeypatch.setattr(campaign.secrets, "randbelow", lambda bound: next(stream))
    result = manifest(corpus({"ising_spin": [100, 104, 110]}), balanced_strata=["ising_spin"])
    assert [(r["world_seed"], r["panel_seed"]) for r in result["instances"]] == [(106, 999), (111, 998)]
    assert inert_only == [("ising_spin", 101), ("ising_spin", 106), ("ising_spin", 108), ("ising_spin", 111)]
    assert [r["operator_sampling_stratum"] for r in result["instances"]] == ["even", "odd"]


@pytest.mark.parametrize("explicit", [False, True])
def test_all_reserved_sampling_is_bounded(monkeypatch, inert_only, explicit):
    draws = []
    monkeypatch.setattr(campaign, "MAX_WORLD_SEED_DRAWS", 5)
    def draw(bound):
        draws.append(7)
        return 7
    monkeypatch.setattr(campaign.secrets, "randbelow", draw)
    with pytest.raises(ValueError, match="bounded world-seed"):
        manifest(corpus({}) if explicit else None)
    assert len(draws) == 5 and inert_only == []


def test_balanced_sampling_uses_one_shared_row_counter(monkeypatch, inert_only):
    monkeypatch.setattr(campaign, "MAX_WORLD_SEED_DRAWS", 5)
    stream = iter([7, 101, 999, 46, 103, 105])  # Five world proposals + one panel proposal.
    draws = []
    def draw(bound):
        value = next(stream)
        draws.append(value)
        return value
    monkeypatch.setattr(campaign.secrets, "randbelow", draw)
    with pytest.raises(ValueError, match="bounded world-seed"):
        manifest(corpus({}), balanced_strata=["ising_spin"])
    assert draws == [7, 101, 999, 46, 103, 105]
    assert inert_only == [("ising_spin", 101), ("ising_spin", 103), ("ising_spin", 105)]


MUTATIONS = [
    lambda m: m["seed_exclusions"]["environments"]["ising_spin"].append(999),
    lambda m: m.update(seed_exclusions_sha256="f" * 64),
    lambda m: m["instances"][0].update(world_seed=901),
    lambda m: m["instances"][0].update(world_seed=7),
    lambda m: m["instances"][0].update(world_seed=True),
    lambda m: m["instances"][0].update(seed_exclusions_sha256="f" * 64),
    lambda m: m["instances"][0].pop("seed_exclusions_sha256"),
    lambda m: m.pop("seed_exclusions"),
    lambda m: m.pop("seed_exclusions_sha256"),
    lambda m: m.update(protocol="sle-pilot-cohort-0.4"),
    lambda m: m.update(reserved_development_world_seeds=[]),
    lambda m: m.update(environments=["unknown"]),
    lambda m: m.update(instances=[]),
]


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_binding_rejected_before_any_run_side_effect(tmp_path, monkeypatch, mutation):
    value = manifest(corpus())
    mutation(value)
    manifest_path = tmp_path / "fixture.json"
    manifest_path.write_text(json.dumps(value))
    root, config = tmp_path / "not-created", tmp_path / "credentials-not-read.json"
    reads, original = [], Path.read_text
    def guarded_read(path, *args, **kwargs):
        assert path == manifest_path, "attempted credential or unrelated file read"
        reads.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: pytest.fail("directory creation before exclusion validation"))
    monkeypatch.setattr(campaign, "source_digest", lambda: pytest.fail("binding validation was not first"))
    with pytest.raises(ValueError):
        campaign.run_cohort(manifest_path, config, root)
    assert reads == [manifest_path]
    assert not root.exists() and not config.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fixture.json"]


def test_new_protocol_cannot_drop_all_binding_fields():
    value = manifest(corpus())
    for field in exclusions.BINDING_FIELDS:
        value.pop(field)
    for row in value["instances"]:
        row.pop("seed_exclusions_sha256")
    with pytest.raises(ValueError):
        exclusions.validate_manifest_binding(value)
    # This is semantic validation, not an external signature or downgrade defense.
    value["protocol"] = "sle-pilot-cohort-0.4"
    assert exclusions.validate_manifest_binding(value) is None


def test_duplicate_manifest_binding_rejected_before_effects(tmp_path):
    value = manifest(corpus())
    text = json.dumps(value)
    path = tmp_path / "duplicate.json"
    path.write_text(text[:-1] + ',"seed_exclusions_sha256":"' + value["seed_exclusions_sha256"] + '"}')
    root = tmp_path / "not-created"
    with pytest.raises(ValueError, match="duplicate"):
        campaign.run_cohort(path, tmp_path / "credentials", root)
    assert not root.exists()


def test_paired_bindings_identical_and_private(tmp_path):
    value = corpus({"ising_spin": [901, 903], "spin_echo": [911]})
    result = design(value)
    public = paired.validate_design(result)
    for arm in result["manifests"].values():
        assert arm["seed_exclusions"] == result["shared_contract"]["seed_exclusions"] == value
        assert arm["seed_exclusions_sha256"] == result["shared_contract"]["seed_exclusions_sha256"]
    encoded = json.dumps(public)
    assert "ising_spin" not in encoded and "spin_echo" not in encoded
    assert public["seed_exclusions"] == exclusions.public_summary(value)
    output = tmp_path / "new-plan"
    assert paired.write_design(result, output) == public
    for path in output.iterdir():
        assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        paired.write_design(result, output)


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_paired_rejects_mutation_after_outer_rehash(mutation):
    result = design(corpus())
    mutation(result["manifests"]["a2"])
    for arm in result["arms"]:
        arm["manifest_sha256"] = paired._hash(result["manifests"][arm["arm"]])
    with pytest.raises(ValueError):
        paired.validate_design(result)


def test_paired_even_consistent_excluded_rows_rejected():
    result = design(corpus())
    result["pair_index"][0]["world_seed"] = 901
    for arm in result["arms"]:
        value = result["manifests"][arm["arm"]]
        value["instances"][0]["world_seed"] = 901
        arm["manifest_sha256"] = paired._hash(value)
    with pytest.raises(ValueError, match="excluded"):
        paired.validate_design(result)


def test_paired_legacy_keeps_public_and_private_shape():
    result = design()
    assert set(result["public_summary"]) == {"protocol", "plan_only", "planned_pairs", "planned_arms",
                                             "planned_episodes", "planned_max_api_attempts", "ledger_modified"}
    assert not set(exclusions.BINDING_FIELDS).intersection(result["shared_contract"])
    assert paired.validate_design(result) == result["public_summary"]


@pytest.mark.parametrize("paired_cli", [False, True])
def test_cli_private_body_and_counts_only_stdout(tmp_path, monkeypatch, capsys, paired_cli):
    from env import __main__ as cli
    path = tmp_path / "operator.json"
    path.write_text(json.dumps(corpus()))
    output = tmp_path / "plan"
    if paired_cli:
        args = ["planner", "--design-id", "fixture", "--environments", "ising_spin", "--factor", "rounds",
                "--values", "6,12", "--instances", "1"]
        entry = paired.main
    else:
        args = ["env", "freeze", "--cohort", "fixture", "--environments", "ising_spin", "--instances", "1"]
        entry = cli.main
    monkeypatch.setattr(sys, "argv", args + ["--seed-exclusions-file", str(path), "--output", str(output)])
    entry()
    public = json.loads(capsys.readouterr().out)
    assert public["seed_exclusions"] == exclusions.public_summary(corpus())
    assert "ising_spin" not in json.dumps(public)
    private = output / "a1-manifest-private.json" if paired_cli else output
    assert json.loads(private.read_text())["seed_exclusions"] == corpus()
    assert private.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("paired_cli", [False, True])
def test_invalid_cli_file_does_not_create_output(tmp_path, monkeypatch, paired_cli):
    from env import __main__ as cli
    path = tmp_path / "bad.json"
    path.write_text('{"protocol":"x","protocol":"y","environments":{}}')
    output = tmp_path / "not-created" / "plan"
    if paired_cli:
        args = ["planner", "--design-id", "fixture", "--environments", "ising_spin", "--factor", "rounds", "--values", "6,12"]
        entry = paired.main
    else:
        args = ["env", "freeze", "--cohort", "fixture", "--environments", "ising_spin"]
        entry = cli.main
    monkeypatch.setattr(sys, "argv", args + ["--seed-exclusions-file", str(path), "--output", str(output)])
    with pytest.raises(ValueError, match="duplicate"):
        entry()
    assert not output.parent.exists()


def test_changed_corpus_and_top_hash_still_require_row_binding():
    value = manifest(corpus())
    value["seed_exclusions"]["environments"]["ising_spin"].append(999)
    value["seed_exclusions_sha256"] = exclusions.exclusion_hash(value["seed_exclusions"])
    with pytest.raises(ValueError, match="row seed exclusion binding"):
        exclusions.validate_manifest_binding(value)


def test_file_growth_after_stat_still_bounded(tmp_path, monkeypatch):
    import io
    path = tmp_path / "growing.json"
    path.write_text("{}")
    sizes = []
    class Stream(io.BytesIO):
        def read(self, size=-1):
            sizes.append(size)
            return super().read(size)
    monkeypatch.setattr(Path, "open", lambda *a, **k: Stream(b" " * (exclusions.MAX_JSON_BYTES + 10)))
    with pytest.raises(ValueError, match="byte bound"):
        exclusions.load_exclusions(path)
    assert sizes == [exclusions.MAX_JSON_BYTES + 1]
