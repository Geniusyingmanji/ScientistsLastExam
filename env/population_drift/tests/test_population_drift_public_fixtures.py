"""Pure interface fixtures; no World, Kernel or reference imports/evaluations."""

import ast
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from env.population_drift.baseline import baseline
from env.population_drift.protocol import CHANNELS, assigned_initial, describe, integer, validate_spec


def spec():
    return {"population_size": 12, "initial_A": 6, "times": [0, 1, 10]}


def test_canonical_defaults_do_not_mutate():
    raw = spec()
    before = copy.deepcopy(raw)
    canonical = validate_spec(raw)
    assert raw == before
    assert canonical["selection_bias"] == canonical["newborn_flip_probability"] == 0
    canonical["times"][0] = .2
    assert raw == before


@pytest.mark.parametrize("bad", [True, np.bool_(False), float("nan"), float("inf"), "1", 1j, 10**400])
def test_nonfinite_and_nonreal_controls(bad):
    raw = spec()
    raw["selection_bias"] = bad
    with pytest.raises(ValueError):
        validate_spec(raw)


@pytest.mark.parametrize("changes", [
    {"extra": 1}, {"population_size": 1}, {"population_size": 33}, {"population_size": 12.0},
    {"population_size": True}, {"initial_A": -1}, {"initial_A": 13}, {"initial_A": 6.0},
    {"initial_A": False}, {"times": []}, {"times": [0]*34}, {"times": [1, 1]},
    {"times": [1, 0]}, {"times": [-.1, 1]}, {"times": [61]}, {"times": [False, 10]},
    {"times": (0, 1, 10)}, {"selection_bias": .501}, {"selection_bias": -.501},
    {"newborn_flip_probability": -.01}, {"newborn_flip_probability": .101},
])
def test_invalid_contract(changes):
    raw = spec()
    raw.update(changes)
    with pytest.raises(ValueError):
        validate_spec(raw)


def test_valid_boundaries_and_initial_readout():
    raw = {"population_size": 32, "initial_A": 32, "times": np.linspace(0, 60, 33).tolist(),
           "selection_bias": -.5, "newborn_flip_probability": .1}
    assert assigned_initial(validate_spec(raw)) == [1, 0, 1, 0]
    assert assigned_initial(validate_spec({"population_size": 2, "initial_A": 0, "times": [0]})) == [0, 0, 0, 1]
    assert assigned_initial(validate_spec({"population_size": 2, "initial_A": 1, "times": [60]})) == [.5, .5, 0, 0]


def test_description_examples_and_manifest():
    public = describe()
    serialized = json.dumps(public)
    for hidden in ("neutral_drift", "constant_selection", "frequency_dependence", "symmetric_mutation", "frequency_effect", "mutation_probability", "41001"):
        assert hidden not in serialized
    assert "current occupancies" in serialized and "WITH replacement" in serialized and "not one realized stochastic trajectory" in serialized
    for raw in public["examples"]:
        validate_spec(raw)
    directory = Path(__file__).parents[1]
    for path in (directory/"examples").glob("*.json"):
        validate_spec(json.loads(path.read_text()))
    manifest = json.loads((directory/"world.json").read_text())
    assert manifest["status"] == "experimental"
    assert manifest["version"] == public["version"] and manifest["channels"] == public["channels"]


def test_source_compiles_and_imports_are_separate():
    directory = Path(__file__).parents[1]
    for path in directory.glob("*.py"):
        compile(path.read_text(), str(path), "exec")
    for filename, forbidden in (("baseline.py", {"kernel", "world", "reference", "generator"}),
                                 ("reference.py", {"kernel", "world", "protocol", "generator"})):
        tree = ast.parse((directory/filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not any(word in (node.module or "").split(".") for word in forbidden)
                if filename == "reference.py":
                    assert not any(alias.name == "expm" for alias in node.names)
            if isinstance(node, ast.Import):
                assert not any(word in alias.name.split(".") for alias in node.names for word in forbidden)
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(ast.parse((directory/"__init__.py").read_text())))


def test_baseline_with_synthetic_public_records_only():
    raw = spec()
    assert np.array_equal(baseline([], raw), [[.5, .5, 0, 0]]*3)
    observation = {"axis": raw["times"], "channels": list(CHANNELS),
                   "values": [[.51, .49, .01, -.01], [.52, .4, .03, .02], [.6, .1, .2, .1]]}
    record = {"spec": raw, "observation": observation}
    before = copy.deepcopy(record)
    result = baseline([record], raw)
    assert result[0] == [.5, .5, 0, 0]
    assert np.allclose(result[1:], observation["values"][1:], rtol=0, atol=1e-15)
    assert record == before


@pytest.mark.parametrize("records", [None, [{}], [False], [{"spec": spec(), "observation": {}}]])
def test_baseline_rejects_bad_records(records):
    with pytest.raises(ValueError):
        baseline(records, spec())


@pytest.mark.parametrize("seed", [True, -1, 1.5, 2**63])
def test_seed_contract_without_world(seed):
    with pytest.raises(ValueError):
        integer(seed, "seed")
