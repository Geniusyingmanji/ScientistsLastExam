"""Candidate-facing apparatus contract; private phase recipes are not imported."""
import math
import numbers
import numpy as np

VERSION = 'phase_equilibria-0.1.0-experimental'
AXIS_FIELD = 'angles_deg'
CHANNELS = ('intensity',)
SCALES = (1.0,)
NOISE_STD = (0.003,)


def integer(value, name, low=0, high=2**63-1):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or not low <= int(value) <= high:
        raise ValueError('%s must be an integer in [%d, %d]' % (name, low, high))
    return int(value)


def number(value, low, high, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise ValueError('%s must be a finite real number' % name)
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ValueError('%s must be a finite real number' % name) from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError('%s must lie in [%g, %g]' % (name, low, high))
    return value


def validate_spec(spec):
    required = {'composition', 'hold_time', 'preparation', AXIS_FIELD}
    if not isinstance(spec, dict) or not required <= set(spec) or set(spec)-required-{'loading'}:
        raise ValueError('expected composition, hold_time, preparation, angles_deg and optional loading')
    preparation = spec['preparation']
    if not isinstance(preparation, str) or preparation not in ('powder_blend', 'quenched'):
        raise ValueError('preparation must be powder_blend or quenched')
    angles = spec[AXIS_FIELD]
    if not isinstance(angles, list) or not 1 <= len(angles) <= 241:
        raise ValueError('angles_deg must list 1..241 angles')
    angles = [number(v, 10, 90, 'angle') for v in angles]
    if any(b <= a for a, b in zip(angles, angles[1:])):
        raise ValueError('angles_deg must be strictly increasing')
    return {'composition': number(spec['composition'], 0, 1, 'composition'),
            'hold_time': number(spec['hold_time'], 0, 120, 'hold_time'),
            'preparation': preparation, 'loading': number(spec.get('loading', 1), 0, 1, 'loading'),
            AXIS_FIELD: angles}


def example():
    return {'composition': .45, 'hold_time': 40, 'preparation': 'powder_blend',
            'loading': 1, AXIS_FIELD: [float(v) for v in range(10, 91)]}


def describe():
    return {'name': 'phase_equilibria', 'version': VERSION,
            'research_prompt': 'Investigate a sealed binary material using controlled composition, preparation, waiting and powder diffraction. Develop quantitative accounts of the spectra, test predictions on new preparations or compositions, and state what remains unresolved.',
            'channels': list(CHANNELS), 'scales': list(SCALES), 'noise_std': list(NOISE_STD),
            'axis': {'name': 'scattering angle', 'unit': 'degrees two-theta', 'rows': 'requested angles_deg'},
            'units': {'composition': 'mole fraction of component B on a common formula-unit basis',
                      'hold_time': 'apparatus time units', 'loading': 'relative formula-unit amount',
                      'intensity': 'calibrated arbitrary diffraction units'},
            'semantics': [
                'Each call prepares a fresh sample. The material and apparatus remain fixed within an instance. No material is carried between calls; no hidden call-order state exists.',
                'composition sets total B fraction and remains conserved during the hold at a fixed apparatus temperature. loading scales sample amount; zero loading measures the empty holder. Loading does not change the preparation or hold dynamics.',
                'powder_blend starts from separate crystalline pure-A and pure-B powders in the requested proportion. quenched starts from a homogeneous noncrystalline precursor of the requested composition. Their diffraction signatures are measured, not supplied.',
                'hold_time is elapsed time from the stated preparation to an instantaneous non-destructive scan. Every angle in a call describes that same sample age; angle ordering has no physical time meaning. Inserting angles does not change the sample or instrument.',
                'The response is a continuous intensity at each requested angle, not a list of detected peaks. The instrument adds independent zero-mean Gaussian noise of standard deviation 0.003 to each requested intensity. Noise is not clipped and negative readings can occur. There is no stochastic synthesis variation in this version.',
                'Scans include a fixed apparatus contribution independent of sample loading. Peak positions, shapes and amplitudes are not supplied. Repeated calls with identical controls reproduce the same clean signal with fresh readout noise.',
                'No readout is assigned by the controls: even time-zero and empty-holder spectra must be measured. A finite observation window and indistinguishable spectra can leave microscopic structure or limiting states unresolved.'
            ],
            'schema': {'required': ['composition', 'hold_time', 'preparation', AXIS_FIELD],
                       'optional': {'loading': 1}, 'additional_fields': False,
                       'composition': {'range': [0, 1]}, 'hold_time': {'range': [0, 120]},
                       'preparation': ['powder_blend', 'quenched'], 'loading': {'range': [0, 1]},
                       AXIS_FIELD: {'range': [10, 90], 'length': [1, 241], 'order': 'strictly increasing'},
                       'validation': 'Finite real numbers only; booleans, unknown fields and repeated angles are rejected.'},
            'cost': '8 + ceil(number of angles/8) + ceil(hold_time/10); maximum 51',
            'examples': [example(), {'composition': .45, 'hold_time': 0, 'preparation': 'quenched', 'loading': 0,
                                     AXIS_FIELD: [10, 20, 30, 40, 50, 60, 70, 80, 90]}],
            'limitations': 'Synthetic isothermal binary instrument, not calibrated materials data. No temperature control, texture, stochastic impurities, shot noise, peak-detection threshold or physical crystallographic structure solution. Finite-time convergence cannot prove thermodynamic equilibrium or a unique phase identity.'}
