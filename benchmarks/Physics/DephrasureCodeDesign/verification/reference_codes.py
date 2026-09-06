"""Reconstruct published numerical witnesses and form their product closure.

No third-party code runs: scipy.io.loadmat parses only hash-pinned small MATLAB
numeric arrays. Printed cost fields are provenance, never evaluation scores.
"""

from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.optimize import minimize_scalar


ROOT = Path(__file__).resolve().parents[1] / "references"
MAT_HASHES = {
    "Dephrasure_008_R2_n3.mat": "a63c1d6149e2684d090a9c8af39decaffc0e7f3738a8459540a33b1c723debd5",
    "Dephrasure_008_R2_n4.mat": "0a33cce0454c6c00fa29db4d7cb9c5c9e43cdffece5a4bae1913dc2b1c9522f7",
    "Dephrasure_008_R3_n3.mat": "009002aa535c4134e14b62440fef7260e54f27a1b85e5321235fb66e00a6a5a7",
    "Dephrasure_008_R3_n4.mat": "56ed52c72f3ca1c47cbec8b60e48b637453e559ab639a1539e82989293a99683",
    "Dephrasure_032_R2_n3.mat": "be066831d7e5303a5a76e50207efaa71044462c4037d5da4c36bf3bee81a8c9f",
    "Dephrasure_032_R2_n4.mat": "879c6a96f641da4e8075afc894dee9ba0806e1a0a371a558602f9f8ce3db1cee",
    "Dephrasure_032_R3_n3.mat": "7673a618b4107f9a0e611d0845d235e9b5fe13a750de04d0b0fbf8ac4cd68811",
    "Dephrasure_032_R3_n4.mat": "9e233174be60e6d10bbb4e5538df8a92e308cefa0f5bf12bab475d6459329b9f",
}


def _evaluator():
    path = Path(__file__).with_name("evaluator.py")
    spec = importlib.util.spec_from_file_location("dephrasure_reference_evaluator", path)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    return ev


def _factor_json(x):
    return {"real": x.real.tolist(), "imag": x.imag.tolist()}


def _normalize(x):
    return x / np.linalg.norm(x)


def _h(x):
    if x <= 0 or x >= 1:
        return 0.0
    return -(x*np.log(x)+(1-x)*np.log1p(-x))/np.log(2)


def repetition_rate(n, p, q, lam):
    t = 4*lam*(1-lam)*(1-(1-2*p)**(2*n))
    small = t / (2*(1+np.sqrt(max(0, 1-t))))
    return float((((1-q)**n-q**n)*_h(lam)-(1-q)**n*_h(small))/n)


def _repetition_factor(n, lam):
    x = np.zeros((2**n, 2), dtype=complex)
    x[0, 0], x[-1, 1] = np.sqrt(lam), np.sqrt(1-lam)
    return x


@lru_cache(maxsize=64)
def _best_repetition(n, p, q):
    # Bounded one-dimensional logit search captures biased, nearly pure optima.
    grid = np.linspace(-60, 0, 1201)
    def rate(t):
        return repetition_rate(n, p, q, 1/(1+np.exp(-t)))
    scores = np.array([rate(t) for t in grid])
    best = (float(scores[-1]), .5)
    for i in range(1, len(grid)-1):
        if scores[i] > scores[i-1] and scores[i] >= scores[i+1]:
            result = minimize_scalar(lambda t: -rate(t), bounds=(grid[i-1], grid[i+1]), method="bounded", options={"xatol":1e-12,"maxiter":100})
            if -result.fun > best[0]:
                best = (-float(result.fun), 1/(1+np.exp(-result.x)))
    return best


def product_repetition_reference(n, p, q):
    best = [(0.0, np.ones((1, 1), dtype=complex))]
    for m in range(1, n+1):
        candidates = []
        for k in range(1, m+1):
            rate, lam = _best_repetition(k, p, q)
            candidates.append((best[m-k][0] + k*rate, np.kron(best[m-k][1], _repetition_factor(k, lam))))
        best.append(max(candidates, key=lambda item:item[0]))
    return best[n][0]/n, best[n][1]


def published_mat_factor(filename):
    """Return A^n-by-R factor from published local unitaries in R,A1,...,An order."""
    if filename not in MAT_HASHES:
        raise ValueError("unknown published witness")
    path = ROOT / filename
    if path.stat().st_size > 10000 or hashlib.sha256(path.read_bytes()).hexdigest() != MAT_HASHES[filename]:
        raise ValueError("published witness size/hash mismatch")
    raw = loadmat(path, simplify_cells=True)
    n = int(filename[-5])
    rank = int(filename.split("_R")[1][0])
    unitaries = raw["best_psi"]
    if set(unitaries) != {"R1", "Main", "R2"}:
        raise ValueError("MAT field schema")
    expected = {"R1":(2*rank,2*rank), "R2":(2*rank,2*rank), "Main":(4,4,2*n-3)}
    for key, shape in expected.items():
        a = unitaries[key]
        if not isinstance(a, np.ndarray) or a.dtype.kind not in "fc" or a.shape != shape or not np.isfinite(a).all():
            raise ValueError("MAT numeric-array schema")
        matrices = [a] if key != "Main" else [a[:, :, k] for k in range(2*n-3)]
        if any(np.linalg.norm(u.conj().T@u-np.eye(len(u))) > 1e-8 for u in matrices):
            raise ValueError("published matrix is not unitary")
    dims = [rank] + [2]*n
    state = np.zeros(rank*2**n, dtype=complex); state[0] = 1
    def apply(state, unitary, targets):
        order = list(targets) + [j for j in range(n+1) if j not in targets]
        tensor = state.reshape(dims).transpose(order)
        transformed = unitary @ tensor.reshape(len(unitary), -1)
        return transformed.reshape([dims[j] for j in order]).transpose(np.argsort(order)).reshape(-1)
    state = apply(state, unitaries["R1"], [0,1])
    for k in range(2, 2*n-1):
        left = k-1 if k <= n else 2*n-k-1
        state = apply(state, unitaries["Main"][:, :, k-2], [left,left+1])
    state = apply(state, unitaries["R2"], [0,1])
    return _normalize(state.reshape(rank, 2**n).T), float(raw["best_cost"])


def _published_nn():
    for code in json.loads((ROOT/"nn2020.json").read_text())["codes"]:
        n = code["n"]
        x = np.zeros((2**n, 2**n), dtype=complex)
        for a, r, real, imag in code["amplitudes"]:
            x[int(a,2), int(r,2)] = complex(real, imag)
        yield code, _normalize(x)


def _published_pi(n):
    for code in json.loads((ROOT/"nonorthogonal2025.json").read_text())["codes"]:
        columns = []
        for weight, (aa, ab, bb) in zip(code["weights"], code["states"]):
            off = complex(*ab)
            matrix = np.array([[complex(*aa), off], [off.conjugate(), complex(*bb)]])
            _, vectors = np.linalg.eigh(matrix)
            state = np.ones(1, dtype=complex)
            for _ in range(n):
                state = np.kron(state, vectors[:, -1])
            columns.append(np.sqrt(weight)*state)
        yield code, _normalize(np.stack(columns, axis=1))


def audit_references():
    """Recompute all witnesses and their pointwise/tensor-product envelope."""
    ev = _evaluator()
    rows, winners = [], []
    nn = list(_published_nn())
    for p, q, code_p in [(0.08,0.4,"008"),(0.32,0.1,"032")]:
        best = [(0.0,np.ones((1,1),dtype=complex),"empty")]
        for n in range(1,5):
            candidates = []
            rep_rate, lam = _best_repetition(n,p,q)
            candidates.append(("repetition",_repetition_factor(n,lam),None))
            candidates.extend((c["id"],x,c["printed_rate"]) for c,x in nn if c["p"]==p and c["n"]==n)
            candidates.extend((c["id"]+f"n{n}",x,None) for c,x in _published_pi(n) if c["p"]==p)
            if n>=3:
                for rank in [2,3]:
                    filename=f"Dephrasure_{code_p}_R{rank}_n{n}.mat"
                    x, stored = published_mat_factor(filename)
                    candidates.append((filename,x,stored))
            for k in range(1,n):
                candidates.append((f"product({best[k][2]},{best[n-k][2]})",np.kron(best[k][1],best[n-k][1]),None))
            evaluated=[]
            for name,x,reported in candidates:
                rho=x@x.conj().T
                rate=ev.coherent_information(rho,p,q)/n
                direct=ev.coherent_information_kraus(rho,p,q)/n
                rows.append(dict(id=name,n=n,p=p,q=q,rate=rate,kraus_rate=direct,dual_error=abs(rate-direct),reported_rate=reported))
                evaluated.append((rate*n,x,name))
            best.append(max(evaluated,key=lambda item:item[0]))
            if n>=3:
                winners.append(dict(n=n,p=p,q=q,reference_id=best[n][2],reference_rate=best[n][0]/n,single_letter_rate=_best_repetition(1,p,q)[0]))
    return dict(winners=winners,witnesses=rows,max_dual_error=max(r["dual_error"] for r in rows))


def evaluation_problems():
    data=json.loads((ROOT/"verified_reference.json").read_text())
    return [dict(row,dimension=2**row["n"],max_rank=2**row["n"],max_abs_coefficient=1e100,numerical_margin=1e-9) for row in data["winners"]]


def design_reference(problem):
    name=problem["reference_id"]
    if name.endswith(".mat"):
        x,_=published_mat_factor(name)
    else:
        matches=[x for code,x in _published_nn() if code["id"]==name]
        if len(matches)!=1:
            raise ValueError("unsupported frozen reference witness")
        x=matches[0]
    return _factor_json(x)


if __name__=="__main__":
    print(json.dumps(audit_references(),indent=2,allow_nan=False))
