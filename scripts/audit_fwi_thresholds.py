"""Sweep refusal thresholds after fitting, then replay the dev-selected policy.

Fits use only public inputs and paid observations. Reusing their deterministic
outputs for threshold postprocessing avoids repeating the same expensive inverse
problem. The selected threshold is then evaluated again without cached artifacts.
Heldout scores never select the threshold.
"""
import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import numpy as np

from audit_fwi_revision import ROOT, TASK, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--family", choices=("one", "three", "stop", "depth"), default="depth")
    args = parser.parse_args()
    # Capture the code actually loaded, not a later checkout after long fits.
    source_state = {
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (TASK / "verification/evaluator.py",
                                    ROOT / ".research/pr20_fwi_continuous_probe.py", Path(__file__))},
    }
    oracle = load(TASK / "verification/evaluator.py", "threshold_oracle")
    probe = load(ROOT / ".research/pr20_fwi_continuous_probe.py", "threshold_probe")
    probe.LENSES, probe.STOP_NOISE, probe.DEPTH_CAP = {
        "one": (1, 0, 1), "three": (3, 0, 1), "stop": (5, 5, 1), "depth": (5, 5, .7)
    }[args.family]
    probe.THRESHOLD = float("inf")
    fits = {}
    for split, specs in (("development", oracle.DEVELOPMENT_SPECS), ("heldout", oracle.HELDOUT_SPECS)):
        fits[split] = []
        for index, spec in enumerate(specs):
            diagnostic = {}

            def capture(*inputs):
                gathers = []

                def acquire(source):
                    gather = inputs[-2](source)
                    gathers.append(gather)
                    return gather

                artifact = probe.invert_velocity_model(*inputs[:-2], acquire, inputs[-1])
                if artifact["abstain"]:
                    diagnostic["error"] = float("inf")
                else:
                    observed = np.asarray([g["pressure"] for g in gathers])
                    predicted = probe.simulate(np.asarray(artifact["velocity_m_s"])[None],
                                               [g["source_index"] for g in gathers],
                                               inputs[1], inputs[6], inputs[5])[0]
                    diagnostic["error"] = float(np.linalg.norm(predicted-observed) /
                                                max(np.linalg.norm(observed), 1e-12))
                return artifact

            claimed = oracle._evaluate_world(capture, spec, split, index)
            assert claimed["valid"], (split, index)
            refused = oracle._evaluate_world(
                lambda *a: {"velocity_m_s": [], "confidence": .1, "abstain": True}, spec, split, index)
            refused["shot_calls"] = claimed["shot_calls"]
            fits[split].append((claimed, refused, diagnostic["error"]))
    sweep = []
    for threshold in np.linspace(.02, 1.0, 50):
        record = {"threshold": float(threshold)}
        for split, specs in (("development", oracle.DEVELOPMENT_SPECS), ("heldout", oracle.HELDOUT_SPECS)):
            rows = [refused if error > threshold else claimed for claimed, refused, error in fits[split]]
            record[split] = oracle._summary(rows, specs)
        sweep.append(record)
    best = max(sweep, key=lambda r: r["development"]["normalized"])
    probe.THRESHOLD = best["threshold"]
    replay = oracle.evaluate(probe.invert_velocity_model)
    assert replay["valid"] == 1.0
    for split, metric in (("development", "combined_score"), ("heldout", "robustness_score")):
        assert abs(replay[metric] - best[split]["normalized"]) < 1e-12
    report = {
        **source_state,
        "scope": "threshold_postprocessing_with_uncached_dev_selected_replay",
        "family": args.family, "platform": platform.platform(),
        "sweep": sweep, "selected_on_development": best, "uncached_replay": replay,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.family, best["threshold"], replay["combined_score"], replay["robustness_score"], flush=True)


if __name__ == "__main__":
    main()
