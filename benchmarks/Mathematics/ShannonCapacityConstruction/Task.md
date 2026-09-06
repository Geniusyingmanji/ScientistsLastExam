# ShannonCapacityConstruction — exact fixed-fifth-power C7 independent-set construction

Construct a large independent set in the **fixed fifth strong power of the
7-cycle**, represented by a list of length-five words over `{0,1,2,3,4,5,6}`.
This is a finite construction optimization task, not a request to determine the
full Shannon capacity of the 7-cycle.

Implement `build_code(problem)` and return exactly:

```python
{"codewords": [[0, 0, 0, 0, 0], [2, 0, 0, 0, 0]]}
```

The example is valid but weak. The fixed input is:

```python
{"alphabet_size": 7, "block_length": 5, "max_codewords": 512, "reference_size": 367}
```

There must be between 1 and 512 distinct rows. Each row must be a Python list of
exactly five native Python integers in `0..6`; booleans, floats, tuples, duplicate
rows, extra dictionary keys, and out-of-range symbols are rejected. No rounding,
deduplication, modulo correction, or tolerance is applied.

For **every distinct pair** of words `x, y`, at least one coordinate `j` must
satisfy `min(abs(x[j]-y[j]), 7-abs(x[j]-y[j])) > 1`. This exact integer predicate
is independence in the strong power. The oracle validates the complete matrix
before crediting any size. A malformed or non-independent artifact is invalid;
a valid small artifact remains valid even when it receives zero reward.

For a valid size `M`, the score is `max(0, (M-243)/(M_reference-243))`, where
`M_reference` is the verified public fixture length, 367. The product code
`{0,2,4}^5` in `solution.py` has 243 words and scores 0. Replaying the reference
scores 1. The score can exceed 1; `beyond_reference` means only that `M` exceeds
the verified fixture length. A claimed size without a passing exact artifact
receives no credit. The 512-word limit bounds resources; it is not a mathematical
optimum. No theoretical numerical upper bound is used for acceptance.

The public reference is the 367-word construction in the Appendix of
[Polak and Schrijver, arXiv:1808.07438v2 (2018)](https://arxiv.org/html/1808.07438v2).
It is cheaply retrievable and shipped in `references/c7_power5_reference.json`;
`verification/reference_code.py` is a standalone literal replay. Thus a score of
1 can demonstrate retrieval or reproduction, and does not establish research
difficulty or novelty. The historical capacity lower bound from this reference
has since been improved using higher powers; see `references/known_best.md`.

Evaluation is deterministic and uses exact checks with standard-library Python.
Any candidate code execution needs the surrounding harness's isolation and
resource limits. The callable wrapper itself is not an execution sandbox.
