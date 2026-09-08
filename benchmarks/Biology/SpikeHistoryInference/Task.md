# SpikeHistoryInference

## Scientific problem

A neuron's spike train reflects both external drive and its own recent firing. In the supported
family, each 5 ms bin follows a conditional Bernoulli point-process model whose log odds combine a
stimulus term with a negative exponential post-spike history kernel. Infer the stimulus gain and
refractory kernel from repeated trials, then predict conditional firing probabilities in supplied
stimulus/history contexts.

Low likelihood under the supported model is not by itself a scientific diagnosis. Refuse and name
the failure when the records resolve a positive burst component, a mixture of trial-level latent
gains, or a refractory effect that changes with the current stimulus.

## Candidate interface

Implement:

```python
def infer_spike_history(problem):
    """Return point-process parameters, predictions, and a model diagnosis."""
```

Every candidate-visible key in `problem` is listed here:

- `schema_version`: contract version;
- `bin_width_ms`: duration represented by one spike/stimulus bin;
- `history_horizon_ms`: maximum recent-spike interval used by the supported model;
- `supported_model`: the conditional log-odds equation;
- `diagnosis_values`: allowed diagnosis strings;
- `parameter_bounds`: inclusive bounds for `intercept`, `stimulus_gain`,
  `refractory_amplitude`, and `refractory_tau_ms`;
- `prediction_contexts`: ordered mappings with `stimulus` and `recent_spike_lags_ms`;
- `abstain_when`: unsupported mechanisms that require refusal;
- `trials`: repeated records, each containing exactly `trial_id`, `stimulus`, and `spikes`.

Within each trial, `stimulus` is an ordered finite scalar sequence and `spikes` is an equally long
binary sequence. For a spike at lag `l`, the supported history contribution is
`-refractory_amplitude * exp(-l/refractory_tau_ms)`.

## Return value

Return exactly these keys:

- `intercept`, `stimulus_gain`, `refractory_amplitude`, `refractory_tau_ms`: finite scalars inside
  their public bounds;
- `prediction_probabilities`: one finite probability in `[0, 1]` for each supplied context, in the
  original order;
- `diagnosis`: `supported`, `burst_history`, `trial_gain_mixture`,
  `stimulus_history_interaction`, or `undetermined`;
- `confidence`: a finite number in `[0, 1]`;
- `abstain`: a boolean;
- `evidence_trial_ids`: at least four unique IDs from the supplied trials.

For supported data, publish the fitted parameters and set `abstain=False`. For a resolved
unsupported mechanism, name it and set `abstain=True`. Do not assume trial order, hidden random
seeds, fixed parameters, or a fixed diagnosis.

## Scoring

The split-prefixed `mechanism_score` is the fraction of all worlds with the correct family
diagnosis: a supported claim on a supported world, or the correct named refusal on an unsupported
world. Each split publishes `mechanism_correct_count` and `mechanism_total_count`.
Undetermined abstention and invalid submissions count as incorrect. This axis is separate from
continuous parameter recovery, prediction, and the composite science score.

On supported worlds, the science score combines recovery of all four parameters and the supported
diagnosis; sealed conditional-probability prediction and confidence calibration are scored
separately. Unsupported worlds reward only the correct named refusal. The clipped development
`combined_score` is normalized so the valid blanket-abstention baseline is exactly zero.
Parameter recovery, prediction, correct refusal, false discovery, supported discovery coverage,
attempted discovery, validity, and held-out transfer retain separate fields with denominators.

The truth-blind reference scores `0.903` development / `0.898` held out. Fixing the refractory
time constant at 20 ms scores `0.876 / 0.879`; retaining parameter fits but never refusing scores
`0.396 / 0.300`; using only the mean firing rate scores `0.234 / 0.179`. A 192-strategy sweep over
low-dimensional trial-rate, delayed-spike, and stimulus-conditioned frequency thresholds reaches
only `0.694 / 0.685` and retains a one-third false-discovery rate. Thus point-process fitting and
structured model checks each change the measured capability.

## Relationship to nearby tasks

`SystemsBiology/GeneNetworkIntervention` actively perturbs a multi-gene nonlinear ODE and designs a
phenotype intervention; this task instead estimates a single-neuron conditional point process from
repeated spike trains and attributes history-model failure. `QuantumDynamics/HamiltonianLearning`
recovers coherent spin-chain parameters from magnetization trajectories, without stochastic event
history, refractory kernels, latent trial gains, or point-process likelihoods.

## Rules and references

Only edit `solution.py`. Use deterministic CPU-only Python, NumPy, SciPy, and the standard library.
Do not read `verification/` or `frontier_eval/`, access the network, or create processes.
`sle.contract_lint` may be used for free shape checks.

The conditional point-process formulation follows Truccolo et al., *Journal of Neurophysiology*
(2005), DOI `10.1152/jn.00697.2004`, and Paninski, *Network* (2004), DOI
`10.1088/0954-898X/15/4/009`. Flexible spike-history filters and stimulus encoding are grounded in
Pillow et al., *Nature* (2008), DOI `10.1038/nature07140`.
