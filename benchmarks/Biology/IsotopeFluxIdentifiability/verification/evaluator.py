"""One-carbon condensation and full two-carbon isotopomer mass balance."""
from copy import deepcopy
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

SPECS = ((.35, .8), (0., 1.2), (.7, .3), (.22, 1.4), (.9, .55), (0., .4))


def _problem():
    return dict(reaction_ids=["feed", "condense", "forward", "reverse_1", "reverse_2", "drain"],
                stoichiometry=[[1, -2, 0, 0, 0, 0], [0, 1, -1, 1, 1, 0], [0, 0, 1, -1, -1, -1]],
                pool_ids=["A", "B", "C"], pool_sizes=[1., 1.5, 2.],
                atom_transitions={"feed": "input[0]->A[0]", "condense": "A_left[0],A_right[0]->B[0],B[1]",
                                  "forward": "B[0],B[1]->C[0],C[1]", "reverse_1": "C[0],C[1]->B[0],B[1]",
                                  "reverse_2": "C[0],C[1]->B[0],B[1]", "drain": "C->output"},
                flux_bounds={"net": [0., 1.2], "exchange_total": [0., 2.]},
                flux_parameterization=["2*v", "v", "v+x", "x1", "x2", "v"],
                identifiable_combinations={"net": "v", "exchange_total": "x=x1+x2"},
                tracer_menu={"full": 1., "half": .5}, sampling_times=[.5, 1., 2., 4., 8., 16.],
                budget_units=6, ions_per_pool=10000, observation_model="independent multinomial mass-isotope counts for B,C")


def isotopomers(problem, net, exchange, enrichment, times):
    pa, pb, pc = problem["pool_sizes"]
    def rhs(t, y):
        q = enrichment*(-np.expm1(-2*net*t/pa))
        monomer = np.array([1-q, q])
        source = np.outer(monomer, monomer).ravel()
        b, c = y[:4], y[4:]
        return np.r_[(net*source+exchange*c-(net+exchange)*b)/pb,
                     ((net+exchange)*b-(net+exchange)*c)/pc]
    initial = np.array([1., 0, 0, 0, 1., 0, 0, 0])
    result = solve_ivp(rhs, (0., max(times)), initial, t_eval=times, rtol=2e-8, atol=2e-10)
    if not result.success:
        raise RuntimeError("isotope integration failed")
    return result.y.T.reshape(-1, 2, 4)


def distributions(problem, net, exchange, enrichment, times):
    full = isotopomers(problem, net, exchange, enrichment, times)
    return np.stack([full[:, :, 0], full[:, :, 1]+full[:, :, 2], full[:, :, 3]], axis=2)


class _Lab:
    def __init__(self, index):
        self.index, self.spent, self.calls, self.violated = index, 0, 0, False

    def __call__(self, *args, **kwargs):
        # Bind arguments inside the guarded call so caught arity errors also
        # permanently invalidate the world, just like invalid values.
        try:
            return self._acquire(*args, **kwargs)
        except (TypeError, ValueError, RuntimeError):
            self.violated = True
            raise

    def _acquire(self, tracer_id, time_ids):
        if type(tracer_id) is not str or tracer_id not in ("full", "half") or not isinstance(time_ids, list) or not time_ids or any(type(i) is not int or not 0 <= i < 6 for i in time_ids) or len(set(time_ids)) != len(time_ids):
            self.violated = True
            raise ValueError("invalid trace acquisition")
        if self.spent+len(time_ids) > 6:
            self.violated = True
            raise RuntimeError("trace budget exhausted")
        self.spent += len(time_ids); self.calls += 1
        p = _problem(); order = sorted(time_ids)
        model = distributions(p, *SPECS[self.index], p["tracer_menu"][tracer_id], [p["sampling_times"][i] for i in order])
        rng = np.random.default_rng([18401, self.index, self.calls])
        values = []
        for row in model:
            values.append([rng.multinomial(10000, np.clip(dist, 0, 1)/np.clip(dist, 0, 1).sum()).tolist() for dist in row])
        lookup = dict(zip(order, values))
        return dict(time_ids=time_ids.copy(), counts=[lookup[i] for i in time_ids], ions_per_pool=10000, cost=len(time_ids))


def reference(problem, trace):
    observation = trace("full", list(range(6)))
    data = np.asarray(observation["counts"])/10000
    if np.max(1-data[:, :, 0]) < .01:
        return dict(abstain=True, fluxes={}, confidence=.99)
    def residual(theta):
        prediction = distributions(problem, *theta, 1., problem["sampling_times"])
        # Marginal binomial standard deviations, floored for boundary cells.
        return ((prediction-data)/np.sqrt(np.maximum(data*(1-data), .002))).ravel()
    fits = [least_squares(residual, start, bounds=([.001, 0.], [1.2, 2.]), max_nfev=45)
            for start in ([.25, .3], [.6, 1.2], [1., .6])]
    best = min(fits, key=lambda fit: float(fit.fun@fit.fun))
    # Local rank check is a reference heuristic, not a general profile-likelihood proof.
    singular = np.linalg.svd(best.jac, compute_uv=False)
    if singular[-1]/singular[0] < 1e-3:
        return dict(abstain=True, fluxes={}, confidence=.8)
    return dict(abstain=False, fluxes=dict(net=float(best.x[0]), exchange_total=float(best.x[1])), confidence=.9)


def _parse(out):
    if not isinstance(out, dict) or set(out) != {"abstain", "fluxes", "confidence"} or type(out["abstain"]) is not bool:
        return None
    if type(out["confidence"]) not in (int, float) or not np.isfinite(out["confidence"]) or not 0 <= out["confidence"] <= 1:
        return None
    flux = out["fluxes"]
    if not isinstance(flux, dict) or set(flux) != (set() if out["abstain"] else {"net", "exchange_total"}):
        return None
    for key, value in flux.items():
        if type(value) not in (int, float) or not np.isfinite(value) or not 0 <= value <= {"net": 1.2, "exchange_total": 2.}[key]:
            return None
    return out


def _mechanism(index, out):
    estimate = np.array([out["fluxes"]["net"], out["fluxes"]["exchange_total"]])
    truth = np.array(SPECS[index])
    return float(max(0., 1-np.mean(np.abs(estimate-truth)/np.maximum(truth, .1))/.025))


def evaluate(infer_fluxes):
    rows = []
    for index, (net, _) in enumerate(SPECS):
        lab = _Lab(index)
        try:
            out = _parse(infer_fluxes(deepcopy(_problem()), lab))
        except Exception:
            out = None
        valid = out is not None and not lab.violated
        claim = bool(valid and not out["abstain"])
        supported = net > 0
        mechanism = _mechanism(index, out) if supported and claim else 0.
        refusal = float(valid and out["abstain"] and not supported)
        correct = mechanism >= .5 if supported and claim else bool(refusal)
        rows.append(dict(valid=valid, supported=supported, claim=int(claim), false_positive=int(claim and not supported),
                         mechanism=mechanism, scientific=mechanism if supported else refusal, refusal=refusal, cost=lab.spent,
                         calibration=(out["confidence"]-float(correct))**2 if valid else 1.))
    dev, held = rows[:3], rows[3:]
    return dict(combined_score=float(max(0., (np.mean([r["scientific"] for r in dev])-1/3)/(2/3))),
                valid=float(all(r["valid"] for r in rows)), development_mechanism_score=float(np.mean([r["mechanism"] for r in dev if r["supported"]])),
                development_false_discovery_count=sum(r["false_positive"] for r in dev), development_claim_count=sum(r["claim"] for r in dev),
                development_false_discovery_rate=sum(r["false_positive"] for r in dev)/max(1, sum(r["claim"] for r in dev)),
                development_correct_refusal_rate=float(np.mean([r["refusal"] for r in dev if not r["supported"]])),
                development_discovery_coverage=float(np.mean([r["claim"] for r in dev if r["supported"]])),
                development_brier_loss=float(np.mean([r["calibration"] for r in dev])),
                heldout_scientific_score=float(np.mean([r["scientific"] for r in held])), per_world=rows)
