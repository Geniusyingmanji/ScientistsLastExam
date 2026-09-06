"""Weak valid process archive for ProcessMicrostructurePropertyDesign.

The archive uses the shortest, hottest anneal, fastest cooling and no draw.  It
is deliberately conservative and is the evaluator's zero-credit anchor.
"""
from __future__ import annotations


def design_process_archive(problem):
    bounds = problem["bounds"]
    blend_low, blend_high = bounds["blend_fraction_b"]
    processes = []
    for index in range(4):
        fraction = index / 3.0
        processes.append({
            "blend_fraction_b": blend_low + fraction * (blend_high - blend_low),
            "anneal_temperature": bounds["anneal_temperature"][1],
            "anneal_time": bounds["anneal_time"][0],
            "cooling_rate": bounds["cooling_rate"][1],
            "draw_ratio": bounds["draw_ratio"][0],
        })
    return {"processes": processes}
