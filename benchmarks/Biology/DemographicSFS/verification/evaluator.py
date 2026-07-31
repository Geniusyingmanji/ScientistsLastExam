"""Trusted oracle for active demographic inference from the unfolded SFS, version 2.

The public forward model is an exact finite-sample Kingman-coalescent CTMC for a
three-epoch, piecewise-constant population history.  Candidates allocate a finite
sequencing budget across sample sizes, then either return four fixed-scale shape
parameters or abstain when the public family is unsupported.  Development fit,
parameter recovery, held-out sample-size prediction and refusal remain separate
evaluator outputs.  Full local rank does not erase finite-SFS conditioning limits.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy.linalg import expm, solve_triangular


DEMOGRAPHIC_SFS_V2 = True

PARAMETER_NAMES = (
    "recent_size_ratio",
    "middle_size_ratio",
    "recent_epoch_end_coalescent_units",
    "middle_epoch_end_coalescent_units",
)
PARAMETER_BOUNDS = np.asarray((
    (0.20, 4.00),
    (0.20, 4.00),
    (0.025, 0.140),
    (0.180, 0.520),
), dtype=float)
# Log-scale tolerances intentionally reflect finite-SFS information limits.  A
# candidate is not rewarded as if exact truth were recoverable from finite loci.
PARAMETER_LOG_TOLERANCES = np.asarray((0.22, 0.28, 0.24, 0.22), dtype=float)

ANCESTRAL_SIZE_RATIO = 1.0
# Aggregate mutation opportunity per independent locus panel.  It sets the
# expected number of segregating sites; it is not a per-nucleotide mutation rate.
THETA_PER_PANEL = 70.0
# Retain the shorter alias for audit helpers while keeping public payloads precise.
THETA_PER_LOCUS = THETA_PER_PANEL
ALLOWED_SAMPLE_SIZES = (12, 20, 32, 48, 64)
HELDOUT_SAMPLE_SIZES = (28, 40, 56)
SEQUENCING_BUDGET_UNITS = 8
MAX_REPLICATES_PER_CALL = 4

DEVELOPMENT_SPECS = (
    (6101, "in_library"),
    (6102, "in_library"),
    (6103, "in_library"),
    (6104, "in_library"),
    (6105, "constant"),
    (6106, "ancestral_misidentification"),
)
HELDOUT_SPECS = (
    (7101, "in_library"),
    (7102, "in_library"),
    (7103, "in_library"),
    (7104, "constant"),
    (7105, "ancestral_misidentification"),
)

_COALESCENT_CACHE = {}


def _coalescent_matrices(n_sample):
    """Return lineage-count generator and descendant-count mapping.

    State ``k`` is the number of extant ancestral lineages.  In units of
    ``2*N_anc`` generations, transitions k -> k-1 occur at choose(k, 2)/N(t).
    Conditional on k lineages, the expected number subtending i leaves is
    k*C(n-i-1,k-2)/C(n-1,k-1).  Multiplication by one half below converts the
    total branch length in these time units to the conventional theta/i SFS.
    """
    n_sample = int(n_sample)
    cached = _COALESCENT_CACHE.get(n_sample)
    if cached is not None:
        return cached
    if n_sample < 3:
        raise ValueError("sample size must be at least three")
    state_count = n_sample - 1
    generator = np.zeros((state_count, state_count), dtype=float)
    descendants = np.zeros((state_count, n_sample - 1), dtype=float)
    for state_index, lineage_count in enumerate(range(n_sample, 1, -1)):
        rate = lineage_count * (lineage_count - 1) / 2.0
        generator[state_index, state_index] = -rate
        if state_index + 1 < state_count:
            generator[state_index, state_index + 1] = rate
        denominator = math.comb(n_sample - 1, lineage_count - 1)
        for derived_count in range(1, n_sample):
            remainder = n_sample - derived_count - 1
            if remainder >= lineage_count - 2:
                descendants[state_index, derived_count - 1] = (
                    lineage_count
                    * math.comb(remainder, lineage_count - 2)
                    / denominator
                )
    _COALESCENT_CACHE[n_sample] = generator, descendants
    return generator, descendants


def expected_sfs_piecewise(n_sample, sizes, epoch_ends):
    """Expected unfolded SFS per unit theta for a piecewise-constant history.

    ``sizes`` are relative to ancestral population size, ordered backward in
    time from the present.  ``epoch_ends`` are strictly increasing times in
    2*N_anc generations and have length ``len(sizes)-1``.
    """
    sizes = np.asarray(sizes, dtype=float).ravel()
    epoch_ends = np.asarray(epoch_ends, dtype=float).ravel()
    if len(sizes) < 1 or len(epoch_ends) != len(sizes) - 1:
        raise ValueError("piecewise history dimensions do not match")
    if (
        not np.all(np.isfinite(sizes)) or np.any(sizes <= 0.0)
        or not np.all(np.isfinite(epoch_ends))
        or np.any(epoch_ends <= 0.0)
        or np.any(np.diff(epoch_ends) <= 0.0)
    ):
        raise ValueError("piecewise history must be finite, positive and ordered")

    generator, descendants = _coalescent_matrices(int(n_sample))
    state_count = len(generator)
    probability = np.zeros(state_count, dtype=float)
    probability[0] = 1.0
    occupancy = np.zeros(state_count, dtype=float)
    start = 0.0
    for epoch_index, size in enumerate(sizes):
        transition_generator = generator / float(size)
        if epoch_index == len(epoch_ends):
            # Integral_0^infinity p exp(Mt) dt = p (-M)^-1.  Solving the
            # transposed triangular system avoids an explicit inverse.
            occupancy += solve_triangular(
                (-transition_generator).T, probability, lower=True
            )
            break
        end = float(epoch_ends[epoch_index])
        transition = expm(transition_generator * (end - start))
        delta = probability @ (transition - np.eye(state_count))
        occupancy += solve_triangular(
            transition_generator.T, delta, lower=True
        )
        probability = probability @ transition
        start = end
    values = 0.5 * occupancy @ descendants
    return np.maximum(np.asarray(values, dtype=float), 1.0e-15)


def public_expected_sfs(n_sample, parameters):
    parameters = np.asarray(parameters, dtype=float).ravel()
    if parameters.shape != (len(PARAMETER_NAMES),):
        raise ValueError("need four public demographic parameters")
    return expected_sfs_piecewise(
        int(n_sample),
        (parameters[0], parameters[1], ANCESTRAL_SIZE_RATIO),
        (parameters[2], parameters[3]),
    )


def _supported_parameters(seed):
    rng = np.random.default_rng(int(seed))
    if int(seed) % 2:
        recent = rng.uniform(0.38, 0.72)
        middle = rng.uniform(1.45, 2.55)
        recent_end = rng.uniform(0.080, 0.120)
        middle_end = rng.uniform(0.340, 0.490)
    else:
        recent = rng.uniform(1.45, 3.10)
        middle = rng.uniform(0.32, 0.66)
        recent_end = rng.uniform(0.055, 0.105)
        middle_end = rng.uniform(0.280, 0.450)
    return np.asarray((recent, middle, recent_end, middle_end), dtype=float)


def _world(spec):
    seed, kind = int(spec[0]), str(spec[1])
    return {
        "seed": seed,
        "kind": kind,
        "parameters": _supported_parameters(seed),
    }


def _clean_sfs(world, n_sample):
    kind = world["kind"]
    if kind == "in_library":
        return public_expected_sfs(n_sample, world["parameters"])
    if kind == "constant":
        return expected_sfs_piecewise(n_sample, (1.0,), ())
    if kind == "four_epoch":
        return expected_sfs_piecewise(
            n_sample, (0.24, 3.60, 0.31, 1.0), (0.032, 0.092, 0.330)
        )
    if kind == "mixture":
        first = expected_sfs_piecewise(
            n_sample, (0.24, 3.45, 1.0), (0.045, 0.300)
        )
        second = expected_sfs_piecewise(
            n_sample, (3.55, 0.28, 1.0), (0.040, 0.310)
        )
        return 0.53 * first + 0.47 * second
    if kind == "null":
        return np.zeros(int(n_sample) - 1, dtype=float)
    if kind == "ancestral_misidentification":
        # A resolvable 20% ancestral-state polarization error mirrors the SFS
        # toward high derived counts and violates the public clean-unfolded model.
        clean = public_expected_sfs(n_sample, world["parameters"])
        return 0.80 * clean + 0.20 * clean[::-1]
    raise ValueError("unknown trusted demographic world")


def _budget_cost(n_sample, replicates):
    # Four 12-chromosome replicates cost one unit.  Larger samples have a
    # proportional chromosome-sequencing cost, rounded up per request.
    return int(math.ceil(int(n_sample) * int(replicates) / 48.0))


class _SFSLaboratory:
    def __init__(self, world):
        self.world = world
        self.used = 0
        self.calls = 0
        self.failure = None

    def observe(self, n_sample, replicates=1):
        if isinstance(n_sample, bool) or not isinstance(n_sample, (int, np.integer)):
            self.failure = "sample size must be an allowed integer"
            raise ValueError(self.failure)
        if isinstance(replicates, bool) or not isinstance(replicates, (int, np.integer)):
            self.failure = "replicate count must be an integer"
            raise ValueError(self.failure)
        n_sample, replicates = int(n_sample), int(replicates)
        if n_sample not in ALLOWED_SAMPLE_SIZES:
            self.failure = "sample size is outside the public menu"
            raise ValueError(self.failure)
        if not 1 <= replicates <= MAX_REPLICATES_PER_CALL:
            self.failure = "replicate count is outside the public range"
            raise ValueError(self.failure)
        cost = _budget_cost(n_sample, replicates)
        if self.used + cost > SEQUENCING_BUDGET_UNITS:
            self.failure = "sequencing budget exceeded"
            raise ValueError(self.failure)
        self.used += cost
        clean = _clean_sfs(self.world, n_sample)
        payload = np.asarray((n_sample, replicates, self.calls), dtype="<i8").tobytes()
        query_seed = int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")
        rng = np.random.default_rng(
            int(self.world["seed"]) * 100003 + query_seed
        )
        expected_counts = THETA_PER_PANEL * replicates * clean
        counts = rng.poisson(expected_counts).astype(float)
        self.calls += 1
        return {
            "n_sample": n_sample,
            "replicates": replicates,
            "unfolded_sfs_counts": counts,
            "theta_per_panel": THETA_PER_PANEL,
            "expected_count_scale": THETA_PER_PANEL * replicates,
            "budget_cost": cost,
            "budget_used": self.used,
        }


def _validate_submission(returned):
    if not isinstance(returned, dict):
        raise ValueError("return artifact must be a dict")
    if set(returned) != {"parameters", "confidence", "abstain"}:
        raise ValueError("return artifact has incorrect fields")
    parameters = np.asarray(returned["parameters"], dtype=float).ravel()
    if parameters.shape != (len(PARAMETER_NAMES),) or not np.all(np.isfinite(parameters)):
        raise ValueError("parameters must contain four finite values")
    confidence = returned["confidence"]
    if isinstance(confidence, bool) or not isinstance(
        confidence, (int, float, np.integer, np.floating)
    ):
        raise ValueError("confidence must be a scalar")
    confidence = float(confidence)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must lie in [0,1]")
    if not isinstance(returned["abstain"], (bool, np.bool_)):
        raise ValueError("abstain must be boolean")
    abstain = bool(returned["abstain"])
    if not abstain and (
        np.any(parameters < PARAMETER_BOUNDS[:, 0])
        or np.any(parameters > PARAMETER_BOUNDS[:, 1])
        or parameters[2] >= parameters[3]
    ):
        raise ValueError("claimed demographic parameters violate public bounds/order")
    if abstain and float(np.max(np.abs(parameters))) > 1.0e6:
        raise ValueError("abstention parameters exceed finite safety bounds")
    return parameters, confidence, abstain


def _poisson_deviance(observed, expected):
    observed = np.asarray(observed, dtype=float)
    expected = np.maximum(np.asarray(expected, dtype=float), 1.0e-15)
    terms = 2.0 * expected
    positive = observed > 0.0
    terms = np.asarray(terms, dtype=float)
    terms[positive] = 2.0 * (
        expected[positive] - observed[positive]
        + observed[positive] * np.log(observed[positive] / expected[positive])
    )
    return float(np.sum(np.maximum(terms, 0.0)))


def _mechanism_score(parameters, truth):
    error = np.log(np.asarray(parameters) / np.asarray(truth))
    scaled = error / PARAMETER_LOG_TOLERANCES
    return float(math.exp(-0.5 * float(np.mean(scaled * scaled))))


def _sfs_prediction_score(world, parameters, sample_sizes):
    scores = []
    for n_sample in sample_sizes:
        actual = _clean_sfs(world, n_sample)
        predicted = public_expected_sfs(n_sample, parameters)
        # Poisson deviance at four independent locus panels.  Exponential
        # normalization keeps a perfect prediction at one without claiming a
        # universal statistical-optimality scale.
        deviance = _poisson_deviance(
            4.0 * THETA_PER_PANEL * actual,
            4.0 * THETA_PER_PANEL * predicted,
        )
        scores.append(math.exp(-deviance / max(2.0 * (n_sample - 1), 1.0)))
    return float(np.mean(scores))


def _public_failure_kind(stage, laboratory):
    if laboratory.failure is not None:
        return "invalid_experiment_request"
    if stage == "submission_validation":
        return "invalid_return_artifact"
    if stage == "candidate_execution":
        return "candidate_runtime_or_callback_processing_error"
    return "trusted_evaluator_internal_error"


def _invalid_record(split, index, kind, failure_kind):
    return {
        "split": split,
        "world_index": int(index),
        "valid": False,
        "reason": str(failure_kind),
        "failure_kind": str(failure_kind),
        "kind": str(kind),
        "claimed_public_model": False,
        "abstain": False,
        "confidence": 0.0,
        "budget_used": 0,
        "experiment_calls": 0,
        "mechanism_quality": 0.0,
        "observed_sfs_fit_quality": 0.0,
        "heldout_sample_size_quality": 0.0,
        "scientific_quality": 0.0,
        "correct_refusal": False,
        "false_discovery": False,
        "supported_claim": False,
        "confidence_score": 0.0,
    }


def _evaluate_world(infer_demography, spec, split, index):
    world = _world(spec)
    laboratory = _SFSLaboratory(world)
    stage = "candidate_execution"
    try:
        returned = infer_demography(
            tuple(PARAMETER_NAMES), PARAMETER_BOUNDS.copy(),
            tuple(ALLOWED_SAMPLE_SIZES), laboratory.observe,
            SEQUENCING_BUDGET_UNITS,
        )
        if laboratory.failure is not None:
            raise ValueError(laboratory.failure)
        stage = "submission_validation"
        parameters, confidence, abstain = _validate_submission(returned)
        stage = "trusted_scoring"
    except Exception:
        return _invalid_record(
            split, index, world["kind"],
            _public_failure_kind(stage, laboratory),
        )

    supported = world["kind"] in {"in_library", "constant"}
    claimed = not abstain
    correct_refusal = bool(not supported and abstain)
    false_discovery = bool(not supported and claimed)
    supported_claim = bool(supported and claimed)
    if supported_claim:
        if world["kind"] == "constant":
            truth = np.asarray((1.0, 1.0, parameters[2], parameters[3]))
            # Epoch boundaries are scientifically irrelevant when all sizes
            # equal one; score only the identifiable constant-size mechanism.
            size_error = np.log(parameters[:2]) / PARAMETER_LOG_TOLERANCES[:2]
            parameter_quality = float(math.exp(
                -0.5 * float(np.mean(size_error * size_error))
            ))
        else:
            truth = world["parameters"]
            parameter_quality = _mechanism_score(parameters, truth)
        observed_fit = _sfs_prediction_score(
            world, parameters, ALLOWED_SAMPLE_SIZES
        )
        heldout_prediction = _sfs_prediction_score(
            world, parameters, HELDOUT_SAMPLE_SIZES
        )
        mechanism_quality = parameter_quality
    elif correct_refusal:
        parameter_quality = observed_fit = heldout_prediction = 1.0
        mechanism_quality = 1.0
    else:
        parameter_quality = mechanism_quality = 0.0
        if claimed:
            observed_fit = _sfs_prediction_score(
                world, parameters, ALLOWED_SAMPLE_SIZES
            )
            heldout_prediction = _sfs_prediction_score(
                world, parameters, HELDOUT_SAMPLE_SIZES
            )
        else:
            observed_fit = heldout_prediction = 0.0
    scientific_quality = (
        mechanism_quality * observed_fit * heldout_prediction
    ) ** (1.0 / 3.0)
    confidence_score = 1.0 - (confidence - scientific_quality) ** 2
    return {
        "split": split,
        "world_index": int(index),
        "valid": True,
        "kind": str(world["kind"]),
        "claimed_public_model": claimed,
        "abstain": abstain,
        "confidence": confidence,
        "budget_used": int(laboratory.used),
        "experiment_calls": int(laboratory.calls),
        "mechanism_quality": float(mechanism_quality),
        "parameter_quality": float(parameter_quality),
        "observed_sfs_fit_quality": float(observed_fit),
        "heldout_sample_size_quality": float(heldout_prediction),
        "scientific_quality": float(scientific_quality),
        "correct_refusal": correct_refusal,
        "false_discovery": false_discovery,
        "supported_claim": supported_claim,
        "confidence_score": float(confidence_score),
        "parameter_log_errors": (
            (
                np.log(parameters / truth).tolist()
                if world["kind"] == "in_library"
                else np.log(parameters[:2]).tolist() + [None, None]
            ) if supported_claim else None
        ),
    }


def _normalized_mean(records, field):
    specs = (
        DEVELOPMENT_SPECS
        if records[0]["split"] == "development"
        else HELDOUT_SPECS
    )
    unsupported = sum(spec[1] not in {"in_library", "constant"} for spec in specs)
    baseline = unsupported / len(records)
    raw = float(np.mean([float(row[field]) for row in records]))
    return float(np.clip((raw - baseline) / max(1.0e-12, 1.0 - baseline), 0.0, 1.0))


def _split_metrics(records):
    specs = (
        DEVELOPMENT_SPECS
        if records[0]["split"] == "development"
        else HELDOUT_SPECS
    )
    supported_count = sum(spec[1] in {"in_library", "constant"} for spec in specs)
    unsupported_count = len(records) - supported_count
    claims = sum(bool(row["claimed_public_model"]) for row in records)
    supported_claims = sum(bool(row["supported_claim"]) for row in records)
    false_discoveries = sum(bool(row["false_discovery"]) for row in records)
    return {
        "mechanism_score": _normalized_mean(records, "mechanism_quality"),
        "observed_fit_score": _normalized_mean(records, "observed_sfs_fit_quality"),
        "prediction_score": _normalized_mean(records, "heldout_sample_size_quality"),
        "scientific_score": _normalized_mean(records, "scientific_quality"),
        "artifact_valid_rate": float(np.mean([row["valid"] for row in records])),
        "supported_claim_coverage": supported_claims / supported_count,
        "false_discovery_rate": false_discoveries / max(claims, 1),
        "unsupported_refusal_rate": sum(
            bool(row["correct_refusal"]) for row in records
        ) / unsupported_count,
        "mean_confidence_score": float(np.mean([
            row["confidence_score"] for row in records
        ])),
        "mean_budget_used": float(np.mean([
            row["budget_used"] for row in records
        ])),
        "mean_experiment_calls": float(np.mean([
            row["experiment_calls"] for row in records
        ])),
    }


def evaluate(infer_demography):
    development, heldout = [], []
    all_specs = [
        ("development", index, spec)
        for index, spec in enumerate(DEVELOPMENT_SPECS)
    ] + [
        ("heldout", index, spec)
        for index, spec in enumerate(HELDOUT_SPECS)
    ]
    for call_index, (split, index, spec) in enumerate(all_specs):
        if call_index and hasattr(infer_demography, "reset_session"):
            infer_demography.reset_session()
        record = _evaluate_world(infer_demography, spec, split, index)
        (development if split == "development" else heldout).append(record)
    dev, held = _split_metrics(development), _split_metrics(heldout)
    development_valid = all(row["valid"] for row in development)
    heldout_valid = all(row["valid"] for row in heldout)
    result = {
        "combined_score": dev["mechanism_score"] if development_valid else 0.0,
        "valid": 1.0 if development_valid else 0.0,
        "feasibility_rate": dev["artifact_valid_rate"],
        "raw_score": dev["mechanism_score"] if development_valid else 0.0,
        "development_mechanism_score": dev["mechanism_score"],
        "development_observed_sfs_fit_score": dev["observed_fit_score"],
        "development_prediction_score": dev["prediction_score"],
        "robustness_score": dev["prediction_score"],
        "development_validation_gap": (
            dev["observed_fit_score"] - dev["prediction_score"]
        ),
        "development_scientific_joint_score": dev["scientific_score"],
        "heldout_policy_score": (
            held["mechanism_score"] if heldout_valid else 0.0
        ),
        "heldout_mechanism_score": held["mechanism_score"],
        "heldout_observed_sfs_fit_score": held["observed_fit_score"],
        "heldout_prediction_score": held["prediction_score"],
        "heldout_scientific_joint_score": held["scientific_score"],
        "heldout_robustness_score": held["prediction_score"] if heldout_valid else 0.0,
        "development_supported_claim_coverage": dev["supported_claim_coverage"],
        "heldout_supported_claim_coverage": held["supported_claim_coverage"],
        "development_false_discovery_rate": dev["false_discovery_rate"],
        "heldout_false_discovery_rate": held["false_discovery_rate"],
        "development_unsupported_refusal_rate": dev["unsupported_refusal_rate"],
        "heldout_unsupported_refusal_rate": held["unsupported_refusal_rate"],
        "development_confidence_score": dev["mean_confidence_score"],
        "heldout_confidence_score": held["mean_confidence_score"],
        "development_mean_budget_used": dev["mean_budget_used"],
        "heldout_mean_budget_used": held["mean_budget_used"],
        "development_mean_experiment_calls": dev["mean_experiment_calls"],
        "heldout_mean_experiment_calls": held["mean_experiment_calls"],
        "heldout_feasibility_rate": held["artifact_valid_rate"],
        "per_world": development + heldout,
        "candidate_world_call_count": len(all_specs),
        "candidate_world_valid_rate": float(np.mean([
            row["valid"] for row in development + heldout
        ])),
    }
    if not development_valid:
        failure_kinds = sorted({row["failure_kind"] for row in development if not row["valid"]})
        result["error_message"] = "candidate invalid: " + ", ".join(failure_kinds)
    return result


def _reference_submission(world):
    if world["kind"] == "in_library":
        return {
            "parameters": world["parameters"].copy(),
            "confidence": 1.0,
            "abstain": False,
        }
    if world["kind"] == "constant":
        return {
            "parameters": np.asarray((1.0, 1.0, 0.07, 0.35)),
            "confidence": 1.0,
            "abstain": False,
        }
    return {
        "parameters": np.zeros(len(PARAMETER_NAMES)),
        "confidence": 1.0,
        "abstain": True,
    }
