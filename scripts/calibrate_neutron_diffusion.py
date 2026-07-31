#!/usr/bin/env python3
"""Reproduce the NeutronDiffusionCriticality normalization witness.

This script independently constructs the conservative two-group generalized eigenproblem,
optimizes a reflection-symmetric loading with deterministic multistart SLSQP, and compares the
dense eigenvalue result with the oracle's power iteration.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.linalg import eig
from scipy.optimize import minimize
from scipy.sparse import diags

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frontier_science.provenance import finalize_report_trust, source_provenance  # noqa: E402

TASK = ROOT / "benchmarks/Engineering/NeutronDiffusionCriticality"


def _load_oracle():
    path = TASK / "verification/evaluator.py"
    spec = importlib.util.spec_from_file_location("neutron_anchor_oracle", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load neutron oracle")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _diffusion_matrix(diffusion: np.ndarray, removal: np.ndarray, width: float):
    n = len(diffusion)
    h = width / (n + 1)
    interface = 2 * diffusion[:-1] * diffusion[1:] / (
        diffusion[:-1] + diffusion[1:]
    )
    left = np.concatenate(([diffusion[0]], interface))
    right = np.concatenate((interface, [diffusion[-1]]))
    return diags(
        [-interface / h**2, (left + right) / h**2 + removal,
         -interface / h**2],
        [-1, 0, 1],
    ).toarray()


def _generalized_keff(oracle, loading: np.ndarray) -> float:
    enrichment = np.repeat(loading, oracle.N_MESH // oracle.N_ZONES)
    d1, sr1, nusf1, ss12, d2, sa2, nusf2 = oracle._cross_sections(enrichment)
    a1 = _diffusion_matrix(d1, sr1, oracle.SLAB_WIDTH)
    a2 = _diffusion_matrix(d2, sa2, oracle.SLAB_WIDTH)
    zeros = np.zeros_like(a1)
    loss = np.block([[a1, zeros], [-np.diag(ss12), a2]])
    production = np.block([
        [np.diag(nusf1), np.diag(nusf2)],
        [zeros, zeros],
    ])
    values = eig(production, loss, right=False, check_finite=False)
    physical = values[
        np.isfinite(values)
        & (np.abs(values.imag) < 1e-8)
        & (values.real > 0)
    ].real
    if physical.size == 0:
        raise RuntimeError("no positive real multiplication eigenvalue")
    return float(np.max(physical))


def _symmetric_loading(half: np.ndarray) -> np.ndarray:
    return np.concatenate((half, half[::-1]))


def calibrate(seed: int, starts: int) -> dict:
    oracle = _load_oracle()
    lower, upper = 0.02, 0.20
    half_size = oracle.N_ZONES // 2
    half_sum = oracle.AVG_ENRICH_MAX * oracle.N_ZONES / 2
    uniform = np.full(oracle.N_ZONES, oracle.AVG_ENRICH_MAX)
    rng = np.random.default_rng(seed)
    initial = [np.full(half_size, oracle.AVG_ENRICH_MAX)]
    for _ in range(starts - 1):
        surplus = (half_sum - lower * half_size) * rng.dirichlet(np.ones(half_size))
        initial.append(lower + surplus)

    solutions = []
    for index, x0 in enumerate(initial):
        result = minimize(
            lambda half: -oracle._compute_keff(_symmetric_loading(half)),
            x0,
            method="SLSQP",
            bounds=[(lower, upper)] * len(x0),
            constraints={"type": "eq", "fun": lambda half: float(np.sum(half) - half_sum)},
            options={"maxiter": 500, "ftol": 1e-13},
        )
        solutions.append({
            "start": index,
            "success": bool(result.success),
            "iterations": int(result.nit),
            "k_eff": float(-result.fun),
            "half_loading": [float(x) for x in result.x],
        })
    best = max(solutions, key=lambda row: row["k_eff"])
    witness = _symmetric_loading(np.asarray(best["half_loading"], dtype=float))
    uniform_power = oracle._compute_keff(uniform)
    witness_power = oracle._compute_keff(witness)
    uniform_exact = _generalized_keff(oracle, uniform)
    witness_exact = _generalized_keff(oracle, witness)
    oracle_reference = np.asarray(oracle.REFERENCE_LOADING, dtype=float)
    oracle_reference_k = oracle._compute_keff(oracle_reference)
    report = {
        "schema_version": 1,
        "trust_status": "TRUSTED_ANCHOR_CALIBRATION",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_provenance": source_provenance(ROOT),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "config": {"seed": seed, "starts": starts, "optimizer": "SLSQP"},
        "uniform": {
            "loading": [float(x) for x in uniform],
            "power_iteration_k_eff": uniform_power,
            "generalized_eigen_k_eff": uniform_exact,
        },
        "optimized_witness": {
            "loading": [float(x) for x in witness],
            "mean_enrichment": float(np.mean(witness)),
            "power_iteration_k_eff": witness_power,
            "generalized_eigen_k_eff": witness_exact,
            "improvement": witness_power - uniform_power,
        },
        "oracle_reference": {
            "loading": [float(x) for x in oracle_reference],
            "power_iteration_k_eff": oracle_reference_k,
        },
        "starts": solutions,
    }
    execution_passed = bool(
        all(row["success"] for row in solutions)
        and abs(uniform_power - uniform_exact) < 1e-8
        and abs(witness_power - witness_exact) < 1e-8
        and abs(float(np.mean(witness)) - oracle.AVG_ENRICH_MAX) < 1e-10
        and witness_power > uniform_power
        and abs(oracle_reference_k - witness_power) < 1e-7
    )
    finalize_report_trust(report, execution_passed)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--starts", type=int, default=16)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.starts < 1:
        raise SystemExit("--starts must be positive")
    report = calibrate(args.seed, args.starts)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["execution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
