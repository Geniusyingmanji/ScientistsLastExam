# Pattern formation laboratory

Status: **registered experimental environment**, selected explicitly as `pattern_formation`, the tenth registry entry. This world supplies a periodic scalar-field laboratory with 16 probes, controlled initial patterns, ring length and uniform drive. Every experiment is deterministic before measurement noise and runs entirely in Python/NumPy/SciPy. It is a phenomenological computational world, not a validated fluid or biological simulator. The registration review is **same-family / provisional**.

The agent receives `World.describe()` and public observations. That contract explains reset assignments, probe locations, noise and controls without supplying a governing equation or a menu of hidden families. The implementation, manifest, parameter generation, reference solver and development records are operator-only. Naming randomized instances does not establish resistance to memorization.

```python
from env.pattern_formation.world import World
world = World(7)                    # operator-selected instance; seed is never agent input
spec = world.describe()["examples"][0]
observation = world.run(spec, noise_key="experiment-001")
```

Each observation has `axis`, `channels` and `values`; values have shape `number_of_times × 16`. Clean evaluation uses `noise_key=None`. Reusing the same explicit noise key and specification reproduces a measurement; fresh keys produce independent modeled readout noise. Parameter values remain fixed across calls.

`baseline(records, spec)` transfers the nearest public trajectory's change from its assigned reset. Empty history predicts the reset persisting. It has no access to world seed, private equations or target outputs. This is a weak empirical comparator, not an oracle or a claim that the initial field actually persists.

Useful investigations include measuring the amplification of individual initial spatial modes, comparing zero and weakly patterned resets, shifting a pattern relative to the fixed apparatus origin, changing the ring length and testing predictions under changed drive. A static picture does not distinguish spontaneous organization from an externally maintained pattern. Exact zero may remain zero in a linearly unstable deterministic system; absence of growth from that reset does not prove stability.

The authoritative world has 64 discrete Fourier-collocation sites. Sixteen probes sample every fourth site; for example, a mode-8 sine can vanish at every probe while the field between probes is nonzero. Initial assignments are public and do not count as discovered dynamics. No process noise excites an exactly zero unforced reset. Shared quantitative-claim eligibility requires at least 0.25 T after reset at matched times; this fixed pilot resolution is not a calibrated physical constant or a mechanism test.

The shared registry, scientific task profiles, public evidence packets, prospective observation contract, public-initial calibration adapter and generic model-snapshot interface support explicit selection. The current full public description is used; `apparatus_only` remains unaudited for this world. Registration does not add this world to historical cohorts or the seven-world null calibration. Existing scoring formulas are unchanged.

Catalog and eligibility metadata revisions intentionally change shared source/contract hashes. Historical result hashes continue to identify their original source snapshot; old frozen manifests are not silently upgraded to this checkout. The integration regressions preserve old scientific schemas, prompt content and null definitions after explicitly removing only the new applicability/policy metadata.

Numerical work is bounded and may fail explicitly. A reviewed internal parameter combination with positive r0 and nonzero forcing exceeded the production Jacobian cap; no current generation stratum produces that combination. Three corresponding generated-stratum endpoint checks completed, while two reviewer reference integrations hit their own RHS cap. These checks do not certify numerical availability across the full constructor-valid parameter box. The original four generated development instances remain three forced, one damped and zero positive-r0 unforced; no difficulty or discovery-depth calibration is implied.

Read [SCIENTIFIC_NOTES.md](SCIENTIFIC_NOTES.md) for the operator model and its limitations. [development/README.md](development/README.md) records bounded implementation diagnostics. Those diagnostics establish neither GPT performance nor a discovery-depth grade. This prototype does not modify any existing frozen model cohort or scoring definition.

Run its focused tests with `python -m pytest env/pattern_formation/tests -q`. Run one private, bounded diagnostic batch with `python -m env.pattern_formation.calibrate --output /private/operator/path/diagnostics.json`; the output must not already exist. Do not publish that raw output to candidates.
