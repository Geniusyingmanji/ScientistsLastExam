"""Outcome-blind domains and control masks for the unified twelve-world cohort."""
from copy import deepcopy

import numpy as np
import pytest

from env.registry import load_world
from env.unified_panels import (ENVIRONMENTS, cell_exclusions, evaluation_mask,
                                generate_panel, mask_contract, public_panel_domain)


def layout(world, spec):
    return {"axis": spec[world.axis_field], "channels": list(world.channels)}


@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_panels_parameter_blind_and_masks_ignore_outcomes(environment):
    first, _ = load_world(environment, 61301)
    second, _ = load_world(environment, 61302)
    for kind in ("conditions", "interventions"):
        panels = generate_panel(first, 71401, kind, 6)
        assert panels == generate_panel(second, 71401, kind, 6)
        for spec in panels:
            assert first.validate(spec) == spec
            public = layout(first, spec)
            mask = evaluation_mask(environment, spec, public)
            assert mask.shape == (len(public["axis"]), len(public["channels"]))
            assert mask.any()
            public["values"] = "ignored sentinel: a mask must not depend on observed outcomes"
            assert np.array_equal(mask, evaluation_mask(environment, spec, public))
    domain = public_panel_domain(environment)
    assert set(domain["domains"]) == {"conditions", "interventions"}
    assert "seed" not in domain


def test_molecular_has_distinct_control_domain_without_changing_legacy():
    world, _ = load_world("molecular_forces", 61301)
    original = world.panel(71401, "conditions", 6)
    revised = generate_panel(world, 71401, "conditions", 6)
    assert all(spec["temperature_k"] == 450.0 for spec in revised)
    assert any(spec["temperature_k"] != 450.0 for spec in original)
    assert world.panel(71401, "conditions", 6) == original
    assert [s["configurations"] for s in revised] == [s["configurations"] for s in original]
    shifted = generate_panel(world, 71401, "interventions", 6)
    assert all(180 <= spec["temperature_k"] <= 900 for spec in shifted)
    assert any(spec["temperature_k"] != 450 for spec in shifted)


def test_microbe_absence_and_exact_depletion_are_prescribed_clean_constants():
    world, _ = load_world("microecology", 61301)
    spec = world.validate({"initial": {"A": .05, "B": 0., "C": .05, "nutrient": 5.},
                           "times_h": [0., 6., 12., 18.],
                           "events": [{"time_h": 12., "deplete": {"channel": "peak-01", "fraction": 1.}}]})
    clean = world.run(spec)
    mask = evaluation_mask(world.name, spec, clean)
    assert not mask[0].any()
    assert not mask[:, 1].any()
    assert not mask[2, 4]
    assert mask[1, 4] and mask[3, 4]
    assert np.array_equal(np.asarray(clean["values"])[:, 1], np.zeros(4))
    assert clean["values"][2][4] == 0


def test_clamps_remove_constants_and_exact_pair_redundancy():
    world, _ = load_world("ising_spin", 61301)
    spec = world.validate({"temperatures": [1., 2.], "clamp": {"A": -1, "B": 1}})
    clean = world.run(spec)
    mask = evaluation_mask(world.name, spec, clean)
    channels = clean["channels"]
    for channel in ("m_A", "m_B", "c_A_B", "c_A_C", "c_B_C"):
        assert not mask[:, channels.index(channel)].any()
    assert mask[:, channels.index("m_C")].all()
    assert mask[:, channels.index("c_C_D")].all()
    values = np.asarray(clean["values"])
    assert np.allclose(values[:, channels.index("c_A_C")], -values[:, channels.index("m_C")])
    assert np.allclose(values[:, channels.index("c_B_C")], values[:, channels.index("m_C")])

    osc, _ = load_world("coupled_oscillators", 61301)
    spec = osc.validate({"times": [0., 1.], "clamp": ["A"]})
    mask = evaluation_mask(osc.name, spec, layout(osc, spec))
    assert not mask[0].any()
    assert not mask[:, [0, 4]].any()
    assert mask[1, 1]


def test_ecology_zero_habitat_is_retained_and_only_single_visit_is_deduplicated():
    world, _ = load_world("field_ecology", 61301)
    spec = world.validate({"habitat_values": [0., 1.], "visits": ["rapid"]})
    clean = world.run(spec)
    mask = evaluation_mask(world.name, spec, clean)
    assert mask[:, 0].all() and not mask[:, 1:].any()
    values = np.asarray(clean["values"])
    assert np.allclose(values[:, 0], values[:, 1], rtol=0, atol=1e-15)
    assert np.allclose(values[:, 0], values[:, 2], rtol=0, atol=1e-15)
    spec["visits"].append("rapid")
    assert evaluation_mask(world.name, spec, layout(world, spec)).all()


def test_hysteresis_initial_and_molecular_zero_index_are_not_known():
    for environment in ("hysteresis_material", "molecular_forces"):
        world, _ = load_world(environment, 61301)
        spec = generate_panel(world, 71401, "conditions", 1)[0]
        public = layout(world, spec)
        assert public["axis"][0] == 0
        assert evaluation_mask(environment, spec, public)[0].all()


def test_contract_and_returned_metadata_are_detached():
    before = public_panel_domain("microecology")
    changed = deepcopy(before)
    changed["domains"]["conditions"] = "tampered"
    assert public_panel_domain("microecology") == before
    assert mask_contract()["outcome_blind"] is True
    assert evaluation_mask("fixture", {}, {"axis": [0], "channels": ["x"]}).all()


def test_masks_reject_axis_or_channel_mismatch():
    world, _ = load_world("field_ecology", 61301)
    spec = generate_panel(world, 71401, "conditions", 1)[0]
    public = layout(world, spec)
    public["axis"] = [0]
    with pytest.raises(ValueError):
        evaluation_mask(world.name, spec, public)
    public = layout(world, spec)
    public["channels"] = ["bogus"]
    with pytest.raises(ValueError):
        cell_exclusions(world.name, spec, public)
