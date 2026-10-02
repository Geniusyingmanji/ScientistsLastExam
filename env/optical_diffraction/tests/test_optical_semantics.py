"""Pure public-coordinate fixtures. No simulation or integrated routing coverage."""
import ast
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from env.optical_diffraction import semantics as policy
from env.optical_diffraction.protocol import VERSION

CHANNEL = "normalized_intensity"
READOUT = {"row": 0, "channel": CHANNEL}
VERSION_ARGS = {"world_version": VERSION}

DESIGN_CASES = json.loads(r'''
[
  {
    "id": "rows_zero_first_unknown",
    "kind": "prediction_rows",
    "spec": {
      "angles_rad": [
        0,
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected_rows": [
      0,
      1
    ]
  },
  {
    "id": "rows_zero_middle_unknown",
    "kind": "prediction_rows",
    "spec": {
      "angles_rad": [
        -0.1,
        0,
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected_rows": [
      0,
      1,
      2
    ]
  },
  {
    "id": "rows_zero_first_known",
    "kind": "prediction_rows",
    "spec": {
      "angles_rad": [
        0,
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 1
    },
    "expected_rows": [
      1
    ]
  },
  {
    "id": "rows_zero_middle_known",
    "kind": "prediction_rows",
    "spec": {
      "angles_rad": [
        -0.1,
        0,
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 1
    },
    "expected_rows": [
      0,
      2
    ]
  },
  {
    "id": "rows_zero_single_unknown",
    "kind": "prediction_rows",
    "spec": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 0
    },
    "expected_rows": [
      0
    ]
  },
  {
    "id": "rows_zero_single_known",
    "kind": "primary_panel_preflight",
    "spec": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 1
    },
    "expected": "reject_before_truth_or_candidate; apparatus diagnostic only"
  },
  {
    "id": "small_nonzero_is_not_exact_forward",
    "kind": "prediction_rows",
    "spec": {
      "angles_rad": [
        1e-14
      ],
      "wavelength_um": 1,
      "contrast_b": 1
    },
    "expected_rows": [
      0
    ]
  },
  {
    "id": "negative_angle_allowed",
    "kind": "readout",
    "spec": {
      "angles_rad": [
        -0.2
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "row": 0,
    "channel": "normalized_intensity",
    "expected": "eligible"
  },
  {
    "id": "zero_angle_unknown_allowed",
    "kind": "readout",
    "spec": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "row": 0,
    "channel": "normalized_intensity",
    "expected": "eligible"
  },
  {
    "id": "zero_angle_default_contrast_known",
    "kind": "readout",
    "spec": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1
    },
    "row": 0,
    "channel": "normalized_intensity",
    "expected": "normalize c=1 then reject known forward"
  },
  {
    "id": "even_symmetry_pair",
    "kind": "pair",
    "control": {
      "angles_rad": [
        -0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "treatment": {
      "angles_rad": [
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected": "reject_publicly_equivalent_selected_condition"
  },
  {
    "id": "wavelength_remap_pair",
    "kind": "pair",
    "control": {
      "angles_rad": [
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "treatment": {
      "angles_rad": [
        0.049937460992958524
      ],
      "wavelength_um": 0.5,
      "contrast_b": 0.5
    },
    "expected": "reject_publicly_equivalent_selected_condition"
  },
  {
    "id": "q_coordinate_contrast",
    "kind": "pair",
    "control": {
      "angles_rad": [
        -0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "treatment": {
      "angles_rad": [
        0.2
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected": "eligible_q_contrast; no matched-theta requirement"
  },
  {
    "id": "zero_coordinate_contrast",
    "kind": "pair",
    "control": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 0.25
    },
    "treatment": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected": "eligible_contrast_effect; never inspect private all-A label"
  },
  {
    "id": "one_known_arm",
    "kind": "pair",
    "control": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 1
    },
    "treatment": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected": "reject_known_forward_arm under conservative single-cell policy"
  },
  {
    "id": "combined_contrast",
    "kind": "pair",
    "control": {
      "angles_rad": [
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.25
    },
    "treatment": {
      "angles_rad": [
        0.2
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected": "eligible_combined_contrast; no isolated actuator interpretation"
  },
  {
    "id": "single_map_point",
    "kind": "map_single_readout",
    "spec": {
      "angles_rad": [
        0
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "expected": "eligible; do not call pair equivalence on spec,spec"
  },
  {
    "id": "equivalent_map_points",
    "kind": "map_points",
    "points": [
      {
        "angles_rad": [
          -0.1
        ],
        "wavelength_um": 1,
        "contrast_b": 0.5
      },
      {
        "angles_rad": [
          0.1
        ],
        "wavelength_um": 1,
        "contrast_b": 0.5
      }
    ],
    "expected": "reject_duplicate_scientific_condition"
  },
  {
    "id": "history_q_remap",
    "kind": "prospective_target_novelty",
    "prior": {
      "angles_rad": [
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "target": {
      "angles_rad": [
        0.049937460992958524
      ],
      "wavelength_um": 0.5,
      "contrast_b": 0.5
    },
    "expected": "reject_target_as_already_observed; raw spec hashes differ"
  },
  {
    "id": "unknown_linear_cancellation",
    "kind": "compound_readout",
    "spec": {
      "angles_rad": [
        -0.1,
        0.1
      ],
      "wavelength_um": 1,
      "contrast_b": 0.5
    },
    "weights": [
      1,
      -1
    ],
    "expected": "reject_multirow_optical_readout in initial integration; publicly cancels"
  },
  {
    "id": "legacy_single_zero",
    "kind": "legacy_metric_compatibility",
    "observation_axis": [
      0
    ],
    "expected_rows": [
      0
    ]
  },
  {
    "id": "legacy_first_zero",
    "kind": "legacy_metric_compatibility",
    "observation_axis": [
      0,
      1
    ],
    "expected_rows": [
      1
    ]
  },
  {
    "id": "legacy_negative_first",
    "kind": "legacy_metric_compatibility",
    "observation_axis": [
      -1,
      0,
      1
    ],
    "expected_rows": [
      0,
      1,
      2
    ]
  }
]
''')


def spec(theta, c=.5, wavelength=1.):
    return {"angles_rad": [theta], "wavelength_um": wavelength, "contrast_b": c}


def from_q(q, c=.5):
    return spec(math.asin(q/(2*math.pi)), c)


def equivalent(a, b):
    return policy.equivalent_selected(a, 0, b, 0, **VERSION_ARGS)


def history_cell(value):
    return {"spec": value, "row": 0, "channel": CHANNEL}


@pytest.mark.parametrize("case", DESIGN_CASES, ids=[case["id"] for case in DESIGN_CASES])
def test_design_matrix_pure_parts(case):
    kind = case["kind"]
    if kind == "legacy_metric_compatibility":
        pytest.skip("Existing scorer behavior is out of scope; no shared scorer imported or tested")
    elif kind == "prediction_rows":
        result = policy.prediction_rows(case["spec"], **VERSION_ARGS)
        assert result["retained_indices"] == case["expected_rows"]
        assert sorted(result["retained_indices"]+[item["row"] for item in result["excluded"]]) == list(range(len(case["spec"]["angles_rad"])))
    elif kind == "primary_panel_preflight":
        with pytest.raises(ValueError, match="all rows are known"):
            policy.primary_panel_preflight(case["spec"], **VERSION_ARGS)
    elif kind in ("readout", "map_single_readout"):
        result = policy.readout_eligibility(case["spec"], case.get("row", 0), case.get("channel", CHANNEL), **VERSION_ARGS)
        known = case["id"] == "zero_angle_default_contrast_known"
        assert result["eligible"] is (not known)
        assert result["reason"] == ("known_forward" if known else "eligible")
    elif kind == "pair":
        result = policy.contrast_eligibility(case["control"], case["treatment"], READOUT, **VERSION_ARGS)
        expected = {
            "even_symmetry_pair": (False, "publicly_equivalent_selected_condition", None),
            "wavelength_remap_pair": (False, "publicly_equivalent_selected_condition", None),
            "q_coordinate_contrast": (True, "eligible", "scattering_coordinate_contrast"),
            "zero_coordinate_contrast": (True, "eligible", "contrast_at_fixed_q"),
            "one_known_arm": (False, "known_forward_arm", None),
            "combined_contrast": (True, "eligible", "combined_contrast"),
        }[case["id"]]
        assert (result["eligible"], result["reason"], result["scope"]) == expected
    elif kind == "map_points":
        assert policy.matching_history(case["points"][1], 0, CHANNEL, [history_cell(case["points"][0])], **VERSION_ARGS) == [0]
    elif kind == "prospective_target_novelty":
        assert case["prior"] != case["target"]
        assert policy.matching_history(case["target"], 0, CHANNEL, [history_cell(case["prior"])], **VERSION_ARGS) == [0]
    elif kind == "compound_readout":
        with pytest.raises(ValueError):
            policy.contrast_eligibility(case["spec"], case["spec"], {"row": [0, 1], "channel": CHANNEL, "weights": case["weights"]}, **VERSION_ARGS)
    else:
        pytest.fail("design kind not explicitly covered or excluded")


def test_inclusive_representable_tolerance_boundary():
    tolerance = policy.Q_TOLERANCE_INV_UM
    boundary = math.asin(tolerance/(2*math.pi))
    below, above = math.nextafter(boundary, -math.inf), math.nextafter(boundary, math.inf)
    values = [abs(2*math.pi*math.sin(theta)) for theta in (below, boundary, above)]
    assert values[0] < tolerance and values[1] == tolerance and values[2] > tolerance
    origin = spec(0.)
    assert equivalent(origin, spec(below))
    assert equivalent(origin, spec(boundary))
    assert not equivalent(origin, spec(above))


def test_nontransitive_close_pairs_do_not_form_history_clusters():
    tolerance = policy.Q_TOLERANCE_INV_UM
    a, b, c = (from_q(tolerance*factor) for factor in (0., .75, 1.5))
    assert equivalent(a, b) and equivalent(b, c)
    assert not equivalent(a, c)
    assert policy.matching_history(a, 0, CHANNEL, [history_cell(b), history_cell(c)], **VERSION_ARGS) == [0]
    assert policy.matching_history(c, 0, CHANNEL, [history_cell(a), history_cell(b)], **VERSION_ARGS) == [1]


def test_adjacent_rounding_buckets_still_pairwise_equivalent():
    tolerance = policy.Q_TOLERANCE_INV_UM
    a, b = from_q(.49*tolerance), from_q(.51*tolerance)
    assert round(.49) != round(.51)
    assert equivalent(a, b)


def test_contrast_is_exact_and_near_zero_is_not_known_forward():
    assert not equivalent(spec(.1, .5), spec(.1, math.nextafter(.5, 1.)))
    result = policy.contrast_eligibility(spec(.1, .5), spec(.1, math.nextafter(.5, 1.)), READOUT, **VERSION_ARGS)
    assert result["eligible"] and result["scope"] == "contrast_at_fixed_q"
    for theta in (-1e-14, 1e-14, math.nextafter(0., 1.)):
        assert policy.readout_eligibility(spec(theta, 1.), 0, CHANNEL, **VERSION_ARGS)["eligible"]
    assert not policy.readout_eligibility(spec(-0., 1.), 0, CHANNEL, **VERSION_ARGS)["eligible"]


def test_missing_contrast_normalizes_to_one_for_equivalence():
    missing = {"angles_rad": [.1], "wavelength_um": 1.}
    assert equivalent(missing, spec(-.1, 1.))


def test_other_rows_do_not_change_selected_equivalence_or_order():
    a = {"angles_rad": [-.2, -.1, 0.], "wavelength_um": 1., "contrast_b": .5}
    b = {"angles_rad": [0., .1, .3], "wavelength_um": 1., "contrast_b": .5}
    originals = deepcopy((a, b))
    assert policy.equivalent_selected(a, 1, b, 1, **VERSION_ARGS)
    assert policy.prediction_rows(a, **VERSION_ARGS)["retained_indices"] == [0, 1, 2]
    assert (a, b) == originals


def test_all_known_prediction_rows_and_panel_preflight_are_separate():
    forward = spec(0., 1.)
    result = policy.prediction_rows(forward, **VERSION_ARGS)
    assert result["retained_indices"] == []
    assert result["excluded"] == [{"row": 0, "reason": "known_forward"}]
    with pytest.raises(ValueError):
        policy.primary_panel_preflight(forward, **VERSION_ARGS)
    assert policy.primary_panel_preflight(spec(0., .5), **VERSION_ARGS)["retained_indices"] == [0]


def test_duplicate_pairs_accept_reverse_and_q_remapping():
    a, b = spec(.1, .25), spec(.2, .5)
    remap_a = spec(math.asin(.5*math.sin(.1)), .25, .5)
    remap_b = spec(-.2, .5)
    first = {"control": a, "treatment": b, "readout": READOUT}
    reverse = {"control": remap_b, "treatment": remap_a, "readout": READOUT}
    assert policy.duplicate_pair(first, reverse, **VERSION_ARGS)
    changed = dict(reverse, treatment=spec(.15, .25))
    assert not policy.duplicate_pair(first, changed, **VERSION_ARGS)


@pytest.mark.parametrize("row", [True, False, -1, 1, .0, "0", None, [0], 10**100])
def test_invalid_scalar_rows(row):
    with pytest.raises(ValueError):
        policy.readout_eligibility(spec(.1), row, CHANNEL, **VERSION_ARGS)


@pytest.mark.parametrize("channel", [None, True, "", "intensity", [CHANNEL]])
def test_invalid_channel(channel):
    with pytest.raises(ValueError):
        policy.equivalent_selected(spec(.1), 0, spec(-.1), 0, channel=channel, **VERSION_ARGS)


@pytest.mark.parametrize("version", [None, True, 1, "", "optical_diffraction-0.1.0-experimental", policy.POLICY_VERSION])
def test_wrong_world_versions_fail_all_public_helpers(version):
    kw = {"world_version": version}
    pair = {"control": spec(.1), "treatment": spec(.2), "readout": READOUT}
    calls = [lambda: policy.readout_eligibility(spec(.1), 0, CHANNEL, **kw),
             lambda: policy.contrast_eligibility(spec(.1), spec(.2), READOUT, **kw),
             lambda: policy.equivalent_selected(spec(.1), 0, spec(.2), 0, **kw),
             lambda: policy.prediction_rows(spec(.1), **kw),
             lambda: policy.primary_panel_preflight(spec(.1), **kw),
             lambda: policy.matching_history(spec(.1), 0, CHANNEL, [], **kw),
             lambda: policy.duplicate_pair(pair, pair, **kw)]
    for call in calls:
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize("bad_spec", [
    None, [], {}, {"angles_rad": [0]}, {"angles_rad": [0], "wavelength_um": True},
    {"angles_rad": [0], "wavelength_um": 2}, {"angles_rad": [0], "wavelength_um": .1},
    {"angles_rad": [float('nan')], "wavelength_um": 1}, {"angles_rad": [float('inf')], "wavelength_um": 1},
    {"angles_rad": [True], "wavelength_um": 1}, {"angles_rad": [-.5], "wavelength_um": 1},
    {"angles_rad": [0, 0], "wavelength_um": 1}, {"angles_rad": [.2, .1], "wavelength_um": 1},
    {"angles_rad": [0]*66, "wavelength_um": 1}, {"angles_rad": [], "wavelength_um": 1},
    {"angles_rad": [0], "wavelength_um": 1, "contrast_b": False},
    {"angles_rad": [0], "wavelength_um": 1, "contrast_b": 1.1},
    {"angles_rad": [0], "wavelength_um": 1, "private_seed": 7},
])
def test_malformed_specs_fail_before_policy_decision(bad_spec):
    with pytest.raises(ValueError):
        policy.prediction_rows(bad_spec, **VERSION_ARGS)


@pytest.mark.parametrize("readout", [None, [], {}, {"row": 0}, {"row": 0, "channel": CHANNEL, "weight": 1}, {"row": [0, 1], "channel": CHANNEL}])
def test_malformed_or_compound_readout(readout):
    with pytest.raises(ValueError):
        policy.contrast_eligibility(spec(.1), spec(.2), readout, **VERSION_ARGS)


def test_history_validates_every_entry_and_obeys_bound():
    matching = history_cell(spec(.1))
    malformed = {"spec": spec(.1), "row": 0, "channel": CHANNEL, "hidden_label": "A"}
    with pytest.raises(ValueError):
        policy.matching_history(spec(.1), 0, CHANNEL, [matching, malformed], **VERSION_ARGS)
    assert policy.matching_history(spec(.1), 0, CHANNEL, [matching]*256, **VERSION_ARGS) == list(range(256))
    with pytest.raises(ValueError):
        policy.matching_history(spec(.1), 0, CHANNEL, [matching]*257, **VERSION_ARGS)
    with pytest.raises(ValueError):
        policy.matching_history(spec(.1), 0, CHANNEL, (matching,), **VERSION_ARGS)


def test_malformed_duplicate_pair_fails_closed():
    valid = {"control": spec(.1), "treatment": spec(.2), "readout": READOUT}
    for bad in (None, {}, dict(valid, hidden_state={}), dict(valid, readout={"row": True, "channel": CHANNEL})):
        with pytest.raises(ValueError):
            policy.duplicate_pair(valid, bad, **VERSION_ARGS)


def test_module_imports_only_math_and_public_protocol_no_callbacks_or_buckets():
    tree = ast.parse(Path(policy.__file__).read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
    assert imports == ["math", "protocol"]
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"round", "hash", "World", "Kernel", "baseline", "reference", "generator", "callback"} & names
    assert policy.POLICY_VERSION.endswith("prototype")
