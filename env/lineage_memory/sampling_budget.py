"""Conservative planning bound, not a power calculation or calibrated task score."""
import math


def contrast_plan(precision, group_size=32, alpha=.05):
    """Compare independent grouping arms using squared within-pair differences.

    Under identical marginals, Z=(D_control-D_treatment)/2 has mean equal
    to the covariance increase and range [-.5,.5]. Independent pair draws
    give a two-sided Hoeffding radius. No known population mean is required.
    Precision is a desired interval radius, not guaranteed detection power.
    """
    if type(group_size) is not int or not 1 <= group_size <= 256:
        raise ValueError('group_size must be integer 1..256')
    for x in (precision, alpha):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
            raise ValueError('finite real design values required')
    if not .0001 <= precision <= .5 or not 0 < alpha < 1:
        raise ValueError('design values outside supported range')
    pairs = math.ceil(math.log(2 / alpha) / (2 * precision ** 2))
    return {'pairs_per_arm': pairs, 'arms': 2, 'group_size': group_size,
            'simulated_individuals': 4 * group_size * pairs,
            'confidence_radius_bound': math.sqrt(math.log(2 / alpha) / (2 * pairs)),
            'fits_single_kernel_call_per_arm': pairs <= 20000,
            'scope': 'Identical marginals and independent pairs required; fixed single contrast only; not power.'}
