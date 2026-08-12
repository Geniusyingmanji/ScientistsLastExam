"""Baseline: read the initial decay rate of each site as its field, and claim no couplings.

A first-order reading of the traces. It ignores that the decay of site 0 is driven by the
couplings, not by its own field, which is the misconception the task is about.
"""


def learn_hamiltonian(observation):
    n = observation["spins"]
    times = observation["times"]
    traces = observation["magnetisation"]
    fields = []
    for trace in traces:
        if len(times) > 1 and times[1] > times[0]:
            slope = (trace[1] - trace[0]) / (times[1] - times[0])
        else:
            slope = 0.0
        fields.append(max(-1.2, min(1.2, slope)))
    return {"fields": fields, "couplings": [[0.0] * n for _ in range(n)]}
