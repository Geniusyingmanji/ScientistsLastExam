"""Discovery contracts, separate from task certification and scalar scores.

Only the four inspected pilots have an assessed profile. Registry discovery tasks
without an adapter remain visible as not_assessed, never inferred from their kind.
Adapters live in Python so changes are bound by runtime_source_sha256.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import yaml


PILOTS = {
    "MolecularDynamics/ForceFieldCalibration": {
        "openness": "L2",
        "claim_types": ["mechanism", "parameter_estimate", "prediction"],
        "unknown": "Mie/Morse/library inadequacy, parameters and thermodynamic consequences",
        "given": "Two enumerated pair-potential families and a budgeted energy/force laboratory",
        "callbacks": {1: "query"},
        "result_axes": {
            "process": ["lineage_quality", "acquisition_quality", "hypothesis_quality",
                        "true_hypothesis_retention_rate", "premature_elimination"],
            "result": ["selection_quality", "parameter_quality", "interval_quality",
                       "prediction_quality", "robust_prediction_quality", "false_discovery",
                       "correct_refusal", "abstained"],
            "resources": ["query_calls", "query_budget_units"],
        },
        "verification": ["simulator_truth", "sealed_configurations"],
        "limitations": "Enumerated family discrimination in a reduced three-particle simulator; no external experiment.",
    },
    "CausalDiscovery/InterventionalSCM": {
        "openness": "L3",
        "claim_types": ["causal_structure", "parameter_estimate", "prediction"],
        "unknown": "Directed graph and structural coefficients of a linear acyclic SCM",
        "given": "Linear acyclic family, seven observed variables and intervention budget",
        "callbacks": {1: "observe", 2: "intervene"},
        "result_axes": {
            "process": [],
            "result": ["edge_f1", "coefficient_score", "mechanism_score",
                       "intervention_prediction_score", "abstained", "null_world"],
            "resources": ["experiment_calls", "experiment_budget_units"],
        },
        "verification": ["simulator_truth", "sealed_interventions"],
        "limitations": "Known linear acyclic simulator; per-world results are unsplit, not a heldout cohort.",
    },
    "DynamicalSystems/ActiveLawDiscovery": {
        "openness": "L3",
        "claim_types": ["law", "parameter_estimate", "prediction"],
        "unknown": "Sparse dynamical equations or inadequacy of the declared library",
        "given": "Public thirteen-term library, two states and bounded trajectory experiments",
        "callbacks": {2: "experiment"},
        "result_axes": {
            "process": [],
            "result": ["edge_f1", "coefficient_score", "mechanism_score",
                       "rollout_prediction_score", "false_discovery",
                       "correct_abstention", "abstained"],
            "resources": ["experiment_calls", "experiment_budget_units"],
        },
        "verification": ["simulator_truth", "sealed_rollouts", "optional_fresh_simulated_panel"],
        "limitations": "Composition within a public library; a fresh panel is simulation, not new physical law confirmation.",
    },
    "EvidenceSynthesis/ProspectiveMetaAnalysis": {
        "openness": "L2",
        "claim_types": ["evidence_synthesis", "parameter_estimate", "prediction"],
        "unknown": "Eligible independent evidence, linear effect model adequacy and benefit claim",
        "given": "Synthetic trial registry, publication lineage, linear effect family and candidate sites",
        "callbacks": {1: "confirm"},
        "result_axes": {
            "process": ["evidence_integrity_score", "design_information_score"],
            "result": ["preconfirmation_mechanism_score", "prediction_score",
                       "forecast_distribution_score", "postconfirmation_score",
                       "confirmation_point_score", "confirmation_interval_covered",
                       "false_discovery", "supported_claim", "correct_refusal"],
            "resources": ["confirmation_call_count"],
        },
        "verification": ["simulator_truth", "precommitted_fresh_simulated_study"],
        "limitations": "Synthetic registered studies; no clinical validation. Post-confirmation updates need new evidence for another confirmation.",
    },
}


# Source reviewed for these labels; a later task edit requires a new review.
REVIEWED_SOURCES = {'CausalDiscovery/InterventionalSCM': {'TASK_CARD.yaml': 'a5ce262040ef07c7800ba1bbed99b8ca876f966ee8ddf3a41e9effc22c105bb5',
                                       'Task.md': '8c56bd39d053fff97f8349fda405ea3f8d46df76ed1eb23f254e2a14dbdaff3e',
                                       'verification/evaluator.py': '8c89ddd03011c1b4870e8dd2118cca217ffd3b89de9e39281c3a7c9086767ec1'},
 'DynamicalSystems/ActiveLawDiscovery': {'TASK_CARD.yaml': '873fe2000dc9899c05e9748be4b0853721687bedc429a284daae2105fb5cba7f',
                                         'Task.md': 'd486dbb7d718da9515f8323a1ae563f7cdcdeee7b67eff8915f47703082e772b',
                                         'verification/evaluator.py': '6b9216d370f4cad53f9f1ace661ff18f756759cfcdcdfba80807d9f961885f39'},
 'EvidenceSynthesis/ProspectiveMetaAnalysis': {'TASK_CARD.yaml': '7201aef90248f972629f7b41f8a1a5e0f6343a2e24c80fefbc1d1c8b288dd8ff',
                                               'Task.md': '017ba1fe2e20b5ec996e0f30c1e074fafdd81de86c295ceac60bea1f58f554fe',
                                               'verification/evaluator.py': 'f96ea57a82b4e81e7d287a3801aa3680a6d577944b2bf9ed3ec9ce30332afe13'},
 'MolecularDynamics/ForceFieldCalibration': {'TASK_CARD.yaml': 'd51058ee1fa89fbd2df353a147d06c7789cc67e63d4d40af406a8eb491134e48',
                                             'Task.md': '6444878ec19203ac056aff223b76f98b0c3913a5b90082b8e00a24a20e68ce4a',
                                             'verification/evaluator.py': 'bc7e5ba7a2d3f9dcd1a1f3fafb6cbfdf5ef2d515f9619128ae144fe6b3e16559'}}

def profile_for(spec):
    """Return declarations and the explicit extent of static inspection."""
    card_path = spec.task_dir / "TASK_CARD.yaml"
    card = yaml.safe_load(card_path.read_text()) if card_path.is_file() else {}
    pilot = PILOTS.get(spec.task_id)
    source_paths = [spec.task_dir / "Task.md", card_path,
                    spec.task_dir / "verification/evaluator.py"]
    source_hashes = {str(p.relative_to(spec.task_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in source_paths if p.is_file()}
    assessment = "not_assessed"
    if pilot:
        assessment = "source_inspected" if source_hashes == REVIEWED_SOURCES[spec.task_id] else "source_changed"
    inspected = pilot if assessment == "source_inspected" else None
    return {
        "schema_version": 1,
        "task_id": spec.task_id,
        "discipline": spec.discipline,
        "assessment_status": assessment,
        "scientific_question": (card or {}).get("scientific_question"),
        "artifact": (card or {}).get("artifact"),
        "openness": inspected["openness"] if inspected else None,
        "claim_types": list(inspected["claim_types"]) if inspected else [],
        "given": inspected["given"] if inspected else None,
        "unknown": inspected["unknown"] if inspected else None,
        "verification": list(inspected["verification"]) if inspected else [],
        "world_type": "simulation" if inspected else "not_assessed",
        "novelty_scope": "benchmark_rediscovery" if inspected else "not_assessed",
        "field_novelty": "not_established",
        "independent_scientific_review": "pending",
        "process_recording": "trusted_callback_and_submission" if pilot else "not_instrumented",
        "limitations": inspected["limitations"] if inspected else "Requires claim and verifier review; labels are not inferred from task kind.",
        "source_sha256": source_hashes,
    }


def pilot_contract(task_id):
    return copy.deepcopy(PILOTS.get(task_id))
