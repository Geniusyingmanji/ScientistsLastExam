"""Public scientific task descriptions; no execution, scoring or hidden state.

These profiles specify evidence to seek within the existing experiment and
submission contracts. Their checklists require a separate scientific review;
this module never returns an automatic scientific-success verdict.
"""

from copy import deepcopy


TASK_PROFILE_CATALOG_VERSION = "scientific-task-profiles-0.1.3"
DEFAULT_TASK_PROFILE = "open_discovery"
TASK_PROFILE_NAMES = ("open_discovery", "mechanism_discrimination", "regime_transfer")
APPLICABLE_ENVIRONMENTS = (
    "microecology", "coupled_oscillators", "reaction_kinetics", "heat_transport",
    "gene_regulation", "ising_spin", "hysteresis_material", "microecology_causal",
    "orbital_dynamics", "pattern_formation",
)


_COMMON_PROMPT = (
    "Use only the public world description, legal experiments and observations you obtain. "
    "There is no prescribed mechanism or required positive discovery. Cite observation IDs "
    "and distinguish measured effects, fitted explanations and unresolved possibilities. "
    "A negative or inconclusive result is valid when supported by the evidence. "
    "Keep the existing submission format: predictor_code, claims and explanation. Put the "
    "task evidence and its limitations in explanation; use earlier research notes to record "
    "predictions before experiments when requested. Quantitative claims remain optional and "
    "follow the existing paired-contrast contract. Freeze a self-contained predictor before "
    "private evaluation. Task evidence is reviewed separately from prediction scores and "
    "numerical claim verification; neither automatically certifies a mechanism or discovery depth."
)


def _evidence(identifier, minimum_count, count_unit, description, sources,
              timing="by_final_submission"):
    return {"id": identifier, "required": True, "minimum_count": minimum_count,
            "count_unit": count_unit, "description": description,
            "sources": list(sources), "timing": timing,
            "assessment": "separate_scientific_evidence_review"}


def _profile(name, prompt, primary_measure, does_not_establish, requirements,
             positive_finding_requires, allowed_conclusions):
    return {
        "name": name, "version": name + "-0.1.0",
        "catalog_version": TASK_PROFILE_CATALOG_VERSION,
        "applicable_environments": list(APPLICABLE_ENVIRONMENTS),
        "public_prompt": prompt + "\n\n" + _COMMON_PROMPT,
        "scientific_scope": {
            "primary_measure": primary_measure,
            "unit_of_inference": "one fixed world instance within its public experimental domain",
            "does_not_establish": list(does_not_establish),
            "hidden_reference_required": False,
        },
        "evidence_requirements": requirements,
        "success_semantics": {
            "unreviewed_status": "requires_evidence_review",
            "process_complete_when": "A separate review finds every required evidence item traceable, scientifically adequate and temporally consistent with its stated requirement.",
            "positive_finding_requires": positive_finding_requires,
            "allowed_conclusions": list(allowed_conclusions),
            "inconclusive_policy": "An adequate inconclusive or falsifying investigation can complete the evidence checklist; it does not count as a positive mechanism or transfer finding.",
            "missing_evidence_status": "not_demonstrated",
            "prediction_score_effect": "none",
            "automatic_checklist_verdict": False,
            "automatic_depth_certification": False,
            "numerical_claim_verification_certifies_mechanism": False,
        },
        "submission_contract": {
            "fields": ["predictor_code", "claims", "explanation"],
            "additional_required_fields": [],
            "evidence_location": "explanation with observation IDs and references to earlier research notes or analysis records",
            "preresult_evidence_location": "research note accompanying or preceding the targeted experiment request, before its observation is returned",
            "quantitative_claims": "optional; existing paired-contrast format and verifier unchanged",
        },
    }


_PROFILES = {
    "open_discovery": _profile(
        "open_discovery",
        "Choose a scientific question about this world and investigate it. Seek a quantitative "
        "regularity, a useful model, a causal effect or a well-supported failure of a plausible "
        "idea. Choose experiments that can change your interpretation. Explain how observations "
        "support or limit your finding and which alternative explanation remains credible. "
        "You decide what is worth studying; no particular phenomenon must be found.",
        "Autonomous question selection and an evidence-supported, appropriately scoped scientific account.",
        ("unique recovery of the complete hidden mechanism", "a required positive discovery",
         "generalization beyond tested conditions", "real-world scientific validity"),
        [
            _evidence("research_question", 1, "question",
                      "State a self-selected question, measurable outcome and relevant experimental scope.",
                      ("research_notes", "explanation")),
            _evidence("traceable_observations", 1, "observed_experiment",
                      "Cite actual observation IDs and connect the measured responses to the question; describe at least one informative comparison or test of the interpretation.",
                      ("experiment_records", "analysis_records", "explanation")),
            _evidence("quantitative_account", 1, "quantitative_account",
                      "Give a quantitative relation, effect, predictive model or bounded negative result with its uncertainty and supporting observations.",
                      ("explanation", "analysis_records", "frozen_predictor")),
            _evidence("scope_and_alternative", 1, "scope_assessment",
                      "State what remains uncertain, one plausible alternative or confound, and which conclusions the present evidence does not support.",
                      ("explanation",)),
        ],
        "A scoped empirical finding survives an informative check and is supported by the cited measurements and uncertainty; a complete hidden mechanism is not required.",
        ("scoped_finding_supported", "proposed_idea_not_supported", "inconclusive"),
    ),
    "mechanism_discrimination": _profile(
        "mechanism_discrimination",
        "Compare at least two plausible, meaningfully different mechanisms that could account "
        "for the observations. Define their differing causal or dynamical assumptions. Choose "
        "a legal targeted experiment for which they predict observably different outcomes; "
        "record both predictions and the intended readout in a research note before obtaining "
        "that result. Run the experiment, compare each prediction with the measured result and "
        "revise the alternatives accordingly. Report whether the evidence favors an account, "
        "rejects both, or leaves them unresolved. Explain remaining observational equivalences "
        "and identifiability limits. Different parameter values alone are insufficient unless "
        "they encode a meaningful mechanistic distinction with different testable predictions.",
        "Construction of competing explanations and experimental discrimination with explicit identifiability limits.",
        ("uniqueness among all possible mechanisms", "the true implementation was recovered",
         "a favored explanation is established by prediction score alone", "forced selection of a winning mechanism"),
        [
            _evidence("competing_mechanisms", 2, "plausible_mechanism",
                      "Describe at least two substantive causal or dynamical accounts, their assumptions, and why each is initially compatible with the public description and available observations.",
                      ("research_notes", "explanation"), "before_discriminating_result"),
            _evidence("discriminating_prediction", 1, "prespecified_comparison",
                      "Specify a legal targeted experiment, the readout and a distinct quantitative prediction or directional/time-pattern prediction under each account; state why the expected separation is observable given noise and uncertainty.",
                      ("research_notes", "analysis_records"), "before_discriminating_result"),
            _evidence("targeted_observation", 1, "observed_discriminating_experiment",
                      "Run the specified test and cite its observation ID; include an observed reference condition when the proposed discriminator is a contrast that requires one.",
                      ("experiment_records", "explanation")),
            _evidence("comparison_and_revision", 1, "mechanism_comparison",
                      "Compare the same observed readout with both prior predictions and their uncertainty; explain support, falsification or unresolved overlap without silently replacing an unsuccessful prior prediction.",
                      ("research_notes", "analysis_records", "explanation")),
            _evidence("identifiability_limits", 1, "identifiability_assessment",
                      "Identify remaining observationally equivalent accounts or unresolved parameters within the tested domain, and name a next discriminating test or explain why the legal interface cannot resolve them.",
                      ("explanation",)),
        ],
        "An observed, prespecified discriminator meaningfully separates the stated alternatives after accounting for uncertainty. Preference is limited to those alternatives and the tested domain.",
        ("stated_alternatives_discriminated", "all_stated_alternatives_rejected", "alternatives_unresolved"),
    ),
    "regime_transfer": _profile(
        "regime_transfer",
        "Seek a quantitative law or model that predicts a change of experimental regime. "
        "Define a source regime and a different legal target regime using initial conditions "
        "where available, control settings, forcing schedules, boundary conditions or other "
        "public controls. Fit or formulate the relation from source observations. Before "
        "measuring the chosen target, record the fixed relation, source evidence IDs, target "
        "specification, predicted readouts and uncertainty. Obtain target observations and "
        "evaluate that recorded prediction before any refitting. Explain which quantities or "
        "parameters remain invariant, what changes with the regime and where transfer fails. "
        "Independent fits to each regime do not by themselves show transfer. This target is "
        "an experiment you choose during exploration, not a private evaluation panel.",
        "Prospective transfer of an evidence-derived quantitative relation across explicit experimental regimes.",
        ("universal laws outside the public domain", "independent target fits demonstrate transfer",
         "prediction transfer uniquely identifies a mechanism", "success on every unseen control regime"),
        [
            _evidence("source_and_target_regimes", 2, "explicit_regime",
                      "Define source and target by concrete legal conditions or control ranges and explain the scientific change being tested. Do not invent an initial-state control when the environment exposes only equilibrium preparations.",
                      ("research_notes", "explanation"), "before_transfer_result"),
            _evidence("shared_relation", 1, "shared_quantitative_relation",
                      "State a quantitative law or model, variables and units where applicable, fitted source evidence and assumptions about invariant parameters versus controlled changes.",
                      ("research_notes", "analysis_records", "explanation"), "before_transfer_result"),
            _evidence("prospective_target_prediction", 1, "recorded_target_prediction",
                      "Before the selected target result is observed, record the target spec, model or parameter version, source observation IDs, predicted readouts and a justified quantitative uncertainty or tolerance that can distinguish consequential failure from agreement; a vacuous interval provides no transfer evidence.",
                      ("research_notes", "analysis_records"), "before_transfer_result"),
            _evidence("source_and_target_observations", 2, "observed_experiment_including_each_regime",
                      "Cite at least one observed source experiment and one observed target experiment; the selected target outcome must not have been used to fit its prospective prediction.",
                      ("experiment_records", "explanation")),
            _evidence("transfer_error_and_scope", 1, "transfer_assessment",
                      "Quantify the original target prediction error relative to the stated uncertainty and public noise or scales; report successes and failures, distinguish interpolation from a new control regime, and label any subsequent refit separately.",
                      ("analysis_records", "explanation")),
        ],
        "A relation fitted without the selected target outcome makes an informative target prediction that meets a justified, nonvacuous prospective uncertainty or tolerance criterion, with the transfer domain and remaining failures explicitly bounded.",
        ("scoped_transfer_supported", "transfer_failed", "transfer_inconclusive"),
    ),
}


def get_task_profile(name=DEFAULT_TASK_PROFILE, environment=None):
    """Return a JSON-safe public profile copy; optionally validate applicability."""
    if not isinstance(name, str) or name not in _PROFILES:
        raise ValueError("unknown task profile; choose open_discovery, mechanism_discrimination or regime_transfer")
    if environment is not None:
        if not isinstance(environment, str) or environment not in _PROFILES[name]["applicable_environments"]:
            raise ValueError("task profile is not applicable to the requested environment")
    return deepcopy(_PROFILES[name])


def list_task_profiles(environment=None):
    """Return profiles in stable order, validating an optional public environment."""
    return [get_task_profile(name, environment) for name in TASK_PROFILE_NAMES]
