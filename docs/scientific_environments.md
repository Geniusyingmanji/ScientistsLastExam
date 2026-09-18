# Scientific discovery environments: construction-stage pilots

The `sle episode` command runs stateful, budgeted scientific experiments and
freezes a claim before releasing fresh confirmation observations. The two
initial environments are candidates, outside the admitted legacy task registry:

- `CausalDiscovery/SurvivorshipAuditDesign`: population effects under direct
  treatment-dependent selection, stratification and paid random follow-up.
- `SystemsBiology/EnzymeMechanismDiscovery`: compositional dynamical mechanisms,
  costly measurements and perturbations, then fresh trajectory confirmation.
  **Protocol-only**: fixed experimental designs still recovered all mechanisms
  and passed all confirmations across the 60/80/104-unit budget study. It is not
  a sufficiently difficult replacement for the retired enzyme task.

They demonstrate executable contracts and verifiable evidence. They are **not
frontier-qualified tasks**. A competent reference can solve them; repeated
model calibration and independent scientific review are still required.
Six saturated or shortcut-compromised legacy tasks are held by the separate
[eligibility policy](discovery_eligibility.md).

## Run without a model

```sh
python -m sle episode --list
python -m sle episode --task SurvivorshipAuditDesign --baseline reference \
  --output-dir /var/tmp/sle-survivorship-reference
python -m sle episode --task EnzymeMechanismDiscovery --baseline fixed \
  --output-dir /var/tmp/sle-enzyme-fixed
```

Each output directory must be new, owner-only and outside every Git checkout.
Use `/private/tmp/...` on macOS. Full reports contain private world seeds,
outcomes and observations. Console output is a status/resource summary.

An operator-reviewed baseline uses only the public problem and experimental
callback, but executes inside the operator process; this mode is for construction
diagnostics. Candidate programs always use the Linux sandbox:

```sh
python -m sle episode --task SurvivorshipAuditDesign --program candidate.py \
  --seed 8173 --max-steps 64 --wall-seconds 300 \
  --output-dir /var/tmp/sle-program-example
```

The self-contained program defines `solve(problem, experiment)`, where
`experiment(tool_name, arguments)` returns the tool observation. The runner
commits its returned claim. Oracle files and private seeds never enter its
workspace. NumPy/SciPy availability follows the existing CandidateProxy runtime.

## Run a model with experiment feedback

```sh
python -m sle episode --task EnzymeMechanismDiscovery \
  --llm-config /private/config/model.yaml --analysis sandbox \
  --seed 9281 --max-steps 32 --wall-seconds 600 \
  --output-dir /var/tmp/sle-interactive-example
```

This uses the existing SLE model configuration and transport. Credentials stay
in the operator configuration, outside source and agent observations. Each model
response must be one JSON action:

```json
{"action":"experiment","tool":"public tool name","arguments":{}}
```

```json
{"action":"analyze","code":"result = 1 + 1"}
```

```json
{"action":"commit","claim":{"task-specific":"public claim schema"}}
```

The initial problem gives exact tool parameters, costs and claim schemas.
`analyze` runs in a persistent, single-process CandidateProxy sandbox. It can
read the JSON variables `problem`, `history`, and the explicitly allowlisted
`public_files`. For the enzyme pilot, `public_files['model.py']` supplies the
public numerical model; the agent may execute it inside its sandbox. Assign a
JSON-serializable value to `result`; captured output is bounded. Python never
executes in the trusted environment process. Linux/bubblewrap is required and
failure does not fall back to host execution. `--analysis none` explicitly
selects an experiment-only model condition.

The program and interactive-model modes share a scientific environment but are
different solver conditions. Record and compare them separately. Model steps,
experimental cost units, analysis calls and elapsed time are separate resources.
Malformed actions consume a step. Overspending does not run an experiment.
Claims committed after the agent deadline cannot be scored. Confirmation is an
operator-reserved phase after commitment, outside the exploration budget.
The standalone POSIX CLI enforces a total deadline around model transport,
including retries and streaming. Embedded interactive calls must run on the
main thread with no existing interval alarm; unsupported contexts fail closed.

## Evidence and verification

The trusted session records action/observation pairs, actual experimental charges,
the frozen claim hash, fresh confirmation, and private evaluator output. The
agent receives confirmation measurements but no oracle metrics. No experiments
or revised claims are accepted after commitment.

`episode.json` binds task source hashes, runtime source and installed package
versions, private world seed, solver mode and model condition, plus an ordered
hash chain. `validate_episode_report` checks structural consistency and resource
accounting. Hashes are content bindings, not signatures or proof of trusted
origin; they also do not prove that a scientific interpretation is valid.

Keep separate statuses for completed evaluation, incomplete delivery, invalid
candidate, model transport error, infrastructure error, exhausted budgets and
incomplete evidence. Only completed evaluations carry scientific metrics.
Each adapter defines mechanism, prediction, false-claim, refusal and coverage
metrics with their denominators. No cross-task scalar average is introduced.
For tasks with no intrinsically unidentifiable worlds, calibrated refusal is
unmeasured with a zero denominator, rather than automatically perfect.

## Adoption and release gates

The architecture adopts immutable source/runtime identity and numerical scientific
checks from [ScienceIDE](https://arxiv.org/html/2609.19134v1), active perturbation
and structural versus predictive evaluation from
[SciGym](https://arxiv.org/html/2507.02083v1), and separate process/outcome evidence
from [TRACES](https://www.apodex.com/blog/apodex-discovery). This is independently
implemented SLE code; it does not bundle ScienceIDE's unreleased task bank or
claim a Harbor/container integration that has not been implemented.

For each successor task, require: a public complete contract; independent oracle
checks; truthful construction provenance; a matched-budget shortcut panel;
fresh private worlds and confirmation; repeated model draws with named budgets;
and independent scientific review. The old saturated task remains held until
its successor passes these gates. Adding noise, renormalizing a full score, or
renaming a task cannot qualify it.

The next environment backend can support scientific repositories and compiled
simulators through a separate container adapter. That backend must pass correct
witness, nop, bad-artifact, timeout and verifier-failure anchors before collecting
model numbers. The current release implements the interactive experiment backend
and the existing secure Python analysis backend, with CPU-only scientific pilots.
