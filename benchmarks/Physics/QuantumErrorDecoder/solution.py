"""Initial baseline for QuantumErrorDecoder (weak but valid).

Predicts that the logical observable never flips. This is legal and costs nothing, but it
ignores the syndrome entirely and therefore scores zero by construction. Replace it with a
real decoder: minimum-weight perfect matching over the graphlike error model, union-find,
belief propagation, correlated matching, a learned decoder, or something better.
"""

import numpy as np


def decode(problem, detection_events):
    """Predict logical observable flips from syndrome data.

    Args:
        problem: dict with
            - ``num_detectors`` (int)
            - ``num_observables`` (int)
            - ``distance`` (int), ``rounds`` (int)
            - ``errors``: list of graphlike error components, each a dict with
                ``p``    independent probability of that component firing,
                ``dets`` the detector indices it flips (at most two),
                ``obs``  the logical observable indices it flips.
        detection_events: bool array of shape (shots, num_detectors).

    Returns:
        Array of shape (shots, num_observables) with 0/1 entries.
    """
    shots = detection_events.shape[0]
    return np.zeros((shots, problem["num_observables"]), dtype=bool)
