"""The accounting every discovery evaluator owes, and the arithmetic it shares.

CONTRIBUTING.md requires a discovery task to publish three axes **separately, never
averaged** - mechanism recovery, false-discovery rate, calibrated refusal - plus a
column for whether the candidate tried to discover at all, and to publish the
denominator beside every rate. Measured across the 46 discovery tasks in this tree with
``scripts/discovery_axis_contract.py``, that requirement is prose only:

  * 5 of 46 publish no attempted-discovery or coverage column, so "every proposal refused
    every world" and "the science was too hard" render identically.
  * 44 of 46 publish at least one rate with no count at its own prefix, so
    ``correct_refusal_rate`` = 1.0 is one world out of one or thirty out of thirty and the
    axis has no known resolution.
  * 7 evaluators publish a ``mechanism_score`` bound to the *raw* mechanism while
    ``combined_score`` correctly uses the normalized one, so a blanket abstainer reports
    its free credit on an axis it earned nothing on. The headline score is right; only the
    reported axis is wrong.
  * 25 evaluators hand-copy the same abstention normalization, and none import anything
    from ``sle`` - so the formula can drift in 25 places at once.

This module is additive: it changes no existing verdict and no evaluator adopts it yet.
It exists so the contract is satisfiable by construction (``DiscoveryAxes`` cannot be
built without all four fields) and so the arrival gate has one definition to check
against instead of four diverging alias lists.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# The four things a discovery report must carry. Three axes plus the column that
# separates "refused everything" from "found nothing"; see the module docstring.
MECHANISM = "mechanism"
FALSE_DISCOVERY = "false_discovery"
REFUSAL = "refusal"
ATTEMPTED = "attempted"
AXES = (MECHANISM, FALSE_DISCOVERY, REFUSAL, ATTEMPTED)

# Canonical published key stems, unprefixed. Evaluators that report a development and a
# heldout split prefix each with the split name, which is the tree's dominant convention.
# The stem is deliberately not the axis name: ``mechanism`` publishes ``mechanism_score``
# - a mechanism *rate* named "score" would collide with the per-world score of the same
# name - and ``refusal`` publishes ``correct_refusal_*`` because a refusal rate that
# counts indiscriminate abstention is not the axis CONTRIBUTING.md asks for.
RATE_KEYS = {
    MECHANISM: "mechanism_score",
    FALSE_DISCOVERY: "false_discovery_rate",
    REFUSAL: "correct_refusal_rate",
    ATTEMPTED: "attempted_discovery",
}
COUNT_KEYS = {axis: stem.replace("_score", "").replace("_rate", "") + "_count"
              for axis, stem in RATE_KEYS.items()}
DENOMINATOR_KEYS = {axis: stem.replace("_score", "").replace("_rate", "") + "_denominator"
                    for axis, stem in RATE_KEYS.items()}
# The baseline the normalization subtracts, and the two mechanism numbers it sits between.
ALWAYS_ABSTAIN_KEY = "always_abstain"
RAW_MECHANISM_KEY = "raw_mechanism"
NORMALIZED_MECHANISM_KEY = "normalized_mechanism"
MECHANISM_QUALITY_KEY = "mechanism_quality_sum"

# Degenerate outcomes of :func:`normalize_mechanism`. Neither is an error: a real task
# can include a split with no worlds, or with no world a mechanism could be recovered on.
NORMALIZED = "normalized"
NO_RECORDS = "no_records"
NO_SUPPORTED_WORLDS = "no_supported_worlds"

# Mechanism-rate aliases an evaluator may already publish instead of ``mechanism_score``.
# Shared with ``scripts.check_task_contribution`` so the gate and this module cannot drift
# into disagreeing about which key is the mechanism axis.
MECHANISM_ALIASES = (
    "heldout_mechanism_score", "mechanism_score", "development_mechanism_score",
    "development_body_support_f1", "heldout_supported_correct_model_rate",
    "development_supported_correct_model_rate", "heldout_hypothesis_score",
    "development_hypothesis_score",
)


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("%s must be a finite number" % name)
    return float(value)


def always_abstain(unsupported_count, record_count) -> float:
    """The raw mechanism a candidate that declines every world earns, exactly.

    The support of a correct refusal is the unsupported worlds, so abstaining everywhere
    is right on all of them and wrong on all the rest. ``unsupported_count`` is that
    count - the worlds where declining *is* the correct answer - and it is the same
    denominator whose rate is published as ``correct_refusal_rate``.
    """
    unsupported = _finite(unsupported_count, "unsupported_count")
    total = _finite(record_count, "record_count")
    if unsupported < 0 or total < 0 or unsupported > total:
        raise ValueError("unsupported_count must be in [0, record_count]")
    if total == 0:
        return 0.0
    return unsupported / total


@dataclass(frozen=True)
class NormalizedMechanism:
    """A mechanism rate that has had the free credit for abstaining removed.

    ``value`` is always finite, because a score has to be: the two degenerate cases
    publish the conservative zero and name themselves in ``status`` rather than raising
    or inventing a number. A reader that wants to know whether the axis was measurable
    reads ``status``; a reader comparing tasks reads ``value``.
    """

    value: float
    status: str
    raw: float
    baseline: float

    @property
    def measurable(self) -> bool:
        return self.status == NORMALIZED


def normalize_mechanism(raw_mechanism, unsupported_count, record_count) -> NormalizedMechanism:
    """``(raw - always_abstain) / (1 - always_abstain)``, as CONTRIBUTING.md specifies.

    Blanket abstention lands on exactly zero: its raw mechanism *is* ``always_abstain``.
    Clipped to [0, 1] because a candidate can score below the abstention baseline and a
    negative recovery rate is not a thing a report can act on.

    Two degenerate inputs have no defined value and are named instead of guessed:

    ``no_records``
        An empty split. There is no rate at all; ``0/0``.
    ``no_supported_worlds``
        Every world is one a correct candidate must refuse. The baseline is 1.0, so the
        denominator is zero and *every* candidate that abstains everywhere is perfect.
        The mechanism axis carries no information here, and reporting 1.0 would read as
        "recovered the mechanism" when nothing was recovered.
    """
    raw = _finite(raw_mechanism, "raw_mechanism")
    baseline = always_abstain(unsupported_count, record_count)
    if _finite(record_count, "record_count") == 0:
        return NormalizedMechanism(0.0, NO_RECORDS, raw, 0.0)
    if baseline >= 1.0:
        return NormalizedMechanism(0.0, NO_SUPPORTED_WORLDS, raw, 1.0)
    normalized = (raw - baseline) / (1.0 - baseline)
    return NormalizedMechanism(min(1.0, max(0.0, normalized)), NORMALIZED, raw, baseline)


@dataclass(frozen=True)
class Rate:
    """A rate that cannot exist without the count it is a rate of.

    There is no constructor that takes only a value. ``correct_refusal_rate = 1.0`` is
    one world out of one or thirty out of thirty, and the difference is the whole
    resolution of the axis: a three-world refusal denominator lets a candidate that
    guesses hit a perfect axis once in twenty-seven tries. The tree's existing evaluators
    already avoid the division by zero with ``max(1, n)``; that is why the count is
    published beside the rate and why ``value`` is None, not zero, when there is nothing
    to be a rate of.

    ``numerator`` is the count of the thing and ``denominator`` the count of the
    population it was found in. For a *mean* axis such as mechanism the numerator is the
    sum of per-world quality rather than a count; ``DiscoveryAxes.as_metrics`` documents
    how the published count is chosen there.
    """

    numerator: float
    denominator: float

    def __post_init__(self):
        _finite(self.numerator, "numerator")
        _finite(self.denominator, "denominator")
        if self.numerator < 0 or self.denominator < 0:
            raise ValueError("a rate's numerator and denominator must be non-negative")
        if self.numerator > self.denominator:
            raise ValueError("a rate's numerator cannot exceed its denominator")

    @property
    def value(self) -> float | None:
        """The rate, or None when the denominator is zero and it is undefined."""
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def readable(self) -> bool:
        return self.denominator > 0

    def as_metrics(self, axis: str, *, count: float | None = None,
                   prefix: str = "") -> dict[str, float]:
        """Publish the rate, its count and its denominator under one axis name.

        The rate falls back to ``0.0`` only so the metric payload stays finite; the
        published denominator of zero is what tells a reader the value is not a
        measurement. ``report_discovery_triple`` reads exactly that pair.
        """
        return {
            prefix + RATE_KEYS[axis]: self.value if self.value is not None else 0.0,
            prefix + COUNT_KEYS[axis]: self.numerator if count is None else count,
            prefix + DENOMINATOR_KEYS[axis]: self.denominator,
        }


@dataclass(frozen=True)
class DiscoveryAxes:
    """One split's four required fields, and the normalized mechanism derived from them.

    Frozen and fully required, so an evaluator cannot report the triple without the
    attempted column or a rate without its denominator: there is no partial
    construction and no default. Each rate is declared the way CONTRIBUTING.md's
    ``len(records)`` reads - the mechanism rate is the mean over *every* measured world,
    so its denominator is the record count and the refusal denominator is a subset of it.
    """

    mechanism: Rate
    false_discovery: Rate
    refusal: Rate
    attempted: Rate

    def __post_init__(self):
        for axis in AXES:
            if not isinstance(getattr(self, axis), Rate):
                raise TypeError("%s must be a Rate" % axis)

    @property
    def record_count(self) -> float:
        """The worlds measured: the mechanism mean's denominator."""
        return self.mechanism.denominator

    @property
    def unsupported_count(self) -> float:
        """The worlds a correct refusal lives in: the refusal rate's denominator."""
        return self.refusal.denominator

    @property
    def normalized_mechanism(self) -> NormalizedMechanism:
        raw = self.mechanism.value
        return normalize_mechanism(0.0 if raw is None else raw,
                                   self.unsupported_count, self.record_count)

    def as_metrics(self, prefix: str = "") -> dict[str, float]:
        """The complete published block: every rate with its denominator, both mechanisms.

        The mechanism axis is the one place a rate's ``_count`` is not its numerator.
        Its numerator is a sum of per-world recovery quality, which is not a count of
        anything; the number a reader means by "how many worlds" is the denominator, so
        both ``mechanism_count`` and ``mechanism_denominator`` carry it and the sum is
        published separately under ``mechanism_quality_sum``.
        """
        normalized = self.normalized_mechanism
        metrics = self.mechanism.as_metrics(MECHANISM, count=self.mechanism.denominator,
                                            prefix=prefix)
        for axis in (FALSE_DISCOVERY, REFUSAL, ATTEMPTED):
            metrics.update(getattr(self, axis).as_metrics(axis, prefix=prefix))
        metrics.update({
            prefix + MECHANISM_QUALITY_KEY: self.mechanism.numerator,
            prefix + RAW_MECHANISM_KEY: normalized.raw,
            prefix + ALWAYS_ABSTAIN_KEY: normalized.baseline,
            prefix + NORMALIZED_MECHANISM_KEY: normalized.value,
            # Republished under the rate key so a reader that takes `mechanism_score` at
            # face value gets the number the headline was computed from, not the raw one.
            # Publishing the raw value there is the defect in 7 evaluators this module
            # exists to stop: a blanket abstainer reported 0.29-0.40 on the axis while
            # `combined_score` correctly gave it zero.
            prefix + RATE_KEYS[MECHANISM]: normalized.value,
        })
        return metrics

    def problems(self) -> list[str]:
        """What a reviewer would still have to ask for. Empty means complete and readable."""
        troubles = []
        for axis in AXES:
            if not getattr(self, axis).readable:
                troubles.append("%s has no denominator" % axis)
        if not self.normalized_mechanism.measurable:
            troubles.append("mechanism is %s" % self.normalized_mechanism.status)
        if self.refusal.denominator > self.mechanism.denominator:
            troubles.append("refusal denominator exceeds the record count")
        return troubles
