# Candidate resources: exact Chowla certificates and approximate MUB6 design

This combined local diff is intentionally separable by task directory. Both packages are registered
as `candidate`, excluded from the default certified inventory, and uncalibrated. It does not request
scientific admission. The MUB package remains removable from central registration if the pending
positioning decision is resource-only rather than candidate.

## Mathematics/ChowlaCosineCertificate

This package chooses finite frequency sets and submits exact rational squared-modulus Laurent
identities proving a global bound for their cosine sums. Verification checks all signed harmonics,
work/bit/denominator budgets, and malformed candidates exactly. The valid baseline scores zero; the
public greedy Sidon constructor scores one. Independent symbolic identities and dense numerical
controls agree with the exact checker.

The main caveat is difficulty, not certificate soundness. The score-one Sidon construction is cheap,
and a bounded local spectral proposal plus exact correction already reaches aggregate score
`1.007421511448179`. This is a stronger finite reference certificate, not a global optimum, global
SoTA, improvement of Bedert's asymptotic result, or evidence that the task is hard for current models.

## QuantumFoundations/MutuallyUnbiasedBases6

This package exactly scores four approximate dimension-six measurement bases represented by bounded
Gaussian-integer rays. The stored rational score-one fixture is recomputed from trusted data and
agrees with the Raynal-Lu-Englert construction. Exact orthogonality, transition-probability marginals,
the ASD normalization, and a rigorous rational enclosure of the published algebraic value have
independent checks.

The public Raynal block equations and public exact Gram-Schmidt helper cheaply reconstruct score one.
A 36-bit requantization already scores above the fixed rational fixture, so ordinary score above one
is not the scientific frontier. `beyond_published_reference` is a separate exact flag; no probe passed
it. The Q(i) representation excludes exact triples including I, so this is approximate optimization
and says nothing decisive about unrestricted exact MUB existence. The published construction is not
known to be globally optimal.

## Dependencies and local structural acceptance

SymPy `1.14.0` is added only to the CI test environment for independent algebraic tests. It is not
added to candidate mounts, candidate dependency policy, or either standard-library oracle.

On macOS, run only structural and focused checks:

```sh
PYTHON=/Users/kel/Projects/daily_work/research/evolve_SAE/.venv-sle/bin/python
"$PYTHON" -m pytest -q tests/test_chowla_mub_registration.py tests/test_task_cards.py tests/test_exam_taxonomy.py tests/test_task_inventory_document.py
"$PYTHON" -m pytest -q tests/test_chowla_cosine_certificate.py tests/test_mutually_unbiased_bases6.py
"$PYTHON" scripts/check_task_contribution.py --task Mathematics/ChowlaCosineCertificate --skip-eval
"$PYTHON" scripts/check_task_contribution.py --task QuantumFoundations/MutuallyUnbiasedBases6 --skip-eval
"$PYTHON" scripts/check_numeric_keys_hold_numbers.py
"$PYTHON" scripts/audit_documented_keys.py --output /tmp/chowla-mub-documented-keys.json
```

`--skip-eval` is explicitly not sandbox evidence: it skips baseline execution, repeat determinism,
and malformed-candidate worker trials. Focused unit tests import trusted test fixtures in-process for
development checks; they are not a substitute for evaluating an untrusted candidate.

## Required Linux acceptance

These commands fail closed on macOS and require Bubblewrap plus `flock`. They use the trusted SLE
worker path; there is no in-process candidate-import fallback.

```sh
test "$(uname -s)" = Linux || { echo "Linux sandbox host required" >&2; exit 1; }
command -v bwrap >/dev/null || { echo "bubblewrap missing" >&2; exit 1; }
command -v flock >/dev/null || { echo "flock missing" >&2; exit 1; }
python -c 'import sympy; assert sympy.__version__ == "1.14.0"' || exit 1
python scripts/check_task_contribution.py --task Mathematics/ChowlaCosineCertificate || exit 1
python scripts/check_task_contribution.py --task QuantumFoundations/MutuallyUnbiasedBases6 || exit 1
python -m sle eval --allow-uncertified --task Mathematics/ChowlaCosineCertificate || exit 1
python -m sle eval --allow-uncertified --task QuantumFoundations/MutuallyUnbiasedBases6 || exit 1
```

Before admission, maintainers must also run hard-model calibration, verify long-horizon headroom,
obtain independent domain and evaluator-security review, and run the complete Linux CI suite. Global
experiment/evidence refresh is intentionally excluded from this candidate PR and occurs only after a
clean committed revision on a trusted Linux host. No model call, Linux bypass, publication, push, or
credential access is part of this diff.
