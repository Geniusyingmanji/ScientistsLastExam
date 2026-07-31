"""Baseline: constant velocity model."""
import numpy as np

def invert_seismic(travel_times, source_positions, receiver_positions, n_layers):
    avg_dist = np.mean(np.abs(np.array(receiver_positions) - np.array(source_positions)))
    avg_time = np.mean(travel_times)
    v = avg_dist / max(avg_time, 1e-6)
    return np.full(n_layers, v)
