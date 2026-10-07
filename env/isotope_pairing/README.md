# Isotope pairing — unregistered synthetic prototype

Study product mass-isotopomer fractions under source recipe changes and chase.
The task tests the information in joint labeling, not only mean enrichment.
Source recipes and product resets are documented by `World.describe()`.
The private model interpolates pair preservation and independent assembly;
this synthetic bookkeeping model is not a validated metabolic simulator.

Development plan: docs/v2/ISOTOPE_PLAN.md. No model evaluation, difficulty
certification, shared runner adapters or parameter-inference screen yet.
Independent-source mixtures can remain indistinguishable: an admissible task
must allow that conclusion. Prototype source and development fixtures are exposed.

## 2026-10-07 numerical adapter gate

`campaign_scoring.py` adds independent `isotope-batch-score-1.0`: initial-state masking, pre-readout history eligibility, redundant/reversed contrast deduplication, strict submission and 32-pair verification. Three focused tests pass (128 simulated verification calls plus one clean mask fixture, zero model calls). Not wired to the agent driver or registered; Linux integration and complete admission remain pending. No frozen V1 scoring changes.
