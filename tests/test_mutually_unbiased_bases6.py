"""Exact ray soundness, independent algebraic anchor, and numerical search controls."""

import copy
import importlib.util
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import sympy as sp


TASK = Path(__file__).resolve().parents[1] / "benchmarks/Physics/MutuallyUnbiasedBases6"


def load(relative):
    path = TASK / relative
    assert path.is_file(), f"Missing MUB implementation: {relative}"
    spec = importlib.util.spec_from_file_location("mub_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity(d=6):
    return [[[int(i == j), 0] for j in range(d)] for i in range(d)]


def submission():
    return {"bases": [identity() for _ in range(3)]}


def decode(value):
    return Fraction(int(value["numerator_hex"], 16), int(value["denominator_hex"], 16))


def test_identity_baseline_and_hand_derived_pauli_control():
    ev = load("verification/evaluator.py")
    baseline = load("solution.py")
    assert ev.score_bases([identity()] * 4) == {"sse": Fraction(30), "asd": Fraction(0)}
    x = [[[1, 0], [1, 0]], [[1, 0], [-1, 0]]]
    y = [[[1, 0], [1, 0]], [[0, 1], [0, -1]]]
    assert ev.score_bases([identity(2), x, y], dimension=2) == {
        "sse": Fraction(0), "asd": Fraction(1)}
    result = ev.evaluate(baseline.build_bases)
    assert result["combined_score"] == 0
    assert result["valid"] == result["feasibility_rate"] == 1
    assert decode(result["asd_exact"]) == 0


def malformed():
    values = [None, {}, [], "bad", {"bases": []}, {"bases": [identity()] * 4}]
    for entry in [True, 1.0, float("nan"), float("inf"), [True, 0], [1.0, 0],
                  [1, 0, 0], [1], [1 << 384, 0], [0, -(1 << 4000)], "1"]:
        s = submission()
        s["bases"][0][0][0] = entry
        values.append(s)
    for change in [
        lambda s: s["bases"][0].pop(),
        lambda s: s["bases"][0][0].append([0, 0]),
        lambda s: s["bases"][0][0].__setitem__(1, [1, 0]),
        lambda s: s["bases"][0][0].__setitem__(0, [0, 0]),
        lambda s: s["bases"][0].__setitem__(1, s["bases"][0][0]),
    ]:
        s = submission()
        change(s)
        values.append(s)
    return values


@pytest.mark.parametrize("bad", malformed())
def test_malformed_input_fails_closed_without_repair(bad):
    ev = load("verification/evaluator.py")
    result = ev.evaluate(lambda _: bad)
    assert result["valid"] == result["combined_score"] == 0
    assert result["beyond_published_reference"] is False
    json.dumps(result, allow_nan=False)


def test_candidate_failure_is_deterministic_and_problem_mutation_is_harmless():
    ev = load("verification/evaluator.py")
    def failure(_):
        raise RuntimeError("arbitrary object addresses or private data must not be copied")
    assert ev.evaluate(failure) == ev.evaluate(failure)
    def mutate(p):
        p["max_coordinate_bits"] = 10000
        s = submission()
        s["bases"][0][0][0] = [1 << 384, 0]
        return s
    assert ev.evaluate(mutate)["valid"] == 0
    assert ev.PROBLEM["max_coordinate_bits"] == 384


def test_public_gram_schmidt_is_exact_and_rejects_dependence():
    public = load("solution.py")
    ev = load("verification/evaluator.py")
    a = [[[1, 1], [2, 0]], [[0, 1], [1, -1]]]
    original = copy.deepcopy(a)
    rays = public.gaussian_integer_gram_schmidt(a)
    assert a == original
    ev.score_bases([identity(2), rays], dimension=2)
    # Independent conjugate inner product, computed with exact SymPy integers.
    matrix = sp.Matrix([[sp.Integer(re) + sp.I * im for re, im in row] for row in rays])
    assert sp.expand((matrix.conjugate().T * matrix)[0, 1]) == 0
    with pytest.raises(ValueError):
        public.gaussian_integer_gram_schmidt([[[1, 0], [2, 0]], [[0, 0], [0, 0]]])


def test_bit_boundary_and_arbitrarily_small_nonorthogonality():
    ev = load("verification/evaluator.py")
    s = submission()
    for i in range(6):
        s["bases"][0][i][i] = [1 << 383, 0]
    assert ev.evaluate(lambda _: s)["valid"] == 1
    s["bases"][0][0][1] = [1,0]
    # Relative overlap is about 2**-383: no floating tolerance may accept it.
    assert ev.evaluate(lambda _: s)["valid"] == 0


def test_numerical_conversion_rejects_nonfinite_and_rank_loss():
    public = load("solution.py")
    for value in (complex(float("nan"),0),complex(0,float("inf"))):
        with pytest.raises(ValueError):
            public.numerical_to_integer_rays([[value,0],[0,1]])
    with pytest.raises(ValueError):
        public.numerical_to_integer_rays([[1,1],[0,1e-20]],bits=20)


def test_interval_against_independent_high_precision_algebraic_expression():
    ev = load("verification/evaluator.py")
    lower, upper = ev.published_asd_interval()
    r = sp.real_root(21 * sp.sqrt(3) - 36, 3)
    s = (3 + 16*r - r*r) / (28*r)
    exact = (71 - 12*(1-s)**2) / 70
    lo, hi = sp.Rational(lower.numerator, lower.denominator), sp.Rational(upper.numerator, upper.denominator)
    assert (exact-lo).evalf(100) > 0
    assert (hi-exact).evalf(100) > 0
    assert 0 < upper-lower < Fraction(1, 10**21)


def test_reference_constructor_matches_equations_and_fixture():
    ref, ev = load("verification/reference_bases.py"), load("verification/evaluator.py")
    bases = ref.raynal_bases()
    assert len(bases) == 4
    for u in bases:
        np.testing.assert_allclose(u.conj().T @ u, np.eye(6), atol=1e-14)
    assert ref.overlap_sse(bases) == pytest.approx(0.05124921899628387, abs=2e-14)
    assert 1 - ref.overlap_sse(bases)/30 == pytest.approx(ref.raynal_asd(), abs=1e-15)
    stored = json.loads((TASK / "references/raynal_rays.json").read_text())
    assert stored == ref.reference_submission(bits=32)
    assert ref.check_fixture()
    lo, hi = ev.published_asd_interval()
    for bits, tolerance in [(20, 1e-10), (32, 1e-15), (36, 1e-15)]:
        candidate = ref.reference_submission(bits=bits)
        metric = ev.score_bases([identity()] + candidate["bases"])
        assert abs(float(metric["asd"]) - ref.raynal_asd()) < tolerance
        assert metric["asd"] < hi
        report = ev.evaluate(lambda _: candidate)
        assert report["valid"] == 1
        assert report["beyond_published_reference"] is False
        assert decode(report["frontier_excess_lower_bound_exact"]) == 0
    report = ev.evaluate(lambda _: stored)
    assert report["combined_score"] == 1
    assert decode(report["normalized_score_exact"]) == 1
    assert json.dumps(report, sort_keys=True, allow_nan=False) == json.dumps(
        ev.evaluate(lambda _: stored), sort_keys=True, allow_nan=False)
    finer = ev.evaluate(lambda _: ref.reference_submission(bits=36))
    assert finer["beyond_rational_fixture"] is True
    assert decode(finer["normalized_score_exact"]) > 1
    assert finer["beyond_published_reference"] is False


def test_raw_fixture_orthogonality_and_probability_marginals():
    ev = load("verification/evaluator.py")
    bases = [identity()] + json.loads((TASK / "references/raynal_rays.json").read_text())["bases"]
    for basis in bases:
        m = sp.Matrix([[sp.Integer(re) + sp.I*im for re, im in row] for row in basis])
        gram = m.conjugate().T*m
        for i in range(6):
            assert sp.expand(gram[i, i]) > 0
            for j in range(i):
                assert sp.expand(gram[i, j]) == 0
    for a in range(4):
        for b in range(a + 1, 4):
            p = ev.overlap_probabilities(bases[a], bases[b])
            assert all(sum(row) == 1 for row in p)
            assert all(sum(p[i][j] for i in range(6)) == 1 for j in range(6))
    bases[1][0][1][0] += 1
    with pytest.raises(ValueError):
        ev.score_bases(bases)


def test_exact_representation_invariances_and_noninvariance():
    ev = load("verification/evaluator.py")
    ref = load("verification/reference_bases.py")
    bases = [identity()] + ref.reference_submission(bits=20)["bases"]
    expected = ev.score_bases(bases)
    changed = copy.deepcopy(bases[::-1])
    for basis in changed:
        for row in basis:
            row.reverse()
            for j, entry in enumerate(row):
                re, im = entry
                row[j] = [-(j+2)*im, (j+2)*re]
    assert ev.score_bases(changed) == expected
    # Common rational orthogonal left transform, scaled by five to stay integral.
    transformed = copy.deepcopy(bases)
    for basis in transformed:
        rows = copy.deepcopy(basis)
        basis[0] = [[3*a-4*b for a,b in zip(x,y)] for x,y in zip(rows[0], rows[1])]
        basis[1] = [[4*a+3*b for a,b in zip(x,y)] for x,y in zip(rows[0], rows[1])]
        for i in range(2,6):
            basis[i] = [[5*a,5*b] for a,b in rows[i]]
    assert ev.score_bases(transformed) == expected
    different = copy.deepcopy(bases)
    different[1][0] = [[-im,re] for re,im in different[1][0]]
    assert ev.score_bases(different)["asd"] != expected["asd"]


def test_full_space_gradient_matches_independent_directional_finite_difference():
    ref = load("verification/reference_bases.py")
    bases = ref.random_bases(seed=19)
    rng = np.random.default_rng(7)
    directions = [rng.normal(size=(6,6)) + 1j*rng.normal(size=(6,6)) for _ in bases]
    gradient = ref.sse_gradient(bases)
    epsilon = 1e-6
    numerical = (ref.overlap_sse([u+epsilon*v for u,v in zip(bases,directions)]) -
                 ref.overlap_sse([u-epsilon*v for u,v in zip(bases,directions)]))/(2*epsilon)
    analytic = sum(np.vdot(g,v).real for g,v in zip(gradient,directions))
    assert analytic == pytest.approx(numerical, rel=2e-8, abs=2e-8)


def test_seeded_full_space_optimizer_descends_and_retains_unitarity():
    ref = load("verification/reference_bases.py")
    first = ref.optimize_bases(seed=5, iterations=80)
    second = ref.optimize_bases(seed=5, iterations=80)
    assert first["history"] == second["history"]
    assert first["history"][-1] < first["history"][0]
    assert all(b < a for a,b in zip(first["history"], first["history"][1:]))
    np.testing.assert_array_equal(first["bases"][0], np.eye(6))
    for u in first["bases"]:
        np.testing.assert_allclose(u.conj().T @ u, np.eye(6), atol=5e-14)
    warm = ref.optimize_bases(initial=ref.raynal_bases(), iterations=80)
    assert abs(warm["sse"] - 0.05124921899628387) < 2e-14
    assert all(b < a for a,b in zip(warm["history"],warm["history"][1:]))
