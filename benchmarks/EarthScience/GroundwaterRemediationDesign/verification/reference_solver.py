"""Standalone public transport integration and archive search; no oracle imports."""
import math
import numpy as np
_REFERENCE_CACHE={}

def _plan_metrics(problem, wells, shift=None):
    shift = shift or {"velocity": 1.0, "dispersion": 1.0, "decay": 1.0, "release": 1.0}
    velocity = problem["groundwater_velocity_m_day"] * shift["velocity"]
    sigma_x0 = problem["longitudinal_sigma_m"] * shift["dispersion"]
    sigma_y0 = problem["transverse_sigma_m"] * shift["dispersion"]
    decay = problem["decay_per_day"] * shift["decay"]
    initial_mass = problem["initial_contaminant_mass_kg"] * shift["release"]
    source_x, source_y = problem["source_location_m"]
    thickness = problem["aquifer_thickness_m"]
    porosity = problem["effective_porosity"]
    # Each initial Gaussian component advects continuously. Pump extraction is
    # Q*C at the *current* well concentration, integrated in time, not distance
    # from the source at the instant pumping was switched on.
    components = np.asarray(problem["plume_components"], dtype=float)
    masses = initial_mass * components[:, 2]
    removed = 0.0
    decayed = 0.0
    time_days = 0.0
    mass_history, concentration_history = [], []
    wells = np.asarray(wells, dtype=float)
    for year in problem["evaluation_times_years"]:
        stop = 365.25 * float(year)
        while time_days < stop - 1e-9:
            dt = min(float(problem["transport_step_days"]), stop - time_days)
            # Split at activation times so delaying a well never gets a free full step.
            starts = 365.25 * wells[:, 2]
            future = starts[(starts > time_days + 1e-9) & (starts < time_days + dt)]
            if len(future):
                dt = float(np.min(future) - time_days)
            mid = time_days + 0.5 * dt
            sx = math.sqrt(sigma_x0 ** 2 + 16.0 * mid)
            sy = math.sqrt(sigma_y0 ** 2 + 4.4 * mid)
            cx = source_x + components[:, 0] + velocity * mid
            cy = source_y + components[:, 1]
            distance = ((wells[:, 0, None] - cx) / sx) ** 2 + ((wells[:, 1, None] - cy) / sy) ** 2
            density = np.exp(-0.5 * distance) / (2 * math.pi * sx * sy * thickness * porosity)
            active_rates = wells[:, 3] * (starts <= mid)
            capture = np.sum(active_rates[:, None] * density, axis=0)
            hazard = capture + decay
            lost = masses * (-np.expm1(-hazard * dt))
            removed += float(np.sum(lost * capture / np.maximum(hazard, 1e-30)))
            decayed += float(np.sum(lost * decay / np.maximum(hazard, 1e-30)))
            masses -= lost
            time_days += dt
        mass_history.append(float(np.sum(masses)))
        sx = math.sqrt(sigma_x0 ** 2 + 16.0 * stop)
        sy = math.sqrt(sigma_y0 ** 2 + 4.4 * stop)
        receptors = np.asarray(problem["receptor_locations_m"])
        cx = source_x + components[:, 0] + velocity * stop
        cy = source_y + components[:, 1]
        distance = ((receptors[:, 0, None] - cx) / sx) ** 2 + ((receptors[:, 1, None] - cy) / sy) ** 2
        concentration_history.append(np.sum(masses * np.exp(-0.5 * distance) /
                                            (2 * math.pi * sx * sy * thickness * porosity), axis=1))
    final_mass = float(mass_history[-1])
    max_receptor = float(np.max(concentration_history))
    horizon_days = 365.25 * problem["horizon_years"]
    pumped = float(np.sum([rate * max(0.0, horizon_days - 365.25 * start)
                           for _, _, start, rate in wells]))
    mean_discount = (1.0 + problem["discount_rate"]) ** (-0.5 * problem["horizon_years"])
    cost = len(wells) * problem["fixed_well_cost_usd"] + pumped * problem["pumping_cost_usd_per_m3"] * mean_discount
    compliance = max_receptor <= problem["concentration_limit_kg_m3"]
    return {"remaining_mass_kg": final_mass, "max_receptor_concentration_kg_m3": max_receptor,
            "lifecycle_cost_usd": float(cost), "total_pumped_m3": pumped, "compliant": bool(compliance),
            "captured_mass_kg": removed, "decayed_mass_kg": decayed,
            "mass_balance_error_kg": abs(initial_mass - final_mass - removed - decayed)}

def _point(problem, metrics):
    if not metrics["compliant"]:
        return None
    cleanup = float(np.clip(1.0 - metrics["remaining_mass_kg"] / problem["initial_contaminant_mass_kg"], 0.0, 1.0))
    max_cost = (5.0 * problem["fixed_well_cost_usd"]
                + problem["max_total_pumping_m3_day"] * 365.25 * problem["horizon_years"]
                * problem["pumping_cost_usd_per_m3"])
    cost_quality = float(np.clip(1.0 - metrics["lifecycle_cost_usd"] / max_cost, 0.0, 1.0))
    return cleanup, cost_quality

def _baseline_archive(problem):
    source_x, source_y = problem["source_location_m"]
    center = min(problem["domain_size_m"][0] * 0.8,
                 source_x + 0.55 * problem["groundwater_velocity_m_day"] * 365.25 * problem["horizon_years"])
    qmin = problem["pumping_rate_bounds_m3_day"][0]
    return [np.asarray([[center, np.clip(source_y + offset, 0.0, problem["domain_size_m"][1]), 2.0, 1.15 * qmin]])
            for offset in (-600.0, -200.0, 200.0, 600.0)]

def _reference_archive(problem):
    """Public-model archive search, including the single-source and weak baselines."""
    key = repr(problem)
    if key in _REFERENCE_CACHE:
        return [p.copy() for p in _REFERENCE_CACHE[key]]
    source_x, source_y = problem["source_location_m"]
    velocity = problem["groundwater_velocity_m_day"]
    candidates = _baseline_archive(problem)
    for rate in np.linspace(80.0, 950.0, 16):
        candidates.append(np.asarray([[source_x, source_y, 0.0, rate]]))
    # Build treatment transects intercepting different moving plume components.
    components = np.asarray(problem["plume_components"])
    for count in (1, 2, 3, 4, 5):
        for encounter in (1.0, 4.0, 8.0, 12.0):
            for rate in (160., 380., 650., 950.):
                component = np.arange(count) % len(components)
                x = source_x + components[component, 0] + velocity * 365.25 * encounter
                y = source_y + components[component, 1] + 100.0 * (np.arange(count) // len(components))
                start = max(0.0, encounter - 3.0)
                wells = np.column_stack((np.clip(x, 0, problem["domain_size_m"][0]),
                                        np.clip(y, 0, problem["domain_size_m"][1]),
                                        np.full(count, min(8., start)),
                                        np.full(count, min(rate, problem["max_total_pumping_m3_day"] / count))))
                candidates.append(wells)
    points = [_point(problem, _plan_metrics(problem, p)) for p in candidates]
    # Greedy hypervolume coverage uses only public homogeneous transport.
    selected = list(range(4))
    def area(indices):
        values = sorted(set(points[i] for i in indices if points[i] is not None))
        frontier = [p for p in values if not any(q[0] >= p[0] and q[1] >= p[1] and q != p for q in values)]
        previous = 0.0; result = 0.0
        for x, y in frontier:
            result += (x - previous) * y; previous = x
        return result
    for _ in range(12):
        best = max((i for i in range(len(candidates)) if i not in selected),
                   key=lambda i: area(selected + [i]))
        selected.append(best)
    answer = [candidates[i] for i in selected]
    _REFERENCE_CACHE[key] = [p.copy() for p in answer]
    return answer

def design_remediation(problem):
    return {"plans": _reference_archive(problem)}
