# Private prediction residual diagnostics

`env/prediction_diagnostics.py` diagnoses the complete private matrices retained
by the runner. It neither changes the formal score nor updates a report, executes
a predictor, loads a World, or infers missing predictions from aggregate metrics.
Only `coupled_oscillators-0.2.0` and `ising_spin-0.2.0` are supported, through the
explicit rules in `prediction_semantics.py`.

```python
from env.prediction_diagnostics import diagnose_report, diagnose_panel

# private_report is an already-loaded runner report, kept in operator custody.
audit = diagnose_report(private_report)

panel = private_report["panels"]["interventions"][0]
candidate_audit = diagnose_panel(
    private_report["environment"], private_report["world_version"], panel)
baseline_audit = diagnose_panel(
    private_report["environment"], private_report["world_version"], panel,
    prediction_record=private_report["baseline_panels"]["interventions"][0])
```

The candidate panel supplies `spec`, `clean_truth`, and `prediction_values`.
Baseline records supply their own `prediction_values`; `diagnose_report` matches
them to candidate panels by panel kind and index. Duplicate or unmatched indices
and unmatched baseline panel kinds are invalid. Inputs are never mutated.

The semantic mask uses only the public spec, channels, axis and exact supported
world version. It never uses target values to decide which cells are excluded.
The diagnostic first uses the original retained-row rule: exclude the first row
only if its coordinate is zero and another row exists. It then removes cells
whose clean response is assigned directly by public initial-state or clamp
controls. Single-clamped-endpoint Ising pairs remain because their numeric values
still depend on an unknown free-spin mean.

For each remaining cell, `e = (prediction - clean_target) / public_channel_scale`.
The reported residual quantities are `sqrt(mean(e**2))` and
`100 * exp(-residual_RMSE / 0.1)`. These reproduce the original per-experiment
mapping on a different, explicitly reported set of cells; they are diagnostics,
not a replacement cohort score. Public scales are fixed at 1 for displacements,
2 for velocities, and 1 for spin observables.

| Panel status | Meaning | Residual metric |
|---|---|---|
| `ok` | Supported semantics, complete valid matrices, at least one residual cell | Computed |
| `unknown` | Missing matrices/artifacts, or unsupported environment/version | `null` |
| `invalid` | Explicit predictor failure, malformed arrays/metadata, or inconsistent clean target | `null` |
| `no_scientific_cells` | Valid matrices, but every legacy retained cell is publicly assigned | `null`, never 100 |

All-clamped experiments and oscillator experiments containing only t=0 therefore
have no residual score. Their recomputed original metric can still be 100: that
field records the old metric's behavior and is distinctly named
`original_metrics_recomputed`. A missing matrix remains unknown even when stored
RMSE says zero. Invalid numbers in removed or initial rows are rejected before
masking, just as the original prediction validation checks the whole matrix.

Matrices must have the complete certified channel order and matching axes.
Known clean target constants are checked within `1e-9 * channel_scale` for
numerical roundoff. A target contradicting a known clean constant is invalid;
this check cannot alter the already-fixed semantic mask. Noisy samples are outside
the input contract even where no known constant makes the noise detectable. No
alternative-instrument semantics are inferred.

Each valid panel reports original, direct-control and residual metrics, plus
residual counts and errors by channel. A channel with zero residual cells has a
null residual RMSE. `diagnose_report` preserves panel statuses and counts them;
it deliberately produces no aggregate replacement score. Missing, invalid and
empty panels must not silently disappear from an aggregate denominator.

A cell fraction is not a score impact. For a known-cell fraction `f`, squared
full RMSE is `f * direct_RMSE**2 + (1-f) * residual_RMSE**2`; the subsequent
exponential mapping is nonlinear. Removing exact control predictions can lower
the diagnostic score, while removing errors on those controls can raise it.
The direct-control error is therefore retained alongside the residual result.
Neither direction proves a mechanism, scientific independence of remaining
channels, or that an agent exploited a shortcut. The status name
`no_scientific_cells` means only that no cells remain after these narrow rules;
an `ok` status does not certify scientific depth.

Old core-c2/expansion-e1 reports without stored prediction matrices remain
unscorable by this diagnostic. Their targets or per-channel RMSE do not authorize
reconstructing, rerunning or inventing the missing predictor matrix.

```sh
python -m pytest env/tests/test_prediction_diagnostics.py env/tests/test_prediction_semantics.py -q
```

Tests use synthetic matrices only: full/partial clamps, single-endpoint spin
pairs, initial-row behavior, public normalization, both directions of score
change at the same cell fraction, missing/invalid inputs, baseline alignment,
immutable inputs and absence of simulator/API/I/O execution paths.
