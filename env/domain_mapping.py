"""Finite-family evidence for one frozen point predictor; no code execution.

Coverage concerns registered clean scalar readouts, not a continuous boundary.
Trusted runners supply canonical World validation and externally anchored hashes.
"""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import re

from numpy import nextafter

from .analysis_api import ModelSnapshots, PROTOCOL as SNAPSHOT_PROTOCOL
from .claim_semantics import claim_eligibility, policy_description
from .prospective import _matrix, _public_contract, digest


PROTOCOL = "sle-single-model-domain-0.1"
CLIPPED = frozenset(("microecology", "microecology_causal"))
MAX_POINTS, MAX_TERMS, MAX_CALLS = 12, 32, 96
MAX_BITS = 16384
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError("invalid " + label + " fields")


def text(value, label, maximum=4000):
    if type(value) is not str or not value.strip() or len(value.encode("utf-8")) > maximum:
        raise ValueError("invalid " + label)
    return value


def identifier(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("invalid identifier")
    return value


def hash_value(value):
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError("invalid hash anchor")
    return value


def number(value, lower=-1e12, upper=1e12):
    if type(value) not in (int, float):
        raise ValueError("expected finite real number")
    try:
        result = float(value)
    except OverflowError:
        raise ValueError("expected finite real number") from None
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError("number outside finite bounds")
    return result


def fraction(value):
    result = value if type(value) is Fraction else Fraction(number(value))
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > MAX_BITS:
        raise ValueError("exact arithmetic capacity exceeded")
    return result


def ratio(value):
    value = fraction(value)
    return [str(value.numerator), str(value.denominator)]


def unratio(value):
    if (type(value) is not list or len(value) != 2 or
            any(type(x) is not str or len(x) > 5000 for x in value)):
        raise ValueError("invalid exact ratio")
    try:
        result = fraction(Fraction(int(value[0]), int(value[1])))
    except (ValueError, ZeroDivisionError):
        raise ValueError("invalid exact ratio") from None
    if ratio(result) != value:
        raise ValueError("noncanonical exact ratio")
    return result


def outward(value, direction):
    """Binary64 presentation bound; decisions use the exact fractions."""
    result = float(fraction(value))
    if not math.isfinite(result):
        raise ValueError("interval presentation overflow")
    if ((direction < 0 and Fraction(result) > value) or
            (direction > 0 and Fraction(result) < value)):
        result = float(nextafter(result, -math.inf if direction < 0 else math.inf))
    if not math.isfinite(result):
        raise ValueError("interval presentation overflow")
    return result


def sqrt_upper(value):
    value = fraction(value)
    if value < 0:
        raise ValueError("negative variance")
    if not value:
        return Fraction(0)
    with localcontext() as context:
        context.prec = 80
        root = (Decimal(value.numerator) / Decimal(value.denominator)).sqrt()
        for _ in range(8):
            bound = fraction(Fraction(root))
            if bound * bound >= value:
                return bound
            root = root.next_plus()
    raise ValueError("could not certify square root")


def resolve_model(snapshot, reference):
    """Validate and bind saved source as text; never import or execute it."""
    keys(snapshot, ("protocol", "name", "version", "parameters", "predictor_code"), "snapshot")
    keys(reference, ("name", "version", "sha256"), "model reference")
    if snapshot["protocol"] != SNAPSHOT_PROTOCOL or snapshot["predictor_code"] is None:
        raise ValueError("saved point predictor required")
    hash_value(reference["sha256"])
    store = ModelSnapshots()
    receipt = store.save_model(snapshot["name"], snapshot["version"], snapshot["parameters"], snapshot["predictor_code"])
    if {key: receipt[key] for key in reference} != reference:
        raise ValueError("saved model reference mismatch")
    store.seal()
    resolved, binding = store.resolve_submission({"model_snapshot": reference, "claims": [],
                                                   "explanation": "Frozen single-model domain assessment."})
    return resolved["predictor_code"], binding


def _pointer(spec, pointer, replacement=None):
    if type(pointer) is not str or not pointer.startswith("/") or len(pointer) > 200:
        raise ValueError("invalid varied path")
    tokens = pointer[1:].split("/")
    if any(not t or "~" in t for t in tokens):
        raise ValueError("only literal numeric-leaf JSON paths are supported")
    node = spec
    try:
        for token in tokens[:-1]:
            node = node[int(token)] if type(node) is list and token.isdigit() else node[token]
        token = tokens[-1]
        index = int(token) if type(node) is list and token.isdigit() else token
        value = number(node[index])
        if replacement is not None:
            node[index] = replacement
        return value
    except (KeyError, IndexError, TypeError):
        raise ValueError("varied path must name an existing numeric leaf") from None


def validate_plan(request, public, validate_spec, source_history):
    keys(request, ("protocol", "scope", "model_snapshot", "provenance", "domain", "points",
                   "tolerance", "tolerance_rationale", "family_alpha"), "domain plan")
    if request["protocol"] != PROTOCOL:
        raise ValueError("unsupported domain protocol")
    contract = _public_contract(deepcopy(public))
    text(request["scope"], "scope")
    text(request["tolerance_rationale"], "scientific tolerance rationale")
    tolerance = number(request["tolerance"], 1e-12, .2)
    alpha = number(request["family_alpha"], 1e-6, .05)
    keys(request["model_snapshot"], ("name", "version", "sha256"), "model reference")
    hash_value(request["model_snapshot"]["sha256"])
    provenance = request["provenance"]
    keys(provenance, ("source_history_sha256", "source_cutoff_receipt", "source_observation_ids",
                      "author_priors", "readout_nontriviality"), "provenance")
    hash_value(provenance["source_history_sha256"])
    for field in ("source_cutoff_receipt", "author_priors", "readout_nontriviality"):
        text(provenance[field], field)
    if type(source_history) is not list or len(source_history) > 512 or digest(source_history) != provenance["source_history_sha256"]:
        raise ValueError("source history anchor mismatch")
    ids = []
    for record in source_history:
        if type(record) is not dict or "id" not in record:
            raise ValueError("invalid source history record")
        ids.append(identifier(record["id"]))
    selected = provenance["source_observation_ids"]
    if (len(ids) != len(set(ids)) or type(selected) is not list or len(selected) > 512 or
            any(type(x) is not str or x not in ids for x in selected) or len(set(selected)) != len(selected)):
        raise ValueError("invalid source evidence IDs")
    domain = request["domain"]
    keys(domain, ("mode", "name", "unit", "lower", "upper", "varied_paths"), "domain")
    if domain["mode"] not in ("scalar_control", "readout_horizon", "ordered_path"):
        raise ValueError("unsupported domain mode")
    text(domain["name"], "domain name", 100)
    text(domain["unit"], "domain unit", 100)
    lower, upper = number(domain["lower"]), number(domain["upper"])
    if lower >= upper:
        raise ValueError("empty domain")
    paths = domain["varied_paths"]
    if (type(paths) is not list or not 1 <= len(paths) <= 32 or
            any(type(x) is not str for x in paths) or len(set(paths)) != len(paths) or
            (domain["mode"] != "ordered_path" and len(paths) != 1)):
        raise ValueError("invalid varied paths")
    points = request["points"]
    if type(points) is not list or not 1 <= len(points) <= MAX_POINTS:
        raise ValueError("invalid finite point family")
    canonical, fixed, template, seen, coordinates = [], None, None, set(), set()
    last_u = -math.inf
    for point in points:
        keys(point, ("id", "u", "spec", "readout", "replicates"), "point")
        pid = identifier(point["id"])
        if len(pid) > 48:
            raise ValueError("point ID exceeds 48 characters")
        u = number(point["u"], lower, upper)
        if pid in seen or u <= last_u:
            raise ValueError("point IDs and ordered coordinates must be unique")
        seen.add(pid)
        last_u = u
        n = point["replicates"]
        if type(n) is not int or not 4 <= n <= 16:
            raise ValueError("replicates must be 4..16")
        spec = validate_spec(deepcopy(point["spec"]))
        if type(spec) is not dict:
            raise ValueError("invalid canonical experiment")
        times = spec.get(contract["axis_field"])
        if type(times) is not list or not 1 <= len(times) <= 256:
            raise ValueError("invalid observation axis")
        if domain["mode"] == "readout_horizon" and paths != ["/%s/%d" % (contract["axis_field"], len(times)-1)]:
            raise ValueError("horizon must vary the final observation coordinate")
        masked = deepcopy(spec)
        for path in paths:
            value = _pointer(masked, path, "DOMAIN_AXIS")
            if domain["mode"] != "ordered_path" and value != u:
                raise ValueError("axis coordinate differs from canonical spec")
        if fixed is None:
            fixed = masked
        elif fixed != masked:
            raise ValueError("undeclared control or grid change")
        terms = point["readout"]
        if type(terms) is not list or not 1 <= len(terms) <= MAX_TERMS:
            raise ValueError("invalid scalar readout")
        cells, coefficients = set(), []
        for term in terms:
            keys(term, ("row", "channel", "coefficient"), "readout term")
            row, channel = term["row"], term["channel"]
            if (type(row) is not int or not 0 <= row < len(times) or
                    type(channel) is not str or channel not in contract["channels"] or (row, channel) in cells):
                raise ValueError("duplicate or invalid readout cell")
            cells.add((row, channel))
            if domain["mode"] == "readout_horizon" and row != len(times)-1:
                raise ValueError("horizon readout must use endpoint cells")
            eligible = claim_eligibility(contract["environment"], spec, spec,
                                         {"row": row, "channel": channel}, contract["axis_field"])
            if not eligible["eligible"]:
                raise ValueError("ineligible readout: " + eligible["reason"])
            coefficient = fraction(term["coefficient"])
            if not coefficient:
                raise ValueError("zero readout coefficient")
            coefficients.append(coefficient)
        mass = sum(map(abs, coefficients), Fraction(0))
        readout = [dict(term, weight=ratio(c / mass)) for term, c in zip(terms, coefficients)]
        current_template = [(x["row"], x["channel"], x["weight"]) for x in readout]
        if template is None:
            template = current_template
        elif template != current_template:
            raise ValueError("readout template changes across points")
        selected_key = digest({"controls": {k: v for k, v in spec.items() if k != contract["axis_field"]},
                               "readout": [[times[x["row"]], x["channel"], x["weight"]] for x in readout]})
        if selected_key in coordinates:
            raise ValueError("duplicate scientific readout condition")
        coordinates.add(selected_key)
        canonical.append({"id": pid, "u": u, "spec": spec, "readout": readout, "replicates": n})
    if sum(p["replicates"] for p in canonical) > MAX_CALLS:
        raise ValueError("finite family exceeds 96 observations")
    planned_ids = {"obs-%s-%02d" % (p["id"], k) for p in canonical for k in range(p["replicates"])}
    if set(ids) & planned_ids:
        raise ValueError("mapping observation IDs overlap source history")
    result = deepcopy(request)
    result.update(points=canonical, public=contract, tolerance=tolerance, family_alpha=alpha,
                  eligibility_policy=policy_description(), held_fixed_spec=fixed)
    return result


def readout(values, point, public):
    values = _matrix(values, point["spec"], public)
    return fraction(sum((unratio(term["weight"]) * fraction(values[term["row"]][public["channels"].index(term["channel"])]) /
                         fraction(public["scales"][public["channels"].index(term["channel"])] ) for term in point["readout"]), Fraction(0)))


def design(plan, point, values):
    public = plan["public"]
    mass_sd, bias, raw_bias = Fraction(0), Fraction(0), Fraction(0)
    for term in point["readout"]:
        c = public["channels"].index(term["channel"])
        coefficient = abs(unratio(term["weight"])) / fraction(public["scales"][c])
        sd, raw = fraction(public["noise_std"][c]), fraction(public["noise_mean_bias_bound"][c])
        certified = max(raw, 2 * sd / 5) if public["environment"] in CLIPPED else raw
        mass_sd += coefficient * sd
        bias += coefficient * certified
        raw_bias += coefficient * raw
    variance = fraction(mass_sd * mass_sd)
    alpha = fraction(plan["family_alpha"]) / len(plan["points"])
    radius = fraction(bias + sqrt_upper(variance / (point["replicates"] * alpha)))
    predicted, tolerance = readout(values, point, public), fraction(plan["tolerance"])
    return {"point_id": point["id"], "alpha": ratio(alpha), "predicted_readout": ratio(predicted),
            "variance_bound": ratio(variance), "raw_bias_bound": ratio(raw_bias), "certified_bias_bound": ratio(bias),
            "confidence_radius": ratio(radius), "tolerance": ratio(tolerance),
            "radius_to_tolerance_upper": outward(radius / tolerance, 1),
            "adequacy_resolution_possible": radius <= tolerance}


def seal(plan, snapshot, predictions, repeated_predictions, runtime_id):
    code, binding = resolve_model(snapshot, plan["model_snapshot"])
    hash_value(runtime_id)
    ids = {p["id"] for p in plan["points"]}
    if type(predictions) is not dict or type(repeated_predictions) is not dict or set(predictions) != ids or set(repeated_predictions) != ids:
        raise ValueError("all point predictions required before sealing")
    clean = {p["id"]: _matrix(predictions[p["id"]], p["spec"], plan["public"]) for p in plan["points"]}
    repeat = {p["id"]: _matrix(repeated_predictions[p["id"]], p["spec"], plan["public"]) for p in plan["points"]}
    if digest(clean) != digest(repeat):
        raise ValueError("nondeterministic point predictor")
    registration = {"protocol": PROTOCOL, "plan": deepcopy(plan), "snapshot": deepcopy(snapshot),
                    "binding": binding, "predictor_code": code, "runtime_id": runtime_id,
                    "predictions": clean, "predictions_sha256": digest(clean),
                    "repeat_predictions_sha256": digest(repeat),
                    "design": [design(plan, p, clean[p["id"]]) for p in plan["points"]]}
    registration["seal_sha256"] = digest(registration)
    return registration


def check_seal(registration, expected_seal):
    hash_value(expected_seal)
    if (registration.get("protocol") != PROTOCOL or registration.get("seal_sha256") != expected_seal or
            digest({k: v for k, v in registration.items() if k != "seal_sha256"}) != expected_seal):
        raise ValueError("domain registration seal mismatch")
    code, binding = resolve_model(registration["snapshot"], registration["plan"]["model_snapshot"])
    if code != registration["predictor_code"] or binding != registration["binding"]:
        raise ValueError("frozen point predictor mismatch")
    predictions = registration["predictions"]
    if digest(predictions) != registration["predictions_sha256"] or digest(predictions) != registration["repeat_predictions_sha256"]:
        raise ValueError("frozen prediction table mismatch")
    expected = [design(registration["plan"], p, predictions[p["id"]]) for p in registration["plan"]["points"]]
    if expected != registration["design"]:
        raise ValueError("frozen statistical design mismatch")


def classify(mean, predicted, radius, tolerance):
    mean, predicted, radius, tolerance = map(fraction, (mean, predicted, radius, tolerance))
    if radius < 0 or tolerance <= 0:
        raise ValueError("invalid interval criterion")
    low, high = mean - radius, mean + radius
    d_low, d_high = max(Fraction(0), abs(mean-predicted)-radius), abs(mean-predicted)+radius
    status = "adequate" if d_high <= tolerance else "inadequate" if d_low > tolerance else "inconclusive"
    return {"classification": status, "mean_readout_exact": ratio(mean),
            "confidence_interval_exact": [ratio(low), ratio(high)],
            "confidence_interval": [outward(low, -1), outward(high, 1)],
            "discrepancy_interval_exact": [ratio(d_low), ratio(d_high)],
            "discrepancy_interval": [outward(d_low, -1), outward(d_high, 1)]}


def validate_observation(observation, spec, public):
    """Validate raw returned data even when its call never becomes evidence."""
    keys(observation, ("axis", "channels", "values"), "observation")
    if (type(observation["axis"]) is not list or type(observation["channels"]) is not list or
            observation["axis"] != spec[public["axis_field"]] or observation["channels"] != public["channels"]):
        raise ValueError("observation schema mismatch")
    # Equality alone would accept boolean coordinates as 0/1.
    for coordinate in observation["axis"]:
        number(coordinate)
    _matrix(observation["values"], spec, public)


def recompute(registration, observations, *, expected_seal, expected_observations_sha256):
    """Read-only numeric replay; expected anchors must come from a trusted log."""
    check_seal(registration, expected_seal)
    hash_value(expected_observations_sha256)
    if type(observations) is not list or digest(observations) != expected_observations_sha256:
        raise ValueError("observation anchor mismatch")
    plan, public = registration["plan"], registration["plan"]["public"]
    points = {p["id"]: p for p in plan["points"]}
    batches, ids, noise_keys = {p: {} for p in points}, set(), set()
    for record in observations:
        keys(record, ("id", "point_id", "replica", "spec_sha256", "noise_key", "observation"), "observation record")
        rid, pid, replica = identifier(record["id"]), record["point_id"], record["replica"]
        key = text(record["noise_key"], "noise key", 256)
        if (type(pid) is not str or pid not in points or type(replica) is not int or
                not 0 <= replica < points[pid]["replicates"] or rid in ids or key in noise_keys or replica in batches[pid]):
            raise ValueError("duplicate or invalid fresh observation")
        point = points[pid]
        if record["spec_sha256"] != digest(point["spec"]):
            raise ValueError("observation spec mismatch")
        observation = record["observation"]
        validate_observation(observation, point["spec"], public)
        batches[pid][replica] = readout(observation["values"], point, public)
        ids.add(rid)
        noise_keys.add(key)
    results = []
    for point, proposed in zip(plan["points"], registration["design"]):
        values = batches[point["id"]]
        result = {"point_id": point["id"], "u": point["u"], "planned_replicates": point["replicates"],
                  "completed_replicates": len(values), "design": deepcopy(proposed)}
        if len(values) != point["replicates"]:
            result["classification"] = "not_evaluated_incomplete"
        else:
            quantities = [values[i] for i in range(point["replicates"])]
            result.update(classify(sum(quantities, Fraction(0)) / len(quantities),
                                   unratio(proposed["predicted_readout"]), unratio(proposed["confidence_radius"]),
                                   fraction(plan["tolerance"])))
            result["replicate_readouts_exact"] = [ratio(v) for v in quantities]
        results.append(result)
    return {"protocol": PROTOCOL, "points": results,
            "complete_family": all(r["classification"] != "not_evaluated_incomplete" for r in results),
            "family_alpha": plan["family_alpha"], "coverage_object": "registered finite clean scalar readout vector, conditional on frozen model and source history",
            "partial_family_assurance": "Unconditional simultaneous soundness of issued complete-point labels at the original family alpha; no improved guarantee conditional on completion.",
            "not_refuted_is_not_adequacy": True, "boundary_identified": False,
            "continuity_certified": False, "mechanism_identified": False, "discovery_depth_certified": False}


def public_plan(plan):
    """Public scientific context, without private cutoff receipts or file paths."""
    if plan is None:
        return None
    return {"scope": plan["scope"], "model_snapshot": deepcopy(plan["model_snapshot"]),
            "domain": deepcopy(plan["domain"]), "points": deepcopy(plan["points"]),
            "tolerance": plan["tolerance"], "tolerance_rationale": plan["tolerance_rationale"],
            "family_alpha": plan["family_alpha"],
            "provenance": {key: deepcopy(plan["provenance"][key]) for key in
                           ("source_history_sha256", "source_observation_ids", "author_priors", "readout_nontriviality")},
            "scope_limits": "One fixed point predictor and finite scalar readouts; no continuous boundary, parameter coverage or mechanism standard."}
