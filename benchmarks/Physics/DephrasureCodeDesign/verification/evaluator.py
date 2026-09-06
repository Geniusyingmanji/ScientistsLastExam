"""Finite-block coherent information; numerical checks, not capacity proofs.

The production oracle resolves erasure flags before entropy evaluation. The
independent audit instead constructs all tensor Kraus operators and their Gram
environment, with no erasure-block or complementary-channel implementation.
"""

import importlib.util
from itertools import product
from pathlib import Path

import numpy as np
from scipy.linalg import eigvalsh


MAX_N = 4
MAX_ABS_COEFFICIENT = 1e100
NUMERICAL_MARGIN = 1e-9  # Conservatively above observed dual-oracle roundoff.


def factor_density(submission, n):
    """Validate a bounded JSON factor and return XX†/Tr(XX†), without projection."""
    if type(n) is not int or not 1 <= n <= MAX_N:
        raise ValueError("block length outside bounded oracle")
    if type(submission) is not dict or set(submission) != {"real", "imag"}:
        raise ValueError("expected real and imag fields")
    d = 2**n
    real, imag = submission["real"], submission["imag"]
    if any(type(a) is not list or len(a) != d for a in (real, imag)):
        raise ValueError("factor row count")
    if type(real[0]) is not list or not 1 <= len(real[0]) <= d:
        raise ValueError("factor rank bound")
    rank = len(real[0])
    for array in (real, imag):
        for row in array:
            if type(row) is not list or len(row) != rank:
                raise ValueError("rectangular equal-shaped factors required")
            for value in row:
                if type(value) not in (int, float) or not -MAX_ABS_COEFFICIENT <= value <= MAX_ABS_COEFFICIENT:
                    raise ValueError("nonfinite, nonnumeric or oversized coefficient")
    # Scale before squaring, so even nonzero subnormal factors are meaningful.
    scale = max(np.max(np.abs(real)), np.max(np.abs(imag)))
    if scale == 0:
        raise ValueError("zero factor")
    x = np.asarray(real, dtype=np.float64) / scale + 1j * (np.asarray(imag, dtype=np.float64) / scale)
    rho = x @ x.conj().T
    return rho / np.trace(rho).real


def _validate(rho, p, q):
    rho = np.asarray(rho, dtype=np.complex128)
    if rho.ndim != 2 or rho.shape[0] != rho.shape[1] or rho.shape[0] not in (2, 4, 8, 16):
        raise ValueError("density dimension must be 2, 4, 8 or 16")
    if not np.isfinite(rho).all() or not np.allclose(rho, rho.conj().T, rtol=0, atol=1e-11):
        raise ValueError("invalid density matrix")
    if abs(np.trace(rho)-1) > 1e-10 or np.linalg.eigvalsh(rho).min() < -1e-11:
        raise ValueError("input must already be a density matrix")
    if not (np.isfinite(p) and np.isfinite(q) and 0 <= p <= 1 and 0 <= q <= 1):
        raise ValueError("channel probability")
    return rho, rho.shape[0].bit_length()-1


def _entropy(state):
    values = np.linalg.eigvalsh((state + state.conj().T) * .5)
    if values.min() < -1e-10:
        raise ValueError("nonpositive channel output")
    values = values[values > 0]
    return float(-np.sum(values * np.log2(values)))


def coherent_information(rho, p, q):
    """Return TOTAL coherent information in bits for 1 <= n <= 4."""
    rho, n = _validate(rho, p, q)
    total = 0.0
    for mask in range(2**n):
        survive = [i for i in range(n) if mask & (1 << i)]
        erase = [i for i in range(n) if i not in survive]
        s, t = len(survive), len(erase)
        weight = (1-q)**s * q**t
        if weight == 0:
            continue
        order = survive + erase
        joint = rho.reshape([2] * (2*n)).transpose(order + [i+n for i in order]).reshape(2**s, 2**t, 2**s, 2**t)
        reduced = np.trace(joint, axis1=1, axis2=3)
        distance = np.array([[(a ^ b).bit_count() for b in range(2**s)] for a in range(2**s)])
        out = reduced * (1-2*p)**distance
        environment = np.zeros((2**n, 2**n), dtype=np.complex128)
        for x in range(2**s):
            phi = np.ones(1)
            for bit in range(s-1, -1, -1):
                phi = np.kron(phi, [np.sqrt(1-p), (-1)**((x >> bit) & 1) * np.sqrt(p)])
            environment += np.kron(np.outer(phi, phi), joint[x, :, x, :])
        total += weight * (_entropy(out) - _entropy(environment))
    return float(total)


def coherent_information_kraus(rho, p, q):
    """Independent full Kraus/Gram audit; TOTAL bits, dense 81/256 at n=4."""
    rho, n = _validate(rho, p, q)
    embed = np.array([[1, 0], [0, 1], [0, 0]], dtype=np.complex128)
    one = [np.sqrt((1-q)*(1-p))*embed,
           np.sqrt((1-q)*p)*(embed @ np.diag([1, -1])),
           np.sqrt(q)*np.array([[0, 0], [0, 0], [1, 0]]),
           np.sqrt(q)*np.array([[0, 0], [0, 0], [0, 1]])]
    operators = []
    for indices in product(range(4), repeat=n):
        op = np.ones((1, 1), dtype=complex)
        for i in indices:
            op = np.kron(op, one[i])
        operators.append(op)
    values, vectors = np.linalg.eigh(rho)
    root = vectors * np.sqrt(np.maximum(values, 0))
    amplitudes = np.asarray(operators) @ root
    bob = np.einsum("kbi,kci->bc", amplitudes, amplitudes.conj())
    flat = amplitudes.reshape(4**n, -1)
    env = flat @ flat.conj().T
    # Deliberately separate spectral/entropy path from the block oracle.
    entropy = []
    for state in (bob, env):
        spectrum = eigvalsh(state, check_finite=True)
        if spectrum.min() < -1e-10:
            raise ValueError("Kraus output not positive")
        entropy.append(float(sum(-v*np.log2(v) for v in spectrum if v > 0)))
    return entropy[0] - entropy[1]


def _references():
    path = Path(__file__).with_name("reference_codes.py")
    spec = importlib.util.spec_from_file_location("dephrasure_references", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluation_problems():
    """Fresh immutable-by-convention public worlds, backed by actual witnesses."""
    return _references().evaluation_problems()


def evaluate(candidate_callable):
    """Finite JSON. The caller/harness must isolate and time-limit candidate code.

    This verifier bounds artifact parsing and numerical work, not execution of an
    arbitrary Python callable. No claim of an in-process security sandbox.
    """
    rows = []
    for problem in evaluation_problems():
        row = dict(n=problem["n"], p=problem["p"], q=problem["q"], valid=False,
                   score=0.0, raw_rate=0.0, single_letter_rate=problem["single_letter_rate"],
                   reference_rate=problem["reference_rate"], reference_excess=0.0,
                   margin_qualified_excess=0.0, numerical_margin=NUMERICAL_MARGIN,
                   reason="invalid submission")
        try:
            candidate = candidate_callable(dict(problem))
            rho = factor_density(candidate, problem["n"])
            rate = coherent_information(rho, problem["p"], problem["q"])/problem["n"]
            baseline, reference = problem["single_letter_rate"], problem["reference_rate"]
            score = max(0.0, (rate-baseline)/(reference-baseline))
            row.update(valid=True, score=float(score), raw_rate=float(rate),
                       reference_excess=max(0.0, rate-reference),
                       margin_qualified_excess=max(0.0, rate-reference-NUMERICAL_MARGIN), reason="ok")
        except Exception:
            pass  # Candidate-controlled exception strings never enter stable JSON.
        rows.append(row)
    count = sum(row["valid"] for row in rows)
    return dict(combined_score=float(sum(r["score"] for r in rows)/len(rows)),
                valid=float(count == len(rows)), feasibility_rate=count/len(rows),
                reference_excess=float(sum(r["margin_qualified_excess"] for r in rows)/len(rows)),
                per_instance=rows)
