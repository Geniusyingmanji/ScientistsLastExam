"""Truth-blind reference witness: base-precision row fits plus budgeted certification.

Uses only the published digits and the charged library. Claims are first screened at
base precision (gross failures are rejected outright); near-zero claims get a fitted
coefficient row. Values whose public cap sits below the epsilon-floor exponent can
never certify a near-zero residual, so their claims are refused without spending.
The purchase budget then covers, by claim coverage, the values of near-zero claims at
the 80-digit tier; a claim whose values are all covered is certified exact or false by
its residual there. Uncovered near-zero claims are answered with the fitted row — the
witness's documented gamble. It deliberately lacks 150-digit escalation, adaptive
replanning after each purchase, and any uncertainty weighting over the gamble.
"""

from __future__ import annotations

from decimal import Decimal, getcontext

# Purchased digit strings far exceed the default Decimal context; every certification
# computation must carry the full purchased precision or residuals are silently rounded.
getcontext().prec = 400

CERTIFY_TIER = 80


def _parse(digits):
    return Decimal(digits)


def _fit_row(digits_map, names, bound):
    best_row, best_residual = None, None
    for a in range(-bound, bound + 1):
        for b in range(-bound, bound + 1):
            if a == 0 and b == 0:
                continue
            for c in (-1, 1):
                total = Decimal(0)
                for name, coefficient in zip(names, (a, b, c)):
                    total += coefficient * digits_map[name]
                residual = abs(total)
                if best_residual is None or residual < best_residual:
                    best_row, best_residual = (a, b, c), residual
    return best_row, best_residual


def audit_identity_claims(problem, purchase, budget_units):
    base = {row["name"]: _parse(row["digits"]) for row in problem["values"]}
    caps = {row["name"]: row["precision_cap"] for row in problem["values"]}
    bound = problem["claims"][0]["coefficient_bound"]
    floor_exp = 70  # matches the published epsilon floor exponent

    rows, residuals = {}, {}
    for claim in problem["claims"]:
        names = claim["values"]
        row, residual = _fit_row(base, names, bound)
        rows[claim["id"]] = row
        scale = max(abs(base[name]) for name in names)
        residuals[claim["id"]] = residual / scale

    verdicts = {}
    pending = []
    for claim in problem["claims"]:
        if residuals[claim["id"]] > Decimal("1e-6"):
            verdicts[claim["id"]] = "false"  # gross failure at base precision
        elif min(caps[name] for name in claim["values"]) < floor_exp + 2:
            # One value's cap already sits below the epsilon-floor exponent, so no
            # purchasable precision can separate a zero residual from an epsilon:
            # certified refusal is the honest verdict and costs nothing.
            verdicts[claim["id"]] = "undecidable"
        else:
            pending.append(claim)

    purchased = {}

    def digits_at(name, tier):
        if (name, tier) not in purchased:
            purchased[(name, tier)] = _parse(purchase(name, tier)["digits"])
        return purchased[(name, tier)]

    budget = int(budget_units)
    while budget > 0:
        # Complete the claim that needs the fewest further values, then the next.
        def missing(claim):
            return [name for name in claim["values"]
                    if (name, CERTIFY_TIER) not in purchased]
        open_claims = [claim for claim in pending
                       if claim["id"] not in verdicts and missing(claim)]
        if not open_claims:
            break
        target = min(open_claims, key=lambda claim: (len(missing(claim)), claim["id"]))
        for name in missing(target):
            if budget <= 0:
                break
            if caps[name] < CERTIFY_TIER:
                continue  # cannot be certified; completion fails below
            digits_at(name, CERTIFY_TIER)
            budget -= 1
        if not missing(target):
            names = target["values"]
            total = Decimal(0)
            for name, coefficient in zip(names, rows[target["id"]]):
                total += coefficient * purchased[(name, CERTIFY_TIER)]
            scale = max(abs(purchased[(name, CERTIFY_TIER)]) for name in names)
            if total == 0:
                verdicts[target["id"]] = "exact"
            elif abs(total) / scale > Decimal("1e-%d" % (CERTIFY_TIER - 4)):
                verdicts[target["id"]] = "false"
            else:
                verdicts[target["id"]] = "exact"  # residual at the tier's noise floor
        else:
            # Budget ran out mid-claim; stop buying and refuse the rest honestly.
            break

    tier_digits = {name: value for (name, tier), value in purchased.items()
                   if tier == CERTIFY_TIER}
    for claim in pending:
        if claim["id"] in verdicts:
            continue
        names = claim["values"]
        if all(name in tier_digits for name in names):
            total = Decimal(0)
            for name, coefficient in zip(names, rows[claim["id"]]):
                total += coefficient * tier_digits[name]
            scale = max(abs(tier_digits[name]) for name in names)
            if total == 0:
                verdicts[claim["id"]] = "exact"
            elif abs(total) / scale > Decimal("1e-%d" % (CERTIFY_TIER - 4)):
                verdicts[claim["id"]] = "false"
            else:
                verdicts[claim["id"]] = "exact"
        else:
            # Uncovered near-zero claim: the honest refusal, no gamble.
            verdicts[claim["id"]] = "undecidable"

    coefficients = {claim["id"]: list(rows[claim["id"]])
                    for claim in problem["claims"]
                    if verdicts[claim["id"]] == "exact"}
    return {"verdicts": verdicts, "coefficients": coefficients, "confidence": 0.7}
