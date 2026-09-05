# TransitTimingAttribution reference record

This candidate uses a deterministic reduced-order transit-timing laboratory. The reference policy
uses widely separated follow-up transit numbers, removes a linear clock component, compares a small
period grid, and abstains when the residual signal is too small or unsupported.

Server replay (2026-09-05, provisional candidate calibration):

- baseline: `combined_score = 0.0000`, valid `1.0`; one legal follow-up is taken and the candidate
  abstains everywhere;
- truth-blind reference: development supported-world mean `0.9034`, held-out supported-world mean
  `0.8992`; development false-discovery rate `0.0` with correct unsupported refusal `1.0`;
- held-out validation has one residual unsupported-world false discovery (`false-discovery rate
  0.1667` over six claims), so the reference is not treated as a ceiling or certification evidence;
- reference uses eight legal follow-up timings, a least-squares/BIC comparison of clock,
  planet and activity models, and a forecast at a future unmeasured transit.

DeepSeek Flash calibration after enabling the chat-wire `thinking: disabled` compatibility path
(temperature `0.0`, `greedy_rewrite`, budget 3, 2026-09-05):

- seed 11: three valid proposals, best development `0.4777`, held-out `0.2170`, development /
  validation false-discovery rates `0.5` / `0.6667`, coverage `0.8` / `0.4`;
- seed 12: one valid proposal out of three, best development `0.5719`, held-out `0.5201`, development
  and validation false-discovery rates `0.4`, coverage `0.8` / `0.8`;
- earlier runs without the chat compatibility fix consumed the output budget entirely in hidden
  reasoning and returned zero visible response bytes; those protocol-incomplete runs are not model
  performance evidence.

Values remain provisional until server-held families, independent photodynamical replication and
external astronomy review. The exact-descriptor ceiling is evaluator-recomputed, not a claim of
photodynamical optimality. Scientific grounding includes Agol et al. (DOI
`10.1111/j.1365-2966.2005.08922.x`) and Holman and Murray (DOI `10.1126/science.1107822`).
