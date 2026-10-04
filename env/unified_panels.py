"""Opt-in unified-evaluation domains and public-control cell exclusions.

The domain descriptions are candidate safe. Realized panels and their seeds are
operator only. These helpers never inspect hidden world parameters, observations'
values or mechanism-family labels. Existing ``World.panel`` behavior is unchanged.
"""
from copy import deepcopy

import numpy as np


PROTOCOL = "sle-unified-panels-1.0"
_LAYOUTS = {
    "microecology": ("times_h", ("A", "B", "C", "nutrient", "peak-01", "peak-02", "peak-03")),
    "coupled_oscillators": ("times", tuple(p + n for p in ("x_", "v_") for n in "ABCD")),
    "reaction_kinetics": ("times_s", tuple("ABCD")),
    "heat_transport": ("times", tuple("probe_%d_temperature" % i for i in (1, 2, 3))),
    "gene_regulation": ("times_h", ("G1", "G2", "G3", "G4")),
    "ising_spin": ("temperatures", tuple("m_" + n for n in "ABCDEF") + tuple(
        "c_" + a + "_" + b for i, a in enumerate("ABCDEF") for b in "ABCDEF"[i + 1:])),
    "hysteresis_material": ("times", ("response",)),
    "molecular_forces": ("configuration_ids", ("energy_ev",) + tuple(
        "f%d%s_ev_per_a" % (i, a) for i in (1, 2, 3) for a in "xyz")),
    "climate_response": ("times_years", ("surface_temperature_anomaly_k", "toa_imbalance_w_m2")),
    "catalyst_aging": ("event_indices", ("measured_signal",)),
    "field_ecology": ("habitat_values", ("first_visit_detection", "any_visit_detection", "all_visits_detection")),
    "phase_equilibria": ("angles_deg", ("intensity",)),
}
ENVIRONMENTS = tuple(_LAYOUTS)
_INITIAL_STATE_WORLDS = {"microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport", "gene_regulation"}
_DOMAINS = {
    "microecology": {
        "conditions": "Fresh batches: A in [0.03,0.15], B/C in [0.03,0.12], nutrient [2,7], temperature [24,36] C; every third item omits B or C; assays at 0,4,8,12,18,24,36,48,60 h.",
        "interventions": "Same fresh-inoculum ranges, with one event at 8/12/18/24 h: fraction depletion [0.6,1], nutrient feed [0.5,2.5], or temperature shift [22,38] C, cycling across items.",
    },
    "coupled_oscillators": {
        "conditions": "Unmodified networks: initial x/v components in [-0.8,0.8], horizon [6,18], 35..81 regular or irregular assay times.",
        "interventions": "Same initial/time domain, cycling through edge cut, added mass [0.5,2.5], added damping [0.3,1.4], clamp, and periodic drive (amplitude [0.3,1.1], frequency [0.12,0.65]).",
    },
    "reaction_kinetics": {
        "conditions": "Mixed initial concentrations (Dirichlet 0.8 composition, total [0.5,1.8] mM), temperature [305,345] K, horizon [70,120] s with 8..15 logarithmic positive assay times plus t=0.",
        "interventions": "Same initial domain plus temperature change at [15,28] s to [285,300] or [350,365] K, then one-species addition [0.2,0.8] mM at [35,50] s; event boundaries are assayed.",
    },
    "heat_transport": {
        "conditions": "Initial [10,55] C, boundaries [5,45] C, ambient [10,30] C, nine positive times [0.1,30] s plus t=0, and three interior probes in [0.07,0.29]/[0.38,0.62]/[0.71,0.93]; other controls use the public example.",
        "interventions": "Adjacent items are matched controls/treatments with initial [30,50] C and heater location [0.2,0.4], power [3,6], width [0.065,0.11]; cycle flow -0.8 versus +0.8, cooling 0 versus 2.5, and mirrored heater location.",
    },
    "gene_regulation": {
        "conditions": "Initial expression components [0.1,0.9], zero external drive, horizon [16,24] h with 10..16 logarithmic positive assays plus t=0.",
        "interventions": "Same initial/time domain plus a signed drive of magnitude [1,3] to one or two genes, on at [1.5,3.5] h and off at [7,10] h; boundaries and pulse midpoint are assayed.",
    },
    "ising_spin": {
        "conditions": "Unmodified systems, 7..13 temperatures between random low [0.4,0.75] and high [2.8,5.8], logarithmic or uniform grids.",
        "interventions": "Same temperature domain; cycle a one-spin field of magnitude [0.2,1], one-spin clamp, bond suppression [0.35,1], and a combined random field [-0.7,0.7] with clamp and cut.",
    },
    "hysteresis_material": {
        "conditions": "Alternate positive/negative resets; major loops amplitude [0.85,1.4] with fast [8,22] or slow [220,420] legs, or prepared dwells/ramps ending at field [-0.2,0.2]; regular samples include protocol knots.",
        "interventions": "Minor loops and interrupted ramps: amplitude [0.85,1.45], log-uniform leg [8,180], dwell [20,100], signed reversal in [-0.25,0.5]; alternate whether an opposite-field prehistory is applied.",
    },
    "molecular_forces": {
        "conditions": "Four fresh triangle configurations per item, side draws uniform [2.3,5.2] angstrom conditioned on triangle inequalities, centered and randomly rotated; fixed temperature 450 K.",
        "interventions": "The same fresh-geometry distribution, with temperature drawn uniformly [180,900] K instead of fixed 450 K. This is temperature-control transfer, not proof of a causal mechanism.",
    },
    "climate_response": {
        "conditions": "40/80/120/160-year histories, forcing amplitude [0.5,7.5] W/m2, alternating constant steps and linear ramps; assays at years 1,2,5, every tenth year, and endpoint.",
        "interventions": "Same horizons/amplitudes, cycling step/ramp, one-third-duration pulse, and sinusoidal forcing (period [8,45] years); even items begin with negative forcing [-1,0] for one fifth of the history.",
    },
    "catalyst_aging": {
        "conditions": "Four cycles for coupon A plus B/C reference coupons at fixed temperature [450,550] K, feed [0.2,1.1], duration [3,14]; blanks/standards before and after cycles 2 and 4; all events read out.",
        "interventions": "Same history layout but independently vary coupon A's cycle temperatures [440,560] K and feeds [0.1,1.2], with B/C reactions held at the initial settings.",
    },
    "field_ecology": {
        "conditions": "Seven sorted habitat coordinates drawn uniformly [-1.6,1.6], 64 independently sampled sites per coordinate, one rapid survey visit.",
        "interventions": "Same habitat domain, with 1..3 visits and independently drawn rapid/intensive methods. Habitat is observational; only survey method and revisit schedule are controlled.",
    },
    "phase_equilibria": {
        "conditions": "Composition [0,1], hold time [0,120], alternate powder-blend/quenched preparation, loading 1, full 161-angle grid from 10 to 90.",
        "interventions": "Same composition/time/preparation and full-angle domain, loading [0.3,1]; the first item is a zero-loading holder control. Holder response is unknown and remains scored.",
    },
}


def public_panel_domain(environment):
    """Return the fixed sampling domain without any realized specs or seeds."""
    if environment not in _DOMAINS:
        raise ValueError("environment has no unified panel contract")
    return {"protocol": PROTOCOL, "environment": environment,
            "labels": {"conditions": "new-condition prediction", "interventions": "control-shift prediction"},
            "domains": deepcopy(_DOMAINS[environment]),
            "interpretation": "Two host-selected prediction domains. Their scores do not by themselves identify causal mechanisms. Candidate programs are frozen before realized test specs are supplied to them.",
            "exclusions": "Prescribed initial states; absent microbial strains; fully depleted fractions at the depletion instant; clamped oscillator coordinates; clamped spin means/pairs and redundant one-clamped-endpoint moments; duplicate single-visit ecology fractions. Other rows, including hysteresis t=0 and static axis coordinate 0, are retained."}


def generate_panel(world, panel_seed, kind, count=8):
    """Opt-in panel constructor; its output is trusted operator material."""
    specs = world.panel(panel_seed, kind, count=count)
    if world.name == "molecular_forces" and kind == "conditions":
        specs = [world.validate(dict(spec, temperature_k=450.0)) for spec in specs]
    return specs


def mask_contract():
    """Machine-readable public rules, with no target values or private inputs."""
    return {"protocol": PROTOCOL, "known_environments": list(ENVIRONMENTS),
            "initial_state_exclusions": sorted(_INITIAL_STATE_WORLDS),
            "rules": {
                "microecology": "Exclude t=0; zero-inoculum strain columns at all times; fully depleted fraction at the exact event time.",
                "coupled_oscillators": "Exclude t=0 and both position/velocity columns of each clamped node.",
                "reaction_kinetics": "Exclude t=0 only.",
                "heat_transport": "Exclude t=0 only; legal probes are interior.",
                "gene_regulation": "Exclude t=0 only.",
                "ising_spin": "Exclude clamped means, both-clamped pair constants, and one-clamped pair moments redundant with a retained free mean.",
                "field_ecology": "With one visit retain first-visit fraction; any/all fractions duplicate it. Retain all three channels with multiple visits.",
                "remaining_worlds": "Retain all cells. Catalyst blanks/standards, hysteresis t=0, and static coordinate/index 0 are not prescribed numerical responses.",
                "unsupported": "Retain all cells; no environment-specific semantic certification."},
            "outcome_blind": True,
            "interpretation": "Exclusions remove certified public constants and selected exact redundancies; remaining cells are not certified independent or mechanism-identifying."}


def cell_exclusions(environment, spec, observation):
    """Public-only exclusion reasons. Empty string denotes a scored cell.

    ``spec`` must already have passed the world's public schema validation.
    ``observation`` supplies only the public axis/channel layout; values are
    deliberately neither inspected nor required. This keeps masks outcome blind.
    """
    if environment not in _LAYOUTS:
        if (not isinstance(observation, dict) or not isinstance(observation.get("axis"), list)
                or not observation["axis"] or not isinstance(observation.get("channels"), list)
                or not observation["channels"]):
            raise ValueError("invalid public instrument layout")
        return [[""] * len(observation["channels"]) for _ in observation["axis"]]
    axis_field, channels = _LAYOUTS[environment]
    if (not isinstance(spec, dict) or not isinstance(observation, dict)
            or tuple(observation.get("channels", ())) != channels
            or observation.get("axis") != spec.get(axis_field)
            or not isinstance(spec.get(axis_field), list) or not spec[axis_field]):
        raise ValueError("observation does not match the public instrument layout")
    axis = spec[axis_field]
    reasons = [[""] * len(channels) for _ in axis]
    for row, coordinate in enumerate(axis):
        if environment in _INITIAL_STATE_WORLDS and coordinate == 0:
            reasons[row] = ["prescribed_initial_state"] * len(channels)
        if environment == "microecology":
            for col, channel in enumerate(channels[:3]):
                if spec["initial"][channel] == 0:
                    reasons[row][col] = "zero_inoculum_strain"
            for event in spec.get("events", []):
                depletion = event.get("deplete", {})
                if event["time_h"] == coordinate and depletion.get("fraction") == 1:
                    reasons[row][channels.index(depletion["channel"])] = "complete_fraction_depletion"
        elif environment == "coupled_oscillators":
            for col, channel in enumerate(channels):
                if channel[2:] in spec.get("clamp", []):
                    reasons[row][col] = "oscillator_clamp"
        elif environment == "ising_spin":
            clamp = spec.get("clamp", {})
            for col, channel in enumerate(channels):
                endpoints = channel[2:].split("_")
                if all(node in clamp for node in endpoints):
                    reasons[row][col] = "spin_clamped_constant"
                elif len(endpoints) == 2 and any(node in clamp for node in endpoints):
                    reasons[row][col] = "redundant_clamped_pair_moment"
        elif environment == "field_ecology" and len(spec["visits"]) == 1:
            reasons[row][1:] = ["redundant_single_visit_fraction"] * 2
    return reasons


def evaluation_mask(environment, spec, observation):
    """Return a boolean matrix with True for cells included in unified scoring."""
    return np.asarray(cell_exclusions(environment, spec, observation)) == ""
