"""Pure public-coordinate policy prototype, intentionally unregistered.

This module does not select a score contract, implement a score, or route any
shared evaluator. All APIs require the exact public world_version. Invalid
specifications, rows, channels, versions or compound readouts raise ValueError.
Legal cells/pairs return eligibility decisions; they are not scientific credit.

readout_eligibility -> {policy_version, eligible, reason}
contrast_eligibility -> the same fields plus scope (or None when ineligible)
equivalent_selected -> bool, for one shared legal channel
prediction_rows -> {policy_version, retained_indices, excluded: [{row, reason}]}
primary_panel_preflight -> prediction_rows, or ValueError when no row is retained
matching_history -> indices of directly equivalent entries, preserving order
  History is a list of <=256 exact {spec,row,channel} entries. All are validated.
duplicate_pair -> bool, including reversed arms; pair objects have the exact
  keys {control,treatment,readout}, with readout={row,channel}. This comparison
  does not certify either pair's eligibility.

Only the exact theta==0,c==1 cell is assigned by the forward predicate. Negative
angles and zero angle at other c values remain legal. No temporal lag applies.
The inclusive 1e-12 inverse-micrometre tolerance is pairwise arithmetic equality
policy, not a detectability threshold or transitive equivalence class. Public
axis order and external observation/prediction shapes are never changed here.
"""
import math

from .protocol import VERSION, normalize_spec

POLICY_VERSION = "optical_public_coordinates-0.1-prototype"
CHANNEL = "normalized_intensity"
Q_TOLERANCE_INV_UM = 1e-12
MAX_HISTORY = 256


def _version(world_version):
    if not isinstance(world_version, str) or world_version != VERSION:
        raise ValueError("unsupported optical world_version")


def _spec(spec, world_version):
    _version(world_version)
    return normalize_spec(spec)


def _selection(spec, row, channel, world_version):
    canonical = _spec(spec, world_version)
    if type(row) is not int or not 0 <= row < len(canonical["angles_rad"]):
        raise ValueError("row must select one valid scalar cell")
    if not isinstance(channel, str) or channel != CHANNEL:
        raise ValueError("unsupported optical channel")
    theta, contrast = canonical["angles_rad"][row], canonical["contrast_b"]
    q_abs = abs(2*math.pi*math.sin(theta)/canonical["wavelength_um"])
    return {"q_abs": q_abs, "contrast": contrast, "known_forward": theta == 0 and contrast == 1}


def _equivalent(left, right):
    return (left["contrast"] == right["contrast"] and
            abs(left["q_abs"]-right["q_abs"]) <= Q_TOLERANCE_INV_UM)


def _decision(eligible, reason):
    return {"policy_version": POLICY_VERSION, "eligible": eligible, "reason": reason}


def _readout(readout):
    if not isinstance(readout, dict) or set(readout) != {"row", "channel"}:
        raise ValueError("readout must contain exactly one row and channel")
    return readout["row"], readout["channel"]


def readout_eligibility(spec, row, channel, *, world_version):
    """Validate one selected public cell; do not compare it with itself."""
    selected = _selection(spec, row, channel, world_version)
    if selected["known_forward"]:
        return _decision(False, "known_forward")
    return _decision(True, "eligible")


def equivalent_selected(a, row_a, b, row_b, *, channel=CHANNEL, world_version):
    """Compare two cells directly; canonical c must be exactly equal."""
    left = _selection(a, row_a, channel, world_version)
    right = _selection(b, row_b, channel, world_version)
    return _equivalent(left, right)


def contrast_eligibility(control, treatment, readout, *, world_version):
    """Select the same row index in each arm; angles may differ between arms."""
    row, channel = _readout(readout)
    left = _selection(control, row, channel, world_version)
    right = _selection(treatment, row, channel, world_version)
    if left["known_forward"] or right["known_forward"]:
        result = _decision(False, "known_forward_arm")
        result["scope"] = None
        return result
    if _equivalent(left, right):
        result = _decision(False, "publicly_equivalent_selected_condition")
        result["scope"] = None
        return result
    matched_q = abs(left["q_abs"]-right["q_abs"]) <= Q_TOLERANCE_INV_UM
    if matched_q:
        scope = "contrast_at_fixed_q"
    elif left["contrast"] == right["contrast"]:
        scope = "scattering_coordinate_contrast"
    else:
        scope = "combined_contrast"
    result = _decision(True, "eligible")
    result["scope"] = scope
    return result


def prediction_rows(spec, *, world_version):
    """Return original indices; exclude only exact known-forward cells."""
    canonical = _spec(spec, world_version)
    retained, excluded = [], []
    for row, theta in enumerate(canonical["angles_rad"]):
        if theta == 0 and canonical["contrast_b"] == 1:
            excluded.append({"row": row, "reason": "known_forward"})
        else:
            retained.append(row)
    return {"policy_version": POLICY_VERSION, "retained_indices": retained, "excluded": excluded}


def primary_panel_preflight(spec, *, world_version):
    """Reject an all-known scientific query without invoking any callback."""
    result = prediction_rows(spec, world_version=world_version)
    if not result["retained_indices"]:
        raise ValueError("all rows are known forward cells; apparatus diagnostic only")
    return result


def matching_history(spec, row, channel, history, *, world_version):
    """Direct pairwise matches against bounded public history, no grouping."""
    target = _selection(spec, row, channel, world_version)
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ValueError("history must be a list of at most 256 public cells")
    selected = []
    for item in history:
        if not isinstance(item, dict) or set(item) != {"spec", "row", "channel"}:
            raise ValueError("history cells require exactly spec, row and channel")
        selected.append(_selection(item["spec"], item["row"], item["channel"], world_version))
    return [index for index, prior in enumerate(selected) if _equivalent(target, prior)]


def _pair(pair, world_version):
    if not isinstance(pair, dict) or set(pair) != {"control", "treatment", "readout"}:
        raise ValueError("pair requires exactly control, treatment and readout")
    row, channel = _readout(pair["readout"])
    return (_selection(pair["control"], row, channel, world_version),
            _selection(pair["treatment"], row, channel, world_version))


def duplicate_pair(first, second, *, world_version):
    """Public semantic duplicate in either orientation; not an eligibility gate."""
    a, b = _pair(first, world_version)
    c, d = _pair(second, world_version)
    return ((_equivalent(a, c) and _equivalent(b, d)) or
            (_equivalent(a, d) and _equivalent(b, c)))
