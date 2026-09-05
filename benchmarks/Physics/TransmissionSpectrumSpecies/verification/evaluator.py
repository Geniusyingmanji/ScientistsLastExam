"""Hidden oracle for TransmissionSpectrumSpecies.

Which molecules are in an exoplanet's atmosphere? The question is live and contested: the JWST
spectrum of K2-18 b produced a reported detection of dimethyl sulfide, and the reanalyses that
followed concluded that the features "are not uniquely identifiable", with ethylene and
chloroethane at least as favoured, and that DMS and DMDS are mutually degenerate in the mid-infrared
(A&A 700 (2025) A55; AJ 170 (2025); arXiv:2505.10539). The field's own summary is that more work is
needed to identify potential false positives.

That is the shape of this task. A searcher is given a spectrograph, a budget of transits, and a
catalogue of candidate species, and must say which are present - or say that the data cannot decide,
which for a third of the systems is the only defensible answer.

**Three axes, reported separately and never averaged**, because they fail in opposite directions and
a single number hides which one moved:

  * *mechanism recovery* - on systems that are identifiable, is the species set right?
  * *false discovery rate* - of the species claimed present, how many are not there? The denominator
    is published, because a rate without it cannot be recomposed.
  * *calibrated refusal* - on systems that are not identifiable, does the searcher abstain?

A fourth counter, *attempted*, records how often the searcher declined to abstain at all. Without it
"abstained on everything" and "the science is too hard" look identical in the report, and they call
for opposite responses. Recovery is normalised so that blanket abstention scores exactly zero:

    normalised = (raw - always_abstain) / (1 - always_abstain)

Three of the four regimes are unidentifiable for three different reasons, and only one of them is
noise. A grey cloud deck mutes every feature at once; a confusable pair overlaps at 0.98 correlation
so that no allocation of the budget separates them; and a faint system never reaches unit
signal-to-noise even if the whole budget is spent on its best band. A searcher that abstains
whenever the spectrum looks noisy will get the third and miss the first two.
"""
from __future__ import annotations

import math
import zlib

import numpy as np

# The world and the system set are inlined rather than imported from siblings. The trusted driver
# loads this file by path, not as a package, so `from world import ...` resolves against the
# harness's sys.path and not against this directory - it raised ModuleNotFoundError inside the
# sandbox while working perfectly when imported directly. verification/world.py and
# verification/systems.py remain the readable statements of the same model, and the task's tests
# check the copies agree.


WAVELENGTHS = np.linspace(0.6, 5.3, 188)          # microns, JWST-like coverage
BAND_EDGES = np.linspace(0.6, 5.3, 13)            # twelve bands the budget is spent on

# (name, [(centre, width, strength), ...]). The pairs that overlap are deliberate.
SPECIES = {
    "H2O":  [(1.40, 0.11, 1.0), (1.90, 0.14, 1.3), (2.70, 0.18, 1.1)],
    "CH4":  [(1.66, 0.09, 0.9), (2.32, 0.12, 1.0), (3.30, 0.16, 1.6)],
    "CO2":  [(2.02, 0.06, 1.2), (4.30, 0.12, 2.4)],
    "CO":   [(2.35, 0.05, 0.7), (4.65, 0.09, 1.5)],
    "NH3":  [(1.50, 0.08, 0.6), (2.25, 0.10, 0.8), (3.00, 0.13, 0.9)],
    "SO2":  [(4.05, 0.10, 1.4)],
    # The confusable pair. Their bands sit on top of each other, which is the situation reported for
    # DMS against C2H4 and chloroethane in the K2-18 b reanalyses. The offsets are small on purpose:
    # at a first attempt they differed by 0.02 um and the fit could still separate them - the
    # design matrix had condition number 93 and the individual amplitudes were recoverable - which
    # made the refusal regime a matter of signal-to-noise rather than of identifiability. Moving
    # them to within a few thousandths of a micron makes the pair genuinely inseparable at any
    # allocation of the budget, which is the claim the task needs to be able to make.
    "DMS":  [(3.400, 0.150, 1.0), (3.850, 0.120, 0.8)],
    "C2H4": [(3.396, 0.152, 1.0), (3.856, 0.121, 0.8)],
}
SPECIES_ORDER = tuple(sorted(SPECIES))
CONFUSABLE = frozenset({"DMS", "C2H4"})


def cross_sections():
    """Fixed opacity templates on the wavelength grid, one row per species."""
    table = np.zeros((len(SPECIES_ORDER), WAVELENGTHS.size))
    for index, name in enumerate(SPECIES_ORDER):
        for centre, width, strength in SPECIES[name]:
            table[index] += strength * np.exp(-0.5 * ((WAVELENGTHS - centre) / width) ** 2)
    return table


def spectrum(abundances, grey, rayleigh, depth, scale):
    """Noise-free transit depth for one atmosphere."""
    opacity = abundances @ cross_sections()
    floor = grey + rayleigh * (1.0 / WAVELENGTHS) ** 4
    return depth + scale * np.log(opacity + floor + 1e-12)


# Four regimes. The names are the scientific claim being made about each system, and the evaluator
# scores different things on different regimes - identification on the ones that are identifiable,
# refusal on the ones that are not.
#
#   clear       enough signal, no confusable species: the set is recoverable and must be reported
#   confusable  exactly one of the DMS/C2H4 pair is present, and their bands overlap at 0.98
#               correlation, so no allocation of the budget separates them: abstention is correct
#   muted       a grey cloud deck sits above the features and mutes all of them at once: nothing is
#               identifiable and abstention is correct
#   sparse      the species are separable in principle but the budget cannot reach the required
#               depth on enough bands at once; abstention is correct


def build(seed, count):
    """Deterministic draw of `count` systems."""
    rng = np.random.default_rng(seed)
    plain = [name for name in SPECIES_ORDER if name not in CONFUSABLE]
    systems = []
    for index in range(count):
        regime = ("clear", "confusable", "muted", "sparse")[index % 4]
        abundances = np.zeros(len(SPECIES_ORDER))
        chosen = rng.choice(plain, size=int(rng.integers(1, 4)), replace=False)
        for name in chosen:
            abundances[SPECIES_ORDER.index(name)] = float(rng.uniform(0.5, 3.0))
        present = set(chosen)
        if regime == "confusable":
            partner = str(rng.choice(sorted(CONFUSABLE)))
            abundances[SPECIES_ORDER.index(partner)] = float(rng.uniform(0.8, 2.5))
            present.add(partner)
        # Calibrated against the budget rather than chosen by eye. With BUDGET transits spread over
        # twelve bands, the best achievable signal-to-noise on the species signal is
        # max|D - D_flat| / (noise / sqrt(budget * points_per_band)); the four regimes are placed at
        # roughly 30, 30, 0.2 and 0.8 by that measure, so "unidentifiable" means the whole budget
        # spent on the best band still does not reach unit signal-to-noise.
        grey = {"clear": 0.02, "confusable": 0.02, "muted": 500.0, "sparse": 0.02}[regime]
        noise = {"clear": 1.0e-3, "confusable": 1.0e-3, "muted": 1.0e-3, "sparse": 6.5e-2}[regime]
        systems.append({
            "system_id": "sys%03d" % index,
            "regime": regime,
            "present": frozenset(present),
            "abundances": abundances,
            "grey": grey,
            "rayleigh": float(rng.uniform(0.0, 0.02)),
            "depth": float(rng.uniform(0.004, 0.012)),
            "scale": float(rng.uniform(2.0e-4, 5.0e-4)),
            "noise_per_transit": noise,
            # Fixed at construction so the noise realisation is a property of the frozen system set
            # rather than of the process that evaluates it.
            "noise_seed": int(rng.integers(0, 2 ** 31 - 1)),
        })
    return systems


def identifiable(system):
    """Is the species set recoverable from any allocation of the budget?"""
    return system["regime"] == "clear"


def scorable_species(system):
    """Which species a report is graded on. The confusable pair is never graded as present or
    absent, because the world does not determine it: grading it would reward a coin flip."""
    return tuple(name for name in SPECIES_ORDER if name not in CONFUSABLE)

DIFFICULTY = 1

BUDGET_TRANSITS = 30
SYSTEM_COUNT = 48
DEV_SEED = 20260906
CONFIDENCE_FLOOR = 0.0


class Spectrograph:
    """Charges each observation against the transit budget and returns binned depths."""

    def __init__(self, system, budget):
        self._system = system
        self._remaining = int(budget)
        self._calls = 0
        self._truth = spectrum(system["abundances"], system["grey"], system["rayleigh"],
                               system["depth"], system["scale"])
        # Seeded from a stable digest, not from hash(): Python randomises string hashing per
        # process unless PYTHONHASHSEED is fixed, so hash() here made the noise realisation - and
        # therefore every score - depend on which process the oracle happened to run in. Measured:
        # the same reference scored 0.4231 in one interpreter and 0.2092 in the next.
        digest = zlib.crc32(system["system_id"].encode("utf-8")) ^ int(system["noise_seed"])
        self._rng = np.random.default_rng(digest & 0xFFFFFFFF)

    @property
    def remaining(self):
        return self._remaining

    def observe(self, allocation):
        """`allocation` is one non-negative integer transit count per band."""
        self._calls += 1
        if self._calls > 64:
            raise ValueError("too many observation calls")
        counts = np.asarray(allocation, dtype=object)
        if counts.shape != (len(BAND_EDGES) - 1,):
            raise ValueError("allocation must have one entry per band")
        integers = []
        for value in counts:
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
                raise ValueError("transit counts must be integers")
            if value < 0:
                raise ValueError("transit counts must be non-negative")
            integers.append(int(value))
        total = sum(integers)
        if total > self._remaining:
            raise ValueError("allocation exceeds the remaining transit budget")
        self._remaining -= total
        bands = []
        for index, count in enumerate(integers):
            low, high = BAND_EDGES[index], BAND_EDGES[index + 1]
            mask = (WAVELENGTHS >= low) & (WAVELENGTHS < high)
            if count == 0 or not mask.any():
                bands.append({"band_index": index, "wavelength_um": float((low + high) / 2),
                              "transits": count, "depth": None, "uncertainty": None})
                continue
            sigma = self._system["noise_per_transit"] / math.sqrt(count * int(mask.sum()))
            value = float(self._truth[mask].mean() + self._rng.normal(0.0, sigma))
            bands.append({"band_index": index, "wavelength_um": float((low + high) / 2),
                          "transits": count, "depth": value, "uncertainty": float(sigma)})
        return {"bands": bands, "remaining_transits": self._remaining}


def _public_problem(system, budget):
    return {
        "system_id": system["system_id"],
        "band_edges_um": [float(v) for v in BAND_EDGES],
        "species_catalogue": list(SPECIES_ORDER),
        "cross_sections": [[float(v) for v in row] for row in cross_sections()],
        "wavelength_um": [float(v) for v in WAVELENGTHS],
        "budget_transits": budget,
        # Named, because it is not a secret and hiding it would only make the task about guessing
        # which species overlap rather than about what to do when two of them do.
        "known_confusable_group": sorted(CONFUSABLE),
        "graded_species": list(scorable_species(system)),
    }


def _read_report(value, graded):
    if not isinstance(value, dict):
        raise ValueError("a report is a mapping")
    abstain = value.get("abstain")
    if not isinstance(abstain, bool):
        raise ValueError("'abstain' must be a boolean")
    confidence = value.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("'confidence' must be a number")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("'confidence' must lie in [0, 1]")
    claimed = set()
    if not abstain:
        species = value.get("species")
        if not isinstance(species, dict):
            raise ValueError("'species' must be a mapping when not abstaining")
        for name, flag in species.items():
            if name not in SPECIES_ORDER:
                raise ValueError("unknown species %r" % (name,))
            if not isinstance(flag, bool):
                raise ValueError("species flags must be booleans")
            if flag:
                claimed.add(name)
    return abstain, claimed, confidence


def evaluate(analyze, seed=DEV_SEED, count=SYSTEM_COUNT, budget=BUDGET_TRANSITS):
    systems = build(seed, count)
    rows = []
    for system in systems:
        graded = scorable_species(system)
        record = {"system_id": system["system_id"], "regime": system["regime"],
                  "identifiable": identifiable(system)}
        try:
            instrument = Spectrograph(system, budget)
            abstain, claimed, confidence = _read_report(
                analyze(_public_problem(system, budget), instrument.observe), graded)
            truth = set(system["present"])
            graded_claimed = {n for n in claimed if n in graded}
            graded_truth = {n for n in truth if n in graded}
            record.update({
                "valid": True, "abstained": abstain, "confidence": confidence,
                "transits_used": budget - instrument.remaining,
                "claimed": sorted(claimed),
                "recovered": bool(not abstain and graded_claimed == graded_truth),
                # Every claimed species that is not present is a false discovery, including a
                # member of the confusable pair: the world does not determine which one it is, so
                # naming either is a claim the data cannot support.
                "false_claims": len(claimed - truth),
                "claims": len(claimed),
            })
        except Exception as exc:  # noqa: BLE001 - a bad report scores zero, it does not crash this
            record.update({
                "valid": False, "reason": "%s: %s" % (type(exc).__name__, exc),
                "abstained": False, "confidence": 0.0, "transits_used": 0, "claimed": [],
                "recovered": False, "false_claims": 0, "claims": 0,
            })
        rows.append(record)

    resolvable = [r for r in rows if r["identifiable"]]
    unresolvable = [r for r in rows if not r["identifiable"]]
    always_abstain = len(unresolvable) / len(rows) if rows else 0.0

    raw_recovery = sum(1 for r in resolvable if r["recovered"]) / len(resolvable) if resolvable else 0.0
    # Blanket abstention recovers nothing, so raw recovery is already zero for it; the anchor is
    # applied to the *combined* score below, where the refusal axis would otherwise pay for it.
    claims = sum(r["claims"] for r in rows)
    false_claims = sum(r["false_claims"] for r in rows)
    false_discovery_rate = (false_claims / claims) if claims else 0.0
    correct_refusal = (sum(1 for r in unresolvable if r["abstained"]) / len(unresolvable)
                       if unresolvable else 0.0)
    attempted = sum(1 for r in rows if not r["abstained"]) / len(rows) if rows else 0.0

    raw_combined = raw_recovery * (1.0 - false_discovery_rate) * correct_refusal
    blanket = 0.0  # blanket abstention recovers nothing, so its combined score is exactly zero
    combined = (raw_combined - blanket) / (1.0 - blanket)

    return {
        "combined_score": float(max(0.0, combined)),
        "valid": 1.0 if any(r["valid"] for r in rows) else 0.0,
        "feasibility_rate": sum(1 for r in rows if r["valid"]) / len(rows),
        "raw_score": float(raw_combined),
        # The triple, separately. Never averaged into one another.
        "mechanism_recovery": float(raw_recovery),
        "mechanism_recovery_denominator": len(resolvable),
        "false_discovery_rate": float(false_discovery_rate),
        "false_discovery_denominator": claims,
        "correct_refusal_rate": float(correct_refusal),
        "correct_refusal_denominator": len(unresolvable),
        "attempted_rate": float(attempted),
        "always_abstain_anchor": float(always_abstain),
        "per_system": rows,
    }
