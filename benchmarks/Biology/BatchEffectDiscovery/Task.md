# BatchEffectDiscovery — differential expression under batch confounding

## Question and nearest tasks

Use a limited follow-up sequencing budget to decide which genes truly respond to condition while
accounting for batch. EvidenceSynthesis/ProspectiveMetaAnalysis audits studies and participant
lineage; this task analyzes a single high-dimensional count experiment. It returns gene-level
evidence, not the network requested by SystemsBiology/GeneNetworkIntervention.

Worlds include supported effects, batch-only nulls, and designs where recruitment
permits only the two already-confounded cells. All worlds start with two replicates in each
of (batch=0, condition=0) and (batch=1, condition=1); supported and null worlds have the same
available follow-up cells. Initial sample count and layout do not reveal effect presence. In the last case no legal follow-up can identify a
condition coefficient and the correct action is refusal.

## Interface

Implement analyze_expression(problem, measure). measure(batch, condition) buys one independent
sample and returns the same row schema as initial_samples.

Problem keys are gene_ids; initial_samples, whose row keys are batch, condition, library_size and
counts; available_cells; sample_budget; effect_scale; and valid_reason_codes.

Return exactly:

    {
      "discoveries": [{"gene": "g03", "effect": 0.9}],
      "abstain": False,
      "reason_code": "supported"
    }

Legal reason codes are supported, not_identifiable, and no_effect. An abstention must contain no
discoveries. The evaluator separately reports supported-world gene recovery, false-discovery rate
and its numerator/denominator, correct identifiability refusal, and discovery coverage. Supported
claims receive partial credit for effect sign and magnitude as well as gene identity; null and
confounded decisions require the matching reason code. Blanket abstention, blanket no-effect denial, layout-only refusal/denial, and the shipped
batch-blind baseline all normalize to zero. The development utility is normalized above
`max(baseline_raw, fraction_of_null_or_confounded_worlds)`; this zeroes every policy that
never attempts a discovery. Discovery/refusal/FDR axes are still reported separately. Held-out worlds are sealed.
Counts are deterministic negative-binomial procedural measurements, not patient data.
sle.contract_lint is importable and free to call for submission-shape checks.
