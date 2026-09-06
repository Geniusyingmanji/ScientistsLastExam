"""DC power-flow topology error identification on a frozen five-bus catalog."""
from __future__ import annotations

import math

import numpy as np

MEASURE_BUDGET = 8
N_BUS = 5
SLACK = 0
SUPPORTED_PREFIX = "graph_"

# graph_3 plus the (2,4) chord is electrically identical on the frozen
# injections, because those injections were chosen so buses 2 and 4 are
# already equipotential. Twin worlds use graph_3's edges; both catalog names fit.
CATALOG = {
    "graph_0": ((0, 1), (1, 2), (2, 3), (3, 4)),
    "graph_1": ((0, 1), (0, 2), (0, 3), (0, 4)),
    "graph_2": ((0, 1), (1, 2), (2, 3), (3, 4), (4, 0)),
    "graph_3": ((0, 1), (1, 2), (2, 3), (3, 4), (1, 3)),
    "graph_4": ((0, 1), (1, 2), (2, 3), (3, 4), (1, 3), (2, 4)),
    "twin": ((0, 1), (1, 2), (2, 3), (3, 4), (1, 3)),
}

INJECTIONS = (
    np.array([-0.32, 1.36, -0.40, -0.72, 0.08]),
    np.array([0.20, -1.08, 0.92, -0.36, 0.32]),
)

PUBLIC_NAMES = ["graph_0", "graph_1", "graph_2", "graph_3", "graph_4"]

PUBLIC_PROBLEM = {
    "bus_count": N_BUS,
    "slack_bus": SLACK,
    "injection_patterns": [row.tolist() for row in INJECTIONS],
    "catalog_names": list(PUBLIC_NAMES),
    "catalog_edges": {name: [list(edge) for edge in CATALOG[name]] for name in PUBLIC_NAMES},
    "measure_budget_calls": MEASURE_BUDGET,
    "measurement_model": (
        "measure(pattern_index, bus_index) returns the DC voltage angle in radians "
        "at that bus for the named injection, with bus 0 the slack"
    ),
    "abstain_when": (
        "two catalog graphs produce the same angles on both frozen injections"
    ),
}


def public_problem():
    return {
        "bus_count": N_BUS,
        "slack_bus": SLACK,
        "injection_patterns": [row.tolist() for row in INJECTIONS],
        "catalog_names": list(PUBLIC_NAMES),
        "catalog_edges": {name: [list(edge) for edge in CATALOG[name]] for name in PUBLIC_NAMES},
        "measure_budget_calls": MEASURE_BUDGET,
        "measurement_model": PUBLIC_PROBLEM["measurement_model"],
        "abstain_when": PUBLIC_PROBLEM["abstain_when"],
    }


def _laplacian(edges):
    admittance = np.zeros((N_BUS, N_BUS), dtype=float)
    for i, j in edges:
        b = 4.0
        admittance[i, j] -= b
        admittance[j, i] -= b
        admittance[i, i] += b
        admittance[j, j] += b
    return admittance


def _angles(edges, injection):
    lap = _laplacian(edges)
    reduced = lap[1:, 1:]
    theta = np.zeros(N_BUS, dtype=float)
    theta[1:] = np.linalg.solve(reduced, injection[1:])
    return theta


class _Lab:
    def __init__(self, spec):
        self.spec = spec
        self.used = 0
        self.violated = False
        self.edges = CATALOG[spec["kind"]]
        rng = np.random.default_rng((int(spec["seed"]), 9))
        self.noise = 0.004 * rng.normal(size=(len(INJECTIONS), N_BUS))

    def measure(self, pattern_index, bus_index):
        pattern = int(pattern_index)
        bus = int(bus_index)
        if pattern not in (0, 1) or bus not in range(N_BUS):
            raise ValueError("pattern_index must be 0 or 1 and bus_index in [0, 4]")
        if self.used >= MEASURE_BUDGET:
            self.violated = True
            raise RuntimeError("measure budget exhausted")
        self.used += 1
        theta = _angles(self.edges, INJECTIONS[pattern])
        return float(theta[bus] + self.noise[pattern, bus])


def _validate(submission):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    abstain = submission.get("abstain", False)
    if not isinstance(abstain, bool):
        raise ValueError("abstain must be a boolean")
    confidence = float(submission.get("confidence", 0.0))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0, 1]")
    if abstain:
        return True, None, confidence
    name = submission.get("catalog_name")
    if name not in PUBLIC_PROBLEM["catalog_names"]:
        raise ValueError("catalog_name must be one of catalog_names")
    return False, name, confidence


def _mechanism(spec, abstain, name):
    if spec["kind"] == "twin":
        return (1.0 if abstain else 0.0), bool(abstain), (not abstain)
    if abstain:
        return 0.0, False, False
    return (1.0 if name == spec["kind"] else 0.0), False, False


DEVELOPMENT_WORLDS = (
    {"kind": "graph_0", "seed": 51001},
    {"kind": "graph_1", "seed": 51002},
    {"kind": "graph_2", "seed": 51003},
    {"kind": "graph_0", "seed": 51004},
    {"kind": "twin", "seed": 52001},
    {"kind": "twin", "seed": 52002},
    {"kind": "twin", "seed": 52003},
)
HELDOUT_WORLDS = (
    {"kind": "graph_0", "seed": 61001},
    {"kind": "graph_1", "seed": 61002},
    {"kind": "graph_2", "seed": 61003},
    {"kind": "twin", "seed": 62001},
    {"kind": "twin", "seed": 62002},
)


def _evaluate_world(recover, spec, split, index):
    lab = _Lab(spec)
    base = {"split": split, "world_index": int(index), "kind": spec["kind"], "measure_calls": 0}
    try:
        submission = recover(public_problem(), lab.measure)
        abstain, name, confidence = _validate(submission)
        if lab.violated:
            raise RuntimeError("measure budget exceeded")
        mech, refused, false = _mechanism(spec, abstain, name)
        return {
            **base,
            "mechanism_score": round(float(mech), 6),
            "correct_refusal": refused,
            "false_discovery": false,
            "valid": True,
            "abstained": bool(abstain),
            "confidence": round(confidence, 6),
            "measure_calls": lab.used,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            **base,
            "mechanism_score": 0.0,
            "correct_refusal": False,
            "false_discovery": False,
            "valid": False,
            "reason": "%s: %s" % (type(exc).__name__, exc),
            "abstained": True,
            "confidence": 0.0,
            "measure_calls": lab.used,
        }


def _split_summary(records):
    supported = [row for row in records if row["kind"] != "twin"]
    unsupported = [row for row in records if row["kind"] == "twin"]
    raw = float(np.mean([row["mechanism_score"] for row in records]))
    always_abstain = len(unsupported) / len(records)
    normalized = float(np.clip((raw - always_abstain) / (1.0 - always_abstain), 0.0, 1.0))
    return {
        "normalized_mechanism": normalized,
        "signal_recovery_rate": float(np.mean([row["mechanism_score"] for row in supported])),
        "false_discovery_rate": float(np.mean([row["false_discovery"] for row in unsupported])),
        "correct_refusal_rate": float(np.mean([row["correct_refusal"] for row in unsupported])),
        "discovery_coverage": float(np.mean([not row["abstained"] for row in supported])),
        "valid_count": sum(bool(row["valid"]) for row in records),
        "world_count": len(records),
    }


def _run(recover, worlds, split, reset_before_first=False):
    rows = []
    for index, spec in enumerate(worlds):
        if (index or reset_before_first) and hasattr(recover, "reset_session"):
            recover.reset_session()
        rows.append(_evaluate_world(recover, spec, split, index))
    return rows


def evaluate(recover_topology):
    development = _run(recover_topology, DEVELOPMENT_WORLDS, "development")
    heldout = _run(recover_topology, HELDOUT_WORLDS, "heldout", reset_before_first=True)
    dev = _split_summary(development)
    held = _split_summary(heldout)
    return {
        "combined_score": dev["normalized_mechanism"],
        "valid": 1.0 if dev["valid_count"] > 0 else 0.0,
        "feasibility_rate": dev["valid_count"] / dev["world_count"],
        "raw_score": dev["normalized_mechanism"],
        "development_mechanism_score": dev["normalized_mechanism"],
        "development_signal_recovery_rate": dev["signal_recovery_rate"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "development_correct_refusal_rate": dev["correct_refusal_rate"],
        "development_discovery_coverage": dev["discovery_coverage"],
        "heldout_mechanism_score": held["normalized_mechanism"],
        "heldout_signal_recovery_rate": held["signal_recovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "heldout_correct_refusal_rate": held["correct_refusal_rate"],
        "heldout_discovery_coverage": held["discovery_coverage"],
        "per_instance": development + heldout,
    }
