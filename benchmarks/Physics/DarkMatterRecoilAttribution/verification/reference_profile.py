"""Joint Poisson fit with a pilot and nuisance-profiled Fisher exposure allocation.

Uses only public settings and paid counts. The one-unit pilot on every target
chooses the remaining exposure allocation by estimated log-mass information,
not by a world identifier or a precomputed answer table.
"""
import numpy as np
from scipy.optimize import least_squares
from scipy.special import xlogy


def unit_means(problem, x, power, ablation=None):
    energy = np.asarray(problem['energy_kev'])
    widths = np.asarray(problem['bin_widths_kev'])
    speeds = np.asarray(problem['speed_components_kms'])
    mass, ratio = np.exp(x[0]), x[1]
    weights = np.full(3, np.mean(x[2:5])) if ablation == 'fixed_halo' else x[2:5]
    gains = np.ones(3) if ablation == 'ignore_gain' else x[8:11]
    predictions = []
    for t, target in enumerate(problem['targets']):
        a, z = target['mass_number'], target['protons']
        nucleus = .9315*a
        reduced = mass*nucleus/(mass+nucleus)
        q = np.sqrt(2*nucleus*energy*1e-6)
        vmin = 299792.458*q/(2*reduced)
        form = np.exp(-(q*(1.2*a**(1/3))/.1973269804)**2/3)
        eta = np.exp(-(vmin[:, None]/speeds)**2)*(260/speeds)
        kernel = (widths*((z+(a-z)*ratio)/100)**2*form*
                  (q/problem['reference_momentum_gev'])**power)[:, None]*eta
        background = widths*(x[5+t]*np.exp(-energy/problem['background_scale_kev']) + problem['flat_background_rate'])
        predictions.append(np.r_[gains[t]*(kernel @ weights+background),
                                  gains[t]*problem['background_control_factor']*background,
                                  gains[t]*problem['calibration_rate']])
    return np.asarray(predictions)


def fit_observations(problem, observations, ablation=None):
    counts = np.asarray([o['counts'] for o in observations])
    controls = np.asarray([o['background_counts'] for o in observations])
    calibration = np.asarray([o['calibration_counts'] for o in observations])
    exposure = np.asarray([o['units'] for o in observations])
    observed = np.column_stack((counts, controls, calibration))
    energy, widths = np.asarray(problem['energy_kev']), np.asarray(problem['bin_widths_kev'])
    gains = calibration/(problem['calibration_rate']*exposure)
    if ablation == 'ignore_gain':
        gains = np.ones(3)
    shape = widths*np.exp(-energy/problem['background_scale_kev'])
    flat = widths*problem['flat_background_rate']
    beta = np.maximum(.2, np.mean(controls/(problem['background_control_factor']*exposure[:, None]*gains[:, None])-flat, axis=1)/shape.mean())
    lower = np.r_[np.log(problem['mass_bounds_gev'][0]), problem['coupling_ratio_bounds'][0], [0]*3, [.01]*3, [.4]*3]
    upper = np.r_[np.log(problem['mass_bounds_gev'][1]), problem['coupling_ratio_bounds'][1], [300]*3, [40]*3, [1.8]*3]

    def residual(x, power):
        prediction = np.maximum(unit_means(problem, x, power, ablation)*exposure[:, None], 1e-9)
        return (np.sign(observed-prediction)*np.sqrt(np.maximum(0, 2*(xlogy(observed, observed/prediction)-observed+prediction)))).ravel()

    background = beta[:, None]*shape + flat
    null_mean = gains[:, None]*exposure[:, None]*background
    null_deviance = 2*np.sum(xlogy(counts, counts/np.maximum(null_mean, 1e-9))-counts+null_mean)
    fits = []
    for model, power in (('contact', 0), ('q2', 2)):
        for mass in (25, 55, 110):
            initial = np.clip(np.r_[np.log(mass), 1, [25]*3, beta, gains], lower+1e-8, upper-1e-8)
            fit = least_squares(residual, initial, bounds=(lower, upper), args=(power,),
                                max_nfev=140, ftol=1e-6, xtol=1e-6, gtol=1e-6)
            fits.append((float(fit.fun @ fit.fun), model, fit.x))
    fits.sort(key=lambda item: item[0])
    return fits, null_deviance


def allocate_remaining(problem, fits, budget, ablation=None):
    """Greedy local c-optimal design for log mass, profiling all fitted nuisances."""
    # Include both fitted laws rather than trusting the pilot's discrete decision.
    representatives = [next(f for f in fits if f[1] == model) for model in ('contact', 'q2')]
    weights = np.exp(-.5*np.minimum(100, [f[0]-fits[0][0] for f in representatives]))
    weights /= weights.sum()
    information = []
    for _, model, x in representatives:
        power = 0 if model == 'contact' else 2
        mean = np.maximum(unit_means(problem, x, power, ablation), 1e-9)
        derivatives = []
        for j in range(len(x)):
            step = 1e-5*max(1, abs(x[j]))
            delta = np.zeros_like(x)
            delta[j] = step
            derivatives.append((unit_means(problem, x+delta, power, ablation)-
                                unit_means(problem, x-delta, power, ablation))/(2*step))
        jac = np.stack(derivatives, axis=-1)
        # Scaling nuisance columns does not change the mass Schur complement,
        # and improves conditioning of the information calculation.
        scale = np.maximum(np.abs(x), 1.)
        scale[0] = 1.
        jac *= scale
        information.append(np.einsum('tbi,tbj,tb->tij', jac, jac, 1/mean))
    allocation = np.ones(3, dtype=int)
    for _ in range(budget-3):
        losses = []
        for target in range(3):
            proposed = allocation.copy()
            proposed[target] += 1
            variance = 0.
            for weight, info in zip(weights, information):
                fisher = np.einsum('t,tij->ij', proposed, info)
                nuisance = fisher[1:, 1:]
                effective = fisher[0, 0] - fisher[0, 1:] @ np.linalg.pinv(nuisance, rcond=1e-12) @ fisher[1:, 0]
                variance += weight/max(float(effective), 1e-12)
            losses.append(variance)
        allocation[int(np.argmin(losses))] += 1
    return allocation


def infer_recoil(problem, experiment, *, ablation=None):
    observations = [experiment({'target': t, 'units': 1}) for t in range(3)]
    fits, null_deviance = fit_observations(problem, observations, ablation)
    if ablation != 'one_unit':
        allocation = (np.full(3, problem['budget_units']//3) if ablation == 'equal_allocation'
                      else allocate_remaining(problem, fits, problem['budget_units'], ablation))
        for t, units in enumerate(allocation):
            if units > 1:
                additional = experiment({'target': t, 'units': int(units-1)})
                for key in ('counts', 'background_counts', 'calibration_counts'):
                    observations[t][key] = (np.asarray(observations[t][key])+additional[key]).tolist()
                observations[t]['units'] += int(units-1)
        fits, null_deviance = fit_observations(problem, observations, ablation)
    bins = len(problem['energy_kev'])*3
    if null_deviance < bins+5*np.sqrt(2*bins):
        return {'model': 'none', 'confidence': .8}
    deviance, model, x = fits[0]
    runner = min(f[0] for f in fits if f[1] != model)
    dof = 2*bins+3-11
    if deviance > dof+5*np.sqrt(2*dof) or runner-deviance < 6:
        return {'abstain': True, 'confidence': .7}
    return {'model': model, 'mass_gev': float(np.exp(x[0])), 'confidence': .8}
