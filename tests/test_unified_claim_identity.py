"""Adversarial public-control aliases must not masquerade as new effects."""
from copy import deepcopy

import numpy as np
import pytest

from env.registry import load_world
from env.unified_scoring import claim_eligibility


def reject_same_target(world, control, treatment, channel, row=0):
    control, treatment = world.validate(control), world.validate(treatment)
    readout = {"row": row, "channel": channel}
    result = claim_eligibility(world, control, treatment, readout)
    assert not result["eligible"], result
    column = world.channels.index(channel)
    left, right = world.run(control)["values"][row][column], world.run(treatment)["values"][row][column]
    assert np.isclose(left, right, rtol=0, atol=1e-10)


@pytest.mark.parametrize("environment", ["microecology", "reaction_kinetics", "gene_regulation"])
def test_future_events_cannot_create_a_past_effect(environment):
    world, _ = load_world(environment, 82101)
    if environment == "microecology":
        control = {"initial": {"A": .1, "B": .1, "C": .1, "nutrient": 5.},
                   "times_h": [0., 12., 48.], "events": []}
        treatment = dict(deepcopy(control), events=[{"time_h": 36., "feed": 1.}])
    elif environment == "reaction_kinetics":
        control = {"temperature_k": 320., "initial_mM": [1., 0., 0., 0.],
                   "times_s": [0., 12., 60.], "interventions": []}
        treatment = dict(deepcopy(control), interventions=[{"time_s": 36., "kind": "add", "amounts_mM": [1., 0., 0., 0.]}])
    else:
        control = {"initial_expression": [.3] * 4, "initial_drive": [0.] * 4,
                   "times_h": [0., 6., 24.], "interventions": []}
        treatment = dict(deepcopy(control), interventions=[{"time_h": 18., "kind": "set_drive", "drive": [1., 0., 0., 0.]}])
    reject_same_target(world, control, treatment, world.channels[0], row=1)


def test_heat_unselected_probe_does_not_change_selected_readout():
    world, _ = load_world("heat_transport", 82101)
    control = world.describe()["examples"][0]
    treatment = deepcopy(control)
    treatment["probes"][1] += .01
    reject_same_target(world, control, treatment, world.channels[0], row=1)


def test_catalyst_coupon_names_and_other_coupon_controls_are_not_new_effects():
    from env.catalyst_aging.protocol import reaction
    world, _ = load_world("catalyst_aging", 82101)
    control = {"events": [reaction("A"), reaction("A")], "event_indices": [2]}
    renamed = {"events": [reaction("D"), reaction("D")], "event_indices": [2]}
    reject_same_target(world, control, renamed, "measured_signal")
    control = {"events": [reaction("A", 460.), reaction("B")], "event_indices": [2]}
    treatment = {"events": [reaction("A", 540.), reaction("B")], "event_indices": [2]}
    reject_same_target(world, control, treatment, "measured_signal")
    # Changing the SELECTED coupon's preceding treatment remains a real contrast.
    control["events"][1]["coupon_id"] = "A"
    treatment["events"][1]["coupon_id"] = "A"
    assert claim_eligibility(world, world.validate(control), world.validate(treatment),
                             {"row": 0, "channel": "measured_signal"})["eligible"]


def test_absent_microbe_in_both_arms_does_not_create_a_claim():
    world, _ = load_world("microecology", 82101)
    control = {"initial": {"A": .1, "B": 0., "C": .1, "nutrient": 5.}, "times_h": [12.]}
    treatment = dict(deepcopy(control), temperature_c=35.)
    reject_same_target(world, control, treatment, "B")


def test_hysteresis_future_protocol_after_enclosing_segment_is_irrelevant():
    world, _ = load_world("hysteresis_material", 82101)
    control = {"reset": "negative", "preparation": [], "times": [8., 20.],
               "protocol": [{"time": 0., "field": -1.}, {"time": 5., "field": 1.},
                            {"time": 10., "field": 0.}, {"time": 20., "field": -1.}]}
    treatment = deepcopy(control)
    treatment["protocol"][-1]["field"] = 1.
    reject_same_target(world, control, treatment, "response")
    # The first knot AFTER the readout controls interpolation before it.
    treatment["protocol"][2]["field"] = .5
    assert claim_eligibility(world, world.validate(control), world.validate(treatment),
                             {"row": 0, "channel": "response"})["eligible"]


def test_climate_future_forcing_does_not_change_past_readout():
    world, _ = load_world("climate_response", 82101)
    control = {"forcing_w_m2": [2.] * 20, "times_years": [5, 20]}
    treatment = deepcopy(control)
    treatment["forcing_w_m2"][10:] = [6.] * 10
    reject_same_target(world, control, treatment, world.channels[0])


def test_molecular_unrelated_batch_row_does_not_change_selected_geometry():
    world, _ = load_world("molecular_forces", 82101)
    control = world.describe()["examples"][0]
    treatment = deepcopy(control)
    treatment["configurations"][1] = deepcopy(control["configurations"][0])
    reject_same_target(world, control, treatment, "energy_ev")


def test_ecology_later_visits_and_other_habitats_do_not_change_first_visit():
    world, _ = load_world("field_ecology", 82101)
    control = {"habitat_values": [0.], "visits": ["rapid"]}
    treatment = {"habitat_values": [0., 1.], "visits": ["rapid", "intensive"]}
    reject_same_target(world, control, treatment, "first_visit_detection")


def test_phase_other_angles_and_empty_holder_preparation_are_aliases():
    world, _ = load_world("phase_equilibria", 82101)
    control = {"composition": .3, "hold_time": 30., "preparation": "powder_blend", "loading": 1., "angles_deg": [40.]}
    treatment = dict(deepcopy(control), angles_deg=[40., 50.])
    reject_same_target(world, control, treatment, "intensity")
    control["loading"] = treatment["loading"] = 0.
    treatment["composition"] = .7
    reject_same_target(world, control, treatment, "intensity")
