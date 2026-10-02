"""Independent physical identities and public-boundary checks for the prototype."""

import copy
import json

import numpy as np
import pytest
from scipy.linalg import eigvals

from env.electrical_impedance import reference
from env.electrical_impedance.baseline import baseline
from env.electrical_impedance.kernel import Branch, Kernel, Parameters, STRUCTURES
from env.electrical_impedance.protocol import CHANNELS, describe, example, validate_spec
from env.electrical_impedance.world import World


FIXTURES = (Parameters(5000., (Branch(250., 2e-6),)),
            Parameters(4000., (Branch(300., .8e-6), Branch(1200., 8e-6))),
            Parameters(7000., (Branch(140., 2e-6, .1),)))


@pytest.mark.parametrize("parameters", FIXTURES)
def test_independent_impedance_identity_and_passivity(parameters):
    spec = example()
    actual, work = Kernel(parameters).spectrum(spec)
    expected = reference.spectrum(parameters, spec)
    np.testing.assert_allclose(actual, expected, atol=3e-14, rtol=3e-13)
    voltage = actual[:, 0]+1j*actual[:, 1]
    admittance = (spec["amplitude_v"]/voltage-1)/spec["source_ohm"]-1/spec["load_ohm"]
    assert np.min(admittance.real) > 0
    assert np.max(abs(voltage)) <= spec["amplitude_v"]
    assert work == {"linear_solves": len(spec["frequencies_hz"]), "state_dimension": len(Kernel(parameters).system(spec)[0])}


@pytest.mark.parametrize("seed", [7, 46, 1439, 8743])
def test_all_structures_have_strictly_stable_state_matrices(seed):
    # No spectra here; generalized eigenvalues verify decay for every class.
    for structure in STRUCTURES:
        kernel = Kernel(Parameters.generate(seed, structure))
        for source, load in ((100., 200.), (2000., 20000.)):
            spec = dict(example(), source_ohm=source, load_ohm=load)
            mass, matrix, _, _, _ = kernel.system(spec)
            assert np.max(eigvals(matrix, np.diag(mass)).real) < 0


@pytest.mark.parametrize("parameters,source,load", [
    (Parameters(1000., (Branch(50., 1e-7),)), 100., 200.),
    (Parameters(20000., (Branch(2500., 2e-5), Branch(2500., 2e-5))), 2000., 20000.),
    (Parameters(1000., (Branch(50., 1e-7, .3),)), 2000., 200.),
    (Parameters(20000., (Branch(2500., 2e-5, .3),)), 100., 20000.)])
def test_finite_parameter_and_instrument_corners(parameters, source, load):
    spec = dict(example(), frequencies_hz=np.geomspace(2, 5000, 65).tolist(),
                source_ohm=source, load_ohm=load, amplitude_v=2.)
    values, work = Kernel(parameters).spectrum(spec)
    assert np.isfinite(values).all()
    assert np.max(np.linalg.norm(values, axis=1)) <= 2.
    assert work["linear_solves"] == 65


def test_small_positive_inductance_has_the_rc_limit_without_overflow():
    tiny = Parameters(5000., (Branch(250., 2e-6, 1e-320),))
    actual, _ = Kernel(tiny).spectrum(example())
    expected = reference.spectrum(FIXTURES[0], example())
    np.testing.assert_allclose(actual, expected, atol=3e-14, rtol=3e-13)


def test_resistor_limit_and_linear_amplitude():
    spec = example()
    values, work = Kernel(Parameters(5000., ())).spectrum(spec)
    expected = 1/(1+500*(1/5000+1/5000))
    np.testing.assert_allclose(values, np.tile([expected, 0.], (len(values), 1)))
    assert work == {"linear_solves": 0, "state_dimension": 0}
    kernel = Kernel(FIXTURES[2])
    first, _ = kernel.spectrum(spec)
    second, _ = kernel.spectrum(dict(spec, amplitude_v=2.))
    np.testing.assert_array_equal(second, 2*first)


def test_phasor_conjugacy_is_an_algebraic_identity():
    # Real descriptor coefficients imply H(-i*w)=conj(H(i*w)); no extra spectra.
    for parameters in FIXTURES:
        system = Kernel(parameters).system(example())
        assert all(np.isrealobj(item) for item in system)


def test_sample_grid_does_not_change_a_reading():
    kernel = Kernel(FIXTURES[1])
    dense, _ = kernel.spectrum(example())
    single, _ = kernel.spectrum(dict(example(), frequencies_hz=[100.]))
    np.testing.assert_array_equal(single[0], dense[3])


def test_measurement_keys_repeat_but_new_readings_are_independent():
    world = World(7)
    spec = dict(example(), frequencies_hz=np.geomspace(2, 5000, 65).tolist())
    clean = world.run(spec)
    first, repeat, second = [world.run(spec, noise_key=key) for key in ("first", "first", "second")]
    assert first == repeat and first != second
    residual = np.asarray(first["values"])-clean["values"]
    assert .0007 < float(residual.std()) < .0013
    assert set(first) == {"axis", "channels", "values"}
    assert first["axis"] == spec["frequencies_hz"]


def test_description_is_identical_and_contains_no_private_menu():
    encoded = json.dumps(describe(), sort_keys=True)
    for seed in (7, 46, 1439, 8743):
        world = World(seed)
        assert json.dumps(world.describe(), sort_keys=True) == encoded
        for structure in STRUCTURES:
            world._structure = structure
            assert json.dumps(world.describe(), sort_keys=True) == encoded
    for marker in STRUCTURES+ ("leakage_ohm", "branches", "capacitance", "inductance", "operator_stratum"):
        assert marker not in encoded


@pytest.mark.parametrize("field,bad", [
    ("frequencies_hz", []), ("frequencies_hz", [0]), ("frequencies_hz", [-1]),
    ("frequencies_hz", [2, 2]), ("frequencies_hz", [5001]), ("frequencies_hz", [2]*66),
    ("frequencies_hz", [float("nan")]), ("frequencies_hz", [float("inf")]),
    ("frequencies_hz", [True]), ("frequencies_hz", [10**1000]),
    ("source_ohm", 0), ("source_ohm", -1), ("source_ohm", 10**1000),
    ("load_ohm", float("nan")), ("load_ohm", float("inf")), ("amplitude_v", 0),
    ("amplitude_v", True), ("amplitude_v", "1")])
def test_invalid_controls_rejected_before_simulation(field, bad):
    with pytest.raises(ValueError):
        validate_spec(dict(example(), **{field: bad}))


def test_unknown_fields_parameters_seed_and_cost():
    world = World(7)
    with pytest.raises(ValueError):
        world.validate(dict(example(), unknown=3))
    for seed in (True, -1, 10**100, 1.5):
        with pytest.raises(ValueError):
            World(seed)
    for arguments in ((0, 2e-6), (50, 0), (50, 2e-6, -1), (50, 2e-6, float("inf"))):
        with pytest.raises(ValueError):
            Branch(*arguments)
    with pytest.raises(ValueError):
        Parameters(5000, (Branch(200, 2e-6, .1), Branch(200, 2e-6)))
    assert world.cost(dict(example(), frequencies_hz=[100.])) == 10
    assert world.cost(dict(example(), frequencies_hz=np.geomspace(2, 5000, 65).tolist())) == 142
    with pytest.raises(ValueError):
        world.run(example(), noise_key=100)


def test_work_cap_is_enforced(monkeypatch):
    kernel = Kernel(FIXTURES[0])
    monkeypatch.setattr(kernel, "MAX_SOLVES", 0)
    with pytest.raises(RuntimeError, match="budget"):
        kernel.spectrum(example())


def test_nonfinite_and_failed_linear_solves_are_bounded(monkeypatch):
    kernel = Kernel(FIXTURES[0])
    monkeypatch.setattr(np.linalg, "solve", lambda *args: np.array([complex(float("nan"))]))
    with pytest.raises(RuntimeError, match="nonfinite"):
        kernel.spectrum(example())
    def fail(*args):
        raise np.linalg.LinAlgError("injected failure")
    monkeypatch.setattr(np.linalg, "solve", fail)
    with pytest.raises(RuntimeError, match="linear solve failed"):
        kernel.spectrum(example())


def test_panel_is_private_parameter_blind_valid_and_bounded():
    left, right = World(7), World(46)
    for kind in ("development", "conditions", "interventions"):
        specs = left.panel(1439, kind, 4)
        assert specs == right.panel(1439, kind, 4)
        assert all(validate_spec(spec) == spec for spec in specs)
    for count in (0, 65, True):
        with pytest.raises(ValueError):
            left.panel(1439, "conditions", count)
    with pytest.raises(ValueError):
        left.panel(1439, "unknown", 1)


def test_weak_baseline_only_uses_public_records(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("private simulator accessed by baseline")
    monkeypatch.setattr(Kernel, "spectrum", forbidden)
    monkeypatch.setattr(Parameters, "generate", forbidden)
    source = dict(example(), frequencies_hz=[10., 1000.])
    record = {"spec": source, "observation": {"axis": source["frequencies_hz"], "channels": list(CHANNELS),
                                             "values": [[.8, -.1], [.4, -.3]]}}
    query = dict(source, frequencies_hz=[100.], amplitude_v=2.)
    np.testing.assert_allclose(baseline([record], query), [[1.2, -.4]])
    np.testing.assert_allclose(baseline([], query), [[2/1.1, 0.]])
    broken = copy.deepcopy(record)
    broken["observation"]["axis"] = [10., 20.]
    with pytest.raises(ValueError):
        baseline([broken], query)
    broken = copy.deepcopy(record)
    broken["observation"]["values"][0][0] = float("nan")
    with pytest.raises(ValueError):
        baseline([broken], query)
