#!/usr/bin/env python3
"""Resolve a recorded run directory against the repository reading it.

Evidence documents record `workdir` as an absolute path, because that is what the driver knew at
the time. It is the absolute path *on the machine that produced the run*, so every reader
elsewhere - a clone, a worktree, another checkout on the same host - fails a containment check
that was meant to stop a report reaching outside the repository, and reports the failure as
"workdir is outside repository". That reads like a security refusal; it is a portability defect.

The containment property is worth keeping, so this rebuilds the path from its `runs/` component
downwards against the repository actually being read. The result is under that repository by
construction, which is what the check wanted, and it no longer depends on where the run happened
to be produced.

A path with no `runs/` component is refused: it is not a run directory, and guessing what it might
be is how a containment check turns into a formality.
"""
from __future__ import annotations

import os
from pathlib import Path


def resolve_run_workdir(recorded: str, root: Path) -> Path:
    """The recorded run directory, relative to `root`.

    Raises ValueError when the recording names no run directory at all, which is the case the
    containment check exists for.
    """
    parts = Path(str(recorded)).parts
    if "runs" not in parts:
        raise ValueError(
            "recorded workdir names no runs/ directory, so it cannot be placed in this "
            "repository: %r" % (recorded,))
    index = len(parts) - 1 - parts[::-1].index("runs")
    # Normalised lexically rather than with `resolve()`. Resolving follows symlinks, and a `runs`
    # symlink pointing at the machine's real run tree - which is how a worktree borrows them -
    # then lands outside the repository and fails the containment check this exists to satisfy.
    # `normpath` still collapses `..`, so a recorded path cannot climb out.
    candidate = os.path.normpath(os.path.join(str(root), *parts[index:]))
    if os.path.commonpath([candidate, str(root)]) != os.path.normpath(str(root)):
        raise ValueError("recorded workdir escapes the repository: %r" % (recorded,))
    return Path(candidate)


def run_workdir_is_present(recorded: str, root: Path) -> bool:
    """Whether the run this evidence describes is on disk here.

    Run directories are not committed, so a reader that does not hold them is a reader missing
    data - not a reader looking at broken evidence. Callers use this to say which it is.
    """
    try:
        workdir = resolve_run_workdir(recorded, root)
    except ValueError:
        return False
    return (workdir / "trajectory.jsonl").is_file()
