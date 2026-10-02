# Public evidence packets

`python -m env.evidence_packet` makes a separate discovery-depth review packet from an existing trusted `report.json`. It never changes the report, imports a world/runner/scorer, executes candidate code, replays predictions, computes a new score, or calls an API. Only the standard library is used. Packets contain inert candidate text and code; reviewers must treat that content as evidence, never as instructions.

```sh
python -m env.evidence_packet --report /operator/episode/report.json \
  --transport /operator/episode/model-transport.jsonl \
  --output /review/review-0001.json --review-id review-0001
```

For a research-runner report, optionally supply its existing scientific bundle and driver receipts. The latter allow an immutable model snapshot reference to be bound to the resolved candidate source without executing or reconstructing it:

```sh
python -m env.evidence_packet --report /operator/research/report.json \
  --science-bundle /operator/research/science/bundle-private.json \
  --driver-receipts /operator/research/driver-receipts \
  --output /review/review-0002.json --review-id review-0002
```

The output must be new. Inputs are read as bytes, hashed and checked unchanged before publication. The receipt printed by the CLI contains hashes and extraction counts, not source paths or model identity. Keep any operator crosswalk between packet IDs and episode paths outside the reviewer directory. A source-report hash supports custody but can also permit linkage if a reviewer already has the original report; this is not an absolute anonymity guarantee.

## Included evidence and provenance

| Packet field | Authoritative source and validation |
|---|---|
| `rounds[].candidate_response` | `rounds[].response`, strict JSON with duplicate keys, nonfinite numbers, trailing text, fences and invalid Unicode rejected; explicit action/spec allowlists, no fallback to reconstructed actions |
| `research_note`, action outcome, analysis | Unique explicit history `round` equal to response `round`; analysis only when the parsed action is `analyze` |
| `observations` | Public history or top-level public `records`; only `id/spec/observation`; explicit per-world spec fields; observation axis, matrix shape and channels checked; repeated copies must agree |
| `final_candidate` | Parsed submit/finish in the same unique round as its freeze/finish outcome; never recovered from private prediction-panel output |
| `candidate_lineage` | The candidate's literal `revision_of`, `change_note`, rival evidence IDs and snapshot references |
| `candidate_versions` | Allowlisted candidate-owned snapshot receipts; no paths, URI or operator storage metadata; creation round/parameter-body absence is explicit |
| `public_contexts` | Optional original transport `started.request.messages` with exactly system/user roles; recompute UTF-8 request hash and the report's ASCII-canonical prompt/system hashes; require explicit round match; retain only actual sent system text and parsed user `problem` |
| `prospective` | Public same-round response with test ID, seal, observed IDs and allowlisted numerical comparison/counterexample results; no automatic depth or mechanism claim |
| Optional sealed public registration | Whole-registration seal must match the same-round public response; scientific request must match the raw candidate request (or journal-bound snapshot resolution); candidate source/prediction hashes and prediction matrix dimensions are checked; only public design, rivals, code, predictions, public observation contract and version references are exported |

The explicit public schema covers the eight current worlds and the research runner's `prospective_fixture` parser fixture. A fixture packet is marked `fixture_only`; it is not a ninth evaluated world or a model result. These schemas validate safe field/type projection and evidence alignment, not the scientific validity of an intervention. They do not call simulator validation or invent default values. New public fields require an intentional schema update; unexpected fields in a spec/action fail closed and produce a gap rather than silently changing the experiment's meaning.

Raw candidate responses that pass the schema are preserved as parsed JSON, with a SHA-256 of their exact original string. Formatting is not the action's scientific content. A malformed/unparseable response is not exported verbatim because doing so bypasses the allowlist; its response state/hash and any independently available public research note remain. Note-only or empty actions remain visibly incomplete. Never infer a missing round from array position, the next action, a final predictor file, or evaluator internals.

## What is excluded

The builder constructs a fresh object; it does not copy a report and blacklist a few keys. It excludes model/provider/request metadata, usage, decoding and every operator configuration container; world/panel seeds and confirmation/noise keys; hidden evaluation specifications and clean truth; baseline results, all score panels and score summaries; private class labels, episode/cohort labels, source/manifest metadata, paths, transport envelopes and operator runtime identifiers. It does not copy `scientific_task` wholesale. Only field-allowlisted portions of a matching trusted registration or driver resolution are eligible for export. The verified original public problem is a deliberate scientific payload: if the candidate was explicitly given an equation family or public scoring rule, retain it so a reviewer does not mistake supplied knowledge for discovery. Public score-contract rules are not private achieved scores. No transport model/endpoint/config/usage or user-prompt budget/history envelope is exported.

There is one deliberate content boundary: candidate-authored notes, code, explanation, stdout and `analysis.result` are scientific payloads. Their strings and arbitrary result JSON are preserved without name/path regex scrubbing, because that can alter scientific claims or fitted parameters. A candidate can mention its model identity or include identity-bearing text in those payloads. This is **metadata blinding, not absolute double blinding or a sanitizer for adversarially forged public payloads**. The input must be an authentic trusted report. A secret injected by an operator into a field already declared to be candidate-authored public text cannot be distinguished from actual candidate content by a field projection. Operator canary tests target metadata containers and unknown structural fields, and separately verify that free scientific text remains unchanged.

## Partial evidence is the normal honest outcome

Missing fields, unknown public schemas, duplicate or mismatched round/observation bindings, malformed JSON, missing sealed matrices, tampered seals, unavailable snapshot resolutions, and missing final actions appear in `gaps`. Unbound public records remain at `round: null`. A history round alone does not prove a request/spec match; that weaker case is labeled explicitly. The builder retains original response order and never repairs a chronology.

Current legacy/research reports do not themselves contain the original complete public problem/system prompts. Supplying the original transport JSONL can close that context gap, only for rounds whose request, prompt and system hashes all match. Missing, duplicated or mismatching requests remain explicit gaps; no current `world.describe()` fallback is permitted. Full sealed predictions without trusted temporal evidence are still not an authenticated prospective test. A local driver hash chain can bind snapshot resolution to a candidate round, but this tool does not authenticate an external clock, verify the complete science observation chain, re-execute predictors, recompute numerical verdicts, or certify reproducibility. It emits `replay_performed: false` and `chronology: not_authenticated_by_this_packet`. Reviewers must not promote hash equality into D3/D4 evidence on its own. All current packets retain this chronology limitation and are partial evidence packets, not replay certificates.

Use these packets for evidence-first D2/D3/D4 review: what was observed, proposed, frozen, contradicted, revised and retested. Keep completion rates, scores and model identities in their existing separate metric workflow. The packet itself assigns no discovery depth, mechanism success, pass/fail scientific grade or comparative model result.

## Verification

```sh
python -m unittest env.tests.test_evidence_packet -v
```

Tests use inert JSON and source strings that would raise if executed. They cover strict parsing, metadata canaries, unknown-spec rejection, exact candidate preservation, explicit round/record binding, mismatch/duplicate/orphan handling, sealed matrix integrity, snapshot journal binding/tampering, no candidate execution/imports, exclusive output and unchanged source bytes. Large historical packets belong in the central artifact archive, not Git.
