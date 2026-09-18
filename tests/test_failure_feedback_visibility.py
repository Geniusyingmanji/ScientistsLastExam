"""What a searcher learns from a rejected candidate, and what it must never learn.

A candidate that sees only "evaluation rejected" cannot tell a typo'd submission key from bad
science: it cannot fix the key, or stop retrying an identity whose budget it already spent.
The repo measured that hiding the evaluator's *input* contract correlates -0.675 with the share
of proposals that are not even valid, and that documenting keys moved one task from 0% to 77%
valid. The same asymmetry applies to the *failure* reason, so the class of failure is public.

The security property is unchanged and these tests pin it: the channel carries which contract
boundary failed - a name - and never a world index, split, hidden category, truth, reference
value or candidate-authored text. Text whose shape cannot be vouched for still collapses to the
generic sentence, and the full reason stays in the trusted diagnostics either way.
"""
from __future__ import annotations

import json

import pytest

from sle.metric_visibility import (
    CANDIDATE_FAILURE_CLASSES, CANDIDATE_FAILURES, MAX_PUBLIC_FAILURE_LABEL,
    public_error_message, search_visible_metrics,
)


def _rejected(**fields):
    metrics = {"combined_score": -1e18, "valid": 0.0}
    metrics.update(fields)
    return metrics


# --------------------------------------------------------------------------------------
# Every harness failure kind maps to exactly one class, and the classes are distinguishable.
# --------------------------------------------------------------------------------------

def test_every_classified_kind_declares_exactly_one_class():
    assert set(CANDIDATE_FAILURE_CLASSES) == set(CANDIDATE_FAILURES)


def test_distinct_failure_kinds_produce_distinct_messages():
    messages = {kind: public_error_message(_rejected(candidate_failure_kind=kind))
                for kind in CANDIDATE_FAILURES}
    assert len(set(messages.values())) == len(CANDIDATE_FAILURES), messages


def test_failure_classes_separate_budget_from_runtime_from_schema():
    """The three corrections a candidate makes are different, so the classes must differ."""
    def message(kind):
        return public_error_message(_rejected(candidate_failure_kind=kind))

    assert "(budget)" in message("callback_budget_exhausted")
    assert "(runtime)" in message("candidate_runtime_error")
    assert "(schema)" in message("candidate_callback_schema_error")
    assert "(timeout)" in message("candidate_timeout")
    assert "(environment)" in message("blocked_or_missing_import")
    assert "(protocol)" in message("candidate_worker_exit")
    assert message("callback_budget_exhausted") != message("candidate_runtime_error")
    assert message("candidate_runtime_error") != message("candidate_callback_schema_error")


def test_identical_failure_yields_identical_string():
    """The metrics channel stays deterministic: same input, same output, no ordering effects."""
    metrics = _rejected(
        candidate_failure_kind="candidate_callback_schema_error",
        error_message="candidate invalid: candidate_callback_schema_error",
    )
    assert len({public_error_message(metrics) for _ in range(50)}) == 1


# --------------------------------------------------------------------------------------
# Task-declared labels. Ten evaluators publish these; nine were being discarded.
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("label", [
    "invalid_return_artifact",
    "invalid_experiment_request",
    "invalid_submission",
    "candidate_runtime_or_callback_processing_error",
    "candidate_execution_failure",
    "trusted_scoring_failure",
    "invalid_sequence",
    "trusted_evaluator_internal_error",
])
def test_task_declared_failure_label_is_forwarded(label):
    """The exact vocabulary the repo's oracles already write into `error_message`."""
    message = public_error_message(_rejected(error_message="candidate invalid: " + label))
    assert message == "candidate invalid: " + label


def test_task_declared_labels_remain_distinguishable_and_ordered_independently():
    first = public_error_message(_rejected(
        error_message="candidate invalid: invalid_submission, candidate_execution_failure"))
    second = public_error_message(_rejected(
        error_message="candidate invalid: candidate_execution_failure, invalid_submission"))
    assert first == second
    assert "invalid_submission" in first and "candidate_execution_failure" in first


def test_repeated_task_labels_are_deduplicated():
    message = public_error_message(_rejected(
        error_message="candidate invalid: invalid_submission, invalid_submission"))
    assert message == "candidate invalid: invalid_submission"


# --------------------------------------------------------------------------------------
# The redaction intent is preserved: no oracle internals, no held-out worlds, no answer.
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("smuggled, forbidden", [
    # a world identity, split and truth value
    ("candidate invalid: heldout world 3 truth=morse", "world"),
    ("candidate invalid: world_index 3 split heldout", "heldout"),
    # a candidate-controlled exception message carrying an observed value
    ("candidate invalid: RuntimeError: observed energy -4.113 eV", "4.113"),
    # candidate text in the label position
    ("candidate invalid: candidate failed after reading reference_value=0.87", "0.87"),
    # labels are names, not sentences or paths
    ("candidate invalid: /home/user/task/verification/evaluator.py", "evaluator.py"),
    ("candidate invalid: " + "x" * (MAX_PUBLIC_FAILURE_LABEL + 1), "x" * 49),
])
def test_oracle_internal_and_candidate_text_is_never_forwarded(smuggled, forbidden):
    message = public_error_message(_rejected(error_message=smuggled))
    assert message == "evaluation rejected; details retained in trusted diagnostics"
    assert forbidden not in message


def test_a_valid_label_does_not_carry_a_smuggled_tail():
    """An unreviewed label makes the entire message private."""
    message = public_error_message(_rejected(
        error_message="candidate invalid: invalid_submission, see world 3"))
    assert message == "evaluation rejected; details retained in trusted diagnostics"
    assert "world" not in message


def test_unclassified_oracle_text_still_collapses_to_generic_sentence():
    """Oracle exception text that is not a classified failure does not become feedback."""
    for text in (
        "at least one query is required",
        "submission must contain exactly the documented fields",
        "the reference agent scored 0.5 on world 4",
    ):
        assert public_error_message(_rejected(error_message=text)) == (
            "evaluation rejected; details retained in trusted diagnostics")


def test_search_visible_metrics_keeps_the_class_and_drops_everything_else():
    metrics = _rejected(
        candidate_failure_kind="callback_budget_exhausted",
        error_message="candidate invalid: callback_budget_exhausted",
        per_world=[{"failure_kind": "invalid_submission", "world_index": 3}],
        heldout_truth="morse",
    )
    visible = search_visible_metrics(metrics)
    assert visible["error_message"] == (
        "candidate invalid: callback_budget_exhausted (budget)")
    rendered = json.dumps(visible, sort_keys=True)
    assert "heldout_truth" not in rendered and "morse" not in rendered
    assert "per_world" not in rendered and "world_index" not in rendered


def test_the_public_message_is_bounded_and_never_echoes_a_candidate():
    """Whatever arrives, the outward channel is short, finite and candidate-independent."""
    long_text = "candidate invalid: " + "reason " * 500
    message = public_error_message(_rejected(error_message=long_text))
    assert len(message) <= len("candidate invalid: ") + MAX_PUBLIC_FAILURE_LABEL
    assert message == "evaluation rejected; details retained in trusted diagnostics"
