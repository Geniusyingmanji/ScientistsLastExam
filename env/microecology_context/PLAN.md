> 当前持续执行计划见 [MATRIX_PLAN.md](MATRIX_PLAN.md)。以下为保留的首轮开发计划，不代表已完成全部预定运行。

# Context-dependent three-species discovery, development v0.1

Approved 2026-10-15. Separate prototype; legacy microecology remains frozen.

## Frozen first development unit
- Three structural families: fixed allocation, signal-controlled allocation,
  environmental threshold plus delayed allocation. Two exposed development
  instances each, seeds 15101..15106. Never reuse for unseen confirmation.
- Carbon states S,A,B,C,X,N,Y,Q,W (mmol C/L); allocation h dimensionless.
  A secretes Q and X; B consumes X and allocates output between C nutrient N
  and inhibitor Y. C consumes N subject to Y inhibition.
- Signal is a carbon pool, not a free extra product. Temperature changes kinetic
  rates and, only in the context family, the switching threshold.
- Initial A/B/C in [0,1], substrate [0,5], metabolites [0,2]. Temperature
  [20,40] C. Duration <=48h; <=25 samples, <=8 scheduled interventions.
  Actions feed a pool, remove a fraction of a pool, or set temperature.
  Each query resets all states; preparation history is explicit in the query.
- First numerical screen <=120 trajectories, independent DOP853/Radau checks,
  carbon balance, positivity, legal event boundaries, signal intervention and
  full/terminal observation consistency. Failure blocks agent admission.
- Observation noise independent Gaussian sigma .002, clipped at zero. No
  biological process noise in v0.1; add separately after core identification.
- Candidate sees all pool concentrations under anonymous channel identifiers
  and biomass labels; no hidden allocation state or private equations.
- Agent pilot: six instances, <=48 experiment calls each, <=1200s wall,
  no automatic retries; GPT on g450 via the Codex harness.
  Freeze actual model, source hash, public contract and transcript before runs.

## Scientific ambiguity and gates
Low-Q observations can make fixed and regulated allocation indistinguishable.
Signal addition/removal at matched biomass separates those particular accounts.
Temperature-step histories and pulse/washout distinguish instantaneous from
lagged response when adequate sampling resolves the lag. Saturated Q regimes
need not identify threshold or Hill exponent; h initial/state equivalences must
be reported rather than falsely scored as unique discovery.

## Discovery evaluation
Separate predictive transfer, recovered mechanism modules, equation equivalence,
and prospective evidence. Do not certify equations by prose or exact strings.
Require submitted executable rates/equations plus parameter bounds and units.
Canonical expression comparison and independent numeric witnesses can validate
algebraic equivalents; functional agreement alone is not structural proof.
Mechanism coverage and false discoveries use a frozen identifiable-module list.
Initially manual structured review for mechanism/equation claims; never substitute
an automated hidden-label quiz. No composite score before rubric calibration.

## Runtime boundary
Trusted simulator and grader must not be readable by Codex shell. Expose an
experiment RPC/MCP surface, immutable public observations and writable analysis
workspace. Authentication stays outside candidate tools. A tool-level denial test
must prove hidden source and target files inaccessible before a scientific run.
