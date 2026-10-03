"""Independent analytic checks plus explicitly labeled consistency checks."""
import copy
import math
import numpy as np
import pytest
from env.molecular_forces.kernel import energy_forces
from env.molecular_forces.protocol import CHANNELS, example
from env.molecular_forces.world import World, baseline


def triangle(a, b=None, c=None):
    b, c = (a if b is None else b), (a if c is None else c)
    x = (a*a+b*b-c*c)/(2*a)
    p = np.array([[0., 0., 0.], [a, 0., 0.], [x, math.sqrt(max(0., b*b-x*x)), 0.]])
    return p-p.mean(axis=0)


def fixture(family="lj", three=0., temperature=0.):
    return {"family": family, "depth": .11, "length": 2.9 if family == "lj" else 3.1,
            "inverse_range": 1.7, "three_body": three, "temperature_coefficient": temperature}


def independent_energy(p, temperature, params):
    """Real Cartesian-dot reference, independent from side-cosine production.

Finite difference of this energy checks the force implementation; agreement
alone still does not validate a real-world molecular potential.
"""
    p = np.asarray(p, dtype=float)
    total = 0.
    for i in range(3):
        for j in range(i):
            r = math.dist(p[i], p[j])
            if params["family"] == "lj":
                total += 4*params["depth"]*((params["length"]/r)**12-(params["length"]/r)**6)
            else:
                u = math.exp(-params["inverse_range"]*(r-params["length"]))
                total += params["depth"]*((1-u)**2-1)
    cosines, sides = [], []
    for i in range(3):
        a, b = [p[j]-p[i] for j in range(3) if j != i]
        cosines.append(float(np.dot(a, b)/(np.linalg.norm(a)*np.linalg.norm(b))))
        sides.append(float(np.linalg.norm(p[(i+1)%3]-p[i])))
    return total*(1+params["temperature_coefficient"]*(temperature-450.)/450.) + params["three_body"]*(1+3*np.prod(cosines))/np.prod(sides)**3


def finite_difference(p, temperature, params, h=3e-4):
    gradient = np.empty((3, 3))
    for i in range(3):
        for j in range(3):
            d = np.zeros((3, 3)); d[i, j] = h
            gradient[i, j] = -(independent_energy(p-2*d, temperature, params)-8*independent_energy(p-d, temperature, params)+8*independent_energy(p+d, temperature, params)-independent_energy(p+2*d, temperature, params))/(12*h)
    return gradient


@pytest.mark.parametrize("family", ["lj", "morse"])
def test_pair_equilateral_well_analytic(family):
    params = fixture(family)
    r = params["length"]*(2**(1/6) if family == "lj" else 1.)
    e, f = energy_forces(triangle(r), 450., params)
    assert abs(e + 3*.11) < 1e-13
    assert np.max(np.abs(f)) < 1e-13


def test_threebody_equilateral_analytic():
    params = fixture(three=200.)
    params["depth"] = 0.
    r = 3.1
    p = triangle(r)
    e, f = energy_forces(p, 450., params)
    expected = 11*200./(8*r**9)
    assert abs(e-expected) < 1e-15
    np.testing.assert_allclose(f, 9*expected/r**2*p, atol=1e-14)


@pytest.mark.parametrize("params", [fixture(), fixture("morse"), fixture(three=200.), fixture("morse", 200.), fixture(temperature=.24)])
@pytest.mark.parametrize("p", [triangle(2.2), triangle(2.4, 3.2, 4.4), np.array([[-2.2, 0, 0], [0, 0, 0], [2.2, 0, 0]])])
def test_independent_reference_and_conservation(params, p):
    e, f = energy_forces(p, 180., params)
    assert abs(e-independent_energy(p, 180., params)) < 1e-10
    np.testing.assert_allclose(f, finite_difference(p, 180., params), atol=1e-7, rtol=1e-8)
    np.testing.assert_allclose(f.sum(axis=0), 0., atol=1e-11)
    np.testing.assert_allclose(np.cross(p, f).sum(axis=0), 0., atol=1e-11)


def test_rotation_translation_permutation_consistency():
    p, params = triangle(2.4, 3.2, 4.4), fixture("morse", 200., .24)
    q = np.array([[0., 0., 1.], [1., 0., 0.], [0., 1., 0.]])
    e, f = energy_forces(p, 900., params)
    e2, f2 = energy_forces(p.dot(q)+[.3, -.4, .2], 900., params)
    assert abs(e-e2) < 1e-12
    np.testing.assert_allclose(f2, f.dot(q), atol=1e-12)
    e3, f3 = energy_forces(p[[2, 0, 1]], 900., params)
    assert abs(e-e3) < 1e-12
    np.testing.assert_allclose(f3, f[[2, 0, 1]], atol=1e-12)


def test_world_public_boundary_and_replay():
    worlds = [World(s) for s in (71001, 71002, 71003)]
    assert all(w.describe() == worlds[0].describe() for w in worlds)
    w, spec = worlds[0], example()
    assert w.run(spec, noise_key="one") == World(71001).run(spec, noise_key="one")
    assert w.run(spec, noise_key="one") != w.run(spec, noise_key="two")
    assert w.cost(spec) == 2
    assert w.run(spec)["axis"] == [0, 1]
    assert np.asarray(w.run(spec)["values"]).shape == (2, 10)
    assert set(w.run(spec)) == {"axis", "channels", "values"}
    for kind in ("development", "conditions", "interventions"):
        assert w.panel(81001, kind, 2) == worlds[1].panel(81001, kind, 2)
        for s in w.panel(81001, kind, 2):
            assert w.validate(s) == s


@pytest.mark.parametrize("mutation", [lambda s: s.update(temperature_k=True), lambda s: s.update(temperature_k=901), lambda s: s.update(private_family="pair"), lambda s: s.update(configuration_ids=[1, 0]), lambda s: s["configurations"][0][0].__setitem__(0, float("nan")), lambda s: s["configurations"][0].__setitem__(1, [0., 0., 0.]), lambda s: s.update(configurations=s["configurations"]*5)])
def test_invalid_requests_are_public_and_stateless(mutation):
    world = World(71001)
    good = example()
    expected = world.run(good)
    invalid = copy.deepcopy(good)
    mutation(invalid)
    with pytest.raises(ValueError):
        world.run(invalid)
    assert world.run(good) == expected


def test_baseline_public_only_shape_and_exact_retrieval():
    spec, world = example(), World(71001)
    assert np.asarray(baseline([], spec)).shape == (2, len(CHANNELS))
    obs = world.run(spec, noise_key="baseline")
    records = [{"spec": spec, "observation": obs}]
    assert baseline(records, spec) == obs["values"]
    altered = copy.deepcopy(records)
    altered[0]["observation"]["values"][0] = [1.]
    with pytest.raises(ValueError):
        baseline(altered, spec)
