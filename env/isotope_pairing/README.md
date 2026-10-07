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

The explicit `model_driver.run_model_episode` entry now supports scripted local episode validation without registry admission. The driver/scorer plus legacy runner regression checks pass (34 tests); real Linux sandbox validation remains pending because the remote machine is unavailable. No isotope API run has been launched.

## Score1.1 correction
Stage B score1.0 rejected numeric NumPy arrays even though the sandbox transport accepts them. A frozen GPT predictor reproduced successfully; its metric failed with row-count mismatch and accepted its list conversion. Version1.1 normalizes real numeric ndarrays and retains strict finite/shape validation. Original cohort source/results remain archived; do not interpret affected zero scores as scientific difficulty. Six targeted checks pass locally; Linux validation of this correction is pending.
