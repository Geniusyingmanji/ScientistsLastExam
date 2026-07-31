"""Oracle for SparseRecovery."""
import numpy as np

INSTANCES = []
def _make_instances():
    if INSTANCES: return
    for seed in range(5):
        rng = np.random.default_rng(seed + 100)
        n, m, k = 200, 60, 8
        A = rng.standard_normal((m, n)) / np.sqrt(m)
        x_true = np.zeros(n)
        support = rng.choice(n, k, replace=False)
        x_true[support] = rng.standard_normal(k) * 3
        noise = rng.standard_normal(m) * 0.01
        y = A @ x_true + noise
        # Oracle: least-squares on known support
        x_oracle = np.zeros(n)
        x_oracle[support] = np.linalg.lstsq(A[:, support], y, rcond=None)[0]
        snr_oracle = 20 * np.log10(np.linalg.norm(x_true) / max(np.linalg.norm(x_true - x_oracle), 1e-15))
        # Baseline: full least-squares
        x_ls = np.linalg.lstsq(A, y, rcond=None)[0]
        snr_base = 20 * np.log10(np.linalg.norm(x_true) / max(np.linalg.norm(x_true - x_ls), 1e-15))
        INSTANCES.append({"A": A, "y": y, "k": k, "x_true": x_true,
                          "snr_oracle": snr_oracle, "snr_base": snr_base})

def evaluate(recover_sparse):
    _make_instances()
    results = []
    for inst in INSTANCES:
        try:
            x_hat = np.asarray(recover_sparse(inst["A"].copy(), inst["y"].copy(), inst["k"]), dtype=float)
        except Exception as e:
            results.append({"valid": False, "reason": str(e), "score": 0.0}); continue
        if x_hat.shape != inst["x_true"].shape:
            results.append({"valid": False, "reason": "bad shape", "score": 0.0}); continue
        err = np.linalg.norm(inst["x_true"] - x_hat)
        snr = 20 * np.log10(np.linalg.norm(inst["x_true"]) / max(err, 1e-15))
        sb, so = inst["snr_base"], inst["snr_oracle"]
        score = max(0.0, min(1.0, (snr - sb) / (so - sb))) if so > sb else 0.0
        results.append({"valid": True, "snr": round(snr, 2), "score": float(score)})
    scores = [r["score"] for r in results]
    return {"combined_score": float(np.mean(scores)), "valid": 1.0 if all(r.get("valid") for r in results) else 0.0,
            "feasibility_rate": sum(1 for r in results if r.get("valid")) / len(results), "per_instance": results}
