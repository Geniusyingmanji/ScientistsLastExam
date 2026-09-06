# DiblockMorphologyDiscovery

## The question

A conformationally symmetric diblock melt self-assembles into lamellae, hexagonally packed
cylinders, BCC spheres, the Ia3d gyroid, or remains disordered. Frozen one-dimensional SAXS
traces are generated from the textbook harmonic ratios of those lattices (Matsen–Bates /
Leibler), not from a live SCFT solve.

You have **16** charged `measure(q_nm_inv)` assays. Identify the morphology, or refuse when
the trace is a kinetically trapped mixture of two lattices or an ABC triblock with two `q*`
families. Publishing `disorder` is allowed: a single broad RPA peak is in-family.

## What you implement

```python
def identify_morphology(problem, measure):
    ...
    return {"morphology": "lamella"|"hex"|"bcc"|"gyroid"|"disorder",
            "confidence": ..., "abstain": False}
```

### `problem` keys

| key | meaning |
|---|---|
| `q_bounds_nm_inv` | inclusive q window |
| `measure_budget_calls` | 16 |
| `family_names` | the five in-family names |
| `measurement_model` | `measure` returns I(q) |
| `abstain_when` | mixture or ABC |

## Relation and distinction

- Not `MaterialsScience/PhaseDiagramDiscovery`: metallic A–B isothermal sections, not diblock SAXS.
- Not `MaterialsScience/ProcessMicrostructurePropertyDesign` (PR #16): process–property Pareto, not morphology ID.
- Not `Spectroscopy/CrowdedSpectrumAssignment`: molecular line lists, not lattice harmonics.
- The reduced SAXS generator is **not** a digitization of Matsen and Bates Figure 2, and not
  the polyester circularity flagship.

## Scoring

Mechanism, false discovery, refusal and coverage are separate. Always-abstain is exactly zero.
`contract_lint` rejects unknown keys by failing closed at the evaluator.
