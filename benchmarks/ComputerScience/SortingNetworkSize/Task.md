# SortingNetworkSize — small sorting networks for 13–17 inputs

## Scientific question

Construct a fixed sequence of compare-exchange gates that sorts every input using
as few comparators as possible. Gate `[i,j]` puts the smaller value on wire `i`
and the larger on wire `j`; gate order matters. Correctness is checked exactly.

## Submission contract

Edit `solution.py` and define `build_network(n: int) -> list` for
**n = 13, 14, 15, 16, 17**. Return a materialized list of pairs `[i,j]` satisfying
`0 <= i < j < n`. Tuples and numeric NumPy arrays are also accepted by the transport.
Finite integral floats such as `5.0` are accepted; booleans, strings, nonintegral
values, NaN/Inf and out-of-range indices are invalid. Duplicate and redundant gates
are legal and counted. At most `n*n` gates are accepted per instance.

No other inputs are supplied. Only edit `solution.py`; do not read evaluator,
verification or frontier_eval files. Use NumPy and the Python standard library.
The default whole-evaluation timeout is 300 seconds across all five calls,
including candidate search and verification. Allocate search effort accordingly;
the output-size cap is separate from this time budget.

## Exact verification

The evaluator simulates every one of the `2^n` Boolean inputs. By the 0-1 principle,
a network passing this check sorts arbitrary ordered values. Reported correctness
or comparator counts are never trusted.

All five instances must be valid. If any returned network is invalid,
`combined_score=0`, `valid=0`, and `raw_score=-1e18`. The fraction of valid instances
is reported as `feasibility_rate`. Per-instance diagnostics retain the failure
reason, but a valid subset earns no aggregate credit. Candidate exceptions may
terminate the sandbox run and produce the runner's failure sentinel.

## Scoring

The executable zero anchor constructs a power-of-two Batcher odd-even mergesort
network, tries every contiguous placement of the real wires between negative and
positive sentinels, and deletes redundant gates to a fixed point. This procedure
is supplied in `solution.py` and independently reconstructed by the evaluator.
The target is an externally cited lower bound on comparator count.

| n | Generic baseline B | Size lower bound L |
|---|---:|---:|
| 13 | 48 | 44 |
| 14 | 53 | 48 |
| 15 | 59 | 53 |
| 16 | 63 | 57 |
| 17 | 75 | 63 |

For a valid network of size m, `score(n) = clip((B-m)/(B-L), 0, 1)`.
When all five networks are valid, `combined_score` is their mean score and
`raw_score` is minus their mean actual size. Both reward fewer comparators.

A score of one means a verified construction attains the cited lower bound;
optimality is conditional on that external bound. The checker proves sorting,
not the lower-bound theorem. These bounds are not known to be attainable:
unused score range is not measured scientific headroom. Clipped scoring expresses
this mathematical target rather than claiming an uncapped performance record.
A valid construction below a cited bound produces `bound_contradiction=1`, an
`audit_required` diagnostic and invalid aggregate scores pending independent audit.

## Relations and differences

- `InformationTheory/ShannonCapacityCertificate` also compares a construction
  with external bounds on an open quantity; its artifact is a graph certificate,
  while this task verifies an ordered comparator circuit.
- `Mathematics/NonlinearCodeRecords` optimizes code size subject to distance
  constraints; this task minimizes sequential gates subject to exact sorting.
- `Algorithm/TensorRank555` and `Algorithm/MatrixMultiplicationRank` optimize
  algebraic decompositions rather than comparator circuits.

The task remains a candidate. Exact verification establishes validity, but does
not distinguish independent search from memorized constructions or establish
frontier-model difficulty. Source provenance and method diagnostics are kept in
reviewer-only reference documentation.
