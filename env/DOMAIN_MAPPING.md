# Single-model prospective domain mapping

`env.domain_mapping_runner` is a separate experimental operator protocol,
`sle-single-model-domain-0.1`. It tests one saved point predictor on a fixed finite
ordered family. It does not require a second rival, alter the existing research
wire protocol, change a score, or automatically identify a continuous boundary.
Implementation validation currently consists of pure/fixture tests only. Neither
an actual candidate process, an actual World trajectory nor a model API has been
validated through this new runner yet. Scientific acceptance remains
**same-family provisional** pending independent code review and bounded execution.

A complete map may have every point adequate, inadequate or inconclusive. These
are legitimate outcomes. Execution completion is not scientific success, and
missing replications do not become an inconclusive statistical test: their point
is `not_evaluated_incomplete`.

## What the evidence means

For each point j, the user declares one scalar linear readout of a single
canonical experiment. Coefficients are normalized once to unit absolute mass;
input and effective rational weights are retained. With public channel scales s,
let theta be the clean readout and p the already frozen predictor readout.
Adequacy means `abs(theta-p) <= tau`, for the same positive, scientifically
justified normalized tolerance across the family. The hard cap `tau <= 0.2` is
an administrative ceiling, not a scientific justification. A broad or vacuous
criterion can still fail separate evidence review.

The statistic uses the approved channel SD upper bounds sigma and mean-bias
bounds b. For n independent replicate vectors at a point,

```
B = sum(abs(w)*b/s)
V = (sum(abs(w)*sigma/s))**2
alpha_point = family_alpha / original_number_of_points
radius = B + sqrt(V/(n*alpha_point))
C = [mean_readout-radius, mean_readout+radius]
```

This variance bound permits arbitrary dependence among cells within a trajectory.
Chebyshev and the union bound give simultaneous coverage at least
`1-family_alpha` for the **finite vector of registered clean scalar readouts**,
conditional on the complete pre-mapping history and sealed predictor. Cross-point
independence is not needed. Replicates at a point must be independent of one
another and of the pre-mapping history. Unique private measurement keys enforce
the existing simulator noise contract; they are not a mathematical certification
of a finite PRNG implementation.

- `adequate`: C is wholly inside `[p-tau,p+tau]`.
- `inadequate`: the closed intervals are disjoint, with strict endpoint inequality.
- `inconclusive`: otherwise. Failure to reject is not adequacy.

The same simultaneous interval event supports both classification directions;
there is no extra factor of two. Alpha is never recycled after partial failure.
A completed subset has the original family's unconditional soundness guarantee,
not an improved guarantee conditional on task completion.

The microecology worlds clip `z + Gaussian noise` at zero. Their noisy mean differs
from the nonnegative clean z, so a Gaussian z/t interval is inappropriate. The
existing bound is `sigma/sqrt(2*pi)`; the new exact arithmetic uses the conservative
rational bound `max(declared_bias, 2*sigma/5)` for these approved clipped worlds.
Clipping is 1-Lipschitz, so its variance remains at most sigma squared. B does not
shrink with replication. Other noise/bias contracts must be approved before use.
No material-specific Gaussian chi-square diagnostic is applied to clipped noise.

Effective weights, readout means, variances, confidence radii, bands and decisions
use bounded exact rational arithmetic. The square-root upper bound is checked by
squaring it as a rational. Display endpoints round outward. Calculation rounding
is distinct from World/predictor integration error. The target is the fixed
implemented World's clean output; no new exact-ODE accuracy claim is made.
Parameter uncertainty and model approximation error are not readout noise. The
map assesses the particular fitted predictor that was saved, without a refit.

Coverage excludes unmeasured controls, all other channels, continuous intervals,
parameter regions, other instances and later map families. A combined claim over
several maps or models needs a separately prespecified outer alpha allocation.
A linear readout can hide errors by cancellation; its scalar scope must remain
explicit. Adjacent adequate/inadequate points do not prove a unique transition,
continuity or monotonicity between them.

## Registration and chronology

Use an existing saved `ModelSnapshots` artifact with its `{name, version, sha256}`
receipt, not an unsigned replacement code string. The existing safe parameter
binder produces the candidate source; the trusted process never executes it.
A complete source-history JSON array, its canonical SHA256, source observation
IDs, a trusted source-cutoff receipt, human model/grid priors and a readout
nontriviality explanation accompany the plan. Source history is not mapping data.
Authenticating that this history is complete remains the operator's responsibility.
Previously observed conditions must be disclosed and cannot support a claim of
unseen-condition extrapolation merely because measurement noise is fresh.

The plan has the following exact top-level fields:

```json
{
  "protocol": "sle-single-model-domain-0.1",
  "scope": "A finite, component-specific scientific question",
  "model_snapshot": {"name": "saved-name", "version": "v1", "sha256": "<saved receipt>"},
  "provenance": {
    "source_history_sha256": "<canonical digest of complete history>",
    "source_cutoff_receipt": "<trusted external receipt>",
    "source_observation_ids": ["source-observation-id"],
    "author_priors": "Disclose human code, functional form, fitting and point-grid choices",
    "readout_nontriviality": "Why the chosen response is not assigned by controls"
  },
  "domain": {
    "mode": "readout_horizon", "name": "horizon", "unit": "T",
    "lower": 0.75, "upper": 8.0, "varied_paths": ["/times/0"]
  },
  "points": [{
    "id": "short", "u": 0.75,
    "spec": {"position": [1.2, 0.0], "velocity": [0.0, 0.8], "times": [0.75]},
    "readout": [{"row": 0, "channel": "x", "coefficient": 1.0}],
    "replicates": 12
  }],
  "tolerance": 0.015,
  "tolerance_rationale": "Human engineering threshold: 0.03 L endpoint-x accuracy; not a mechanism criterion",
  "family_alpha": 0.05
}
```

The placeholders must be actual trusted hashes/receipts. This one-point schema
example does not supply a model, observations or evidence of a boundary.

The modes are `scalar_control`, `readout_horizon` and `ordered_path`. The first
two vary one numeric leaf exactly equal to u; horizon selects the final requested
coordinate and endpoint readout. A path is an explicit table with all varying
numeric leaves named. All other canonical fields remain identical. A table does
not certify legal or observed interpolation. Point coordinates are strictly
ordered and inside the declared nonempty domain. Duplicate readout cells and
scientifically duplicate conditions are rejected. The scalar template is fixed.

Every selected cell passes the unchanged public eligibility policy. t=0,
pre-resolution readouts, immediate post-event readouts and directly assigned
clamped outputs are excluded. Material drive knots are not state assignments.
The checker is not proof that an arbitrary sum or conservation identity is
scientifically nontrivial; that remains a separate review item.

The runner validates and admits the entire family before prediction. It obtains
every full prediction matrix twice in fresh `CandidateProxy` workers and rejects
nonfinite, malformed or nonrepeatable outputs. Two matches are a drift check,
not proof of universal determinism. A durable single seal covers the complete
prediction table, exact design and model binding before any new observation.
Collection is fixed point-major order with fixed n. There is no adaptive action,
resampling, early success stop, tolerance change, model update, alpha recycling
or resume. An unsuccessful family cannot be silently replaced.

The new class reuses unchanged `ProspectiveTask._predict` and `_observe` transport
methods with its own initialization, phase guard, report and lifecycle. It never
constructs the old two-rival session or fabricates its finish test. Old source and
preregister entry points are disabled. The original journal protocol identifies
the transport envelope; `domain_*` payloads and the new manifest identify the
single-model protocol. Its verifier has a separate event grammar.

A transport call may save `observation_returned` and then fail in its final budget
or checkpoint processing. That raw prefix remains in the journal. It is not
promoted to a completed mapping replication and is not replaced. Completed
points remain classifiable at their original alpha; partial points remain
unclassified. Failed prediction passes are likewise retained before any data.
Every raw return still receives exact schema, finite matrix, axis and channel
checks during replay, including a return retained only in a failed prefix.

## Resources, invocation and verification

Default ceilings only decrease through the Python API: 12 points, 4–16 repeats
per point, 96 mapping World calls, 10,000 experiment units, 24 predictor calls,
5 seconds per predictor call / 120 seconds charged, 3 seconds per simulation /
300 seconds cumulative, 2,048 MB candidate memory, 900 seconds wall, and 64 MiB of
artifacts. Admission reserves the entire call/cost schedule, maximal call-time
allowances and 30 seconds of wall margin. Actual timeout/failure attempts are
charged. The candidate memory limit does not cap trusted World memory. A slow
World may fail within these bounds. Input/snapshot limits remain bounded.
Per-call elapsed time includes the unchanged transport's measured overhead; an
actual overrun closes this runner as incomplete even if transport returned data.
The elapsed receipt and raw data are retained, without a retry or statistical
promotion of that call.

After a separate source/plan review and execution authorization, the operator
entry point is:

```bash
python -m env.domain_mapping_runner run --environment orbital_dynamics --seed 7 \
  --plan frozen-plan.json --snapshot saved-snapshot.json \
  --source-history complete-source-history.json --output new-private-directory
```

This command runs the actual candidate and World; it has **not** been run in the
current implementation validation. Programmatic use is
`DomainMappingTask(...).run(plan, snapshot, source_history)`. A new directory is
required. CLI input bytes are archived in addition to canonical objects.

Keep the returned receipt head outside the output directory, under trusted
operator control. Verification is read-only and never executes code or a World:

```bash
python -m env.domain_mapping_runner verify new-private-directory \
  --expected-head <externally-kept-final-receipt-head>
```

The verifier never defaults to the directory's own head. It checks the complete
chain, event order, source/snapshot/prediction artifacts, canonical plan,
point/replicate/spec/axis/channel associations, independent measurement keys,
complete-pass prediction seal, retained raw prefixes, terminal usage and numeric
replay. Resource audit schema `sle-domain-resource-audit-0.2` adds a trusted
monotone wall timestamp to every receipt. Replay validates all limits against
the fixed ceilings, full-family admission reservations, typed call counts,
charges and elapsed durations. Terminal actual seconds must equal the recorded
finished-call sums. A completed family must fit the elapsed and wall limits;
an authentic failed overrun may remain as incomplete evidence. Retained bundle
bytes must also fit the quota. These checks authenticate recorded accounting,
not an independent measurement of the operator clock, process memory, final
report-writing time or historical transient file-size peaks.

Runtime binding schema `sle-domain-runtime-binding-0.2` archives bound sources
under content hashes and identifies them by canonical repository-relative paths,
such as `env/domain_mapping.py`. The original absolute root is private provenance
only. Identical source bytes can therefore replay under a different checkout
root. Every local source helper used for numerical replay must match its bound
hash before replay; missing, duplicate or ambiguous identities fail closed.
The earlier unversioned implementation bundles are intentionally rejected by
this verifier and remain preserved with their original audit results. No old
prospective or research protocol is changed by these new schemas.

A missing terminal receipt yields an interrupted
prefix, even if all observations happen to be present. A missing/corrupt head
never triggers recovery. A self-consistent forged chain is not authenticated by
its own hash; the external anchor and trusted complete observation history matter.

Public reports contain scientific scope, model reference, design, human priors,
point classifications and limits. They omit operator seed, measurement keys,
source-cutoff receipt and operator runtime paths. The private directory contains
all raw receipts and source archives. Human-authored free text should itself
avoid including secrets. No `apparatus_only` presentation is claimed here.

## Author reference remains a separate unexecuted plan

The approved proposed orbital example fits a local constant-acceleration vector
once by a predetermined weighted least-squares rule using eight public short-arc
experiments at 0.25, 0.375 and 0.5 T. It then saves one predictor before testing
endpoint x at horizons 0.75, 1, 1.5, 2, 4 and 8 T, with 12 fresh repeats each.
Seed 7 is a previously studied development seed. The functional form, fit rule,
axis, horizons and precision target are human choices, not a hidden-force answer.

The approved tau=0.03 L is an **author-defined engineering accuracy threshold**,
1.5% of the public 2 L x scale and about 6.3 times the precomputed statistical
radius 0.0047434 L. It is not a mechanism or discovery standard. The source fit's
uncertainty is not inflated into observation noise. This is a useful local
approximation tested over longer sampled horizons, not a correct model paired
against a deliberately broken rival. No short-adequate/long-inadequate outcome
is guaranteed. No seed, grid, tolerance, readout or model may be retuned to force
that picture. The encompassing proposed budget is 80 World attempts, 12 candidate
calls and 864 orbital experiment units, including source acquisition.

The author source, exact plan and runtime still need their separate freeze,
independent review and run authorization. No reference fitting, real trajectory,
real candidate execution or GPT validation accompanies this implementation.
