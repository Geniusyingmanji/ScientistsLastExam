"""Inert metadata/schema fixtures only: never call World.run or Kernel.intensity."""
import ast
import json
from pathlib import Path

import pytest

from env.optical_diffraction import protocol
from env.optical_diffraction.baseline import _groups, baseline, support_labels
from env.optical_diffraction.kernel import Parameters

BASE = {"angles_rad": [-.2, 0., .2], "wavelength_um": 1.}


@pytest.mark.parametrize("patch", [
    {"angles_rad": []}, {"angles_rad": [.1]*66}, {"angles_rad": [0., 0.]},
    {"angles_rad": [.1, 0.]}, {"angles_rad": [.41]}, {"angles_rad": [True]},
    {"angles_rad": [float('nan')]}, {"wavelength_um": .49}, {"wavelength_um": True},
    {"contrast_b": 1.1}, {"contrast_b": float('inf')}, {"contrast_b": False}, {"seed": 7},
])
def test_reject_invalid_specs(patch):
    with pytest.raises(ValueError):
        protocol.validate_spec(dict(BASE, **patch))


def test_legal_instrument_edges():
    for angle in (-.4, 0., .4):
        for wavelength in (.5, 1.5):
            for contrast in (-1., 1.):
                spec = {"angles_rad": [angle], "wavelength_um": wavelength, "contrast_b": contrast}
                assert protocol.validate_spec(spec) == spec
                assert protocol.cost(spec) == 9
    assert protocol.cost({"angles_rad": [-.4+k/80 for k in range(65)], "wavelength_um": 1}) == 73


def test_description_and_panels_are_parameter_free():
    description = protocol.describe()
    json.dumps(description, allow_nan=False)
    assert description["axis"]["name"] == "angle"
    assert description["noise_std"] == [.002]
    assert not {"seed", "stratum", "weights", "tags", "positions_um"} & set(description)
    assert protocol.public_panel(7) == protocol.public_panel(7)
    assert all(protocol.validate_spec(row) == row for row in protocol.public_panel(7))


def test_parameter_validation_without_kernel_execution():
    state = Parameters([-.5, .5], [.5, .5], ["A", "B"])
    assert state.as_dict()["weights"] == [.5, .5]
    with pytest.raises(ValueError):
        Parameters([0, 0], [.5, .5], ["A", "B"])
    with pytest.raises(ValueError):
        Parameters([0], [-1], ["A"])


def inert_record(c, values):
    spec = dict(BASE, contrast_b=c)
    return {"id": "fixture", "spec": spec, "observation": {"axis": BASE["angles_rad"], "channels": ["normalized_intensity"], "values": [[x] for x in values]}}


def test_duplicate_absolute_q_is_averaged_before_interpolation():
    groups = _groups([inert_record(1., [.2, .3, .6])])
    assert len(groups[1.]) == 2
    assert groups[1.][1][1] == .4
    assert baseline([inert_record(1., [.2, .3, .6])], dict(BASE, contrast_b=.5)) == [[.4], [.3], [.4]]


def test_zero_record_baseline_and_known_quadratic_fixture():
    assert baseline([], BASE) == [[1.], [1.], [1.]]
    records = [inert_record(-1., [.9]*3), inert_record(0., [.1]*3), inert_record(1., [.5]*3)]
    answer = baseline(records, dict(BASE, contrast_b=.5))
    assert all(abs(row[0]-.15) < 1e-12 for row in answer)


def test_outside_support_uses_endpoint_without_clipping():
    query = {"angles_rad": [-.4, .4], "wavelength_um": .5, "contrast_b": 0.}
    assert baseline([inert_record(1., [-.2, .4, -.6])], query) == [[-.4], [-.4]]
    assert support_labels([BASE], query) == ["extrapolation", "extrapolation"]
    assert support_labels([BASE], BASE) == ["interpolation"]*3
    assert support_labels([], BASE) == ["no_source"]*3


def test_partial_contrast_tie_prefers_smaller_contrast():
    assert baseline([inert_record(1., [.7]*3), inert_record(-1., [.3]*3)], dict(BASE, contrast_b=0.)) == [[.3]]*3


@pytest.mark.parametrize("fault", ["shape", "nan", "private"])
def test_bad_source_records_fail_without_fallback(fault):
    record = inert_record(1., [.2]*3)
    if fault == "shape":
        record["observation"]["values"][0] = []
    elif fault == "nan":
        record["observation"]["values"][0] = [float('nan')]
    else:
        record["private_seed"] = 7
    with pytest.raises(ValueError):
        baseline([record], BASE)


def test_reference_source_has_no_production_import():
    tree = ast.parse((Path(protocol.__file__).parent / "reference.py").read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    assert imports == ["math"]


@pytest.mark.parametrize("positions,weights,tags", [
    ([0], None, ["A"]), ([0], [True], ["A"]), ([10**1000], [1], ["A"]),
    ([float('nan')], [1], ["A"]), ([0], [float('inf')], ["A"]),
    ([3.01], [1], ["A"]), ([0], [.5], ["A"]), ([0], [1], ["C"]),
])
def test_private_state_schema_fails_closed_without_scattering(positions, weights, tags):
    with pytest.raises(ValueError):
        Parameters(positions, weights, tags)
