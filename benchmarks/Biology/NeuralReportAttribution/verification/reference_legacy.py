"""Truth-blind nonlinear frequency-response fit, with calibrated sensor nuisance."""
import numpy as np
from scipy.optimize import least_squares


def infer_circuit(problem, experiment, *, ablation=None):
    calibrations, responses = [], []
    for report in (0, 1):
        calibration_units = 1 if ablation in ("one_unit", "six_units") else 2
        cal = experiment({"kind": "calibration", "report": report, "frequency": 0, "units": calibration_units})
        calibrations.append([np.array(cal[k]) for k in
                             ("sensor_mixing", "actuator_mixing", "feedthrough", "sensor_time_constants")])
        schedule = ((0, 1), (3, 1)) if ablation == "six_units" else ((0, 1), (1, 2), (2, 1), (3, 1))
        for f, units in schedule:
            if ablation == "one_unit":
                units = 1
            data = experiment({"kind": "response", "report": report, "frequency": f, "units": units})
            responses.append((report, problem["angular_frequencies"][f], units,
                              np.array(data["real"])+1j*np.array(data["imag"])))

    calibration_vector = np.concatenate([np.concatenate([a.ravel() for a in c]) for c in calibrations])

    def residual(x, model):
        tau = x[:4]
        a, b, local, feed, feedback, report_feedback = x[4:10]
        if model == "report_only":
            feedback = 0.
        if model == "none":
            a=b=local=feed=feedback=report_feedback=0.
        result = []
        for report, omega, units, obs in responses:
            matrix = np.diag(-1/tau)
            matrix[1,0],matrix[2,1],matrix[0,1],matrix[3,2] = a,b,local,feed
            matrix[1,2],matrix[1,3] = feedback,report*report_feedback
            values = x[10+52*report:10+52*(report+1)]
            c = values[:16].reshape(4,4)
            stim = values[16:32].reshape(4,4)
            direct = values[32:48].reshape(4,4)
            sensor_tau = values[48:52]
            if ablation == "ignore_instruments":
                c, stim, direct, sensor_tau = np.eye(4), np.eye(4), np.zeros((4,4)), np.zeros(4)
            h = (c @ np.linalg.inv(1j*omega*np.eye(4)-matrix) @ stim)/(1+1j*omega*sensor_tau[:,None])+direct
            error = (h-obs)*np.sqrt(units)/problem["measurement_noise_sd"]
            result.extend(error.real.ravel())
            result.extend(error.imag.ravel())
        result.extend((x[10:]-calibration_vector)/(problem["calibration_noise_sd"]/np.sqrt(calibration_units)))
        return np.array(result)

    fits = []
    lower = np.array([.25]*4+[0]*6+[-3]*104)
    upper = np.array([.8]*4+[1.2]*6+[3]*104)
    for report in (0, 1):
        lower[58+52*report:62+52*report] = .001
        upper[58+52*report:62+52*report] = 1.
    models = ("recurrent",) if ablation == "no_model_selection" else ("none", "report_only", "recurrent")
    for model in models:
        x0 = np.concatenate([[.5]*4+[.5,.5,.2,.6,.3,.4], calibration_vector])
        x0 = np.clip(x0, lower+1e-8, upper-1e-8)
        fit = least_squares(residual, x0, bounds=(lower, upper),
                            args=(model,), max_nfev=140, ftol=1e-6, xtol=1e-6, gtol=1e-6)
        # Joint likelihood includes calibration noise instead of treating it as exact.
        deviance = float(fit.fun @ fit.fun)
        parameters = {"none":4,"report_only":9,"recurrent":10}[model]
        fits.append((deviance+parameters*np.log(len(fit.fun)), deviance, model, fit.x))
    fits.sort(key=lambda item:item[0])
    _, error, model, x = fits[0]
    if error > 420 and ablation != "never_abstain":
        return {"abstain": True, "confidence": .75}
    if model == "none":
        return {"model":"none","confidence":.8}
    if model == "recurrent" and x[8] < problem["minimum_feedback"] and ablation != "never_abstain":
        return {"abstain": True,"confidence":.7}
    return {"model":model,"feedback":float(x[8]) if model=="recurrent" else 0.,
            "report_feedback":float(x[9]),"confidence":.8}
