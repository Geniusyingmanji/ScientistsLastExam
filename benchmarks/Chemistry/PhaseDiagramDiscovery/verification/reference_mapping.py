"""A truth-blind reference for PhaseDiagramDiscovery.

It uses only the public problem and the budgeted synthesizer, and never reads the hidden world.

    anchor      the terminal compositions are single-phase by construction of a binary system, so
                one synthesis near each end anchors the two terminal signatures.
    check       three replicates at mid-composition, before anything else. An equilibrium sample
                reproduces its strong peaks call after call; a kinetically trapped one returns a
                different mixture and different transient peaks each time. If the replicates
                disagree, nothing downstream is worth buying, and the honest answer is to decline.
    scan        nine points across the interior. A point whose strong peaks are all explained by
                the two terminal signatures is terminal or two-phase; strong residual peaks that
                repeat across neighbouring points are an intermediate compound. Weak unexplained
                peaks are ignored: the impurity never exceeds the detection floor by much, and
                believing every faint peak is how impurities become phases.
    localise    boundaries come from the lever rule, not from bisection. In the gap between two
                known phases the mixing fraction is linear in composition, so measured fractions
                at the scan points already inside the gap - topped up to at least two - fit a
                line whose intercepts at fraction 0 and 1 are the two boundaries. That costs one
                or two syntheses per gap where a bisection would cost four or five.

Two floors, on purpose. Signature discovery and the equilibrium check read only strong peaks,
because the impurity lives below 0.2 and believing faint peaks is how impurities become phases.
Fraction estimation reads the whole pattern down to the detection limit, matched against known
signatures - a minority phase at fraction 0.2 puts every one of its peaks under the strong floor,
and a first version of this reference that reused the strong floor there could not see the gaps
it was supposed to regress over: most scan points inside a two-phase field read as pure. Matching
against a known signature is itself the impurity filter at that stage.

Fractions are normalised by each phase's pure-pattern total intensity before the lever fit.
The raw intensity ratio is biased toward whichever phase scatters more, and the bias walks the
fitted intercepts off the true boundaries by more than the scoring tolerance.
"""
from __future__ import annotations

import math

import numpy as np

STRONG_PEAK_FLOOR = 0.27       # impurity peaks stay below ~0.2; genuine peaks at fraction ~1 exceed 0.33
MATCH_TOL = 0.4                # position-noise sigma is 0.08; this is five sigma
REPRODUCIBILITY_JACCARD = 0.55 # equilibrium replicates sit near 1.0, trapped ones near 0.2


def _strong(pattern, floor=STRONG_PEAK_FLOOR):
    return [(float(p["two_theta"]), float(p["intensity"]))
            for p in pattern if float(p["intensity"]) >= floor]


def _positions(peaks):
    return [pos for pos, _v in peaks]


def _matched(pos, signature):
    return any(abs(pos - s) <= MATCH_TOL for s in signature)


def _jaccard(a, b):
    if not a and not b:
        return 1.0
    hits = sum(1 for pos in a if _matched(pos, b))
    return hits / max(len(set(a)) + len(set(b)) - hits, 1)


def _signature_intensity(pattern, signature):
    """Summed intensity of this pattern's peaks that belong to the signature."""
    return sum(v for pos, v in pattern if _matched(pos, signature))


def _all_peaks(pattern):
    """Every reported peak, down to the detection limit. Used only where a known signature does
    the filtering; the impurity is rejected by not matching, not by a floor."""
    return [(float(p["two_theta"]), float(p["intensity"])) for p in pattern]


def discover_phases(problem, synthesize):
    budget = int(problem["synthesis_budget_calls"])
    calls = {"n": 0}

    def measure(x):
        if calls["n"] >= budget:
            return None
        calls["n"] += 1
        return synthesize(float(np.clip(x, 0.0, 1.0)))

    # Anchors: the terminal solid solutions.
    left = measure(0.02)
    right = measure(0.98)
    if left is None or right is None:
        return {"abstain": True, "confidence": 0.0}
    sig_alpha = _positions(_strong(left))
    sig_beta = _positions(_strong(right))

    # Equilibrium check before anything else is bought.
    replicates = [m for m in (measure(0.5), measure(0.5), measure(0.5)) if m is not None]
    if len(replicates) < 2:
        return {"abstain": True, "confidence": 0.0}
    # Two instability signals, either one damning. A trapped sample freezes in a different
    # mixture each time, so the terminal-phase share swings between replicates; and its transient
    # peaks - strong, unexplained by either terminal - never reproduce. A shared-peak Jaccard over
    # the whole pattern misses both: the terminals contribute the same peaks to every replicate,
    # and in one measured world that overlap alone kept the Jaccard above threshold.
    unexplained_sets = []
    alpha_shares = []
    for m in replicates:
        peaks = _strong(m)
        unexplained_sets.append([pos for pos, _v in peaks
                                 if not _matched(pos, sig_alpha)
                                 and not _matched(pos, sig_beta)])
        total = sum(v for _p, v in peaks)
        alpha_shares.append(_signature_intensity(peaks, sig_alpha) / max(total, 1e-9))
    share_swing = float(np.max(alpha_shares) - np.min(alpha_shares))
    transient = any(unexplained_sets) and float(np.mean([
        _jaccard(unexplained_sets[i], unexplained_sets[j])
        for i in range(len(unexplained_sets)) for j in range(i + 1, len(unexplained_sets))
    ])) < 0.4
    if share_swing > 0.15 or transient:
        return {"abstain": True, "confidence": 0.9}

    # Interior scan.
    scan_xs = [round(0.1 * i, 3) for i in range(1, 10)]
    scan = {}
    scan_full = {}
    for x in scan_xs:
        pattern = measure(x)
        if pattern is None:
            break
        scan[x] = _strong(pattern)
        scan_full[x] = _all_peaks(pattern)
    scan[0.5] = _strong(replicates[0])
    scan_full[0.5] = _all_peaks(replicates[0])
    scan_full[0.02] = _all_peaks(left)
    scan_full[0.98] = _all_peaks(right)

    # Split the candidates into compounds by iterative peeling. Grouping peaks by which scan
    # points share them cannot work here: in the gap between two intermediate compounds every
    # pattern carries both signatures, so their supports always touch and the two compounds merge
    # into one claim - which is exactly what happened to both two-compound worlds in the first
    # version. Peeling instead: take the purest unexplained point, read one compound's signature
    # off a targeted synthesis there, add it to the known set, and look again at what is still
    # unexplained. Each round explains more of the scan or stops.
    intermediates = []
    known = [sig_alpha, sig_beta]
    for _round in range(3):
        residual_by_x = {}
        for x, peaks in scan.items():
            residual = [(pos, v) for pos, v in peaks
                        if not any(_matched(pos, sig) for sig in known)]
            if residual:
                residual_by_x[x] = residual
        # Repeatable residuals only: a peak seen at one lone point is an impurity that cleared
        # the strong floor by noise, not a compound.
        xs_sorted = sorted(residual_by_x)
        supported = {}
        for i, x in enumerate(xs_sorted):
            neighbours = [xs_sorted[j] for j in (i - 1, i + 1) if 0 <= j < len(xs_sorted)]
            good = [(pos, v) for pos, v in residual_by_x[x]
                    if any(_matched(pos, _positions(residual_by_x[n])) for n in neighbours)]
            if good:
                supported[x] = good
        if not supported:
            break
        best_x = max(supported, key=lambda x: (
            sum(v for _p, v in supported[x]) / max(sum(v for _p, v in scan[x]), 1e-9)))
        probe = measure(best_x)
        if probe is None:
            break
        pure = [(pos, v) for pos, v in _strong(probe)
                if not any(_matched(pos, sig) for sig in known)]
        if len(pure) < 3:
            break
        signature = sorted(_positions(pure))
        intermediates.append({"signature": signature, "near": best_x,
                              "pure_pattern": _all_peaks(probe)})
        known.append(signature)
    intermediates.sort(key=lambda c: c["near"])

    # The phase sequence across composition.
    sequence = [{"signature": sig_alpha, "kind": "alpha"}]
    sequence += [{"signature": c["signature"], "kind": "intermediate", "near": c["near"],
                  "pure_pattern": c.get("pure_pattern")}
                 for c in intermediates]
    sequence.append({"signature": sig_beta, "kind": "beta"})

    # Pure-pattern total intensity per phase, so lever fractions can be normalised: the raw
    # intensity ratio is biased toward whichever phase scatters more.
    pure_total = {
        tuple(sig_alpha): _signature_intensity(_all_peaks(left), sig_alpha),
        tuple(sig_beta): _signature_intensity(_all_peaks(right), sig_beta),
    }
    for entry in sequence:
        key = tuple(entry["signature"])
        if key not in pure_total:
            pattern = entry.get("pure_pattern")
            pure_total[key] = (_signature_intensity(pattern, entry["signature"])
                               if pattern else None)

    def fraction_of(pattern, sig_left, sig_right):
        """Lever fraction of the right phase, from the full pattern, normalised by pure totals."""
        t_left = pure_total.get(tuple(sig_left))
        t_right = pure_total.get(tuple(sig_right))
        i_left = _signature_intensity(pattern, sig_left)
        i_right = _signature_intensity(pattern, sig_right)
        if t_left and t_right:
            i_left, i_right = i_left / t_left, i_right / t_right
        total = i_left + i_right
        if total <= 1e-9:
            return None
        return i_right / total

    # Assign each scan point to a segment between adjacent phases: a point belongs to the gap
    # (p, q) when its peaks are explained by p and q together and p's and q's shares are both
    # visible; it is inside a single-phase region when one signature explains nearly everything.
    def dominant_share(pattern, signature):
        total = sum(v for _p, v in pattern)
        if total <= 1e-9:
            return 0.0
        return _signature_intensity(pattern, signature) / total

    claims = []
    boundaries = {}
    for index in range(len(sequence) - 1):
        p, q = sequence[index], sequence[index + 1]
        gap_points = []
        for x, pattern in sorted(scan_full.items()):
            share_p = dominant_share(pattern, p["signature"])
            share_q = dominant_share(pattern, q["signature"])
            if share_p > 0.12 and share_q > 0.12 and share_p + share_q > 0.75:
                inside = any(dominant_share(pattern, r["signature"]) > 0.5
                             for r in sequence if r is not p and r is not q)
                if not inside:
                    fraction = fraction_of(pattern, p["signature"], q["signature"])
                    if fraction is not None and 0.03 < fraction < 0.97:
                        gap_points.append((x, fraction))
        # Top up to two usable points per gap.
        attempts = 0
        while len(gap_points) < 2 and attempts < 3 and calls["n"] < budget:
            attempts += 1
            if gap_points:
                x0, f0 = gap_points[0]
                x_new = float(np.clip(x0 + (0.08 if f0 < 0.5 else -0.08), 0.02, 0.98))
            else:
                lo_ref = p.get("near", 0.05 if p["kind"] == "alpha" else 0.5)
                hi_ref = q.get("near", 0.95 if q["kind"] == "beta" else 0.5)
                x_new = float(np.clip((lo_ref + hi_ref) / 2.0, 0.02, 0.98))
            pattern = measure(x_new)
            if pattern is None:
                break
            fraction = fraction_of(_all_peaks(pattern), p["signature"], q["signature"])
            if fraction is not None and 0.03 < fraction < 0.97:
                gap_points.append((x_new, fraction))
        if len(gap_points) >= 2:
            xs = np.array([x for x, _f in gap_points])
            fs = np.array([f for _x, f in gap_points])
            slope, intercept = np.polyfit(xs, fs, 1)
            if slope > 1e-9:
                boundaries[(index, "hi")] = float(np.clip(-intercept / slope, 0.0, 1.0))
                boundaries[(index + 1, "lo")] = float(np.clip((1.0 - intercept) / slope, 0.0, 1.0))
        elif len(gap_points) == 1:
            # One usable point: split the gap at the lever ratio around it.
            x0, f0 = gap_points[0]
            boundaries[(index, "hi")] = max(0.0, x0 - f0 * 0.15)
            boundaries[(index + 1, "lo")] = min(1.0, x0 + (1.0 - f0) * 0.15)

    for index, entry in enumerate(sequence):
        if entry["kind"] == "alpha":
            lo = 0.0
            hi = boundaries.get((index, "hi"), 0.08)
        elif entry["kind"] == "beta":
            lo = boundaries.get((index, "lo"), 0.92)
            hi = 1.0
        else:
            near = entry.get("near", 0.5)
            lo = boundaries.get((index, "lo"), max(0.0, near - 0.04))
            hi = boundaries.get((index, "hi"), min(1.0, near + 0.04))
        if hi <= lo:
            center = (lo + hi) / 2.0
            lo, hi = max(0.0, center - 0.01), min(1.0, center + 0.01)
        claims.append({"composition_range": [round(lo, 5), round(hi, 5)],
                       # Measured positions carry noise, and a peak near the edge of the window
                       # can land just outside it; the claim clips back inside.
                       "peak_two_thetas": [round(float(np.clip(p_, 10.0, 90.0)), 3)
                                           for p_ in entry["signature"][:12]]})

    # Ranges must not overlap; trim any regression overshoot pairwise.
    for left_claim, right_claim in zip(claims, claims[1:]):
        if left_claim["composition_range"][1] > right_claim["composition_range"][0]:
            middle = (left_claim["composition_range"][1]
                      + right_claim["composition_range"][0]) / 2.0
            left_claim["composition_range"][1] = round(middle - 1e-4, 5)
            right_claim["composition_range"][0] = round(middle + 1e-4, 5)

    return {"phases": claims, "confidence": 0.85, "abstain": False}
