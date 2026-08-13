# Graph reconstruction from distance queries

A weighted network exists but you cannot see it. You may ask how far apart any two nodes are, a
limited number of times. Recover the edges.

## Why this is inverse and not transcription

A short distance between two nodes does not make them adjacent — it may be a two-hop path whose
legs happen to be short. Separating direct edges from short paths is the whole problem, and it is
the classical question in network tomography.

Two things make it more than bookkeeping:

- **The budget is smaller than the number of pairs.** Which pairs you ask about determines what
  you can conclude, and a good strategy adapts to what earlier answers revealed.
- **Some edges are invisible.** An edge whose endpoints have an equally short route around it
  lies on no shortest path between any pair. No number of distance queries can reveal it.

## Your function

```python
def reconstruct(problem, distance) -> dict:
    ...
```

`problem` gives `nodes` and `query_budget`. `distance(u, v)` returns the shortest-path distance
and costs one unit per distinct unordered pair; repeats are free; it returns `None` once the
budget is spent. Return

```python
{"edges": [(u, v, weight), ...]}
{"abstain": True}          # when the graph is not identifiable from distances
```

## Oracle

Distances come from **networkx**, the standard library for graph algorithms, so they are computed
by the reference implementation of Dijkstra rather than by a reimplementation of it. networkx is
available to you as well.

## Three axes, reported separately

- **mechanism** — F1 over the edge set with weights, on the graphs that are identifiable.
- **false discovery rate** — edges claimed that do not exist, over the pairs that are not edges.
- **calibrated refusal** — about half the graphs contain an invisible edge. Abstaining is correct
  there and wrong everywhere else; abstaining on an identifiable graph scores zero for it.

Invisible edges are excluded from both recovery and false discovery rather than counted as
misses, because no method can find them and scoring them would measure luck.

The three are printed side by side and must not be averaged. A reconstruction can look
respectable on F1 while inventing edges, and one number would hide that.

## Rules

- Only edit `solution.py`; keep `reconstruct(problem, distance)`.
- Deterministic CPU code. The standard library, NumPy, SciPy and networkx are available.
- `sle.contract_lint` is importable and free to call for shape checks.
- Do not read `verification/` or `frontier_eval/`.

## Difficulty

Graphs are generated, not hand-drawn, and filtered so that about half of each set is
unidentifiable. Harder levels add nodes, thin the graph and cut the budget fraction. Read the node
count and budget from `problem` rather than assuming them.
