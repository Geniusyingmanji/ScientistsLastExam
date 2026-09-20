"""Prepare blank, detached scientific-review forms from recorded evidence.

This is an operator-side index, not a judge or candidate-code runner. It checks
the existing report format and refers to original bytes without copying private
observations or assigning scientific ratings. Hashes do not authenticate sources.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .discovery_review import SEMANTIC_REVIEW_AXES
from .scientific_episode import digest, prepare_output, validate_episode_report


STAGES = (
    ("question", "问题", ("scientific_question",)),
    ("competing_hypotheses", "竞争假设", ("hypothesis_operationalization", "competing_explanations")),
    ("experiment_or_derivation", "实验或推导", ("experimental_rationale", "uncertainty_and_selection")),
    ("evidence", "证据", ("hypothesis_operationalization", "reproducibility", "uncertainty_and_selection")),
    ("testing_and_revision", "检验（必要时修订）", ("inference_warrant", "competing_explanations")),
    ("scoped_conclusion", "有适用范围的结论", ("inference_warrant", "novelty_and_scope")),
)
MAX_REPORT_FILE_BYTES = 128 * 1024 * 1024


def _blank_judgment():
    return {"status": "unassessed", "evidence_references": [],
            "counterevidence_references": [], "missing_evidence": [],
            "rationale": None, "scope_and_limitations": []}


def build_review_packet(report, *, source_file_sha256=None):
    binding = report.get("binding") if isinstance(report, dict) else None
    if not isinstance(binding, dict) or binding.get("evaluation_mode") != "evidence_only":
        raise ValueError("review packets require a ground-truth-free evidence episode")
    validation = validate_episode_report(report)
    if source_file_sha256 is not None and (
        not isinstance(source_file_sha256, str) or len(source_file_sha256) != 64
        or any(char not in "0123456789abcdef" for char in source_file_sha256)
    ):
        raise ValueError("invalid source file SHA-256")
    references = {key: [] for key, _label, _axes in STAGES}
    analysis_pending = False
    for event in report["events"]:
        kind, payload = event["kind"], event["payload"]
        targets = []
        if kind == "start":
            targets = ["question"]
        elif kind in {"discovery_hypothesis", "discovery_revision"}:
            targets = ["competing_hypotheses"]
            if kind == "discovery_revision":
                targets.append("testing_and_revision")
        elif kind == "discovery_test":
            targets = ["experiment_or_derivation", "testing_and_revision"]
        elif kind == "native_observation":
            targets = ["evidence"]
        elif kind == "analysis_started":
            targets = ["experiment_or_derivation"]
        elif kind in {"commit", "test_plan_committed"}:
            targets = ["testing_and_revision"]
            if report["schema_version"] == 1:
                targets.append("scoped_conclusion")
        elif kind in {"confirmation", "sealed_results"}:
            targets = ["testing_and_revision", "evidence"]
        elif kind == "interpretation_submitted":
            targets = ["testing_and_revision", "scoped_conclusion"]
        elif kind == "action":
            action = payload.get("action") if isinstance(payload, dict) else None
            analysis_pending = action == "analyze"
            if action in {"analyze", "experiment"}:
                targets = ["experiment_or_derivation"]
        elif kind == "observation" and analysis_pending:
            # Include unsuccessful analysis receipts too. Their existence is
            # not a successful execution, a replay or a native measurement.
            targets = ["experiment_or_derivation", "evidence"]
            analysis_pending = False
        for target in targets:
            references[target].append({"report_pointer": "/events/%d" % event["seq"],
                                       "event_kind": kind, "event_sha256": event["sha256"]})
    posttest = report["schema_version"] == 2
    interpretation_recorded = any(event["kind"] == "interpretation_submitted" for event in report["events"])
    packet = {
        "schema_version": 1, "kind": "discovery_scientific_review_template",
        "status": "unassessed", "ground_truth_used": False, "judge_model_used": False,
        "scientific_score": None,
        "source": {"report_sha256": report["sha256"], "file_sha256": source_file_sha256,
                   "episode_schema_version": report["schema_version"],
                   "task_id": report["binding"]["task_id"], "episode_status": report["status"],
                   "recording_complete": report["recording_complete"]},
        "process_check": {"validation_result": validation,
                          "scope": "existing report structural replay only; no candidate code execution",
                          "source_authenticity": "unassessed", "scientific_validity": "not_assessed"},
        "reviewer": {"identity": None, "review_type": None, "reviewed_at": None,
                     "domain_expertise": None, "model_id_if_agent": None, "provider_if_agent": None,
                     "implementation_involvement": None, "data_preparation_involvement": None,
                     "prior_exposure_to_results": None, "independence_declaration": None},
        "stages": [{"stage": key, "label": label, "semantic_axes": list(axes),
                    "record_availability": "recorded" if references[key] else "not_recorded",
                    "available_record_references": references[key], "judgment": _blank_judgment()}
                   for key, label, axes in STAGES],
        "semantic_axes": [{"axis": axis, "question": descriptor,
                           "required_evidence_types": list(required), "judgment": _blank_judgment()}
                          for axis, descriptor, required in SEMANTIC_REVIEW_AXES],
        "posttest_interpretation": {
            "record_availability": ("not_available_in_protocol" if not posttest else
                                    "recorded" if interpretation_recorded else "not_recorded"),
            "absence_is_scientific_failure": False,
            "conclusion_timing": "posttest" if posttest else "pretest",
        },
        "additional_review": {"claim_types": [], "novelty_scope": None,
                              "external_evidence": [], "unresolved_disagreements": [],
                              "materials_examined": [], "materials_unavailable": [],
                              "execution_scope": None},
        "limitations": [
            "Record availability is an index, not evidence-use quality or a scientific rating.",
            "A hash binds content; provenance, sampling independence and authenticity need separate review.",
            "An analysis receipt is not independent reproduction; code and tools are never run here.",
            "Legacy v1 has no posttest candidate interpretation; do not assign failure for that absent opportunity.",
            "Scientific judgments remain blank, including null findings and incomplete episodes.",
            "This private operator form does not modify or rescore the original report.",
        ],
    }
    # Hash only the generated blank form. A filled review is a new artifact and
    # must not keep this digest while implying it still matches the template.
    packet["sha256"] = digest(packet)
    return packet


def prepare_review_packet(episode_path, output_dir):
    source = Path(episode_path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_REPORT_FILE_BYTES:
        raise ValueError("episode must be a bounded regular report file")
    raw = source.read_bytes()
    if len(raw) > MAX_REPORT_FILE_BYTES:
        raise ValueError("episode report too large")

    def reject_constant(_value):
        raise ValueError("report contains a nonfinite constant")

    report = json.loads(raw, parse_constant=reject_constant)
    packet = build_review_packet(report, source_file_sha256=hashlib.sha256(raw).hexdigest())
    directory = prepare_output(output_dir)
    output = directory / "review-template.json"
    rendered = (json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    # Exclusive creation also refuses a pre-existing symlink or previous review.
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(rendered)
    return output
