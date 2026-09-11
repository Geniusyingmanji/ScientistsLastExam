"""Public-input-only joint Gaussian fit with exact derivatives and algebraic starts.

No latent parameters or evaluator imports. The calibration uncertainty remains in
the likelihood, and each hypothesis optimizes only its active parameters.
"""
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import chi2


def response_and_jacobian(x, report, omega):
    """Public transfer equation and derivatives with respect to 114 real parameters."""
    edges = ((1, 0), (2, 1), (0, 1), (3, 2), (1, 2), (1, 3))
    a = np.diag(-1 / x[:4])
    for j, (row, col) in enumerate(edges):
        a[row, col] = x[4+j] * (report if j == 5 else 1)
    offset = 10 + 52*report
    v = x[offset:offset+52]
    c, b, d = [v[k:k+16].reshape(4, 4) for k in (0, 16, 32)]
    low = 1 / (1 + 1j*omega*v[48:52])
    r = np.linalg.inv(1j*omega*np.eye(4) - a)
    left, right = low[:, None]*(c @ r), r @ b
    core = c @ right
    h = low[:, None]*core + d
    jac = np.zeros((4, 4, 114), complex)
    for j in range(4):
        jac[:, :, j] = np.outer(left[:, j], right[j]) / x[j]**2
    for j, (row, col) in enumerate(edges):
        jac[:, :, 4+j] = np.outer(left[:, row], right[col]) * (report if j == 5 else 1)
    for row in range(4):
        for col in range(4):
            j = 4*row + col
            jac[row, :, offset+j] = low[row]*right[col]
            jac[:, col, offset+16+j] = left[:, row]
            jac[row, col, offset+32+j] = 1
        jac[row, :, offset+48+row] = -1j*omega*low[row]**2*core[row]
    return h, jac.reshape(16, 114)


def algebraic_initial(problem, calibrations, responses):
    """Project measured inverse responses onto the publicly specified graph."""
    estimates = []
    for report, omega, units, observed in responses:
        c, b, d, tau = calibrations[report]
        try:
            neural = np.linalg.solve(c, (observed-d)*(1+1j*omega*tau[:, None])) @ np.linalg.inv(b)
            a = (1j*omega*np.eye(4) - np.linalg.inv(neural)).real
        except np.linalg.LinAlgError:
            continue
        if np.isfinite(a).all():
            estimates.append((report, units, a))
    if not estimates:
        return np.array([.5]*4 + [.5, .5, .2, .6, .3, .4])
    mean = np.average([a for _, _, a in estimates], axis=0, weights=[u for _, u, _ in estimates])
    report_rows = [(u, a[1, 3]) for s, u, a in estimates if s == 1]
    report_edge = np.average([v for _, v in report_rows], weights=[u for u, _ in report_rows]) if report_rows else .4
    return np.r_[np.clip(-1/np.minimum(np.diag(mean), -1e-6), *problem['time_constant_bounds']),
                 np.clip([mean[1, 0], mean[2, 1], mean[0, 1], mean[3, 2], mean[1, 2], report_edge],
                         *problem['edge_bounds'])]


def infer_circuit(problem, experiment, *, ablation=None):
    calibrations, responses, calibration_units = [], [], []
    for report in problem['report_conditions']:
        n = 1 if ablation in ('one_unit', 'six_units') else 2
        cal = experiment(dict(kind='calibration', report=report, frequency=0, units=n))
        calibrations.append([np.asarray(cal[k]) for k in
                             ('sensor_mixing', 'actuator_mixing', 'feedthrough', 'sensor_time_constants')])
        calibration_units.append(n)
        schedule = ((0, 1), (3, 1)) if ablation == 'six_units' else ((0, 1), (1, 2), (2, 1), (3, 1))
        for frequency, units in schedule:
            units = 1 if ablation == 'one_unit' else units
            data = experiment(dict(kind='response', report=report, frequency=frequency, units=units))
            responses.append((report, problem['angular_frequencies'][frequency], units,
                              np.asarray(data['real']) + 1j*np.asarray(data['imag'])))
    cal_vector = np.concatenate([np.concatenate([a.ravel() for a in c]) for c in calibrations])
    cal_sd = np.repeat(problem['calibration_noise_sd']/np.sqrt(calibration_units), 52)
    lower = np.r_[[problem['time_constant_bounds'][0]]*4, [problem['edge_bounds'][0]]*6, [-3.]*104]
    upper = np.r_[[problem['time_constant_bounds'][1]]*4, [problem['edge_bounds'][1]]*6, [3.]*104]
    for report in (0, 1):
        lower[58+52*report:62+52*report] = .001
        upper[58+52*report:62+52*report] = 1.
    guesses = [algebraic_initial(problem, calibrations, responses),
               np.array([.5]*4 + [.5, .5, .2, .6, .3, .4])]
    if ablation == 'midpoint_only':
        guesses = guesses[1:]
    joint = ablation not in ('ignore_instruments', 'fixed_calibration')
    models = ('recurrent',) if ablation == 'no_model_selection' else ('none', 'report_only', 'recurrent')
    fits = []
    for model in models:
        circuit = list(range(4)) if model == 'none' else [j for j in range(10) if j != 8 or model == 'recurrent']
        active = np.array(circuit + (list(range(10, 114)) if joint else []))
        template = np.r_[np.zeros(10), cal_vector]
        if ablation == 'ignore_instruments':
            template[10:] = np.tile(np.r_[np.eye(4).ravel(), np.eye(4).ravel(), np.zeros(20)], 2)
        cache = {}

        def compute(z):
            if 'z' in cache and np.array_equal(z, cache['z']):
                return cache['residual'], cache['jacobian']
            x = template.copy()
            x[active] = z
            errors, derivatives = [], []
            for report, omega, units, observed in responses:
                h, jac = response_and_jacobian(x, report, omega)
                scale = np.sqrt(units)/problem['measurement_noise_sd']
                error = (h-observed).ravel()*scale
                errors.extend((error.real, error.imag))
                derivatives.extend((jac.real[:, active]*scale, jac.imag[:, active]*scale))
            if joint:
                errors.append((x[10:]-cal_vector)/cal_sd)
                derivatives.append(np.eye(114)[10:, active]/cal_sd[:, None])
            result = np.concatenate(errors), np.vstack(derivatives)
            cache.update(z=z.copy(), residual=result[0], jacobian=result[1])
            return result

        best = None
        for guess in guesses:
            initial = np.r_[guess, cal_vector]
            z0 = np.clip(initial[active], lower[active]+1e-8, upper[active]-1e-8)
            fit = least_squares(lambda z: compute(z)[0], z0, jac=lambda z: compute(z)[1],
                                bounds=(lower[active], upper[active]), x_scale='jac',
                                max_nfev=250, ftol=1e-8, xtol=1e-8, gtol=1e-8)
            deviance = float(fit.fun @ fit.fun)
            if np.isfinite(deviance) and (best is None or deviance < best[0]):
                x = template.copy()
                x[active] = fit.x
                best = deviance, x, len(fit.fun)
        if best is not None:
            deviance, x, n = best
            fits.append((deviance+len(active)*np.log(n), deviance, model, x, n-len(active)))
    if not fits:
        return {'abstain': True, 'confidence': 0.}
    fits.sort(key=lambda item: item[0])
    _, deviance, model, x, dof = fits[0]
    # A fixed 0.1% residual tail check uses the actual observation/parameter count.
    if deviance > chi2.isf(.001, max(1, dof)) and ablation != 'never_abstain':
        return {'abstain': True, 'confidence': .75}
    if model == 'none':
        return {'model': 'none', 'confidence': .8}
    if model == 'recurrent' and x[8] < problem['minimum_feedback'] and ablation != 'never_abstain':
        return {'abstain': True, 'confidence': .7}
    return {'model': model, 'feedback': float(x[8]) if model == 'recurrent' else 0.,
            'report_feedback': float(x[9]), 'confidence': .8}
