"""Weak valid baseline: schedule the jobs in the order they were given.

The as-given order ignores the processing times entirely, which is exactly the
factory-default dispatch the makespan normalization starts from.
"""

from __future__ import annotations


def schedule_flow_shop(problem):
    return list(range(problem["jobs"]))
