# Manual discovery-evidence annotations

`env.discovery_evidence` keeps human scientific judgments separate from checks of
their evidence references. It accepts one existing public review packet from
`env.evidence_packet`, bound by the SHA-256 of its **exact original bytes**.
It never imports a world, runner, scorer, simulator or model API, and never
executes candidate code. Its only project dependency is the inert packet reader's
strict JSON/hash helpers.

There is no D0–D4 computation, scientific-success verdict, reviewer winner,
cross-packet pooling or model discovery rate. `supported` is a reviewer's manual
assessment, not a validator result. `mechanically_consistent: true` means only
that the implemented structure, reference and recorded-order checks passed.
It does not verify semantic truth, hypothesis quality, quantitative accuracy,
causal eligibility, parameter identity, protocol equivalence or scientific depth.

## Form

Use `create_annotation(packet_bytes, reviewer_id)` or the CLI to obtain the exact
schema. Unknown fields are rejected, including added depth/score fields.

- The root contains `protocol`, `packet_sha256`, `reviewer_id`, `question`,
  `scope`, `prior_knowledge`, and `dimensions`.
- Each of `question`, `scope`, `prior_knowledge` has `text`, `attribution`,
  and `citations`.
- `dimensions` has exactly `quantitative_model`, `prospective_test`,
  `meaningful_rival`, `changed_regime_transfer`, `empirical_boundary`, and
  `uncertainty_and_negative_results`.
- Each dimension has `assessment`, `attribution`, `rationale`, `citations`,
  `prospective_links`, and `gaps` (an array of human-written strings).
- Assessments are `supported`, `partial`, `not_demonstrated`, or `unassessable`.
  A supported/partial item requires an evidence citation; that requirement does
  not establish that the cited evidence supports the judgment.
- Attribution is `candidate_explicit`, `reviewer_inferred`, `public_supplied`,
  or `unknown`. The validator checks source categories, not whether the prose
  actually says what the reviewer claims. Mark a reviewer-constructed rival or
  extrapolation as `reviewer_inferred`, even if it cites candidate text.

All template assessments start `unassessable`, attribution `unknown`, with
`manual_review_required` gaps. Fill them manually; do not interpret a blank form
as a negative result.

## Exact anchors

A citation has exactly these fields (this is an **invented fixture**, not a trace):

```json
{
  "path": "/rounds/0/candidate_response/note",
  "quote": "predict a decrease",
  "round": 1,
  "observation_id": null
}
```

`path` is an RFC 6901 JSON pointer, with zero-based array indices. It must select
existing content. For strings, `quote` must be an exact nonempty substring;
no normalization, paraphrase or fuzzy match occurs. For a non-string value,
quote the **whole** canonical JSON value, using sorted object keys, compact
separators, UTF-8 characters and no NaN/Infinity. A numeric value of 0.4 therefore
uses `"quote": "0.4"`. Numbers in a code string remain inert strings.

Allowed locations are candidate response text/data, bound research notes,
analysis results/stdout/errors, observations, public context system/problem,
final candidate content, packet gaps, and snapshot receipts. The validator
derives source type from the path; the annotation cannot label a tool error as
candidate analysis. `round` must match its actual owner, and observation
citations must also give the exact observation ID. Other citations use a null
observation ID; context/gap/receipt citations use a null round. A receipt with
no creation round does not acquire a time from its position in an array.

Only successful analysis results/stdout count as candidate analysis material.
Failed analysis outputs are tool-error evidence, not scientific failures.
They may document unavailable analysis in `uncertainty_and_negative_results`;
they cannot serve as prospective prediction sources or positive/partial
`empirical_boundary` evidence. Assigned initial values and clamped readouts
still require human causal-eligibility review; this tool does not infer those
world-specific semantics or turn an assignment into a scientific finding.

## Recorded order, not clock authentication

A dimension may contain a link:

```json
{
  "citation_index": 0,
  "target_observation_id": "obs-fixture",
  "claimed_order": "before"
}
```

`citation_index` selects a citation in that dimension. The source must be
candidate request material or successful analysis output; the target ID must
exist uniquely. `claimed_order` is `before` or `unknown`.

- A parsed request note/code with bound earlier round may precede a later target.
- A candidate experiment/preregistration request note may precede its **same-round**
  bound observations. The note is part of the request, not the returned outcome.
- Analysis results are available after that round's action: they cannot be used
  as predictions before observations in the same or an earlier round.
- Post-target analysis remains post-target even if its text says “preregistered”.
- Missing, ambiguous or unverified local bindings yield `unknown` plus a gap.
  They are not fabricated into ordering evidence. Known contradictions to a
  `before` claim are mechanical errors.

Returned relations are `before_recorded`, `not_before_recorded`, or `unknown`.
Packet gaps remain in the report. **Every report says
`external_chronology: unverified` and `semantic_validation: not_performed`.**
Even a correctly ordered code excerpt does not prove it was the program that
made the prediction, that coefficients were unchanged, or that a test separated
meaningful rivals. Those are manual judgments with their own citations/gaps.

## Comparison and private CLI outputs

`compare_annotations(packet_bytes, left, right)` requires both forms to pass
mechanical checks against the same packet bytes. It recursively lists differing
fields and includes both mechanical reports, preserving unresolved timing/gaps.
It does not resolve disagreement or modify either annotation. Unequal arrays
are reported as differing fields without trying to match or pool their entries.

Create an existing private output directory, then run from the repository root:

```sh
python -m env.discovery_evidence template --packet /private/packet.json --reviewer-id reviewer-a --output /private/annotation-a.json
python -m env.discovery_evidence validate --packet /private/packet.json --annotation /private/annotation-a.json --output /private/validation-a.json
python -m env.discovery_evidence compare --packet /private/packet.json --left /private/annotation-a.json --right /private/annotation-b.json --output /private/disagreements.json
```

Each command creates exactly one new output with exclusive creation and mode
0600; it refuses existing files, symlinks and replacing an input. It checks all
input bytes before and after writing and prints input/output hashes to stdout.
If an input changes during the write, the command raises an error and the output
must be treated as unverified. Validation exits 1 for mechanical errors, 0 for
mechanical consistency; neither exit code is a scientific verdict. API calls
are read-only, apart from the explicitly writing CLI.

## Evidence to request in future disputed cases

These examples describe missing evidence types, not new historical requirements
or retroactive preregistration. No private episode trajectories are included.

- **Oscillators:** cite the numeric model before the target and distinguish fresh
  repeats from new controls. Anchor the candidate's real-versus-absent-edge
  prediction separately from a reviewer-inferred interpolation alternative.
  Record successful coefficient-preserving transfer separately from empirical
  validity-boundary investigation.
- **Gene regulation:** match amplitude, start/end time, duration, initial state
  and readout exactly. Successful values for one model do not automatically
  separate slow relaxation from switching. Cite the rival's differing predicted
  outcome and mark any remaining ambiguity; a mismatched duration protocol is
  not repaired by a nearby successful amplitude test.
- **Ising:** anchor direct-versus-indirect intervention predictions and the
  unchanged pre-target coefficient version. Within-family transfer can be real.
  Keep stress-test success separate from locating a failure/validity boundary,
  and keep small refit shifts separate from parameter uncertainty estimates.

A reviewer should also distinguish experimental failures from computational
errors, empirical boundary investigations from generic domain caveats, and
publicly supplied equation knowledge from learned instance-specific results.
This validator cannot make those scientific distinctions from text.
