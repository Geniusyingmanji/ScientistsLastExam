"""The three worlds, and why two of them cannot be answered.

Extrapolating a closure to a Reynolds number ten times larger is legitimate *if* you have the right
law and its parameters are pinned. That is what a law is for. So the question is not whether
extrapolation is allowed - it is whether the observations determine the closure at all.

  * `recoverable` - the sampled Reynolds numbers span enough that the two parameters of the damped
    mixing length separate. The law is determined; extrapolate.
  * `degenerate_parameters` - the sampled range is too narrow to separate `kappa` from `A+`. A
    whole family of pairs fits the observations within noise, and they disagree at the held-out
    Reynolds numbers. The residuals look *excellent*.
  * `inconsistent` - no single closure generated the profiles. The residuals look *bad*.

The two refusal regimes fail in opposite directions, and that is the point. A searcher that
abstains when its residuals are large catches `inconsistent` and walks straight into
`degenerate_parameters`, which is the failure mode the data-driven closure literature reports:
a fit that reproduces its training flows and disagrees with everything else.

An earlier design made the third regime "structure above the sampled `y+`". It was discarded: that
structure is unconstrained in *every* regime, so blanket abstention would have been the correct
answer everywhere and the task would have measured nothing.
"""
from __future__ import annotations

import numpy as np

# Wide span: the near-wall damping and the log-region slope are both exercised.
WIDE_RE = (180.0, 950.0, 4000.0)
# Narrow span: only low Reynolds numbers, where kappa and A+ trade off against each other.
NARROW_RE = (180.0, 200.0, 220.0)
HELDOUT_RE = (2000.0, 5200.0)


def damped_mixing_length(kappa, a_plus):
    def closure(y, re_tau):
        return kappa * y * (1.0 - np.exp(-y / a_plus))
    return closure


def build(seed, count):
    rng = np.random.default_rng(seed)
    cases = []
    for index in range(count):
        regime = ("recoverable", "degenerate_parameters", "inconsistent")[index % 3]
        kappa = float(rng.uniform(0.38, 0.44))
        a_plus = float(rng.uniform(22.0, 30.0))
        record = {
            "case_id": "flow%03d" % index,
            "regime": regime,
            "kappa": kappa,
            "a_plus": a_plus,
            "sampled_re": WIDE_RE if regime == "recoverable" else NARROW_RE,
            "noise": float(rng.uniform(0.008, 0.014)),
            # The two systematics a profile measurement actually carries: where the wall is, and
            # how the friction velocity was calibrated. Both are constant across a profile.
            "wall_shift": float(rng.uniform(0.4, 0.9)),
            "calibration": float(rng.uniform(0.010, 0.020)),
            "seed": int(rng.integers(0, 2 ** 31 - 1)),
        }
        if regime == "inconsistent":
            # Each sampled Reynolds number comes from a different closure, so nothing fits them all.
            record["per_sample_truth"] = [damped_mixing_length(kappa * f, a_plus)
                                          for f in (0.80, 1.0, 1.25)]
            record["truth"] = record["per_sample_truth"][1]
            record["heldout_truth"] = None
        else:
            record["truth"] = damped_mixing_length(kappa, a_plus)
            record["heldout_truth"] = record["truth"]
        cases.append(record)
    return cases


def answerable(case):
    return case["regime"] == "recoverable"
