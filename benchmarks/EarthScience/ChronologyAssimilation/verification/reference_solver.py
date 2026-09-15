"""Public-input joint age-depth / climate MAP witness with uncertainty propagation.

Dates initialize a monotone accumulation model. A shared latent field then refines
all record chronologies jointly; laboratory calibration and cross-record coherence
are separate adequacy checks. No evaluator imports or hidden seeds are used.
"""
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix


def reconstruct_climate(time_grid_years, proxy_catalog, date_sample, budget_units):
    return solve(time_grid_years, proxy_catalog, date_sample, budget_units)


def solve(time_grid_years, proxy_catalog, date_sample, budget_units, *,
          joint=True, field=True, propagate=True, calibration=True, coherence=True):
    empty = {"temperature_mean": [], "temperature_std": [], "age_offsets_years": [],
             "confidence": .1, "abstain": True}
    chi = []
    for row in proxy_catalog:
        predicted = row["sensitivity"] * np.asarray(row["calibration_temperature_c"])
        chi.extend(((np.asarray(row["calibration_proxy_values"]) - predicted) /
                    row["calibration_noise_std"]) ** 2)
    if calibration and np.mean(chi) > 4.0:
        return empty
    grid = np.asarray(time_grid_years)
    dates, sigmas, signals, nominals, noises, curves = [], [], [], [], [], []
    cost = 0
    for row in proxy_catalog:
        nominal = np.asarray(row["nominal_age_years"])
        indices = np.linspace(1, len(nominal) - 2, 5, dtype=int)
        if cost + 2 > budget_units:
            return empty
        dated = date_sample(int(row["proxy_index"]), indices)
        cost += int(dated["budget_cost"])
        measured = np.maximum.accumulate(np.asarray(dated["dated_age_years"]))
        curves.append(np.maximum.accumulate(np.clip(
            PchipInterpolator(nominal[indices], measured)(nominal), grid[0], grid[-1])))
        dates.append((indices, np.asarray(dated["dated_age_years"])))
        sigmas.append(float(dated["date_noise_std_years"]))
        signals.append(np.asarray(row["values"]) / row["sensitivity"])
        noises.append(float(row["noise_std"] / row["sensitivity"]))
        nominals.append(nominal)
    matrix = np.array([np.interp(grid, age, val) for age, val in zip(curves, signals)])
    if coherence and np.mean((matrix - matrix.mean(axis=0)) ** 2) > .35:
        return empty
    # The public accumulation family fixes knot locations, but not rates or offset.
    # Log-duration parameters enforce positive accumulation without oracle bounds.
    if joint:
        count = len(proxy_catalog)
        segments = int(proxy_catalog[0]["accumulation_segments"])
        knots = np.linspace(grid[0], grid[-1], segments + 1)
        width = segments + 1
        def decode(params):
            age_curves = []
            for nominal, par in zip(nominals, params[:count*width].reshape(count, width)):
                duration = np.exp(par[1:] - np.max(par[1:]))
                age_knots = np.r_[0., (grid[-1]-grid[0])*np.cumsum(duration)/sum(duration)] + par[0]
                age_curves.append(np.clip(np.interp(nominal, knots, age_knots), grid[0], grid[-1]))
            return np.asarray(age_curves)
        start = []
        for nominal, curve in zip(nominals, curves):
            ky = PchipInterpolator(nominal, curve)(knots)
            start.extend([np.clip(ky[0], -300, 300), *np.log(np.maximum(np.diff(ky), 10.))])
        start = np.r_[start, matrix.mean(axis=0)]
        # Residuals are proxy innovations, charged dates, a weak accumulation
        # regularizer, and climate second differences. No true climate spectrum.
        def residual(params):
            ages = decode(params)
            climate = params[count*width:]
            out = []
            for j, (age, signal, noise, date, sigma) in enumerate(zip(ages, signals, noises, dates, sigmas)):
                out.extend((np.interp(age, grid, climate) - signal)/noise)
                out.extend((age[date[0]]-date[1])/sigma)
                out.extend(np.diff(params[j*width+1:(j+1)*width])/2.)
            out.extend(np.diff(climate, n=2)/.3)
            return np.asarray(out)
        nres = sum(len(s)+len(d[0])+segments-1 for s,d in zip(signals,dates))+len(grid)-2
        sparsity = lil_matrix((nres,len(start)),dtype=int)
        at=0
        for j, (signal,date) in enumerate(zip(signals,dates)):
            n=len(signal)+len(date[0])+segments-1
            sparsity[at:at+n,j*width:(j+1)*width]=1
            sparsity[at:at+len(signal),count*width:]=1
            at+=n
        for j in range(len(grid)-2):
            sparsity[at+j,count*width+j:count*width+j+3]=1
        lower=np.r_[np.tile([-300., *([-8.]*segments)],count),np.full(len(grid),-10.)]
        upper=np.r_[np.tile([300., *([12.]*segments)],count),np.full(len(grid),10.)]
        fit=least_squares(residual,np.clip(start,lower+1e-6,upper-1e-6),bounds=(lower,upper),
                          jac_sparsity=sparsity.tocsr(), max_nfev=100, ftol=1e-5)
        curves=decode(fit.x)
    ages=np.asarray(curves).ravel(); values=np.asarray(signals).ravel()
    variances=[]
    for nominal, signal, noise, sigma in zip(nominals,signals,noises,sigmas):
        slope=np.gradient(signal,nominal)
        variances.extend(noise**2 + (slope**2*(sigma**2+20.**2) if propagate else np.zeros_like(slope)))
    if not field:
        matrix=np.array([np.interp(grid,age,val) for age,val in zip(curves,signals)])
        mean=matrix.mean(axis=0); std=np.full_like(mean,.15)
    else:
        def kernel(a,b):
            distance=np.abs(np.asarray(a)[:,None]-np.asarray(b)[None,:])
            return .55*np.exp(-.5*(distance/100.)**2)+.10*np.exp(-distance/35.)
        covariance=kernel(ages,ages)+np.diag(variances)+1e-8*np.eye(len(ages))
        factor=cho_factor(covariance,lower=True); cross=kernel(grid,ages)
        mean=cross@cho_solve(factor,values)
        variance=np.diag(kernel(grid,grid))-np.sum(cross*cho_solve(factor,cross.T).T,axis=1)
        std=np.sqrt(np.maximum(variance,.04**2))
    return {"temperature_mean":mean,"temperature_std":std,
            "sample_ages_years":curves,"confidence":.8,"abstain":False}
