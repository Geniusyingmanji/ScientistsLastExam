"""Public Raynal constructor and full-space local optimization (NumPy).

This module is never imported by the evaluator. Numerical optimization is an
exploration aid; its output must be converted to legal rays and scored exactly.
"""

import argparse
import importlib.util
import json
from pathlib import Path
from time import perf_counter

import numpy as np


TASK = Path(__file__).resolve().parents[1]


def raynal_parameter():
    r = np.cbrt(21*np.sqrt(3.0)-36)
    return (3+16*r-r*r)/(28*r)


def raynal_asd():
    """Independent scalar Eq.(22), not inferred from the matrix overlaps."""
    return float((71-12*(1-raynal_parameter())**2)/70)


def raynal_bases():
    """I and M1,M2,M3 from arXiv:1103.1025 Eqs.(5),(6),(19)–(22)."""
    s = raynal_parameter()
    omega = np.exp(2j*np.pi/3)
    x = np.exp(1j*np.arcsin(np.sqrt(s)))
    t = np.exp(1j*(np.arccos((1-2*s)/np.sqrt(s))-np.pi/3))
    z = np.diag([1,-1])
    xx = np.diag([np.conj(x),x])
    f = np.array([[1,1],[1,-1]],dtype=complex)
    tt = np.array([[1,omega*t*t],[1,-omega*t*t]])
    zero = np.zeros((2,2),dtype=complex)
    l1 = np.block([[xx,zero,zero],
                   [zero,1j*np.conj(omega)*t*z @ xx.conj() @ xx.conj(),zero],
                   [zero,zero,xx]])
    l3 = np.block([[xx.conj(),zero,zero],
                   [zero,np.conj(omega)*xx.conj(),zero],
                   [zero,zero,-1j*t*z @ xx @ xx]])
    n1 = np.block([[f,f,f],[f,omega*f,np.conj(omega)*f],
                   [tt,np.conj(omega)*tt,omega*tt]])
    n2 = np.block([[f,f,f],[tt,omega*tt,np.conj(omega)*tt],
                   [tt,np.conj(omega)*tt,omega*tt]])
    n3 = np.block([[f,f,f],[tt,omega*tt,np.conj(omega)*tt],
                   [f,np.conj(omega)*f,omega*f]])
    return [np.eye(6,dtype=complex), l1@n1/np.sqrt(6),
            n2/np.sqrt(6), l3@n3/np.sqrt(6)]


def _public_helper():
    spec = importlib.util.spec_from_file_location("mub_public_solution", TASK / "solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_submission(bits=32):
    helper = _public_helper()
    return {"bases": [helper.numerical_to_integer_rays(u,bits=bits) for u in raynal_bases()[1:]]}


def fixture_text():
    return json.dumps(reference_submission(32), indent=2) + "\n"


def check_fixture():
    return (TASK / "references/raynal_rays.json").read_text(encoding="utf-8") == fixture_text()


def overlap_sse(bases):
    """Numerical SSE, also defined off-manifold for independent gradient checks."""
    d = bases[0].shape[0]
    return float(sum(np.sum((np.abs(a.conj().T@b)**2-1/d)**2)
                     for i,a in enumerate(bases) for b in bases[i+1:]))


def sse_gradient(bases):
    """Euclidean real gradient for Re tr(G† dU), including the U0 component."""
    d = bases[0].shape[0]
    gradient = [np.zeros_like(u) for u in bases]
    for i,a in enumerate(bases):
        for j in range(i+1,len(bases)):
            b = bases[j]
            c = a.conj().T@b
            e = (np.abs(c)**2-1/d)*c
            gradient[i] += 4*b@e.conj().T
            gradient[j] += 4*a@e
    return gradient


def random_bases(seed=0):
    """Seeded Gaussian-QR starts in the full three-unitary space, with U0=I."""
    rng = np.random.default_rng(seed)
    result = [np.eye(6,dtype=complex)]
    for _ in range(3):
        q,r = np.linalg.qr(rng.normal(size=(6,6))+1j*rng.normal(size=(6,6)))
        phase = np.diag(r)/np.abs(np.diag(r))
        result.append(q*phase)
    return result


def optimize_bases(seed=0, iterations=2000, initial=None, step=1.0,
                   max_backtracks=40, gradient_tolerance=1e-10):
    """Projected gradient descent with polar retraction and strict backtracking.

    U0=I stays fixed. Every other unitary can move freely; no Hadamard ansatz.
    History contains only accepted SSE values. Termination is not optimality.
    """
    if type(iterations) is not int or not 0 <= iterations <= 100000:
        raise ValueError("invalid iteration budget")
    if type(max_backtracks) is not int or not 1 <= max_backtracks <= 100:
        raise ValueError("invalid backtracking budget")
    if not np.isfinite(step) or step <= 0 or not np.isfinite(gradient_tolerance) or gradient_tolerance < 0:
        raise ValueError("invalid optimizer scale")
    bases = random_bases(seed) if initial is None else [np.array(u,dtype=complex,copy=True) for u in initial]
    if len(bases) != 4 or any(u.shape != (6,6) or not np.all(np.isfinite(u)) for u in bases):
        raise ValueError("expected four finite 6x6 matrices")
    if not np.array_equal(bases[0],np.eye(6)):
        raise ValueError("initial U0 must equal I")
    if any(not np.allclose(u.conj().T@u,np.eye(6),rtol=0,atol=1e-12) for u in bases):
        raise ValueError("initial bases must be unitary")
    history = [overlap_sse(bases)]
    evaluations, reason = 1, "iteration_budget"
    for _ in range(iterations):
        gradient = sse_gradient(bases)
        tangent = []
        for u,g in zip(bases[1:],gradient[1:]):
            ug = u.conj().T@g
            tangent.append(g-u@((ug+ug.conj().T)/2))
        norm2 = float(sum(np.vdot(v,v).real for v in tangent))
        if norm2 <= gradient_tolerance**2:
            reason = "gradient_tolerance"
            break
        trial_step, accepted = step, False
        for _ in range(max_backtracks):
            trial = [bases[0]]
            for u,v in zip(bases[1:],tangent):
                left,_,right = np.linalg.svd(u-trial_step*v,full_matrices=False)
                trial.append(left@right)
            trial_sse = overlap_sse(trial)
            evaluations += 1
            if trial_sse < history[-1] and trial_sse <= history[-1]-1e-4*trial_step*norm2:
                bases = trial
                history.append(trial_sse)
                accepted = True
                break
            trial_step /= 2
        if not accepted:
            reason = "backtracking_stalled"
            break
    return {"bases": bases, "sse": history[-1], "asd": 1-history[-1]/30,
            "history": history, "accepted_iterations": len(history)-1,
            "objective_evaluations": evaluations, "stop_reason": reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=["emit","check"])
    parser.add_argument("--seeds",type=int,nargs="*",default=[0,1,2])
    parser.add_argument("--iterations",type=int,default=2000)
    args = parser.parse_args()
    if args.fixture == "emit":
        print(fixture_text(),end="")
        return
    if args.fixture == "check":
        if not check_fixture():
            raise SystemExit("fixture differs from deterministic regeneration")
        print("fixture matches")
        return
    for name,seed,initial in [(f"random_{s}",s,None) for s in args.seeds] + [("raynal_warm",0,raynal_bases())]:
        start = perf_counter()
        result = optimize_bases(seed=seed,iterations=args.iterations,initial=initial)
        report = {k:v for k,v in result.items() if k not in ("bases","history")}
        report.update(name=name,seed=seed,iteration_budget=args.iterations,
                      initial_sse=result["history"][0],seconds=perf_counter()-start)
        print(json.dumps(report,sort_keys=True,allow_nan=False))


if __name__ == "__main__":
    main()
