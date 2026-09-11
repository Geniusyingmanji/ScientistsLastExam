# ParticlePhysics/DarkMatterRecoilAttribution: scope and overlap review

Compared with all 84 task names and catalog descriptions at origin/main
`b0855012ea48b8901cf46dd6ceea8fc7ffbb1812`. No exact equivalent was found.
A shared recoil-law and mass fit across nuclear targets differs from a resonance-window significance test or atmospheric absorption-species inference.

The external comparison covers the 47-task [Frontier-Eng Appendix A](https://arxiv.org/html/2604.12290v1#A1)
and the entire [pinned repository catalog](https://github.com/Einsia/Frontier-Engineering/blob/e3fa29c193356af2ce1ec8b3d23ab1a2e2410071/TASK_DETAILS.md).
Neither contains this question. The latter has 78 task rows / 84 expanded identifiers;
the historical CONTRIBUTING count of 95 cannot be reconciled with that revision.
These are catalog-level builder checks, not independent domain review or a proof of novelty.

This branch adds one task, its independent tests/audit script, registration and
source-bound evidence. It has no dependency on another new task package.
Reference/baseline repeats, ablations and the completed 233280-strategy four-way finite builder probe
are reproducible with `scripts/audit_dark_matter_recoil.py`. Numerical equations and parameter
recovery are checked separately from the reported discovery/refusal/coverage axes.

Status remains `candidate`. Independent model calibration, domain review and
server-held reissue are outstanding. Repository-visible instances can be memorized;
low-dimensional probes are not an exhaustive upper bound. The numerical model's
scientific assumptions and limits are documented in Task.md and known_best.md.

PR 72 review revision: paired log-mass strata and locally supported but jointly
inconsistent target spectra replace the clustered signal sample and narrow-peak
misspecification. Exact constant-mass bounds supplement the finite probe. The closest
structural neighbour, `Gravitation/PTAHellingsDowns`, shares paid mechanism decisions
and refusal; this task additionally estimates mass from nuclear-target energy spectra.
Historical 480-strategy evidence is retained as pre-revision evidence, not reused to
claim the revised task passed. See `references/known_best.md` in the task package.
