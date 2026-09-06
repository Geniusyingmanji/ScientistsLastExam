"""Proof identities and hostile-input behavior, independent of the constructor."""

import importlib.util
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import sympy as sp


TASK = Path(__file__).resolve().parents[1] / "benchmarks/Mathematics/ChowlaCosineCertificate"


def load(relative):
    path = TASK / relative
    assert path.is_file(), f"Missing Chowla implementation: {relative}"
    spec = importlib.util.spec_from_file_location("chowla_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def problem(n=2, degree=8):
    return dict(n_terms=n, max_frequency=degree, max_factors=degree + 1,
                max_total_terms=4 * degree + 4, max_pair_products=100000,
                max_rational_bits=128, max_denominator_lcm_bits=512,
                reference_bound=[3, 2])


def witness():
    # cos(x) + cos(2x) + 9/8 = 1/2 |1 + z/2 + z^2|^2.
    return dict(frequencies=[1, 2], bound=[9, 8], factors=[
        dict(weight=[1, 2], terms=[[0, 1], [1, [1, 2]], [2, 1]])])


def test_hand_derived_exact_witness_and_symbolic_independence():
    evaluator = load("verification/evaluator.py")
    assert evaluator.certified_bound(witness(), problem()) == Fraction(9, 8)
    z = sp.Symbol("z", nonzero=True)
    q = 1 + z / 2 + z ** 2
    target = sp.Rational(9, 8) + (z + 1/z + z**2 + z**-2) / 2
    assert sp.expand(q * q.subs(z, 1/z) / 2 - target) == 0
    x = np.linspace(0, 2 * np.pi, 8193)
    assert np.min(9/8 + np.cos(x) + np.cos(2*x)) >= -1e-12


@pytest.mark.parametrize("change", [
    lambda s: s.update(bound=1),
    lambda s: s["factors"][0]["terms"][1].__setitem__(1, [2, 3]),
    lambda s: s["frequencies"].append(3),
    lambda s: s["factors"][0].update(weight=[-1, 2]),
])
def test_false_identity_is_rejected(change):
    evaluator = load("verification/evaluator.py")
    submission = witness()
    change(submission)
    with pytest.raises(ValueError):
        evaluator.certified_bound(submission, problem())


def test_coarse_grid_false_positive_has_no_proof():
    evaluator = load("verification/evaluator.py")
    x = np.arange(4) * np.pi / 2
    assert np.min(1 + np.cos(x) + np.cos(2*x)) >= -1e-14
    # At cos(x)=-1/4 the purported nonnegative polynomial is -1/8.
    assert 1 + Fraction(-1, 4) + (2 * Fraction(1, 16) - 1) == Fraction(-1, 8)
    submission = witness()
    submission["bound"] = 1
    with pytest.raises(ValueError):
        evaluator.certified_bound(submission, problem())


def test_full_laurent_support_not_just_selected_frequencies():
    evaluator = load("verification/evaluator.py")
    submission = witness()
    submission["bound"] = [13, 8]
    submission["factors"].append(dict(weight=[1, 4], terms=[[0, 1], [8, 1]]))
    # Constant and the requested harmonics agree, but extra +/-8 remain.
    with pytest.raises(ValueError):
        evaluator.certified_bound(submission, problem())


def malformed_submissions():
    variants = [None, {}, [], "bad", float("nan")]
    for key, value in [
        ("frequencies", [1, 1]), ("frequencies", [0, 2]),
        ("frequencies", [True, 2]), ("frequencies", [1.0, 2]),
        ("frequencies", [1, 9]), ("frequencies", [1, 1 << 10000]),
        ("bound", True), ("bound", 1.125), ("bound", float("nan")),
        ("bound", [9, 0]), ("bound", [9, -8]), ("bound", [9, 8.0]),
        ("bound", [9, True]), ("bound", [1 << 10000, 8]),
        ("bound", [9, 1 << 10000]), ("bound", [1, 2, 3]),
        ("bound", 0), ("bound", 3), ("factors", []),
        ("factors", [{}] * 10), ("factors", "bad"),
    ]:
        submission = witness()
        submission[key] = value
        variants.append(submission)
    for field, value in [
        ("weight", float("nan")), ("weight", [-1, 2]),
        ("weight", [1, 0]), ("weight", [1, -2]),
        ("terms", [[0, 1], [0, 1]]), ("terms", [[-1, 1]]),
        ("terms", [[True, 1]]), ("terms", [[9, 1]]),
        ("terms", [[1 << 10000, 1]]), ("terms", [[0, 0]]),
        ("terms", [[0, True]]), ("terms", [[0, 0.5]]),
        ("terms", [[0, [1, 0]]]), ("terms", [[0, [1, -2]]]),
        ("terms", [[0, [1, 2.0]]]), ("terms", [[0, [1 << 10000, 1]]]),
        ("terms", [[0, 1, 2]]), ("terms", [[0, 1]] * 1000),
        ("terms", []),
    ]:
        submission = witness()
        submission["factors"][0][field] = value
        variants.append(submission)
    return variants


@pytest.mark.parametrize("submission", malformed_submissions())
def test_malformed_payloads_fail_closed(submission):
    evaluator = load("verification/evaluator.py")
    with pytest.raises(ValueError):
        evaluator.certified_bound(submission, problem())
    payload = evaluator.evaluate(lambda _: submission)
    assert payload["valid"] == payload["combined_score"] == 0
    assert len(payload["per_instance"]) == 3
    json.dumps(payload, allow_nan=False)


@pytest.mark.parametrize("corrupt", [
    lambda submission, _: submission["factors"][0].update(weight=[-1, 2]),
    lambda submission, _: submission["factors"][0]["terms"].append([0, 1]),
    lambda submission, _: submission["factors"][0]["terms"][1].__setitem__(1, True),
    lambda submission, p: submission["factors"][0]["terms"][1].__setitem__(
        0, p["max_frequency"] + 1),
    lambda submission, p: submission.update(bound=[p["n_terms"] - 1, 1]),
])
def test_real_world_baseline_corruptions_reach_deep_evaluator_checks(corrupt):
    """A real-sized payload must reach the corrupted field before failing.

    The general malformed fixtures above have two frequencies, so evaluation against the frozen
    15/28/45-term worlds rejects them at the outer length gate. Starting from each world's valid
    baseline protects the deeper evaluator path itself.
    """
    evaluator = load("verification/evaluator.py")
    baseline = load("solution.py")

    def corrupted_candidate(problem):
        candidate = baseline.build_certificate(problem)
        corrupt(candidate, problem)
        return candidate

    payload = evaluator.evaluate(corrupted_candidate)
    assert payload["valid"] == payload["combined_score"] == 0
    assert payload["feasibility_rate"] == 0
    assert len(payload["per_instance"]) == 3
    assert all(row["valid"] is False and row["reason"] == "invalid submission"
               for row in payload["per_instance"])
    json.dumps(payload, allow_nan=False)


@pytest.mark.parametrize("budget,value", [
    ("max_factors", 0), ("max_total_terms", 2),
    ("max_pair_products", 8), ("max_rational_bits", 3),
])
def test_work_and_integer_budgets_are_enforced(budget, value):
    evaluator = load("verification/evaluator.py")
    limits = problem()
    limits[budget] = value
    with pytest.raises(ValueError):
        evaluator.certified_bound(witness(), limits)


def test_small_denominators_collectively_exceed_lcm_budget():
    evaluator = load("verification/evaluator.py")
    limits = problem()
    limits["max_denominator_lcm_bits"] = 8
    submission = witness()
    submission["factors"][0]["terms"] = [[0, [1, 7]], [1, [1, 11]], [2, [1, 13]]]
    with pytest.raises(ValueError, match="denominator"):
        evaluator.certified_bound(submission, limits)
    # Exercise the actual 512-bit public cap with individually ten/eleven-bit primes.
    limits = problem(degree=64)
    primes = list(sp.primerange(1000, 1500))[:60]
    submission["factors"][0]["terms"] = [[i, [1, p]] for i, p in enumerate(primes)]
    with pytest.raises(ValueError, match="denominator"):
        evaluator.certified_bound(submission, limits)


def test_raising_and_partial_candidates_keep_all_worlds():
    evaluator = load("verification/evaluator.py")
    reference = load("verification/reference_search.py")
    def raises(_):
        raise RuntimeError("candidate error")
    assert evaluator.evaluate(raises)["combined_score"] == 0
    def partial(p):
        return reference.sidon_certificate(p) if p["n_terms"] == 15 else {}
    payload = evaluator.evaluate(partial)
    assert payload["combined_score"] == pytest.approx(1/3)
    assert payload["feasibility_rate"] == pytest.approx(1/3)
    assert payload["valid"] == 0
    assert all(set(row) == set(payload["per_instance"][0]) for row in payload["per_instance"])
    json.dumps(payload, allow_nan=False)


def test_sidon_small_example_and_repeated_differences():
    evaluator = load("verification/evaluator.py")
    reference = load("verification/reference_search.py")
    submission = reference.sidon_certificate(problem(3, 8))
    assert submission["frequencies"] == [1, 2, 3]
    assert evaluator.certified_bound(submission, problem(3, 8)) == Fraction(3, 2)
    z = sp.Symbol("z", nonzero=True)
    q = 1 + z + z**3
    assert sp.expand(q*q.subs(z, 1/z)/2 - sp.Rational(3, 2)
                     - sum((z**a + z**-a)/2 for a in [1, 2, 3])) == 0
    # B={0,1,2} repeats difference 1. It cannot represent a set of unit cosines.
    invalid = dict(frequencies=[1, 2], bound=[3, 2], factors=[
        dict(weight=[1, 2], terms=[[0, 1], [1, 1], [2, 1]])])
    with pytest.raises(ValueError):
        evaluator.certified_bound(invalid, problem())
    with pytest.raises(ValueError):
        reference.sidon_certificate(problem(2, 8))
    with pytest.raises(ValueError):
        reference.sidon_certificate(problem(15, 4))


def test_baseline_reference_and_complete_payload_determinism():
    evaluator = load("verification/evaluator.py")
    baseline = load("solution.py")
    reference = load("verification/reference_search.py")
    weak = evaluator.evaluate(baseline.build_certificate)
    strong = evaluator.evaluate(reference.sidon_certificate)
    assert weak["combined_score"] == 0 and weak["valid"] == 1
    assert strong["combined_score"] == 1 and strong["valid"] == 1
    assert [row["bound"] for row in strong["per_instance"]] == [[3, 1], [4, 1], [5, 1]]
    assert [row["bound_over_sqrt_n"] for row in strong["per_instance"]] == pytest.approx(
        [3/math.sqrt(15), 4/math.sqrt(28), 5/math.sqrt(45)])
    assert json.dumps(strong, sort_keys=True, allow_nan=False) == json.dumps(
        evaluator.evaluate(reference.sidon_certificate), sort_keys=True, allow_nan=False)
    assert all(row["reference_excess"] == 0 for row in strong["per_instance"])


def test_candidate_mutation_cannot_change_world_or_later_evaluations():
    evaluator = load("verification/evaluator.py")
    baseline = load("solution.py")
    expected = evaluator.evaluate(baseline.build_certificate)
    def mutate(p):
        result = baseline.build_certificate(p)
        p["n_terms"] = 1
        p["reference_bound"][0] = 1000000
        p.clear()
        return result
    assert evaluator.evaluate(mutate) == expected
    assert evaluator.evaluate(baseline.build_certificate) == expected


def test_exact_correction_handles_missing_and_extra_harmonics():
    evaluator = load("verification/evaluator.py")
    reference = load("verification/reference_search.py")
    # q=1/2+z/2+z^2/2+z^3/4 needs errors -1/8,+1/8,-1/8.
    result = reference.corrected_certificate([1, 2], [Fraction(1, 2), Fraction(1, 2),
                                                        Fraction(1, 2), Fraction(1, 4)])
    assert evaluator.certified_bound(result, problem()) == Fraction(25, 16)
    z = sp.Symbol("z", nonzero=True)
    expanded = 0
    for factor in result["factors"]:
        weight = factor["weight"]
        weight = sp.Rational(*weight) if isinstance(weight, list) else sp.Integer(weight)
        q = sum((sp.Rational(*c) if isinstance(c, list) else sp.Integer(c)) * z**e
                for e, c in factor["terms"])
        expanded += weight * q * q.subs(z, 1/z)
    target = sp.Rational(25, 16) + (z + 1/z + z**2 + z**-2) / 2
    assert sp.expand(expanded - target) == 0
    zero = reference.corrected_certificate([1, 2], [0])
    assert evaluator.certified_bound(zero, problem()) == 2
    assert zero["factors"] == [
        {"weight": [1, 2], "terms": [[0, 1], [1, 1]]},
        {"weight": [1, 2], "terms": [[0, 1], [2, 1]]},
    ]


def test_search_returns_exact_certificate_and_is_deterministic():
    evaluator = load("verification/evaluator.py")
    reference = load("verification/reference_search.py")
    p = problem(3, 8)
    first = reference.search_certificate(p, iterations=12, grid_size=256)
    second = reference.search_certificate(p, iterations=12, grid_size=256)
    assert first == second
    assert evaluator.certified_bound(first, p) <= Fraction(3, 2)
    # Spectral extraction must produce an identity independently of a sampled minimum.
    extracted = reference.spectral_certificate([1, 2], grid_size=1024)
    assert evaluator.certified_bound(extracted, problem()) < Fraction(3, 2)


def test_improved_certificate_scores_above_constructive_reference(monkeypatch):
    evaluator = load("verification/evaluator.py")
    reference = load("verification/reference_search.py")
    monkeypatch.setattr(evaluator, "WORLD_SPECS", ((3, 8),))
    result = evaluator.evaluate(lambda _: reference.spectral_certificate([1, 2, 3], grid_size=1024))
    assert result["valid"] == 1
    assert result["combined_score"] > 1
    assert result["reference_excess"] == pytest.approx(result["combined_score"] - 1)


def test_local_search_outputs_fit_public_world_budgets():
    evaluator = load("verification/evaluator.py")
    reference = load("verification/reference_search.py")
    result = evaluator.evaluate(reference.search_certificate)
    assert result["valid"] == 1
    assert result["combined_score"] >= 1
    assert result == evaluator.evaluate(reference.search_certificate)
