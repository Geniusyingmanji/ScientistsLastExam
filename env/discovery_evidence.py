"""Manual evidence annotations, with mechanical checks only. Never execute evidence."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re

from env.evidence_packet import PROTOCOL as PACKET_PROTOCOL, sha256, strict_json


PROTOCOL = "sle-discovery-evidence-annotation-0.1"
DIMENSIONS = ("quantitative_model", "prospective_test", "meaningful_rival",
              "changed_regime_transfer", "empirical_boundary", "uncertainty_and_negative_results")
ASSESSMENTS = ("supported", "partial", "not_demonstrated", "unassessable")
ATTRIBUTIONS = ("candidate_explicit", "reviewer_inferred", "public_supplied", "unknown")


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, keys):
    _need(type(value) is dict and set(value) == set(keys), "unexpected or missing object fields")


def _text(value):
    _need(type(value) is str, "expected string")


def _packet(raw):
    _need(type(raw) is bytes, "packet must be original bytes")
    packet = strict_json(raw)
    _need(type(packet) is dict and packet.get("protocol") == PACKET_PROTOCOL, "unsupported packet")
    for key in ("rounds", "observations", "gaps"):
        _need(type(packet.get(key)) is list, "missing packet array: " + key)
    for row in packet["rounds"]:
        _need(type(row) is dict, "invalid round object")
        _need(row.get("candidate_response") is None or type(row["candidate_response"]) is dict, "invalid candidate response")
        _need("analysis" not in row or type(row["analysis"]) is dict, "invalid analysis object")
    _need(all(type(o) is dict for o in packet["observations"]), "invalid observation object")
    _need(all(type(g) is str for g in packet["gaps"]), "invalid packet gaps")
    return packet


def create_annotation(packet_bytes, reviewer_id):
    """Create an unassessed form, not evidence or a scientific verdict."""
    _packet(packet_bytes)
    _text(reviewer_id)
    result = {"protocol": PROTOCOL, "packet_sha256": sha256(packet_bytes), "reviewer_id": reviewer_id}
    for key in ("question", "scope", "prior_knowledge"):
        result[key] = {"text": "", "attribution": "unknown", "citations": []}
    result["dimensions"] = {key: {"assessment": "unassessable", "attribution": "unknown",
        "rationale": "", "citations": [], "prospective_links": [], "gaps": ["manual_review_required"]}
        for key in DIMENSIONS}
    return result


def _pointer(packet, pointer):
    _need(type(pointer) is str and pointer.startswith("/"), "expected JSON pointer")
    tokens = pointer[1:].split("/")
    _need(all(re.search(r"~(?![01])", t) is None for t in tokens), "invalid pointer escape")
    tokens = [t.replace("~1", "/").replace("~0", "~") for t in tokens]
    value = packet
    for token in tokens:
        if type(value) is list:
            _need(re.fullmatch(r"0|[1-9][0-9]*", token) is not None, "invalid array index")
            value = value[int(token)]
        else:
            _need(type(value) is dict, "pointer traverses a scalar")
            value = value[token]
    return tokens, value


def _citation(packet, cite):
    _keys(cite, ("path", "quote", "round", "observation_id"))
    _need(type(cite["quote"]) is str and bool(cite["quote"]), "empty or invalid exact quote")
    _need(cite["round"] is None or type(cite["round"]) is int, "invalid citation round")
    tokens, value = _pointer(packet, cite["path"])
    exact = cite["quote"] in value if type(value) is str else cite["quote"] == json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    _need(exact, "quote not present at pointer")
    kind, number, oid = "unknown", None, None
    if tokens[0] == "rounds" and len(tokens) >= 3:
        owner = packet["rounds"][int(tokens[1])]
        number = owner["round"]
        if tokens[2] == "candidate_response":
            kind = "candidate_request"
        elif tokens[2] == "research_note":
            if value == (owner.get("candidate_response") or {}).get("note"):
                kind = "candidate_request"
        elif tokens[2] == "analysis" and len(tokens) >= 4:
            if tokens[3] in ("result", "stdout") and owner["analysis"].get("ok") is True:
                kind = "candidate_analysis_result"
            else:
                kind = "tool_error"
        else:
            raise ValueError("not an allowed round evidence path")
    elif tokens[0] == "observations" and len(tokens) >= 3:
        owner = packet["observations"][int(tokens[1])]
        kind, number, oid = "observation", owner.get("round"), owner["id"]
        _need(sum(o.get("id") == oid for o in packet["observations"]) == 1, "ambiguous observation ID")
    elif tokens[0] == "public_contexts" and len(tokens) >= 3 and tokens[2] in ("system", "problem"):
        kind = "public_context"
    elif tokens[0] == "final_candidate" and len(tokens) >= 2 and tokens[1] in ("submission", "finish"):
        kind, number = "candidate_final", packet["final_candidate"].get("round")
    elif tokens[0] not in ("gaps", "candidate_versions"):
        raise ValueError("not an allowed evidence path")
    _need(cite["round"] == number and cite["observation_id"] == oid, "citation owner mismatch")
    return kind, number


def _round(packet, number):
    rows = [r for r in packet["rounds"] if r.get("round") == number]
    if len(rows) != 1 or rows[0].get("history_binding") != "explicit_unique_round_field":
        return None
    if "nonmonotonic_or_duplicate_rounds" in packet["gaps"]:
        return None
    return rows[0]


def _order(packet, source, target_id):
    matches = [o for o in packet["observations"] if o.get("id") == target_id]
    _need(len(matches) == 1, "missing or ambiguous target observation")
    target = matches[0]
    kind, start = source
    _need(kind in ("candidate_request", "candidate_analysis_result"), "prospective source is not candidate prediction material")
    end = target.get("round")
    source_row, target_row = _round(packet, start), _round(packet, end)
    if (type(start) is not int or type(end) is not int or not source_row or not target_row
            or target.get("binding") != "explicit_history_observation"
            or target_id not in target_row.get("observation_ids", [])
            or source_row.get("response_state") != "parsed"):
        return "unknown"
    if start < end:
        return "before_recorded"
    same_request = kind == "candidate_request" and bool(
        {"experiments", "preregister"} & set(source_row.get("candidate_response") or {}))
    return "before_recorded" if start == end and same_request else "not_before_recorded"


def validate_annotation(packet_bytes, annotation):
    """Check anchors/structure/order, never the truth of manual assessments."""
    report = {"mechanically_consistent": False, "errors": [], "gaps": [], "timing": [],
              "semantic_validation": "not_performed", "external_chronology": "unverified",
              "packet_sha256": sha256(packet_bytes) if type(packet_bytes) is bytes else None}
    try:
        packet = _packet(packet_bytes)
        report["gaps"] = deepcopy(packet["gaps"])
        report["gaps"].append("external_chronology_not_authenticated")
        # Apply strict JSON rules even when called with a Python object.
        annotation = strict_json(json.dumps(annotation, allow_nan=False))
        _keys(annotation, ("protocol", "packet_sha256", "reviewer_id", "question", "scope", "prior_knowledge", "dimensions"))
        _need(annotation["protocol"] == PROTOCOL, "unsupported annotation protocol")
        _need(annotation["packet_sha256"] == sha256(packet_bytes), "packet hash mismatch")
        _text(annotation["reviewer_id"])
        _keys(annotation["dimensions"], DIMENSIONS)
        blocks = [(k, annotation[k], False) for k in ("question", "scope", "prior_knowledge")]
        blocks += [(k, annotation["dimensions"][k], True) for k in DIMENSIONS]
        for name, block, dimension in blocks:
            _keys(block, ("assessment", "attribution", "rationale", "citations", "prospective_links", "gaps")
                  if dimension else ("text", "attribution", "citations"))
            _text(block["rationale" if dimension else "text"])
            _need(block["attribution"] in ATTRIBUTIONS, "invalid attribution")
            _need(type(block["citations"]) is list, "citations must be an array")
            sources = [_citation(packet, c) for c in block["citations"]]
            kinds = [s[0] for s in sources]
            if block["attribution"] == "candidate_explicit":
                _need(bool(sources) and all(k.startswith("candidate_") for k in kinds), "candidate attribution/source mismatch")
            if block["attribution"] == "public_supplied":
                _need(bool(sources) and all(k == "public_context" for k in kinds), "public attribution/source mismatch")
            if not dimension:
                continue
            _need(block["assessment"] in ASSESSMENTS, "invalid manual assessment")
            _need(type(block["gaps"]) is list and all(type(g) is str for g in block["gaps"]), "invalid manual gaps")
            if block["assessment"] in ("supported", "partial"):
                _need(bool(sources), "positive manual assessment needs citations")
                if name == "empirical_boundary":
                    _need("tool_error" not in kinds, "tool error is not empirical-boundary evidence")
            _need(type(block["prospective_links"]) is list, "prospective_links must be an array")
            for index, link in enumerate(block["prospective_links"]):
                _keys(link, ("citation_index", "target_observation_id", "claimed_order"))
                ci = link["citation_index"]
                _need(type(ci) is int and 0 <= ci < len(sources), "invalid citation_index")
                _text(link["target_observation_id"])
                _need(link["claimed_order"] in ("before", "unknown"), "invalid order claim")
                order = _order(packet, sources[ci], link["target_observation_id"])
                report["timing"].append({"dimension": name, "link_index": index, "order": order})
                if order == "unknown":
                    report["gaps"].append(name + ":unresolved_order:" + str(index))
                _need(not (order == "not_before_recorded" and link["claimed_order"] == "before"), "prospective order contradiction")
        report["mechanically_consistent"] = True
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, UnicodeError, RecursionError) as exc:
        report["errors"].append(str(exc))
    return report


def compare_annotations(packet_bytes, left, right):
    """Read-only field differences for one packet; no winner, pooling or grades."""
    checks = []
    for annotation in (left, right):
        check = validate_annotation(packet_bytes, annotation)
        _need(check["mechanically_consistent"], "invalid comparison input: " + str(check["errors"]))
        checks.append(check)
    differences = []
    def walk(a, b, path):
        if type(a) is dict and type(b) is dict and set(a) == set(b):
            for key in sorted(a):
                walk(a[key], b[key], path + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif type(a) is list and type(b) is list and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + "/" + str(i))
        elif type(a) is not type(b) or a != b:
            differences.append({"path": path, "left": deepcopy(a), "right": deepcopy(b)})
    walk(left, right, "")
    return {"packet_sha256": sha256(packet_bytes), "differences": differences,
            "semantic_adjudication": "not_performed", "external_chronology": "unverified",
            "left_validation": checks[0], "right_validation": checks[1]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("template", "validate", "compare"))
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reviewer-id", default="anonymous-reviewer")
    parser.add_argument("--annotation", type=Path)
    parser.add_argument("--left", type=Path)
    parser.add_argument("--right", type=Path)
    args = parser.parse_args(argv)
    paths = [args.packet]
    if args.command == "validate":
        _need(args.annotation is not None, "validate needs --annotation")
        paths.append(args.annotation)
    if args.command == "compare":
        _need(args.left is not None and args.right is not None, "compare needs --left and --right")
        paths.extend((args.left, args.right))
    _need(all(p.resolve() != args.output.resolve() for p in paths), "output cannot replace input")
    originals = [p.read_bytes() for p in paths]
    if args.command == "template":
        result = create_annotation(originals[0], args.reviewer_id)
    elif args.command == "validate":
        result = validate_annotation(originals[0], strict_json(originals[1]))
    else:
        result = compare_annotations(originals[0], strict_json(originals[1]), strict_json(originals[2]))
    _need(all(p.read_bytes() == b for p, b in zip(paths, originals)), "input changed during read")
    raw = (json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    fd = os.open(str(args.output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
    _need(all(p.read_bytes() == b for p, b in zip(paths, originals)), "input changed during write; output is unverified")
    print(json.dumps({"input_sha256": {str(p): sha256(b) for p, b in zip(paths, originals)},
                      "input_hashes_unchanged": True, "output_sha256": sha256(raw)}))
    return 1 if args.command == "validate" and result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
