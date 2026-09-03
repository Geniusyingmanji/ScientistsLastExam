"""Tell a test that needs the candidate sandbox from one that can run anywhere.

The trusted evaluation path runs candidates under Bubblewrap and serialises cohort cells with
`flock`. Neither exists on macOS, so on a developer laptop every test that reaches them fails,
and a suite with 84 environmental failures hides a real regression in the noise. That is what
happened on the first review of #2-#4: five genuine `run_cohort` failures and one wrong anchor
had to be dug out from under a wall of `secure evaluation requires bubblewrap (bwrap)`.

The security suite's own note still stands: a skipped security suite looks like a passing one.
So this is deliberately narrow. It skips only when the *platform cannot have* the tool - Linux
without `bwrap` still fails loudly, because that is a misconfigured benchmark host, not a laptop -
and CI runs the whole suite on Linux with both tools installed, which is where the guarantee lives.
"""
from __future__ import annotations

import platform
import shutil
import unittest

SANDBOX_TOOLS = ("bwrap", "flock")


def missing_sandbox_tools(*tools: str) -> tuple[str, ...]:
    wanted = tools or SANDBOX_TOOLS
    return tuple(tool for tool in wanted if shutil.which(tool) is None)


def platform_can_have_sandbox() -> bool:
    """Bubblewrap is Linux-only; util-linux `flock` ships with every Linux distribution."""
    return platform.system() == "Linux"


def skip_unless_sandbox(*tools: str):
    """Skip on platforms that cannot provide the tools; fail normally on Linux without them.

    Usable on a test method or a whole TestCase. The reason names the missing tools so the skip
    count in a local run says what was not exercised, rather than looking like coverage.
    """
    missing = missing_sandbox_tools(*tools)
    if missing and not platform_can_have_sandbox():
        return unittest.skip(
            "requires %s, which %s cannot provide; run this on Linux (CI does)"
            % (", ".join(missing), platform.system()))
    return lambda obj: obj
