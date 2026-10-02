"""Opt-in public presentation, separate from tasks, worlds and scoring.

``full_description`` returns the supplied problem unchanged apart from copying.
``apparatus_only`` reconstructs an audited instrument manual for two backends;
it never edits a World, request, observation, predictor, panel or score. Call
``present_problem`` AFTER assembling task/score/submission contracts, and pass
the SAME returned problem to both the language-model prompt and isolated
analysis. Pair it with ``present_system`` before enabling this experimental arm.

The catalog and leakage boundary returned by ``get_presentation_profile`` and
``leakage_boundary`` are OPERATOR-ONLY. They intentionally name the withheld
families. Only the outputs of present_problem/present_system are agent-facing.

Audited-input hashes are drift guards, not security proofs or secret hashes.
They force a fresh manual review when a world description, task, system prompt,
or scoring contract changes. Update templates and tests before changing hashes.
Existing full_description/open_discovery callers never consult these guards.

No runner or campaign is wired here. This module performs no I/O and imports
no World, registry, numerical solver, baseline, scorer or model client.
"""

from copy import deepcopy
import hashlib
import json
import math


PRESENTATION_CATALOG_VERSION = "presentation-profiles-0.1.0"
DEFAULT_PRESENTATION_PROFILE = "full_description"
PRESENTATION_PROFILE_NAMES = ("full_description", "apparatus_only")
APPARATUS_ENVIRONMENTS = ("coupled_oscillators", "ising_spin")

_DESCRIPTION_HASHES = {
    "coupled_oscillators": "7cda13cff601e67884a38d56a8e2a96a14c1ede9e626d522172d7e9d58370038",
    "ising_spin": "4101a4788fd43ae618092f02ac45a41fbbe01ff45a2e7dc446327f0cb4ed8572",
}
_TASK_HASHES = {
    "open_discovery": "a1e2e994e05ca8d3c5486365b4184e129851ea49d65d48fb8a10125d137d630e",
    "mechanism_discrimination": "6d397176213bb35c18f67d58a042a21ee3aa88d5fe1caa9e6144a6e49bb45844",
    "regime_transfer": "dbd82544c11f75c8d991798eb6e3fee44d1b0c64c8d364583aac8ed445687372",
}
# The two new scientific tasks remain unaudited for apparatus_only. The original
# three hash updates account only for catalog 0.1.6 and twelfth-world applicability.
# Spin-echo policy additions are scoped out of the two apparatus projections;
# old scientific content is identical after only catalog/policy version normalization.
_SCORE_HASH = "a9d80c99e75cda6353741543844915b94284abbc59aaa1cbf2a975f0d07a9137"
_SYSTEM_HASH = "66b2af813e28055ecb137da97d7720f5c57de8d636ff6de8ab5edb00e21afa3e"
_ATTACHMENTS = ("task_profile", "score_contract", "submission_contract")
_SUBMISSION_CONTRACT = {
    "entrypoint": "predict(spec)",
    "returns": "values array only; exact public channel order",
    "claim_count": "0..3",
    "claim_replicates_per_arm": 8,
}


def _profile_name(name):
    if not isinstance(name, str) or name not in PRESENTATION_PROFILE_NAMES:
        raise ValueError("unknown presentation profile; choose full_description or apparatus_only")
    return name


def _apparatus_environment(environment):
    if not isinstance(environment, str) or environment not in APPARATUS_ENVIRONMENTS:
        raise ValueError("apparatus_only is not audited for this environment")
    return environment


def _digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded) > 128000:
            raise ValueError()
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError):
        raise ValueError("presentation input must be a bounded finite JSON object") from None


def _audited_task(task):
    name = task.get("name") if isinstance(task, dict) else None
    if not isinstance(name, str) or name not in _TASK_HASHES:
        raise ValueError("task profile is not audited for apparatus_only")
    if _digest(task) != _TASK_HASHES[name]:
        raise ValueError("task presentation changed; apparatus_only requires an audit")


def get_presentation_profile(name=DEFAULT_PRESENTATION_PROFILE, environment=None, *, task_profile=None):
    """Return detached OPERATOR metadata; do not attach this catalog to a prompt."""
    name = _profile_name(name)
    if name == "apparatus_only" and environment is not None:
        _apparatus_environment(environment)
    if name == "apparatus_only" and task_profile is not None:
        _audited_task(task_profile)
    return {
        "name": name,
        "version": name + "-0.1.0",
        "catalog_version": PRESENTATION_CATALOG_VERSION,
        "operator_only": True,
        "supported_environments": list(APPARATUS_ENVIRONMENTS) if name == "apparatus_only" else "any_existing_public_description",
        "default_enabled": name == DEFAULT_PRESENTATION_PROFILE,
        "changes": "public_problem_and_system_wording_only" if name == "apparatus_only" else "none",
        "world_request_observation_and_scoring_changes": False,
        "task_profile_override": None,
        "recommended_comparison": "Use the same task_profile, seeds, panels, budgets and model settings in both presentations; mechanism_discrimination is useful for reviewing evidence about model class.",
        "assessment": "Separate evidence review of assumptions, prospective discriminators, observations and remaining equivalences; prediction score does not certify model-class recovery.",
        "leakage_boundary": leakage_boundary() if name == "apparatus_only" else None,
    }


def leakage_boundary():
    """Return the OPERATOR-only information policy and wiring audit."""
    return {
        "operator_only": True,
        "retained": [
            "Original request keys, defaults, accepted values, finite ranges and all rejection constraints.",
            "Apparatus labels, channel order/definitions, units, measurement noise and fixed normalization scales.",
            "Known actuator calibration, including imposed force waveform, added brake coefficient, loading, clamp assignment and connector attenuation.",
            "Fresh-preparation semantics and the distinction between a time series and independent equilibrated temperature preparations.",
            "Cost formula, maximum data sizes and the requirement to expose unchanged episode limits and remaining budget.",
            "Existing submission, scientific-task and numerical-scoring obligations, with claim eligibility scoped to this apparatus.",
        ],
        "withheld": [
            "Backend registry names, world-version identifiers and the list of other environments.",
            "Governing differential equations, Hamiltonian, Gibbs/Boltzmann distribution and named physical families.",
            "Hidden-parameter definitions/ranges, graph connectivity/sparsity/sign priors and the number of unknown coefficients.",
            "Claims excluding nonlinear forces, delays, higher-order interactions or additional latent mechanisms.",
            "Implementation algorithms, exact state enumeration, integrator details and the physics-informed baseline fitting recipe.",
            "Directed discovery suggestions such as spring reconstruction, frustration or susceptibility, and theory-specific diagnostics.",
            "Private instance/panel seeds, parameters, outcomes, reference mechanisms and operator artifacts, which remain private in every profile.",
        ],
        "residual_information": [
            "This is reduced model-family prompting, not domain blindness: displacement/velocity, binary readings, temperature and control names reveal apparatus type.",
            "Known actuator laws are retained even when they suggest useful model terms; hiding their calibration would change the experimental problem.",
            "The same fixed backend families are used. Prior knowledge or recognition can identify them; this does not establish held-out-family generalization or contamination resistance.",
            "All observed channels remain available. A sufficiently informative measurement set can make identifying a family easy.",
            "Existing public-data baselines retain family priors; treat them as family-informed references, not equally blinded discovery policies.",
        ],
        "entrypoint_audit": {
            "world_public_entrypoint": "World.describe(); no batch World.public_info entrypoint exists in the audited revision.",
            "problem_sinks": ["runner prompt.problem", "isolated analysis problem"],
            "secondary_leaks": ["runner.SYSTEM", "score_contract.claim_eligibility environment table and family labels", "task_profile.applicable_environments", "future raw errors or operator reports copied into candidate history"],
            "unchanged_visible_data": ["canonical experiment specs", "observation axis/channels/values", "observation IDs", "costs", "remaining budgets", "agent research notes"],
        },
        "integration_order": [
            "Build the original problem including task_profile, score_contract and submission_contract.",
            "Project that final problem once with present_problem; give exactly that projection to both candidate prompt and analysis.",
            "Project the system prompt with present_system; do not append raw descriptions, catalogs or contracts afterwards.",
            "Leave limits/budget in the existing prompt envelope unchanged. Store backend identity, profile version and rendered prompt hashes only in operator provenance.",
            "Keep original World/specs/observations, panel hashes, baselines and scorer. Scope raw errors and later interpretation context separately before exposing operator metadata.",
        ],
    }


def _base_public(info, axis, summary):
    return {
        "name": "apparatus",
        "version": "apparatus-interface-0.1.0",
        "presentation": {"name": "apparatus_only", "version": "apparatus_only-0.1.0"},
        "summary": summary,
        "axis_field": axis,
        "nodes": deepcopy(info["nodes"]),
        "channels": deepcopy(info["channels"]),
        "channel_units": deepcopy(info["channel_units"]),
        "scales": deepcopy(info["scales"]),
        "noise_std": deepcopy(info["noise_std"]),
        "documentation_scope": "This manual defines measurements and available preparations and controls. Infer a response model from evidence; distinguish assumptions from observed regularities. The scientific task and submission contracts still apply.",
        "observation": {"axis": axis, "shape": "[number of requested coordinates, number of public channels]", "row_order": "Matches the requested coordinate list.", "noise": "Independent additive Gaussian measurement errors with the listed standard deviations for every row/channel, including prescribed initial or clamped values. No clipping; repeated preparations have no additional process noise."},
        "budget": {"cost_units": "Use the cost formula below; invalid requests are not experiments.", "episode_limits": "The separate limits and remaining budget in each request are authoritative, including turns, experiment count/units and active analysis time. A rejected action still consumes its model turn."},
    }


def _mechanical_public(info):
    result = _base_public(info, "times", "Four labelled moving elements on a mechanical test bench. Position and velocity are measured after a fresh preparation; controls are held fixed throughout each run.")
    result.update({
        "units": {"time": "s", "position": "m", "velocity": "m/s", "mass": "kg", "added_brake_coefficient": "N s/m", "applied_force": "N", "frequency": "Hz", "phase": "rad"},
        "apparatus_calibration": {"unloaded_mass_kg": [1.0] * 4, "labels": "A,B,C,D identify measurement and actuation locations; the letters do not specify geometry.", "reset": "Every experiment starts at time zero with the specified positions and velocities on the same fixed apparatus. There is no carryover from an earlier run."},
        "channel_definitions": {"x_A..x_D": "Signed displacements in node order A,B,C,D, measured in m.", "v_A..v_D": "Corresponding signed velocities in the same order, measured in m/s."},
        "experiment_schema": {
            "required": ["times"],
            "unknown_fields": "Rejected at every level. Numeric values must be finite numbers, not booleans or strings.",
            "times": {"type": "array", "length": [1, 241], "range": [0, 24], "unit": "s", "ordering": "strictly increasing; time zero is optional"},
            "initial_position": {"type": "array", "length": 4, "range": [-1, 1], "unit": "m", "default": [0.0] * 4},
            "initial_velocity": {"type": "array", "length": 4, "range": [-2, 2], "unit": "m/s", "default": [0.0] * 4},
            "mass_add": {"type": "array", "length": 4, "range": [0, 3], "unit": "kg", "default": [0.0] * 4, "action": "Attach the specified extra mass at each element. Existing connections and the settings of other apparatus components are retained."},
            "damping_add": {"type": "array", "length": 4, "range": [0, 2], "unit": "N s/m", "default": [0.0] * 4, "action": "Attach calibrated ground-referenced brakes. Each added brake contributes force -damping_add_i*v_i. This specifies the added actuator, not the remaining apparatus response."},
            "cut_edges": {"type": "array of distinct unordered node pairs", "max_length": 6, "default": [], "action": "Disconnect the selected possible connectors at both endpoints for this run. A pair that was not connected is unchanged. Endpoints must be different names from A,B,C,D; reversed duplicate pairs are invalid."},
            "clamp": {"type": "array of distinct node names", "max_length": 4, "default": [], "action": "Hold named elements at zero displacement and velocity. Their initial positions and velocities must also be zero. Existing connections to a held element stay attached at that fixed position."},
            "drive": {"type": "null or object", "default": None, "required_object_fields": ["node", "amplitude", "frequency", "phase"], "node": ["A", "B", "C", "D"], "amplitude": {"range": [-2, 2], "unit": "N"}, "frequency": {"range": [0, 2], "unit": "Hz"}, "phase": {"range": [-math.pi, math.pi], "unit": "rad"}, "calibration": "The imposed force is amplitude*sin(2*pi*frequency*t+phase) at the selected node. Zero frequency with phase pi/2 is a constant force. Nonzero drive on a clamped node is invalid."},
            "control_timing": "All controls apply at time zero and stay fixed. Four-element arrays always follow A,B,C,D.",
        },
        "cost": {"formula": "1 + ceil(last_requested_time/4) + ceil(number_of_rows/32)", "range": [2, 15]},
        "examples": [
            {"times": [0, 0.1, 0.2, 0.5, 1, 2, 4], "initial_position": [0.4, 0, 0, 0]},
            {"times": [0, 0.25, 0.5, 1, 2], "initial_velocity": [0, 0.5, 0, 0], "cut_edges": [["A", "C"]], "mass_add": [0, 1, 0, 0], "damping_add": [0.2, 0, 0, 0]},
            {"times": [0, 0.5, 1, 3], "clamp": ["D"], "drive": {"node": "B", "amplitude": 0.5, "frequency": 0.25, "phase": 0}},
        ],
    })
    return result


def _binary_public(info):
    result = _base_public(info, "temperatures", "Six labelled sites have binary readings -1 or +1. The instrument reports averages over equilibrated preparations at controlled bath temperatures, with local inputs, holding clamps and pair-specific attenuators.")
    result.update({
        "units": {"temperature": "known reduced bath temperature k_B*T/epsilon", "external_field": "energy units epsilon", "observations": "dimensionless", "suppression_fraction": "dimensionless"},
        "apparatus_calibration": {"binary_values": [-1, 1], "reset": "Each requested temperature is a separate freshly equilibrated preparation of the same apparatus. Row order is not a cooling trajectory. No initial-state, elapsed-time or history control is available.", "energy_scale": "epsilon is fixed and known; temperature and local inputs use this same calibration."},
        "channel_definitions": {"m_A..m_F": "Mean binary reading at each site, in order A,B,C,D,E,F.", "c_LEFT_RIGHT": "Mean product of the two simultaneous binary readings for that pair; these are raw pair moments, not covariance. All 15 distinct unordered pairs are reported in the listed channel order.", "clean_range": [-1, 1]},
        "experiment_schema": {
            "required": ["temperatures"],
            "unknown_fields": "Rejected at every experiment/control level. Numeric values must be finite numbers, not booleans or strings.",
            "temperatures": {"type": "array", "length": [1, 32], "range": [0.35, 6], "unit": "k_B*T/epsilon", "ordering": "strictly increasing"},
            "external_field": {"type": "array", "length": 6, "range": [-2, 2], "unit": "epsilon", "default": [0.0] * 6, "calibration": "Six additive local inputs. At site i the imposed input contributes energy -external_field_i*s_i for binary reading s_i; zero adds no local bias. This calibrates the applied input, not the complete energy or probability law."},
            "clamp": {"type": "object mapping site names to integer -1 or +1", "max_length": 6, "default": {}, "action": "Hold each listed site's binary reading fixed; retain its connections to other sites. All six sites may be held. Zero, fractional values and booleans are invalid. A local input on an already held site does not change the measured averages."},
            "suppress_bonds": {"type": "array of control objects", "max_length": 15, "default": [], "required_object_fields": ["nodes", "fraction"], "nodes": "Two distinct names from A,B,C,D,E,F. Pairs are unordered; duplicates, including reversed pairs, are invalid.", "fraction": {"range": [0, 1]}, "action": "Reduce the strength of the selected possible connector by the given fraction, preserving its sign. Zero leaves it unchanged and one disables it fully. An absent connector is unaffected. No rule for the resulting ensemble averages is supplied."},
            "control_timing": "The same static controls apply at every requested temperature. Six-element arrays follow A,B,C,D,E,F.",
        },
        "cost": {"formula": "1 + ceil(number_of_temperatures/4)", "range": [2, 9]},
        "examples": [
            {"temperatures": [0.5, 0.8, 1.2, 2, 3.5, 6]},
            {"temperatures": [0.7, 1.4, 2.8], "external_field": [0.6, 0, 0, 0, 0, 0]},
            {"temperatures": [0.5, 1, 2], "clamp": {"B": -1}, "suppress_bonds": [{"nodes": ["A", "C"], "fraction": 0.5}]},
        ],
    })
    return result


def _project_score(contract, environment):
    if _digest(contract) != _SCORE_HASH:
        raise ValueError("scoring presentation changed; apparatus_only requires an audit")
    result = deepcopy(contract)
    policy = contract["claim_eligibility"]
    projected = {key: deepcopy(policy[key]) for key in (
        "protocol", "input_contract", "absolute_coordinate_tolerance",
        "resolution_interpretation", "limits", "reason_codes",
    )}
    if environment == "coupled_oscillators":
        projected["minimum_lag"] = deepcopy(policy["minimum_lag"][environment])
        projected["matched_coordinate"] = "Both arms must use the same requested time at the readout row, within absolute_coordinate_tolerance."
        projected["time_rule"] = "The readout must be at least minimum_lag.value after preparation at time zero in each arm. The boundary is inclusive within absolute_coordinate_tolerance."
        projected["readout_rule"] = policy["oscillator_rule"]
    else:
        projected["minimum_lag"] = None
        projected["matched_coordinate"] = "The two temperatures may differ as a controlled treatment. There is no elapsed-time or cross-arm temperature matching requirement."
        projected["readout_rule"] = policy["ising_rule"]
    result["claim_eligibility"] = projected
    return result


def present_problem(public_info, profile=DEFAULT_PRESENTATION_PROFILE, *, environment=None):
    """Project a fully assembled public problem, without changing experiments.

    The default is an exact defensive copy, including any existing open_discovery
    task. For apparatus_only, descriptions and known attached contracts must match
    reviewed revisions; unknown additions fail closed before a candidate is run.
    This guards against a later family hint entering through a newly copied field.
    """
    profile = _profile_name(profile)
    if not isinstance(public_info, dict):
        raise ValueError("public_info must be a public-description object")
    if profile == "full_description":
        return deepcopy(public_info)
    environment = _apparatus_environment(public_info.get("name") if environment is None else environment)
    if public_info.get("name") != environment:
        raise ValueError("apparatus source identity does not match the requested environment")
    base = {key: value for key, value in public_info.items() if key not in _ATTACHMENTS}
    if _digest(base) != _DESCRIPTION_HASHES[environment]:
        raise ValueError("world description changed; apparatus_only requires a schema and leakage audit")
    result = _mechanical_public(base) if environment == "coupled_oscillators" else _binary_public(base)
    if "task_profile" in public_info:
        task = public_info["task_profile"]
        _audited_task(task)
        result["task_profile"] = deepcopy(task)
        del result["task_profile"]["applicable_environments"]
    if "score_contract" in public_info:
        result["score_contract"] = _project_score(public_info["score_contract"], environment)
    if "submission_contract" in public_info:
        if public_info["submission_contract"] != _SUBMISSION_CONTRACT:
            raise ValueError("submission presentation changed; apparatus_only requires an audit")
        result["submission_contract"] = deepcopy(_SUBMISSION_CONTRACT)
    return result


_SYSTEM_CLAIM_BLOCK = """Row is zero-based and must be after t=0. The interval is a central 90% predictive
interval for the mean of eight fresh noisy treatment-minus-control differences.
The public claim_eligibility rules exclude immediate assignment/addition readouts
and directly clamped observables. Use the declared minimum evolution time after
preparation/events, and matched times in dynamical worlds. Temperature contrasts
in equilibrium spin systems are permitted. Prefer effects requiring learned
behavior rather than facts already given by the tool contract.
"""
_APPARATUS_CLAIM_BLOCK = """Row is zero-based. Follow this apparatus's public claim_eligibility policy for
allowed coordinates, coordinate matching and minimum lag where applicable.
The interval is a central 90% predictive interval for the mean of eight fresh
noisy treatment-minus-control differences. Public rules exclude direct assignment
readouts and directly clamped observables. Prefer effects requiring learned
behavior rather than facts already given by the tool contract.
"""


def present_system(system_prompt, profile=DEFAULT_PRESENTATION_PROFILE):
    """Remove cross-apparatus labels from the audited system claim paragraph.

    This exact, reviewed paragraph substitution preserves action/submission
    instructions. It is not a keyword scrubber. The default returns the original
    string; any unreviewed apparatus-only system prompt fails closed.
    """
    profile = _profile_name(profile)
    if not isinstance(system_prompt, str):
        raise ValueError("system_prompt must be text")
    if profile == "full_description":
        return system_prompt
    try:
        digest = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
    except UnicodeError:
        raise ValueError("system prompt changed; apparatus_only requires an audit") from None
    if digest != _SYSTEM_HASH or system_prompt.count(_SYSTEM_CLAIM_BLOCK) != 1:
        raise ValueError("system prompt changed; apparatus_only requires an audit")
    return system_prompt.replace(_SYSTEM_CLAIM_BLOCK, _APPARATUS_CLAIM_BLOCK, 1)
