"""Deterministic exact-identity evidence oracle.

Fourteen anonymous constants are published to twelve significant digits. Each is an
integer combination of six hidden exact bases (pi, ln 2, ln 3, sqrt 2, e, phi)
computed by pure-integer series to any requested precision, with a few carrying one
planted decimal epsilon. Twelve claims assert that value triples satisfy small integer
relations. The candidate buys extra digits under a tight budget and must return a
verdict per claim — exact (with the recovered coefficient row), false, or undecidable
at the purchasable precision — where epsilons below a value's public precision cap
make certified refusal the only correct answer.
"""

from __future__ import annotations

import math

BASE_PRECISION = 12
PRECISION_TIERS = (40, 80, 150)
PURCHASE_BUDGET = 10
COEFFICIENT_BOUND = 9
EPSILON_FLOOR_EXPONENT = 70  # any planted epsilon is zero or at least 10**-70
VERDICTS = ("exact", "false", "undecidable")

_BASE_DEVELOPMENT_SPECS = (91011, 91017, 91023, 91029, 91031, 91037)
HELDOUT_SPECS = (92007, 92013, 92019, 92023)


def _pi_scaled(power):
    """Machin: pi = 16 atan(1/5) - 4 atan(1/239), in units of 10**power."""
    def atan_inv(x):
        total, term_index = 0, 0
        while True:
            denominator = (2 * term_index + 1) * x ** (2 * term_index + 1)
            term = 10 ** power // denominator
            if term == 0 and term_index > 0:
                break
            total += -term if term_index % 2 else term
            term_index += 1
        return total
    return 16 * atan_inv(5) - 4 * atan_inv(239)


def _ln_scaled(numerator, denominator, power):
    """ln(numerator/denominator) = 2 atanh((num-den)/(num+den)), units 10**power."""
    z_num, z_den = numerator - denominator, numerator + denominator
    total, term_index = 0, 0
    while True:
        exponent = 2 * term_index + 1
        term = ((10 ** power) * z_num ** exponent
                // ((2 * term_index + 1) * z_den ** exponent))
        if term == 0 and term_index > 0:
            break
        total += term
        term_index += 1
    return 2 * total


def _sqrt_scaled(value, power):
    return math.isqrt(value * 10 ** (2 * power))


def _e_scaled(power):
    total, factorial, index = 0, 1, 0
    while True:
        term = 10 ** power // factorial
        if term == 0 and index > 0:
            break
        total += term
        index += 1
        factorial *= index
    return total


def _basis_scaled(power):
    """The six hidden exact bases in units of 10**power."""
    return {
        "pi": _pi_scaled(power),
        "ln2": _ln_scaled(2, 1, power),
        "ln3": _ln_scaled(3, 1, power),
        "sqrt2": _sqrt_scaled(2, power),
        "e": _e_scaled(power),
        "phi": (10 ** power + _sqrt_scaled(5, power)) // 2,
    }


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _rng_factory(seed):
    state = int(seed) % 2147483647 or 1

    def rng():
        nonlocal state
        state = (48271 * state) % 2147483647
        return state / 2147483647.0
    return rng


def _independent_bases(rng, count=4):
    """Four integer vectors of rank `count` over Z^6, entries in [-6, 6]."""
    while True:
        vectors = [[int(rng() * 13) - 6 for _ in range(6)] for _ in range(count)]
        if any(all(v == 0 for v in vector) for vector in vectors):
            continue
        import numpy as np
        if np.linalg.matrix_rank(np.asarray(vectors)) == count:
            return vectors


def _world(spec):
    seed = int(spec)
    rng = _rng_factory(seed)
    vectors = _independent_bases(rng, 4)

    def small():
        value = int(rng() * 17) - 8
        return value if value not in (0,) else 1

    # Five combination values q05..q09, each an exact two-term combination of the
    # bases, give five true claims with rows (-alpha, -beta, 1).
    combinations = []
    for _ in range(5):
        left, right = int(rng() * 4), int(rng() * 4)
        while right == left:
            right = int(rng() * 4)
        alpha, beta = small(), small()
        vector = [alpha * vectors[left][j] + beta * vectors[right][j]
                  for j in range(6)]
        combinations.append((left, right, alpha, beta, vector))
    # Distractor q10 enters three grossly false claims (residual far above the
    # base precision).
    distractor = _independent_bases(rng, 1)[0]
    gross_claims = []
    for index in range(3):
        left, right = int(rng() * 4), int(rng() * 4)
        while right == left:
            right = int(rng() * 4)
        a, b = small(), small()
        residual = [a * vectors[left][j] + b * vectors[right][j] + distractor[j]
                    for j in range(6)]
        if all(component == 0 for component in residual):
            continue  # never accidentally exact
        gross_claims.append((left, right, a, b))
    while len(gross_claims) < 3:
        gross_claims.append((0, 1, 2, -3))
    # Two hard-false values: exact vector cancellation with an epsilon that needs
    # purchased digits to see (kappa in [25, 54], visible at the 80-digit tier).
    hard = []
    for _ in range(2):
        left, right = int(rng() * 4), int(rng() * 4)
        while right == left:
            right = int(rng() * 4)
        a, b = small(), small()
        kappa = 25 + int(rng() * 30)
        vector = [-a * vectors[left][j] - b * vectors[right][j] for j in range(6)]
        hard.append((left, right, a, b, kappa, vector))
    # Two capped values: the epsilon sits below the value's purchasable precision
    # cap, so the residual can never be certified — refusal is the only honest
    # verdict. Caps 40 and 60 both sit below the published epsilon floor exponent.
    capped = []
    for cap, kappa_hi in ((40, 69), (60, 69)):
        left, right = int(rng() * 4), int(rng() * 4)
        while right == left:
            right = int(rng() * 4)
        a, b = small(), small()
        kappa = cap + 5 + int(rng() * max(kappa_hi - cap - 4, 1))
        vector = [-a * vectors[left][j] - b * vectors[right][j] for j in range(6)]
        capped.append((left, right, a, b, kappa, vector, cap))

    values = []
    for index, vector in enumerate(vectors):
        values.append({"name": "q%02d" % (index + 1), "vector": vector,
                       "epsilon": None, "cap": 150})
    for index, (_left, _right, _alpha, _beta, vector) in enumerate(combinations):
        values.append({"name": "q%02d" % (5 + index), "vector": vector,
                       "epsilon": None, "cap": 150})
    values.append({"name": "q10", "vector": distractor, "epsilon": None, "cap": 150})
    for index, (left, right, a, b, kappa, vector) in enumerate(hard):
        values.append({"name": "q%02d" % (11 + index), "vector": vector,
                       "epsilon": (1 if rng() < 0.5 else -1, kappa), "cap": 150})
    for index, (left, right, a, b, kappa, vector, cap) in enumerate(capped):
        values.append({"name": "q%02d" % (13 + index), "vector": vector,
                       "epsilon": (1 if rng() < 0.5 else -1, kappa), "cap": cap})

    claims = []
    for index, (left, right, alpha, beta, _vector) in enumerate(combinations):
        claims.append({"id": "C%02d" % (index + 1),
                       "values": ["q%02d" % (left + 1), "q%02d" % (right + 1),
                                  "q%02d" % (5 + index)],
                       "coefficients": [-alpha, -beta, 1], "kind": "exact"})
    for index, (left, right, a, b) in enumerate(gross_claims[:3]):
        claims.append({"id": "C%02d" % (6 + index),
                       "values": ["q%02d" % (left + 1), "q%02d" % (right + 1), "q10"],
                       "coefficients": [a, b, 1], "kind": "gross_false"})
    for index, (left, right, a, b, _kappa, _vector) in enumerate(hard):
        claims.append({"id": "C%02d" % (9 + index),
                       "values": ["q%02d" % (left + 1), "q%02d" % (right + 1),
                                  "q%02d" % (11 + index)],
                       "coefficients": [a, b, 1], "kind": "hard_false"})
    for index, (left, right, a, b, _kappa, _vector, _cap) in enumerate(capped):
        claims.append({"id": "C%02d" % (11 + index),
                       "values": ["q%02d" % (left + 1), "q%02d" % (right + 1),
                                  "q%02d" % (13 + index)],
                       "coefficients": [a, b, 1], "kind": "undecidable"})
    return {"seed": seed, "values": values, "claims": claims}


def _digits(world, name, precision):
    for value in world["values"]:
        if value["name"] != name:
            continue
        precision = min(int(precision), value["cap"])
        basis = _basis_scaled(precision)
        scaled = sum(coefficient * basis[key]
                     for coefficient, key in zip(value["vector"],
                                                 ("pi", "ln2", "ln3", "sqrt2", "e", "phi")))
        if value["epsilon"] is not None:
            sign, kappa = value["epsilon"]
            if precision > kappa:
                scaled += sign * 10 ** (precision - kappa)
        negative = scaled < 0
        scaled = abs(int(scaled))
        text = str(scaled).rjust(precision + 1, "0")
        sign = "-" if negative else ""
        return "%s%s.%s" % (sign, text[:-precision], text[-precision:])
    raise KeyError(name)


def problem_statement(world):
    values = [{"name": value["name"],
               "digits": _digits(world, value["name"], BASE_PRECISION),
               "precision_cap": value["cap"]} for value in world["values"]]
    return {
        "values": values,
        "base_precision": BASE_PRECISION,
        "precision_tiers": list(PRECISION_TIERS),
        "purchase_budget": PURCHASE_BUDGET,
        "claims": [{"id": claim["id"], "values": claim["values"],
                    "coefficient_bound": COEFFICIENT_BOUND}
                   for claim in world["claims"]],
        "epsilon_floor": "any deviation in a value is either zero or at least 1e-%d in magnitude"
                         % EPSILON_FLOOR_EXPONENT,
        "claim_note": (
            "each claim asserts that its three values satisfy a*x + b*y + c*z = 0 "
            "with the common factor removed and |a|,|b|,|c| within the bound; exact "
            "verdicts carry the recovered row; a certified-false verdict on an "
            "exactly true relation scores below abstention"
        ),
    }


class _Library:
    """Charged interface: extra digits at the published tiers."""

    def __init__(self, world):
        self.world = world
        self.used = 0
        self.violated = False

    def purchase(self, name, precision):
        try:
            if precision not in PRECISION_TIERS:
                self.violated = True
                raise ValueError("precision must be one of the published tiers")
            if self.used + 1 > PURCHASE_BUDGET:
                self.violated = True
                raise RuntimeError("purchase budget exceeded")
            self.used += 1
            return {"name": name, "precision": int(precision),
                    "digits": _digits(self.world, name, precision), "budget_cost": 1}
        except Exception:
            self.violated = True
            raise


def _validate(submission, world):
    if not isinstance(submission, dict):
        raise ValueError("submission must be a mapping")
    verdicts = submission.get("verdicts")
    if not isinstance(verdicts, dict) or set(verdicts) != {
            claim["id"] for claim in world["claims"]}:
        raise ValueError("verdicts must cover every claim id exactly")
    for verdict in verdicts.values():
        if verdict not in VERDICTS:
            raise ValueError("verdict must be exact, false or undecidable")
    coefficients = submission.get("coefficients")
    if not isinstance(coefficients, dict):
        raise ValueError("coefficients must be a mapping")
    rows = {}
    for claim in world["claims"]:
        row = coefficients.get(claim["id"])
        if verdicts[claim["id"]] == "exact":
            if row is None:
                raise ValueError("exact verdicts require a coefficient row")
            array = [int(value) for value in row]
            if len(array) != 3 or any(value == 0 for value in array):
                raise ValueError("coefficient rows hold three nonzero integers")
            if any(abs(value) > COEFFICIENT_BOUND for value in array):
                raise ValueError("coefficient rows must respect the public bound")
            rows[claim["id"]] = array
        elif row is not None:
            raise ValueError("only exact verdicts carry a coefficient row")
    confidence = float(submission.get("confidence"))
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0,1]")
    return verdicts, rows, confidence


def _normalized_row(row):
    scale = 0
    for value in row:
        scale = math.gcd(scale, abs(value))
    scale = scale or 1
    row = [value // scale for value in row]
    if row[0] < 0 or (row[0] == 0 and row[1] < 0):
        row = [-value for value in row]
    return row


def _score_claim(entry, verdict, row):
    kind = entry["kind"]
    if kind == "exact":
        if verdict == "exact":
            return 1.0 if _normalized_row(row) == _normalized_row(
                entry["coefficients"]) else 0.5
        if verdict == "false":
            return -0.5  # a certified rejection of a true relation is worse than abstention
        return 0.0
    if kind in ("gross_false", "hard_false"):
        return 1.0 if verdict == "false" else 0.0
    return 1.0 if verdict == "undecidable" else 0.0


def _empty(split, index):
    return {"split": split, "world_index": index, "valid": False, "raw": 0.0,
            "normalized": 0.0, "exact_hits": 0, "false_hits": 0,
            "refusal_hits": 0, "false_discovery": False,
            "attempt_count": 0, "claim_count": 0, "budget_used": 0,
            "passive_raw": 0.0}


def _evaluate_world(candidate, spec, split, index):
    row = _empty(split, index)
    world = _world(spec)
    library = _Library(world)
    passive = _mean([_score_claim(entry, "undecidable", None)
                     for entry in world["claims"]])
    row["passive_raw"] = passive
    try:
        submission = candidate(problem_statement(world), library.purchase,
                               PURCHASE_BUDGET)
        verdicts, coefficient_rows, _confidence = _validate(submission, world)
        if library.violated:
            raise ValueError("library contract violated")
        scores, false_discoveries = [], 0
        for entry in world["claims"]:
            verdict = verdicts[entry["id"]]
            scores.append(_score_claim(entry, verdict,
                                       coefficient_rows.get(entry["id"])))
            if entry["kind"] != "exact" and verdict == "exact":
                false_discoveries += 1
        raw = _mean(scores)
        normalized = (raw - passive) / (1.0 - passive) if passive < 1.0 else 0.0
        row.update({
            "valid": True, "raw": raw, "normalized": float(max(0.0, normalized)),
            "exact_hits": sum(1 for entry in world["claims"]
                              if entry["kind"] == "exact"
                              and verdicts[entry["id"]] == "exact"),
            "false_hits": sum(1 for entry in world["claims"]
                              if entry["kind"] in ("gross_false", "hard_false")
                              and verdicts[entry["id"]] == "false"),
            "refusal_hits": sum(1 for entry in world["claims"]
                                if entry["kind"] == "undecidable"
                                and verdicts[entry["id"]] == "undecidable"),
            "false_discovery": false_discoveries > 0,
            "attempt_count": sum(1 for entry in world["claims"]
                                 if verdicts[entry["id"]] != "undecidable"),
            "claim_count": len(world["claims"]),
            "budget_used": library.used,
        })
    except Exception:
        pass
    return row


def _summary(rows):
    raw = _mean([r["raw"] for r in rows])
    passive = _mean([r.get("passive_raw", 0.0) for r in rows])
    normalized = (raw - passive) / (1.0 - passive) if passive < 1.0 else 0.0
    claims = sum(r["claim_count"] for r in rows if r["valid"])
    return {
        "raw": raw, "passive": passive,
        "normalized": float(max(0.0, normalized)),
        "valid_count": sum(r["valid"] for r in rows),
        "false_discovery_count": sum(r["false_discovery"] for r in rows),
        "attempt_count": sum(r["attempt_count"] for r in rows if r["valid"]),
        "claim_count": claims,
    }


def evaluate(audit_identity_claims):
    development = [_evaluate_world(audit_identity_claims, spec, "development", i)
                   for i, spec in enumerate(_BASE_DEVELOPMENT_SPECS)]
    heldout = [_evaluate_world(audit_identity_claims, spec, "heldout", i)
               for i, spec in enumerate(HELDOUT_SPECS)]
    dev, hold = _summary(development), _summary(heldout)
    dev_valid = dev["valid_count"] == len(development)
    hold_valid = hold["valid_count"] == len(heldout)
    return {
        "combined_score": dev["normalized"] if dev_valid else 0.0,
        "valid": 1.0 if dev_valid else 0.0,
        "feasibility_rate": dev["valid_count"] / len(development),
        "mechanism_score": dev["raw"],
        "passive_mechanism_score": dev["passive"],
        "development_false_discovery_rate": (
            dev["false_discovery_count"] / dev["claim_count"]
            if dev["claim_count"] else 0.0),
        "development_discovery_coverage": (
            dev["attempt_count"] / dev["claim_count"] if dev["claim_count"] else 0.0),
        "false_discovery_count": dev["false_discovery_count"],
        "claim_count": dev["claim_count"],
        "robustness_score": hold["normalized"] if hold_valid else 0.0,
        "heldout_feasibility_rate": hold["valid_count"] / len(heldout),
        "heldout_false_discovery_rate": (
            hold["false_discovery_count"] / hold["claim_count"]
            if hold["claim_count"] else 0.0),
        "per_world": development + heldout,
    }
