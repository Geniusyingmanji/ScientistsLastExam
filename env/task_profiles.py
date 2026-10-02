"""Public scientific task descriptions; no execution, scoring or hidden state.

These profiles specify evidence to seek within the existing experiment and
submission contracts. Their checklists require a separate scientific review;
this module never returns an automatic scientific-success verdict.
"""

from copy import deepcopy


TASK_PROFILE_CATALOG_VERSION = "scientific-task-profiles-0.1.4"
DEFAULT_TASK_PROFILE = "open_discovery"
TASK_PROFILE_NAMES = ("open_discovery", "mechanism_discrimination", "regime_transfer",
                      "model_revision", "boundary_mapping")
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
             positive_finding_requires, allowed_conclusions, inconclusive_policy=None):
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
            "inconclusive_policy": inconclusive_policy or "An adequate inconclusive or falsifying investigation can complete the evidence checklist; it does not count as a positive mechanism or transfer finding.",
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


_LIMITED_EVIDENCE_POLICY = (
    "An adequately documented negative, entirely inconclusive or budget-limited investigation is a valid "
    "scientific conclusion and need not produce a revision success or boundary. State which observations "
    "were obtained and which requirements remain not_demonstrated because the necessary test was not "
    "performed. A valid limited conclusion does not declare an incomplete checklist complete. Preserve "
    "failed predictions, ambiguous results and stopping reasons; do not expand the budget, manufacture "
    "a failure or assert a positive result to satisfy the task."
)


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
    "model_revision": _profile(
        "model_revision",
        "Investigate whether a model can be usefully revised after an observed prediction failure or "
        "demonstrated limitation. Start from a prediction and its model version recorded before the "
        "corresponding result, and retain that original record and the actual observation with IDs. "
        "Diagnose the discrepancy relative to measurement uncertainty and the original criterion; "
        "a hypothetical failure or a model invented after its result is not this evidence. State "
        "exactly what assumptions, parameters or scope you revise and why, and what remains fixed. "
        "Before obtaining results in new legal conditions that were not used to formulate or fit the "
        "revision, record the revised model version, predicted readouts and informative justified "
        "uncertainty or tolerance. Test those predictions and assess them before further refitting. "
        "When claiming improvement, compare the unchanged original and revised models on the same "
        "new readouts with the comparison criterion fixed in advance. Do not overwrite failed "
        "predictions, silently substitute a newer model or treat a better fit to revision data as "
        "prospective success. A failed revision, no supported reason to revise, entirely inconclusive "
        "observations or insufficient budget for a new test is a valid scoped conclusion; identify "
        "the missing evidence rather than inventing a failure or claiming completion.",
        "Traceable correction of a diagnosed predictive limitation, tested prospectively on conditions excluded from revision.",
        ("improved fit to already used data proves predictive revision", "the revised model is the true mechanism",
         "a hypothetical or retrospectively invented failure is observed evidence", "every revision must succeed"),
        [
            _evidence("original_prediction", 1, "prediction_recorded_before_its_result",
                      "Identify the original model/version, conditions, predicted readouts and original uncertainty or criterion in a record that preceded the associated observation. Preserve the original record.",
                      ("research_notes", "analysis_records"), "before_original_result"),
            _evidence("observed_limitation_and_diagnosis", 1, "observed_prediction_limitation",
                      "Cite the actual observation exposing the earlier prediction's failure or limitation, quantify the discrepancy and diagnose it against uncertainty. Distinguish noise, missing evidence and a model limitation; no unsupported failure may be manufactured.",
                      ("experiment_records", "research_notes", "analysis_records", "explanation"), "before_revision"),
            _evidence("documented_revision", 1, "explicit_model_revision",
                      "Link the revised version to the unchanged original and failed/limiting evidence. State the changed assumptions, parameters or scope, rationale and retained components; list all data used for the revision.",
                      ("research_notes", "analysis_records"), "before_revision_test_result"),
            _evidence("fresh_revision_prediction", 1, "prospective_prediction_on_unused_conditions",
                      "Before new outcomes are observed, freeze the revised version, legal test conditions not used to formulate or fit it, readouts and justified nonvacuous tolerance. For an improvement claim, also freeze the original model's predictions and the comparison criterion for these same readouts.",
                      ("research_notes", "analysis_records"), "before_revision_test_result"),
            _evidence("revision_test_and_assessment", 1, "observed_prospective_revision_test",
                      "Cite the new observation, assess the recorded predictions before any further refit and preserve all unsuccessful comparisons. Separate surviving the fresh test from merely fitting the earlier counterexample.",
                      ("experiment_records", "analysis_records", "explanation")),
            _evidence("revision_scope_and_limits", 1, "bounded_revision_assessment",
                      "Report whether revision helped, failed or remains unresolved; state uncertainty, untested conditions, remaining alternatives and budget/stopping limits. If no actual limitation or no fresh test was obtained, say which requirements are not demonstrated.",
                      ("research_notes", "explanation")),
        ],
        "A revision linked to a documented earlier predictive limitation survives an informative prospective test in conditions excluded from its construction; any claimed improvement is supported by the prespecified comparison to the unchanged original on the same new readouts.",
        ("scoped_revision_supported", "revision_failed", "revision_inconclusive",
         "no_supported_limitation_to_revise", "revision_untested_budget_limited"),
        inconclusive_policy=_LIMITED_EVIDENCE_POLICY,
    ),
    "boundary_mapping": _profile(
        "boundary_mapping",
        "Investigate the empirical domain of adequacy of a fixed quantitative model. Before the "
        "mapping observations, record its version and source evidence, chosen readouts, and an "
        "informative tolerance or adequacy criterion justified by measurement uncertainty and the "
        "scientific size of error that matters. Fix a continuous or ordered legal control axis, or "
        "an explicitly parameterized path, its concrete domain and the other controls held fixed. "
        "Plan observations that seek both adequate and inadequate predictions across that domain, "
        "and how to refine transitions or stop within the existing budget. Record predictions before "
        "each new result using the same frozen model and criterion; do not refit the model or widen "
        "the tolerance to redraw its boundary. Preserve adequate, failed and uncertainty-limited "
        "results with observation IDs. A scoped empirical boundary needs evidence on both sides "
        "and a supported transition bracket or region at stated sampling resolution. A successful "
        "regime transfer or one failed point alone does not establish a complete empirical boundary. "
        "Do not assume monotonicity or that unmeasured intervals behave like sampled points; disclose "
        "any such assumptions and unresolved gaps. If the domain contains no detected transition, "
        "all results are inconclusive or the budget is insufficient, report the tested bounds and "
        "limits without forcing a boundary or treating its absence as universal adequacy.",
        "Prospective empirical localization of where a fixed model meets or fails a prespecified adequacy criterion across a declared control domain.",
        ("one successful transfer establishes an empirical boundary", "one failure locates a complete domain boundary",
         "finite observations prove adequacy between or beyond sampled controls", "a boundary must exist or be found"),
        [
            _evidence("fixed_model_and_criterion", 1, "frozen_model_and_adequacy_criterion",
                      "Record the model/version, source evidence, target readouts and scientific justification for the uncertainty-aware, nonvacuous tolerance or adequacy criterion. Freeze them before using mapping results.",
                      ("research_notes", "analysis_records"), "before_boundary_observations"),
            _evidence("ordered_control_domain", 1, "explicit_control_domain",
                      "Specify a continuous or ordered legal control axis or parameterized path, concrete ranges/ordered values, held-fixed controls and the scope of inference. State possible nonmonotonicity rather than presuming a single threshold.",
                      ("research_notes", "analysis_records"), "before_boundary_observations"),
            _evidence("boundary_search_design", 1, "bounded_sampling_and_stopping_plan",
                      "Plan how observations will seek both model adequacy and failure and refine any apparent transition, with resolution, uncertainty and stopping/budget rules. Adaptive point selection may use earlier observations while retaining the same frozen model and criterion.",
                      ("research_notes", "analysis_records"), "before_boundary_observations"),
            _evidence("prospective_mapping_predictions", 1, "prediction_recorded_before_mapping_result",
                      "Record each queried condition and the frozen model's prediction before its observation. Keep all predictions and model/tolerance versions; revised models require a separate map and cannot replace the original evidence.",
                      ("research_notes", "analysis_records"), "before_each_mapping_result"),
            _evidence("mapping_observations", 1, "traceable_mapping_observation_set",
                      "Cite the sampled control values and observations, errors and uncertainty; classify adequate, failed or unresolved points using the fixed criterion. A positive boundary claim additionally requires both adequate and failed evidence supporting a transition bracket or region, not just one failed point.",
                      ("experiment_records", "analysis_records", "explanation")),
            _evidence("boundary_extent_and_limits", 1, "bounded_domain_assessment",
                      "Give supported brackets/regions and their resolution, unmeasured gaps and conditional assumptions, or report no boundary found within explicitly tested bounds. Preserve all-inconclusive and budget-limited outcomes; do not call isolated failure or ordinary successful transfer a complete boundary map.",
                      ("research_notes", "analysis_records", "explanation")),
        ],
        "Prospective observations under one frozen model and informative criterion support both adequate and failed predictions and localize a transition bracket or region along the declared control domain, with uncertainty, sampling resolution and unmeasured gaps stated.",
        ("scoped_empirical_boundary_supported", "boundary_not_found_within_tested_domain",
         "boundary_inconclusive", "boundary_search_budget_limited"),
        inconclusive_policy=_LIMITED_EVIDENCE_POLICY,
    ),
}


def get_task_profile(name=DEFAULT_TASK_PROFILE, environment=None):
    """Return a JSON-safe public profile copy; optionally validate applicability."""
    if not isinstance(name, str) or name not in _PROFILES:
        raise ValueError("unknown task profile; choose " + ", ".join(TASK_PROFILE_NAMES))
    if environment is not None:
        if not isinstance(environment, str) or environment not in _PROFILES[name]["applicable_environments"]:
            raise ValueError("task profile is not applicable to the requested environment")
    return deepcopy(_PROFILES[name])


def list_task_profiles(environment=None):
    """Return profiles in stable order, validating an optional public environment."""
    return [get_task_profile(name, environment) for name in TASK_PROFILE_NAMES]
