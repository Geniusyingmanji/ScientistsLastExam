"""Oracle: traffic signal timing optimization — minimize total delay.

Arterial corridor with N intersections. Agent sets green times and offsets. Oracle computes
total vehicle delay using the Highway Capacity Manual (HCM) formula with platoon dispersion.
"""
import numpy as np

N_INTERSECTIONS = 5
CYCLE_LENGTH = 90  # seconds
DEMANDS = [800, 900, 750, 850, 700]  # veh/hr per intersection (main direction)
SAT_FLOW = 1800  # veh/hr/lane
N_LANES = 2
LINK_LENGTH = 400  # meters between intersections
SPEED = 50 / 3.6  # m/s

def _hcm_delay(demand_vph, green_time, cycle):
    """HCM 2010 uniform delay formula."""
    g_C = green_time / cycle
    capacity = SAT_FLOW * N_LANES * g_C
    x = demand_vph / max(capacity, 1)  # degree of saturation
    x = min(x, 1.5)  # cap
    # Uniform delay: d1 = 0.5*C*(1-g/C)^2 / (1 - min(1,x)*g/C)
    d1 = 0.5 * cycle * (1 - g_C)**2 / max(1 - min(1.0, x) * g_C, 0.01)
    # Overflow delay: d2 approximation
    d2 = 900 * cycle / 3600 * (max(x - 1, 0))**2 if x > 1 else 0
    return d1 + d2

def _total_delay(green_times, offsets):
    """Total network delay (veh-seconds per hour)."""
    total = 0.0
    for i in range(N_INTERSECTIONS):
        d = _hcm_delay(DEMANDS[i], green_times[i], CYCLE_LENGTH)
        total += d * DEMANDS[i]
        # Progression bonus: if offset matches travel time, reduce delay
        if i > 0:
            travel_time = LINK_LENGTH / SPEED
            ideal_offset = travel_time % CYCLE_LENGTH
            offset_error = abs((offsets[i] - offsets[i-1]) % CYCLE_LENGTH - ideal_offset)
            progression = max(0, 1 - offset_error / (CYCLE_LENGTH / 2))
            total -= progression * 0.2 * d * DEMANDS[i]  # up to 20% reduction with good progression
    return total

def evaluate(optimize_signals):
    try:
        result = optimize_signals(N_INTERSECTIONS, CYCLE_LENGTH, DEMANDS)
        green_times = np.asarray(result["green_times"], dtype=float)
        offsets = np.asarray(result["offsets"], dtype=float)
    except Exception as e:
        return {"combined_score": 0.0, "valid": 0.0, "error_message": str(e), "feasibility_rate": 0.0}
    if green_times.shape != (N_INTERSECTIONS,) or offsets.shape != (N_INTERSECTIONS,):
        return {"combined_score": 0.0, "valid": 0.0, "error_message": "bad shape", "feasibility_rate": 0.0}
    green_times = np.clip(green_times, 15, CYCLE_LENGTH - 15)
    offsets = offsets % CYCLE_LENGTH
    delay = _total_delay(green_times, offsets)
    # Baseline: equal green, zero offset
    g_base = np.full(N_INTERSECTIONS, CYCLE_LENGTH / 2)
    o_base = np.zeros(N_INTERSECTIONS)
    delay_base = _total_delay(g_base, o_base)
    delay_sota = delay_base * 0.55  # ~45% reduction with optimal timing
    score = max(0.0, min(1.0, (delay_base - delay) / (delay_base - delay_sota)))
    return {"combined_score": float(score), "valid": 1.0, "feasibility_rate": 1.0,
            "total_delay": round(delay, 0), "baseline_delay": round(delay_base, 0)}
