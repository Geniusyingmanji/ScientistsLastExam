# Replicated ecological survey laboratory

Choose habitat strata and one to three survey visits. For each stratum the
apparatus samples 64 sites; those same sites receive all visits in that request.
It reports fractions detected on the first visit, at least once, and on every
visit. An undetected species may be absent or missed by the survey.

```python
from env.field_ecology.world import World
world = World(123)  # Operator only.
spec = {"habitat_values": [-1.5, 0.0, 1.5],
        "visits": ["rapid", "rapid", "intensive"]}
observed = world.run(spec, noise_key="fresh-independent-panel")
```

`habitat_values` has 1–24 strictly increasing values in [−1.6, 1.6]. Each visit
uses `rapid` or `intensive`. Different habitat rows sample independent groups;
a new experiment samples fresh populations under the same hidden ecological
laws. This is explicitly a replicated-population adaptation of the old fixed
48-site task, not an interface for returning to an earlier site's coordinates.

Within a request, occupancy is sampled once per site and shared across its
visits. Detection varies with survey method and possibly habitat. Occupied sites
can be missed; absent sites never produce false positives. The channels are
`first_visit_detection`, `any_visit_detection`, `all_visits_detection`.

Observed fractions are multiples of 1/64. Their marginal standard deviations
are at most 0.0625, but this is **not Gaussian measurement noise**. Channels are
correlated. With one visit all three channels are identical by definition.
With several visits, `all <= first <= any` holds for every realized panel.
Those bookkeeping identities do not constitute ecological discoveries.

Operator-only `noise_key=None` returns exact population expectations, not a
noise-free observation of an actual finite field panel. The public agent receives
sampled panels with fresh keys. These two estimands must not be confused.

Cost is 4 + strata × summed method batch costs (rapid 1, intensive 2), at most
148. One batch surveys 64 sites. Actual effort also records up to 4608 site
visits per request; cost units are not counts of individual sites.

Tests independently enumerate latent occupancy and detection histories, verify
exact variance/covariance and detection limits, and check sampling against
predeclared Monte Carlo tolerances. Run:

```
python -m unittest discover -s env/field_ecology/tests -p 'test_*.py'
```

The baseline interpolates public fractions from matching visit designs; with no
matching records it predicts 0.5. This weak baseline does not establish headroom.
See `SCIENTIFIC_NOTES.md` for what these synthetic surveys can identify.
