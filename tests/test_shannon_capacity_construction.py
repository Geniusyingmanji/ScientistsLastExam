"""Exact artifact checks; the independent oracle enumerates graph neighbors."""
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmarks/Mathematics/ShannonCapacityConstruction"


def load(relative):
    path = TASK / relative
    assert path.is_file(), f"Missing task implementation: {path}"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def independent_by_neighbors(rows, q):
    """Different algorithm from the production pairwise distance checker."""
    words = {tuple(row) for row in rows}
    if len(words) != len(rows):
        return False
    for word in words:
        for offset in itertools.product((-1, 0, 1), repeat=len(word)):
            if any(offset) and tuple((x + dx) % q for x, dx in zip(word, offset)) in words:
                return False
    return True


def fixture():
    path = TASK / "references/c7_power5_reference.json"
    assert path.is_file(), "Missing primary-source 367-word witness"
    return json.loads(path.read_text())


def test_product_baseline_is_valid_and_scores_zero():
    evaluator, baseline = load("verification/evaluator.py"), load("solution.py")
    result = evaluator.evaluate(baseline.build_code)
    assert result["valid"] and result["raw_size"] == 243
    assert result["combined_score"] == 0 and not result["beyond_reference"]
    assert independent_by_neighbors(baseline.build_code({})["codewords"], 7)


def test_primary_fixture_is_exact_and_reference_replays_it():
    reference = fixture()
    rows = reference["codewords"]
    assert len(rows) == 367
    assert all(type(row) is list and len(row) == 5 for row in rows)
    assert all(type(x) is int and 0 <= x < 7 for row in rows for x in row)
    assert independent_by_neighbors(rows, 7)
    digest = hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
    assert digest == reference["witness_sha256"]
    evaluator, replay = load("verification/evaluator.py"), load("verification/reference_code.py")
    assert replay.build_code({}) == {"codewords": rows}
    result = evaluator.evaluate(replay.build_code)
    assert result["valid"] and result["raw_size"] == 367
    assert result["combined_score"] == 1 and not result["beyond_reference"]


def test_reference_program_is_self_contained_when_copied(tmp_path):
    import subprocess
    import sys
    import shutil

    source = TASK / "verification/reference_code.py"
    assert source.is_file(), "Missing standalone reference program"
    copied = tmp_path / "candidate.py"
    shutil.copyfile(source, copied)
    result = subprocess.run([sys.executable, str(copied)], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"codewords": fixture()["codewords"]}


def test_small_graph_controls_and_wraparound():
    evaluator = load("verification/evaluator.py")
    good = [[i, 2 * i % 5] for i in range(5)]
    assert evaluator.verify_codewords(good, alphabet_size=5, block_length=2)["valid"]
    assert independent_by_neighbors(good, 5)
    for bad in ([[0, 0], [1, 1]], [[0, 0], [4, 4]]):
        assert not evaluator.verify_codewords(bad, alphabet_size=5, block_length=2)["valid"]
        assert not independent_by_neighbors(bad, 5)


@pytest.mark.parametrize("artifact", [
    {}, {"codewords": [[0] * 5], "extra": 1}, None, [],
    {"codewords": []}, {"codewords": [[0] * 5] * 2},
    {"codewords": [[0, 0, 0, 0, -1]]},
    {"codewords": [[0, 0, 0, 0, 7]]},
    {"codewords": [[0, 0, 0, 0, True]]},
    {"codewords": [[0, 0, 0, 0, 2.0]]},
    {"codewords": [[0, 0, 0, 0, float("nan")]]},
    {"codewords": [[0, 0, 0, 0]]},
    {"codewords": [(0, 0, 0, 0, 0)]},
    {"codewords": [[0] * 5] * 513},
    {"codewords": [[0] * 5, [1] * 5]},
])
def test_bad_artifacts_do_not_receive_counts_or_reward(artifact):
    result = load("verification/evaluator.py").evaluate(lambda _: artifact)
    assert not result["valid"] and result["raw_size"] is None
    assert result["combined_score"] == 0 and not result["beyond_reference"]
    json.dumps(result, allow_nan=False)


def test_candidate_exception_is_a_finite_deterministic_failure():
    def raises(_):
        raise ValueError("deliberate")

    evaluator = load("verification/evaluator.py")
    result = evaluator.evaluate(raises)
    assert not result["valid"] and result["reason"].startswith("candidate raised")
    assert json.dumps(result, sort_keys=True, allow_nan=False) == json.dumps(
        evaluator.evaluate(raises), sort_keys=True, allow_nan=False)


def test_input_mutation_cannot_change_fixed_problem_or_next_evaluation():
    evaluator = load("verification/evaluator.py")

    def mutates(problem):
        assert problem == {"alphabet_size": 7, "block_length": 5,
                           "max_codewords": 512, "reference_size": 367}
        problem.update(alphabet_size=999, block_length=1, max_codewords=9999, reference_size=1)
        return {"codewords": [[99]]}

    assert not evaluator.evaluate(mutates)["valid"]
    baseline = load("solution.py")
    first = evaluator.evaluate(baseline.build_code)
    second = evaluator.evaluate(baseline.build_code)
    assert first["raw_size"] == 243
    assert json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(second, sort_keys=True, allow_nan=False)


def test_valid_below_baseline_is_distinct_from_invalid_and_scores_are_monotone():
    evaluator = load("verification/evaluator.py")
    rows = fixture()["codewords"]
    results = [evaluator.evaluate(lambda _, m=m: {"codewords": rows[:m]})
               for m in (1, 243, 244, 300, 367)]
    assert all(result["valid"] for result in results)
    assert [result["raw_size"] for result in results] == [1, 243, 244, 300, 367]
    assert [result["combined_score"] for result in results] == [0, 0, 1 / 124, 57 / 124, 1]
    # This checks score semantics only; it does not claim a 368-word witness exists.
    assert evaluator.normalized_size_gain(368, 367) > 1
