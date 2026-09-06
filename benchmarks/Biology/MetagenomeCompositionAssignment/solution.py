"""Weak legal single-marker baseline."""
import numpy as np
def assign_composition(problem, sequence):
    counts=np.asarray(problem["initial_observation"]["marker_counts"],float)
    refs=np.asarray(problem["reference_profiles"],float)
    j=int(np.argmax(refs.T@counts))
    return {"taxa":[{"taxon":problem["taxon_ids"][j],"abundance":1.0}],"ambiguous_groups":[],"abstain":False}
