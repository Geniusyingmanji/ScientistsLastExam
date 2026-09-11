"""Truth-blind reference witness: decomposition, flat-background filter, greedy attachment.

Uses only the public problem statement and the charged instrument. Four energy scans and
one precursor-window zoom; mass decomposition of every surviving peak into CHNO formulas;
greedy parent attachment through the public loss library; refusal when the precursor ion
never survives or two precursor ions with different isotope ratios share the window.
"""

from __future__ import annotations

import math

import numpy as np

ENERGIES = (12.0, 24.0, 38.0, 54.0)
ZOOM_WIDTH = 2.6


def _formula_grid(element_mass_table, ranges):
    carbons = np.arange(ranges["C"][0], ranges["C"][1] + 1)
    hydrogens = np.arange(ranges["H"][0], ranges["H"][1] + 1)
    nitrogens = np.arange(ranges["N"][0], ranges["N"][1] + 1)
    oxygens = np.arange(ranges["O"][0], ranges["O"][1] + 1)
    grid = np.stack(np.meshgrid(carbons, hydrogens, nitrogens, oxygens, indexing="ij"),
                    axis=-1).reshape(-1, 4)
    masses = (grid[:, 0] * element_mass_table["C"] + grid[:, 1] * element_mass_table["H"]
              + grid[:, 2] * element_mass_table["N"] + grid[:, 3] * element_mass_table["O"])
    return grid, masses


def _decompose(neutral_mass, tolerance, element_mass_table, ranges):
    grid, masses = _formula_grid(element_mass_table, ranges)
    hits = np.nonzero(np.abs(masses - neutral_mass) <= tolerance)[0]
    candidates = []
    for index in hits:
        carbon, hydrogen, nitrogen, oxygen = grid[index]
        if carbon == 0:
            if hydrogen > 4:
                continue
        else:
            dbe = carbon - hydrogen / 2.0 + nitrogen / 2.0 + 1.0
            if not 0.0 <= dbe <= 13.0 or hydrogen > 2 * carbon + 2 + nitrogen:
                continue
        candidates.append((int(carbon), int(hydrogen), int(nitrogen), int(oxygen)))
    return candidates


def _formula_mass(formula, element_mass_table):
    carbon, hydrogen, nitrogen, oxygen = formula
    return (carbon * element_mass_table["C"] + hydrogen * element_mass_table["H"]
            + nitrogen * element_mass_table["N"] + oxygen * element_mass_table["O"])


def recover_fragmentation_tree(problem, acquire, zoom, budget_units):
    del budget_units
    tolerance = float(problem["mass_tolerance_da"])
    proton = float(problem["proton_mass"])
    precursor_mz = float(problem["precursor_mz"])
    element_mass_table = problem["element_mass_table"]
    ranges = problem["fragment_formula_ranges"]
    loss_masses = {name: float(spec["neutral_mass"])
                   for name, spec in problem["loss_library"].items()}

    spectra = [acquire(energy) for energy in ENERGIES]
    window = zoom(precursor_mz, ZOOM_WIDTH)

    # Precursor-window audit: surviving molecular ions, told apart by isotope ratio.
    precursor_rows = [row for row in window["peaks"]
                      if abs(row["mz"] - precursor_mz) <= 1.3 and row["intensity"] >= 1.0]
    if len(precursor_rows) >= 2:
        ratios = sorted(row["m1_ratio"] for row in precursor_rows)
        if ratios[-1] - ratios[0] > 0.03 * max(ratios[-1], 1e-6):
            return {"nodes": [], "edges": [], "abstain": True, "confidence": 0.8}
    root_seen = any(abs(row["mz"] - precursor_mz) <= tolerance
                    for row in precursor_rows)
    if not root_seen:
        for spectrum in spectra:
            if any(abs(row["mz"] - precursor_mz) <= tolerance
                   and row["intensity"] >= 1.0 for row in spectrum["peaks"]):
                root_seen = True
                break
    has_fragments = any(
        row["intensity"] >= 1.0 and abs(row["mz"] - precursor_mz) > 3.0
        for spectrum in spectra for row in spectrum["peaks"])
    if not root_seen and has_fragments:
        return {"nodes": [], "edges": [], "abstain": True, "confidence": 0.75}

    # Aggregate peaks across energies; background peaks stay flat as energy changes,
    # while analyte fragments rise from the lowest to the highest energy (saturated
    # fragments plateau too, so the contrast is taken first-vs-last, not max-vs-min).
    track = {}
    for spectrum in spectra:
        for row in spectrum["peaks"]:
            track.setdefault(round(row["mz"], 1), []).append(row["intensity"])
    analyte_peaks = {}
    for spectrum in spectra:
        for row in spectrum["peaks"]:
            mz, intensity = float(row["mz"]), float(row["intensity"])
            key = round(mz, 1)
            series = sorted(track.get(key, [intensity]))
            if intensity < 0.5:
                continue
            contrast = max(series[-1] / max(series[0], 1e-9), 1.0)
            if contrast < 1.35 and intensity < 3.0:
                continue  # flat low background
            analyte_peaks[round(mz, 3)] = max(analyte_peaks.get(round(mz, 3), 0.0),
                                               intensity)

    # The same fragment measured at several energies carries independent mass noise;
    # merge observations closer than a third of the tolerance into one node.
    merged = []
    for mz in sorted(analyte_peaks):
        if merged and mz - merged[-1][0] <= tolerance / 3.0:
            merged[-1] = (0.5 * (mz + merged[-1][0]),
                          max(merged[-1][1], analyte_peaks[mz]))
        else:
            merged.append((mz, analyte_peaks[mz]))
    analyte_peaks = dict(merged)
    if not analyte_peaks:
        return {"nodes": [precursor_mz], "edges": [], "abstain": False, "confidence": 0.3}

    # Decompose each analyte peak; keep the plausibility-cleanest formula per peak.
    node_formulas = {round(precursor_mz, 4): _decompose(
        precursor_mz - proton, tolerance, element_mass_table, ranges)[:1]}
    for mz in sorted(analyte_peaks, reverse=True):
        if abs(mz - precursor_mz) <= tolerance:
            continue
        candidates = _decompose(mz - proton, tolerance, element_mass_table, ranges)
        if not candidates:
            continue
        node_formulas[round(mz, 4)] = candidates[:1]

    # Greedy attachment: heaviest fragment first, parent whose mass gap matches a loss.
    nodes = sorted(node_formulas, reverse=True)
    edges = []
    attached = {nodes[0]}
    for mz in nodes[1:]:
        parent, chosen = None, None
        for candidate_parent in sorted(attached, reverse=True):
            if candidate_parent == mz:
                continue
            gap = candidate_parent - mz
            best = min(loss_masses, key=lambda name: abs(loss_masses[name] - gap))
            if abs(loss_masses[best] - gap) <= 2.0 * tolerance:
                parent, chosen = candidate_parent, best
                break
        if parent is None:
            for candidate_parent in sorted(attached, reverse=True):
                gap = candidate_parent - mz
                best = min(loss_masses, key=lambda name: abs(loss_masses[name] - gap))
                if abs(loss_masses[best] - gap) <= 3.0 * tolerance:
                    parent, chosen = candidate_parent, best
                    break
        if parent is not None:
            edges.append([parent, mz, chosen])
            attached.add(mz)
        else:
            attached.add(mz)
    return {"nodes": [float(node) for node in nodes], "edges": edges,
            "abstain": False, "confidence": 0.7}
