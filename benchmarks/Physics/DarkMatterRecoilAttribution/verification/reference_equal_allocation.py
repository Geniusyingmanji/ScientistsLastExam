"""Truth-blind profiled Poisson fit. Imports no evaluator or repository data."""
import numpy as np
from scipy.optimize import least_squares
from scipy.special import xlogy


def infer_recoil(problem, experiment, *, ablation=None):
    observations = [experiment({"target": t, "units": 1 if ablation == "one_unit" else problem["budget_units"] // 3})
                    for t in range(3)]
    energies = np.array(problem["energy_kev"])
    widths = np.array(problem["bin_widths_kev"])
    speeds = np.array(problem["speed_components_kms"])
    exposure = np.array([o["units"] for o in observations])[:, None]
    counts = np.array([o["counts"] for o in observations])
    control = np.array([o["background_counts"] for o in observations])
    cal = np.array([o["calibration_counts"] for o in observations])
    gains = cal / (problem["calibration_rate"] * exposure[:, 0])
    if ablation == "ignore_gain":
        gains = np.ones(3)
    # Estimate background from controls; jointly profile its amplitude below.
    shape = widths * np.exp(-energies / problem["background_scale_kev"])
    flat = widths * problem["flat_background_rate"]
    factor = problem["background_control_factor"]
    b0 = np.maximum(0.2, np.mean(control / (factor * exposure * gains[:, None]) - flat, axis=1) / shape.mean())

    def kernel(mass, ratio, power):
        out = []
        for target in problem["targets"]:
            a, z = target["mass_number"], target["protons"]
            nucleus = .9315 * a
            reduced = mass * nucleus / (mass + nucleus)
            q = np.sqrt(2 * nucleus * energies * 1e-6)
            vmin = 299792.458 * q / (2 * reduced)
            form = np.exp(-(q * (1.2 * a ** (1/3)) / .1973269804) ** 2 / 3)
            eta = np.exp(-(vmin[:, None] / speeds) ** 2) * (260 / speeds)
            out.append(widths[:, None] * ((z + (a-z)*ratio)/100)**2 * form[:, None] *
                       (q[:, None]/problem["reference_momentum_gev"])**power * eta)
        return np.array(out)

    def residual(x, power):
        fit_gains = np.ones(3) if ablation == "ignore_gain" else x[8:11]
        background = x[5:8, None] * shape + flat
        weights = np.repeat(np.mean(x[2:5]), 3) if ablation == "fixed_halo" else x[2:5]
        signal = np.einsum('tbk,k->tb', kernel(np.exp(x[0]), x[1], power), weights)
        mean = fit_gains[:, None] * exposure * (signal + background)
        mean_c = fit_gains[:, None] * exposure * factor * background
        mean_cal = fit_gains * exposure[:, 0] * problem["calibration_rate"]
        pred = np.concatenate([mean.ravel(), mean_c.ravel(), mean_cal])
        obs = np.concatenate([counts.ravel(), control.ravel(), cal])
        pred = np.maximum(pred, 1e-9)
        return np.sign(obs-pred) * np.sqrt(np.maximum(0, 2*(xlogy(obs, obs/pred)-obs+pred)))

    background = b0[:, None] * shape + flat
    null_mean = gains[:, None] * exposure * background
    null_dev = 2 * np.sum(xlogy(counts, counts/np.maximum(null_mean, 1e-9))-counts+null_mean)
    if null_dev < counts.size + 5 * np.sqrt(2*counts.size):
        return {"model": "none", "confidence": .8}
    fits = []
    lo = [np.log(10), .5, 0, 0, 0, .01, .01, .01, .4, .4, .4]
    hi = [np.log(250), 1.5, 300, 300, 300, 40, 40, 40, 1.8, 1.8, 1.8]
    for model, power in (("contact", 0), ("q2", 2)):
        for mass in (25, 55, 110):
            x0 = [np.log(mass), 1, 25, 25, 25, *b0, *gains]
            fit = least_squares(residual, x0, bounds=(lo, hi), args=(power,),
                                max_nfev=140, ftol=1e-6, xtol=1e-6, gtol=1e-6)
            fits.append((float(fit.fun @ fit.fun), model, float(np.exp(fit.x[0]))))
    fits.sort()
    best = fits[0]
    runner = min(v[0] for v in fits if v[1] != best[1])
    dof = counts.size * 2 + 3 - 11
    if best[0] > dof + 5*np.sqrt(2*dof) or runner-best[0] < 6:
        return {"abstain": True, "confidence": .7}
    return {"model": best[1], "mass_gev": best[2], "confidence": .8}
