"""Prototype prospective uncertainty; no shared-runner admission implied.

For predeclared scalar mean contrasts, independent additive Gaussian readouts,
and equal replication per arm. No process noise, clipping or parameter uncertainty.
Repeated keys are not independent replicates. Adaptive readout selection is outside
this contract. Bonferroni protects a fixed declared family without assuming
independence between its contrasts.
"""
import math
from env.prototype_history import real
from scipy.stats import norm


def contrast_uncertainty(replicates,comparisons=1,alpha=.05):
    if type(replicates) is not int or not 2<=replicates<=128:
        raise ValueError('replicates per arm must be integer 2..128')
    if type(comparisons) is not int or not 1<=comparisons<=64:
        raise ValueError('predeclared comparisons must be integer 1..64')
    alpha=real(alpha,1e-6,.2,'alpha')
    se=.002*math.sqrt(2./replicates)
    return {'standard_error':se,'half_width':float(norm.isf(alpha/(2*comparisons))*se),
            'readout_noise_std':.002,'mean_bias_bound':0.,
            'observations_required':2*replicates,
            'scope':'mean of treatment minus control; independent fresh readout noise only; fixed predeclared comparison family'}
