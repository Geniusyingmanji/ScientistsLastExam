# Reproducible references; no global-best claim

All numbers below are **local development diagnostics** from 2026-09-06. This
package remains candidate. Score one is the greedy Sidon construction, not SoTA,
and the title of this repository-required file does not assert a world record.

## 1. Reference construction

`verification/reference_search.py:sidon_certificate(problem)` recomputes these
marks without oracle access. The unchanged proposed frequency ceilings all fit.

| n | Frequency ceiling | Greedy marks | Exact r | r/sqrt(n) | Score |
|---:|---:|---|---:|---:|---:|
| 15 | 64 | 0,1,3,7,12,20 | 3 | 0.7745966692414834 | 1 |
| 28 | 128 | 0,1,3,7,12,20,30,44 | 4 | 0.7559289460184544 | 1 |
| 45 | 256 | 0,1,3,7,12,20,30,44,65,80 | 5 | 0.7453559924999299 | 1 |

The certificates have one factor, 6/8/10 sparse terms, and 36/64/100 pair
products. Their proof is the distinct-difference squared-modulus identity derived
in [scientific_basis.md](scientific_basis.md). Theoretical context is
[Bedert v3](https://arxiv.org/abs/2509.05260v3); this constructive anchor is
independently generated rather than extracted from a published record.

## 2. Baseline

`solution.py:build_certificate(problem)` returns n factors with weight 1/2 and
polynomials `1+z^a`, for a=1,...,n. Every world is valid, bounds are 15/28/45,
and all world and aggregate scores are zero. This explicit certificate makes
format failure separable from scientific improvement.

## 3. Ablation ladder

The following are bounded construction probes, not a validated difficulty
ladder. Grid size is 8192, common rational precision is 24 dyadic bits, and the
local NumPy generator is reset to seed 20260906 per call. Proposal counts include
draws skipped when the replacement frequency was already present.

| n | Swap proposals | Exact-checked returned r | Score | Selected A changed? | Seconds incl. exact check |
|---:|---:|---:|---:|---|---:|
| 15 | 0 | 3 | 1 | no | 0.0172 |
| 15 | 128 | 2.788586283658290 | 1.0176178096951425 | yes | 0.0071 |
| 15 | 1024 | 2.736475148797172 | 1.0219604042669024 | yes | 0.0128 |
| 28 | 0 | 4 | 1 | no | 0.0112 |
| 28 | 128 | 4 | 1 | no | 0.0111 |
| 28 | 1024 | 4 | 1 | no | 0.0174 |
| 45 | 0 | 4.987834796894589 | 1.0003041300776352 | no | 0.0353 |
| 45 | 128 | 4.987834796894589 | 1.0003041300776352 | no | 0.0340 |
| 45 | 1024 | 4.987834796894589 | 1.0003041300776352 | no | 0.0400 |

Zero proposals still attempts spectral extraction. The 15-term case benefits
from discrete search, the 45-term gain comes from extraction alone, and the
28-term reference is not improved by these probes. No uniform ablation gain is
claimed. Removing rational correction leaves a sampled numerical screen with
no admissible certificate, so its numerical objective is not a score.

## 4. Shortcut probes and exact outputs

The 1024-proposal result for n=15 is exactly
`770249278776973/281474976710656`; the 128-proposal result is
`196229314812093/70368744177664`. For n=45, all three extraction probes return
`175493835411563/35184372088832`. These are certified values for particular sets,
not global optima. The 15-term result uses 21 factors, 61 terms, 521 pair products;
the 45-term result uses 81 factors, 241 terms, 6881 pair products. Both need only
49 bits for the common denominator LCM. No resource or frequency caps were
increased. The inexpensive score-one Sidon construction and these easy gains
must be disclosed during admission review; normalization was not changed to
hide them.

## 5. Frontier/model draw

Not performed. There are no strong-model calibration, model comparison, Linux
sandbox, empirical hard/flagship certification, or global-experiment claims.
The public [Epoch problem](https://epoch.ai/frontiermath/open-problems/chowla-cosine)
is a known family overlap; the fixed finite optimization objective and exact
certificate format differ from its quantified asymptotic target.

## 6. Construction errors and scientific traps

- A={1,2}, r=1 passes the four-point grid at multiples of pi/2 but is false:
  at cos(x)=-1/4 the shifted polynomial is -1/8. Tests reject it exactly.
- B={0,1,2} repeats a difference and gives a multiset cosine coefficient. It
  cannot be silently deduplicated into a valid certificate.
- Comparing only selected lags misses unsupported harmonics. Tests add a
  spurious degree-eight factor while matching all selected coefficients.
- Per-scalar rational limits alone permit denominator explosion. A collective
  512-bit LCM limit was added before Fraction arithmetic; dyadic extraction fits.
- During test design, the first arbitrary-q correction example gave r=33/16,
  exceeding its n=2 contract. Before implementation it was replaced by a
  hand-derived r=25/16 example, now also expanded independently with SymPy.

## 7. Robustness and reproduction

Focused tests exercise the exact 9/8 witness, independent symbolic Laurent
expansions, dense trigonometric cross-checks, positive and negative correction
errors, q=0, 45 malformed payloads, raw integer and work limits, collective LCM
limits, candidate exceptions, partial success, input mutation, complete payload
determinism, valid baseline/reference anchors, and scores above one.

From the repository root, using a Python with NumPy, pytest and SymPy:

```bash
python -m pytest -q tests/test_chowla_cosine_certificate.py
```

The exact checker and trivial baseline use only the Python standard library.
SymPy is an independent test dependency; the numerical construction uses NumPy.
To reproduce the bounded local diagnostics without a second verifier:

```python
import importlib.util
from pathlib import Path
from time import perf_counter
from fractions import Fraction

base = Path("benchmarks/Mathematics/ChowlaCosineCertificate/verification")
def load(name):
    spec = importlib.util.spec_from_file_location(name, base / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

evaluator, reference = load("evaluator"), load("reference_search")
for problem in evaluator.evaluation_problems():
    for proposals in (0, 128, 1024):
        start = perf_counter()
        submission = reference.search_certificate(problem, iterations=proposals, grid_size=8192)
        bound = evaluator.certified_bound(submission, problem)
        reference_bound = Fraction(*problem["reference_bound"])
        score = (problem["n_terms"] - bound) / (problem["n_terms"] - reference_bound)
        print(problem["n_terms"], proposals, bound, float(score), perf_counter() - start)
```

The local complete score payloads repeated exactly. Floating-point search paths
may differ across numerical-library/platform versions; the rational certificate
itself has platform-independent mathematical meaning and is always rechecked.
