"""Physical identities and hostile artifact boundaries for finite-block coding.

Expectations come from channel limits, the analytic repetition formula, and a
separate tensor-Kraus computation, not from reference table scores.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


TASK = Path(__file__).resolve().parents[1] / "benchmarks/Physics/DephrasureCodeDesign"


def load(name):
    path = TASK / name
    assert path.is_file(), f"missing implementation: {name}"
    spec = importlib.util.spec_from_file_location("dephrasure_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ev():
    return load("verification/evaluator.py")


def artifact(x):
    return {"real": np.asarray(x).real.tolist(), "imag": np.asarray(x).imag.tolist()}


def random_density(n, rank, seed):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(2**n, rank)) + 1j * rng.normal(size=(2**n, rank))
    return x @ x.conj().T / np.vdot(x, x).real


def test_artifact_contract_exists():
    ev = load("verification/evaluator.py")
    rho = ev.factor_density({"real": [[1], [0]], "imag": [[0], [0]]}, 1)
    np.testing.assert_array_equal(rho, [[1, 0], [0, 0]])


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_factor_covers_full_rank_and_normalizes_scale(ev, n):
    x = np.eye(2**n, dtype=complex) * (1 + 2j)
    expected = np.eye(2**n) / 2**n
    for scale in [1e-290, 1.0, 1e90]:
        np.testing.assert_allclose(ev.factor_density(artifact(x * scale), n), expected, atol=1e-15)


@pytest.mark.parametrize("bad", [
    None, [], {}, {"real": [[1], [0]]},
    {"real": [[1], [0]], "imag": [[0], [0]], "extra": 0},
    {"real": [1, 0], "imag": [[0], [0]]},
    {"real": [[1]], "imag": [[0]]},
    {"real": [[], []], "imag": [[], []]},
    {"real": [[1, 0, 0], [0, 0, 0]], "imag": [[0, 0, 0], [0, 0, 0]]},
    {"real": [[1, 0], [0]], "imag": [[0, 0], [0, 0]]},
    {"real": [[1], [0]], "imag": [[0, 0], [0, 0]]},
    {"real": [[True], [0]], "imag": [[0], [0]]},
    {"real": [["1"], [0]], "imag": [[0], [0]]},
    {"real": [[float("nan")], [0]], "imag": [[0], [0]]},
    {"real": [[float("inf")], [0]], "imag": [[0], [0]]},
    {"real": [[10**1000], [0]], "imag": [[0], [0]]},
    {"real": [[0], [0]], "imag": [[0], [0]]},
    {"real": [[1e101], [0]], "imag": [[0], [0]]},
    {"real": [[1+0j], [0]], "imag": [[0], [0]]},
])
def test_malformed_factors_rejected_before_linear_algebra(ev, bad):
    with pytest.raises(ValueError):
        ev.factor_density(bad, 1)


def test_oversized_outer_container_is_rejected(ev):
    with pytest.raises(ValueError):
        ev.factor_density({"real": [[]] * 100000, "imag": [[]] * 100000}, 4)
    with pytest.raises(ValueError):
        ev.factor_density(artifact(np.ones((32, 1))), 5)


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_analytic_channel_limits(ev, n):
    rho = np.eye(2**n) / 2**n
    assert ev.coherent_information(rho, 0, .2) == pytest.approx(.6 * n, abs=2e-12)
    h = -.2 * np.log2(.2) - .8 * np.log2(.8)
    assert ev.coherent_information(rho, .2, 0) == pytest.approx(n * (1-h), abs=2e-12)
    assert ev.coherent_information(rho, .13, 1) == pytest.approx(-n, abs=2e-12)
    mixed = random_density(n, 2**n, 30+n)
    assert ev.coherent_information(mixed, 0, .5) == pytest.approx(0, abs=2e-12)


@pytest.mark.parametrize("n,rank", [(1, 1), (2, 1), (3, 1), (4, 1), (2, 4), (3, 3), (4, 16)])
def test_independent_kraus_agrees_on_random_states(ev, n, rank):
    rho = random_density(n, rank, 100*n+rank)
    direct = ev.coherent_information_kraus(rho, .137, .319)
    block = ev.coherent_information(rho, .137, .319)
    assert block == pytest.approx(direct, abs=2e-11)
    if rank == 1:
        assert abs(block) < 2e-11
        assert abs(direct) < 2e-11


def test_repetition_formula_and_positive_superadditivity(ev):
    ref = load("verification/reference_codes.py")
    for n in [1, 2, 3, 4]:
        for lam in [0, 1e-8, .05, .5, 1]:
            x = np.zeros((2**n, 2)); x[0, 0] = np.sqrt(lam); x[-1, 1] = np.sqrt(1-lam)
            rho = x @ x.T
            expected = ref.repetition_rate(n, .115, .345, lam) * n
            assert ev.coherent_information(rho, .115, .345) == pytest.approx(expected, abs=2e-12)
    assert ref.repetition_rate(2, .112, .336, .5) == pytest.approx(.005333268281771247, abs=1e-13)
    assert ref.repetition_rate(2, .112, .336, .5) > .002801436639346


def test_tensor_product_additivity(ev):
    a, b = random_density(2, 3, 101), random_density(2, 2, 102)
    total = ev.coherent_information(np.kron(a, b), .12, .31)
    assert total == pytest.approx(ev.coherent_information(a, .12, .31) + ev.coherent_information(b, .12, .31), abs=3e-12)


def test_evaluator_baseline_and_references_are_finite_and_deterministic(ev):
    baseline = load("solution.py").design_code
    result = ev.evaluate(baseline)
    assert result["valid"] == 1
    assert result["combined_score"] == pytest.approx(0, abs=1e-8)
    assert result == ev.evaluate(baseline)
    json.dumps(result, allow_nan=False)
    ref = load("verification/reference_codes.py")
    reference_result = ev.evaluate(ref.design_reference)
    assert reference_result["valid"] == 1
    assert reference_result["combined_score"] == pytest.approx(1, abs=1e-9)
    assert reference_result["reference_excess"] == 0
    assert all(row["reference_rate"] > row["single_letter_rate"] + 1e-6 for row in reference_result["per_instance"])


def test_invalid_cases_do_not_disappear_and_input_mutation_does_not_change_world(ev):
    assert ev.evaluate(lambda _: None)["valid"] == 0
    def broken(_):
        raise RuntimeError("secret or unbounded error text")
    result = ev.evaluate(broken)
    assert result["combined_score"] == 0
    assert len(result["per_instance"]) == len(ev.evaluation_problems())
    json.dumps(result, allow_nan=False)
    def mutate(problem):
        problem["n"] = 1
        problem["reference_rate"] = 0
        return {"real": [[1], [0]], "imag": [[0], [0]]}
    assert ev.evaluate(mutate)["valid"] == 0


def test_reference_witnesses_recompute_and_beat_closed_product_baseline(ev):
    ref = load("verification/reference_codes.py")
    for problem in ev.evaluation_problems():
        rho = ev.factor_density(ref.design_reference(problem), problem["n"])
        direct = ev.coherent_information_kraus(rho, problem["p"], problem["q"]) / problem["n"]
        assert direct == pytest.approx(problem["reference_rate"], abs=2e-11)
        assert problem["reference_rate"] >= ref.product_repetition_reference(problem["n"], problem["p"], problem["q"])[0] - 2e-11


def test_score_above_reference_is_not_clipped_and_requires_margin(ev, monkeypatch):
    ref = load("verification/reference_codes.py")
    problem = ev.evaluation_problems()[0]
    # A lower trusted reference makes a known physical witness exceed score one.
    weaker = dict(problem, reference_rate=4.0195149656e-5)
    monkeypatch.setattr(ev, "evaluation_problems", lambda: [weaker])
    result = ev.evaluate(lambda _: ref.design_reference(problem))
    assert result["combined_score"] > 1.1
    assert result["per_instance"][0]["margin_qualified_excess"] > 7e-6


def test_all_published_mat_witnesses_match_independent_entropy_and_stored_cost(ev):
    ref = load("verification/reference_codes.py")
    for filename in ref.MAT_HASHES:
        x, stored = ref.published_mat_factor(filename)
        n = int(filename[-5])
        p, q = (.08, .4) if "008" in filename else (.32, .1)
        rho = x @ x.conj().T
        fast = ev.coherent_information(rho, p, q)/n
        direct = ev.coherent_information_kraus(rho, p, q)/n
        assert fast == pytest.approx(direct, abs=2e-11)
        assert fast == pytest.approx(stored, abs=1e-10)


def test_hash_gate_prevents_parsing_modified_mat_resources(monkeypatch):
    ref = load("verification/reference_codes.py")
    name = next(iter(ref.MAT_HASHES))
    monkeypatch.setitem(ref.MAT_HASHES, name, "0"*64)
    with pytest.raises(ValueError):
        ref.published_mat_factor(name)
