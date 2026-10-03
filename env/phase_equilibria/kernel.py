"""Trusted synthetic phase populations and diffraction. Never candidate-mounted."""
import hashlib
import math
import numpy as np

STRUCTURES = ('two_terminal_phases', 'one_intermediate', 'two_intermediates')


def random_generator(seed, tag):
    payload = ('phase_equilibria-v1:%d:%s' % (seed, tag)).encode()
    return np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:16], 'big'))


def generate(seed, structure):
    rng = random_generator(seed, 'parameters-' + structure)
    interiors = {'two_terminal_phases': [], 'one_intermediate': [float(rng.uniform(.35, .65))],
                 'two_intermediates': [float(rng.uniform(.25, .4)), float(rng.uniform(.6, .75))]}[structure]
    compositions = np.asarray([0.] + interiors + [1.])
    energy_scale = float(rng.uniform(.7, 1.3))
    energies = -energy_scale*compositions*(1-compositions)
    # Distinct and overlapping peaks are allowed. No rejection loop or unique-signature oracle.
    centers = rng.uniform(15, 85, size=(len(compositions), 5))
    heights = rng.uniform(.3, .95, size=centers.shape)
    widths = rng.uniform(.5, .9, size=centers.shape)
    return {'compositions': compositions, 'energies': energies, 'centers': centers,
            'heights': heights, 'widths': widths, 'holder_centers': rng.uniform(18, 82, size=2),
            'holder_heights': rng.uniform(.025, .07, size=2), 'offset': float(rng.uniform(.003, .012)),
            'slope': float(rng.uniform(-.002, .002)), 'tau_fast': float(rng.uniform(5, 12)),
            'tau_slow': float(rng.uniform(25, 50)), 'slow_weight': float(rng.uniform(.15, .45)),
            'rate_center': float(rng.uniform(.3, .7)), 'rate_curve': float(rng.uniform(1, 3)),
            'amorphous_centers': rng.uniform([29, 49], [41, 64]),
            'amorphous_heights': rng.uniform(.1, .2, size=2)}


def gaussian_pattern(angles, centers, heights, widths):
    angles = np.asarray(angles, float)
    return np.exp(-.5*((angles[:, None]-np.asarray(centers)[None, :])/np.asarray(widths))**2).dot(heights)


class Kernel:
    def __init__(self, parameters):
        self.p = parameters

    def equilibrium_weights(self, composition):
        c = self.p['compositions']
        result = np.zeros(len(c))
        if composition >= c[-1]:
            result[-1] = 1.
        else:
            left = max(0, int(np.searchsorted(c, composition, side='right'))-1)
            fraction = (composition-c[left])/(c[left+1]-c[left])
            result[left], result[left+1] = 1-fraction, fraction
        return result

    def rates(self, composition):
        factor = 1 + self.p['rate_curve']*(composition-self.p['rate_center'])**2
        return factor/self.p['tau_fast'], factor/self.p['tau_slow']

    def residual_fraction(self, composition, hold_time):
        fast, slow = self.rates(composition)
        weight = self.p['slow_weight']
        return (1-weight)*math.exp(-fast*hold_time) + weight*math.exp(-slow*hold_time)

    def populations(self, composition, hold_time, preparation):
        eq = self.equilibrium_weights(composition)
        residual = self.residual_fraction(composition, hold_time)
        crystal = (1-residual)*eq
        amorphous = 0.
        if preparation == 'powder_blend':
            crystal[0] += residual*(1-composition)
            crystal[-1] += residual*composition
        else:
            amorphous = residual
        return crystal, amorphous

    def spectrum(self, spec):
        p, angles = self.p, np.asarray(spec['angles_deg'])
        x = spec['composition']
        crystal, amorphous = self.populations(x, spec['hold_time'], spec['preparation'])
        intensity = np.zeros(len(angles))
        for fraction, centers, heights, widths in zip(crystal, p['centers'], p['heights'], p['widths']):
            intensity += fraction*gaussian_pattern(angles, centers, heights, widths)
        # The amorphous reservoir has the same composition x as the whole sample.
        precursor = gaussian_pattern(angles, p['amorphous_centers'] + [3*x, -2*x],
                                     p['amorphous_heights'] * [1-.3*x, .7+.3*x], [5., 7.])
        sample = intensity + amorphous*precursor
        holder = p['offset'] + p['slope']*(angles-50)/40
        holder += gaussian_pattern(angles, p['holder_centers'], p['holder_heights'], [.65, .65])
        return (spec['loading']*sample + holder)[:, None]
