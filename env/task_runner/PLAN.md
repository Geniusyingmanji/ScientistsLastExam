# Standard scientific task packages and unified execution

Approved scope: ecology and coupled oscillators first, following ALE's public
seed/private reference separation, fixed runtimes, independent evaluation and
clean submission replay. Existing cohorts, services and grades stay unchanged.

Four trust boundaries: (1) candidate workspace, (2) trusted live laboratory,
(3) untrusted prediction executor without network or answers, (4) trusted numeric
and semantic judge. Do not mount the repository, simulator or reference in the
candidate or prediction executor. Public and private artifacts are physically
separate; a directory convention alone is not isolation.

Package: public instruction/apparatus/delivery and manifest; instance parameters,
queries and judge material in private per-attempt operator storage. Freeze package,
source, image digests, resources and judge contract before new runs. Instances are
not new mechanism families merely because their seeds differ.

Lifecycle: prepare -> laboratory + external harness -> seal -> clean prediction
execution -> numeric evaluation -> independent layer judgment -> archive. Each
attempt uses a previously nonexistent directory. Failed attempts are retained.
Seal verifies actual model bytes against the laboratory submission. No automatic
repair of misplaced or missing deliverables. Optional model state must be declared.
Replay rebuilds predictions, not the exploration or original report.

Initial implementation: common CLI, two packages, isolated Docker prediction
backend with pinned image and no unsafe fallback. Harness integration is a backend
boundary: its workspace, public bridge and laboratory endpoint are supplied by
runner; no model credentials in package/output. Existing Linux execution remains
available for old cohorts. Docker/AKernel adapters must be admitted with real
permission and isolation probes before any new model cohort uses them.

Next acceptance: validate both packages and prepare/seal failure behavior locally;
run real container prediction with no reference visibility and writable output
only; integrate fixed harness runtime; run one new instance of each task. Separate
execution failure, deliverable failure, numeric performance and discovery scores.
AKernel and object storage are subsequent backends, not claimed implemented.
