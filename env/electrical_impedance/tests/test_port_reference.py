"""Synthetic public-record fixtures only: no World, kernel or true components."""

import ast
import builtins
import copy
from pathlib import Path

import numpy as np
import pytest

from env.electrical_impedance.baseline import baseline
from env.electrical_impedance import port_reference as module
from env.electrical_impedance.port_reference import ReferenceFailure, port_reference, predict_with_diagnostics


def spec(frequencies=None, **changes):
    return {"frequencies_hz": frequencies or [2., 100., 5000.], "source_ohm": 500.,
            "load_ohm": 5000., "amplitude_v": 1., **changes}


def synthetic_record(source, admittance):
    # This generic numerical admittance is not a hidden circuit-family fixture.
    y = np.asarray(admittance, dtype=complex)+np.zeros(len(source["frequencies_hz"]))
    voltage = source["amplitude_v"]/(1+source["source_ohm"]*(1/source["load_ohm"]+y))
    return {"spec": source, "observation": {"axis": source["frequencies_hz"],
            "channels": ["voltage_real", "voltage_imag"], "values": np.column_stack((voltage.real, voltage.imag)).tolist()}}


@pytest.mark.parametrize("changes", [{}, {"load_ohm": 500.}, {"source_ohm": 1500.}, {"amplitude_v": .5}])
def test_deembed_reembed_public_divider(changes):
    source = spec()
    y = .001+.0004j
    record = synthetic_record(source, y)
    query = spec(**changes)
    expected = synthetic_record(query, y)["observation"]["values"]
    np.testing.assert_allclose(port_reference([record], query), expected, atol=5e-16, rtol=1e-14)


def test_linear_admittance_in_log_frequency_has_exact_interpolation():
    source = spec([2., 5000.])
    def y(f):
        return .0005+.00002*np.log(f)+1j*(.0002-.00001*np.log(f))
    record = synthetic_record(source, y(np.array(source["frequencies_hz"])))
    query = spec([2., 17., 400., 5000.], source_ohm=1500., load_ohm=500.)
    expected = synthetic_record(query, y(np.array(query["frequencies_hz"])))["observation"]["values"]
    np.testing.assert_allclose(port_reference([record], query), expected, atol=5e-16, rtol=1e-14)


def test_known_amplitude_scaling_agrees_with_unchanged_weak_baseline():
    record = synthetic_record(spec(), [.001+.0002j, .003-.0004j, .0002+.0008j])
    query = spec(amplitude_v=.5)
    expected = np.asarray(record["observation"]["values"])*.5
    np.testing.assert_allclose(port_reference([record], query), expected, atol=5e-16)
    np.testing.assert_allclose(port_reference([record], query), baseline([record], query), atol=5e-16)


@pytest.mark.parametrize("voltage", [0., .004, .005])
def test_near_zero_threshold_is_inclusive_without_fallback(voltage):
    record = synthetic_record(spec([100.]), .001)
    record["observation"]["values"] = [[voltage, 0.]]
    with pytest.raises(ReferenceFailure) as caught:
        port_reference([record], spec([100.]))
    assert caught.value.code == "source_near_zero"
    assert caught.value.diagnostics["min_source_magnitude_v"] == voltage


def test_just_above_threshold_is_not_rejected():
    record = synthetic_record(spec([100.]), .001)
    record["observation"]["values"] = [[float(np.nextafter(.005, np.inf)), 0.]]
    np.testing.assert_allclose(port_reference([record], spec([100.])), record["observation"]["values"], atol=1e-16)


def test_denominator_cancellation_is_a_failure():
    y = -1/1500.-1/5000.
    record = synthetic_record(spec(), y)
    with pytest.raises(ReferenceFailure) as caught:
        port_reference([record], spec(source_ohm=1500.))
    assert caught.value.code == "ill_conditioned_denominator"


def test_finite_nonphysical_estimates_are_retained_without_clipping():
    record = synthetic_record(spec(), -.0005)
    result = predict_with_diagnostics([record], spec())
    np.testing.assert_allclose(result["values"], record["observation"]["values"])
    assert result["diagnostics"]["negative_conductance_count"] == 3
    assert result["diagnostics"]["finite_passive_bound_violations"] == 3
    assert min(row[0] for row in result["values"]) > 1.


@pytest.mark.parametrize("frequency", [2., 5000.])
def test_out_of_observed_band_rejects_legal_public_frequency(frequency):
    record = synthetic_record(spec([10., 1000.]), .001)
    with pytest.raises(ReferenceFailure) as caught:
        port_reference([record], spec([frequency]))
    assert caught.value.code == "out_of_band"


@pytest.mark.parametrize("bad", [True, "1", float("nan"), float("inf"), 10**1000])
def test_invalid_observation_cells(bad):
    record = synthetic_record(spec(), .001)
    record["observation"]["values"][0][0] = bad
    with pytest.raises(ReferenceFailure) as caught:
        port_reference([record], spec())
    assert caught.value.code == "invalid_record"


def test_finite_inputs_that_overflow_a_phasor_are_guarded():
    record = synthetic_record(spec([100.]), .001)
    record["observation"]["values"] = [[1.79e308, 1.79e308]]
    with pytest.raises(ReferenceFailure) as caught:
        port_reference([record], spec([100.]))
    assert caught.value.code == "nonfinite_computation"


def test_record_shape_axis_channels_and_private_extras_rejected():
    base = synthetic_record(spec(), .001)
    bad = []
    row = copy.deepcopy(base); row["seed"] = 10000; bad.append(row)
    row = copy.deepcopy(base); row["observation"]["axis"] = [3., 100., 5000.]; bad.append(row)
    row = copy.deepcopy(base); row["observation"]["channels"].reverse(); bad.append(row)
    row = copy.deepcopy(base); row["observation"]["values"][0] = [1.]; bad.append(row)
    for record in bad:
        with pytest.raises(ReferenceFailure):
            port_reference([record], spec())
    for records in ([], [base, base], {"record": base}):
        with pytest.raises(ReferenceFailure):
            port_reference(records, spec())


def test_prediction_does_not_mutate_inputs_or_import_private_implementation(monkeypatch):
    record, query = synthetic_record(spec(), .001+.0002j), spec([30., 700.])
    before = copy.deepcopy((record, query))
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if any(part in name.split(".") for part in ("world", "kernel", "reference")):
            raise AssertionError("private import attempted")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    port_reference([record], query)
    assert (record, query) == before
    tree = ast.parse(Path(module.__file__).read_text(), feature_version=(3, 8))
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert imported == ["protocol"]
