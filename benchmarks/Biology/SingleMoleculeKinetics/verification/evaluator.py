"""Two-state CTMC and Poisson photon observations with charged acquisition."""
from copy import deepcopy
import numpy as np
from scipy.linalg import expm
from scipy.special import gammaln

SPECS = (("supported", .7, 1.4, .18, .78), ("null", 0., 0., .5, .5),
         ("alias", 1.7, .4, .5, .5), ("supported", 1.6, .6, .25, .85),
         ("supported", .45, 1.8, .22, .72), ("alias", .3, 2., .5, .5),
         ("null", 0., 0., .5, .5), ("supported", 1.9, .8, .3, .8))


def transition(rates, dt):
    a, b = rates
    return expm(np.array([[-a, a], [b, -b]])*dt)


def _problem():
    return dict(model_family="two_state_instantaneous_poisson", parameter_bounds=dict(rates=[.1, 3.], efficiencies=[.05, .95]),
                exposure_menu=[.1, .2, .4], trace_length=400, photon_rate=200., budget_units=1600,
                detector_model="independent donor/acceptor Poisson at sampled state; mean total=photon_rate*exposure")


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

    def _acquire(self, exposure, length):
        if type(exposure) not in (int, float) or exposure not in (.1, .2, .4) or type(length) is not int or length != 400:
            self.violated = True
            raise ValueError("invalid acquisition")
        cost = int(round(exposure/.1))*length
        if self.spent+cost > 1600:
            self.violated = True
            raise RuntimeError("budget exhausted")
        self.spent += cost
        self.calls += 1
        _, a, b, e0, e1 = SPECS[self.index]
        rng = np.random.default_rng([74620, self.index, self.calls])
        state = int(rng.random() < a/(a+b)) if a+b else 0
        p = transition([a, b], exposure)
        counts = []
        for _ in range(length):
            efficiency = (e0, e1)[state]
            counts.append(rng.poisson(200*exposure*np.array([1-efficiency, efficiency])).tolist())
            state = int(rng.random() < p[state, 1])
        return dict(counts=counts, exposure=exposure, cost=cost)


def _fit(traces, dt, initial):
    """Baum-Welch with independent stationary-start traces; no true labels."""
    efficiencies = np.array(initial, float)
    trans = transition([1., 1.], dt)
    total = 200*dt
    for _ in range(30):
        transitions, photons, occupancies = np.zeros((2, 2)), np.zeros((2, 2)), np.zeros(2)
        ll = 0.
        for counts in traces:
            means = total*np.array([1-efficiencies, efficiencies]).T
            log_emission = (counts[:, None, :]*np.log(means)[None] - means[None] - gammaln(counts[:, None, :]+1)).sum(axis=2)
            offset = log_emission.max(axis=1)
            emission = np.exp(log_emission-offset[:, None])
            forward, scales = np.zeros_like(emission), np.zeros(len(counts))
            stationary = np.array([trans[1, 0], trans[0, 1]])
            stationary /= stationary.sum()
            forward[0] = stationary*emission[0]
            scales[0] = forward[0].sum(); forward[0] /= scales[0]
            for t in range(1, len(counts)):
                forward[t] = (forward[t-1]@trans)*emission[t]
                scales[t] = forward[t].sum(); forward[t] /= scales[t]
            backward = np.ones_like(emission)
            for t in range(len(counts)-2, -1, -1):
                backward[t] = trans@(emission[t+1]*backward[t+1])/scales[t+1]
            gamma = forward*backward
            gamma /= gamma.sum(axis=1)[:, None]
            xi = forward[:-1, :, None]*trans[None]*emission[1:, None, :]*backward[1:, None, :]
            xi /= xi.sum(axis=(1, 2))[:, None, None]
            transitions += xi.sum(axis=0)
            photons += gamma.T@counts
            occupancies += gamma.sum(axis=0)
            ll += float(np.sum(np.log(scales)+offset))
        trans = np.clip(transitions/transitions.sum(axis=1)[:, None], 1e-6, 1-1e-6)
        efficiencies = np.clip(photons[:, 1]/photons.sum(axis=1), .05, .95)
    jump = np.clip(trans[0, 1]+trans[1, 0], 1e-6, .999999)
    rate_sum = -np.log1p(-jump)/dt
    rates = np.clip(rate_sum*np.array([trans[0, 1], trans[1, 0]])/jump, .1, 3.)
    return ll, rates.tolist(), efficiencies.tolist()


def reference(problem, observe):
    traces = [np.array(observe(.2, 400)["counts"], float) for _ in range(2)]
    counts = np.concatenate(traces)
    ratio = counts[:, 1]/np.maximum(1, counts.sum(axis=1))
    excess = float(np.var(ratio)-np.mean(ratio*(1-ratio)/np.maximum(1, counts.sum(axis=1)-1)))
    if excess < .015:
        return dict(abstain=True, rates=[], efficiencies=[], confidence=.95)
    best = max((_fit(traces, .2, init) for init in ((.2, .8), (.35, .65))), key=lambda x:x[0])
    return dict(abstain=False, rates=best[1], efficiencies=best[2], confidence=.9)


def _parse(out):
    if not isinstance(out, dict) or set(out) != {"abstain", "rates", "efficiencies", "confidence"} or type(out["abstain"]) is not bool:
        return None
    c = out["confidence"]
    if type(c) not in (int, float) or not np.isfinite(c) or not 0 <= c <= 1:
        return None
    for key, bounds in (("rates", (.1, 3.)), ("efficiencies", (.05, .95))):
        values = out[key]
        if not isinstance(values, list) or len(values) != (0 if out["abstain"] else 2):
            return None
        if any(type(v) not in (int, float) or not np.isfinite(v) or not bounds[0] <= v <= bounds[1] for v in values):
            return None
    return out


def _mechanism(index, out):
    _, a, b, e0, e1 = SPECS[index]
    errors = []
    for perm in ((0, 1), (1, 0)):
        rates = np.array(out["rates"])[list(perm)]
        efficiencies = np.array(out["efficiencies"])[list(perm)]
        errors.append(float(np.mean(np.abs(np.log(rates/[a, b])))) + 3*float(np.mean(np.abs(efficiencies-[e0, e1]))))
    return float(max(0., 1-min(errors)/0.10))


def evaluate(infer_kinetics):
    rows = []
    for index, spec in enumerate(SPECS):
        lab = _Lab(index)
        try:
            out = _parse(infer_kinetics(deepcopy(_problem()), lab))
        except Exception:
            out = None
        valid = out is not None and not lab.violated
        claim = bool(valid and not out["abstain"])
        supported = spec[0] == "supported"
        mechanism = _mechanism(index, out) if claim and supported else 0.
        refusal = float(valid and out["abstain"] and not supported)
        correct = (mechanism >= .5) if supported and claim else bool(refusal)
        rows.append(dict(valid=valid, mechanism=mechanism, scientific=mechanism if supported else refusal,
                         claim=int(claim), false_positive=int(claim and not supported), supported=supported,
                         refusal=refusal, cost=lab.spent, calibration=(out["confidence"]-float(correct))**2 if valid else 1.))
    dev, held = rows[:4], rows[4:]
    return dict(combined_score=float(max(0., 2*np.mean([r["scientific"] for r in dev])-1)),
                valid=float(all(r["valid"] for r in rows)), development_mechanism_score=float(np.mean([r["mechanism"] for r in dev if r["supported"]])),
                development_false_discovery_count=sum(r["false_positive"] for r in dev),
                development_claim_count=sum(r["claim"] for r in dev),
                development_false_discovery_rate=sum(r["false_positive"] for r in dev)/max(1, sum(r["claim"] for r in dev)),
                development_correct_refusal_rate=float(np.mean([r["refusal"] for r in dev if not r["supported"]])),
                development_discovery_coverage=float(np.mean([r["claim"] for r in dev if r["supported"]])),
                development_brier_loss=float(np.mean([r["calibration"] for r in dev])),
                heldout_scientific_score=float(np.mean([r["scientific"] for r in held])), per_world=rows)
