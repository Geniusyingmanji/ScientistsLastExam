"""Operator population law and shared-occupancy survey simulator."""

import hashlib

import numpy as np
from scipy.special import expit

STRATA = ("linear_occupancy", "curved_occupancy", "detection_confounding")


def random_generator(seed, purpose):
    payload = (str(int(seed))+":"+purpose).encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], "big"))


def generate(seed, stratum):
    rng = random_generator(seed, "parameters-v1")
    sign = float(rng.choice([-1, 1]))
    return {"occupancy_intercept": float(rng.uniform(-.7,.5)),
            "occupancy_slope": sign*float(rng.uniform(.65,1.5)),
            "occupancy_curvature": float(rng.choice([-1,1]))*float(rng.uniform(.9,1.8)) if stratum == "curved_occupancy" else 0.0,
            "rapid_intercept": float(rng.uniform(-1.1,-.3)),
            "intensive_boost": float(rng.uniform(1.0,1.8)),
            "detection_slope": -sign*float(rng.uniform(1.0,1.8)) if stratum == "detection_confounding" else float(rng.uniform(-.25,.25))}


class Kernel:
    def __init__(self, parameters):
        self.parameters = dict(parameters)

    def probabilities(self, spec):
        h = np.asarray(spec["habitat_values"])
        p = self.parameters
        psi = expit(p["occupancy_intercept"]+p["occupancy_slope"]*h+p["occupancy_curvature"]*(h*h-.85))
        detection = np.column_stack([expit(p["rapid_intercept"]+p["detection_slope"]*h+
                                          (p["intensive_boost"] if method == "intensive" else 0))
                                     for method in spec["visits"]])
        return psi, detection

    @staticmethod
    def expectations(psi, detection):
        psi = np.asarray(psi)
        detection = np.asarray(detection)
        return np.column_stack([psi*detection[:,0], psi*(1-np.prod(1-detection, axis=1)),
                                psi*np.prod(detection, axis=1)])

    @staticmethod
    def sample(psi, detection, rng, panel_size=64):
        # A SINGLE latent occupancy vector is shared by every visit at a row.
        occupied = rng.random((len(psi),panel_size)) < np.asarray(psi)[:,None]
        detections = (rng.random((len(psi),panel_size,detection.shape[1])) < detection[:,None,:]) & occupied[:,:,None]
        return np.column_stack([detections[:,:,0].mean(axis=1), detections.any(axis=2).mean(axis=1),
                                detections.all(axis=2).mean(axis=1)])
