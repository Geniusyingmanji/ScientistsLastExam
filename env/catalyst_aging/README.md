# Catalyst aging laboratory

The agent plans complete serial histories involving four coupons, reaction
conditions, blanks and calibration standards. It measures the instrument signal
and can ask whether changes follow a coupon's past use, the instrument's history,
or both. Only the apparatus is disclosed; no family labels or kinetic equations
are given in `World.describe()`.

Every call resets the whole laboratory. Histories are explicit inside one
`events` array; this package does **not** provide persistent sessions,
concurrency, request idempotency or cross-call coupon versions. It migrates the
physical questions from `CatalystDeactivationLab` while deliberately changing
its interaction contract to a reproducible full-history experiment. The old
answer evaluator, refusal labels and parameter-recovery score are not reused.

- `events`:1–24serial events of kind blank, standard or reaction.
- Reaction: coupon A–D, temperature440–560K, feed0.1–1.2 normalized units,
  duration2–15min. Maximum6reaction events/coupon.
- `event_indices`: increasing1-based subset to observe. All scheduled events
  execute and cost1each, even unobserved preparation.
- `measured_signal`: one observed scalar per selected event; no output is a
  directly assigned value. Standard supplies1.5true product units, but observed
  signal is affected by the instrument.
- Independent additive Gaussianσ.003, no clipping; scale1.5. Replay keys bind
  each event's prefix and preserve shared outputs when observation subsets change.

Sources/manifest/scientific notes are trusted operator material. Shared registry,
semantics, evidence-packet and runner integration are separate acceptance steps.
Run `pytest env/catalyst_aging/tests` for focused checks. See the bounded
[development plan](DEVELOPMENT_PLAN.md) and [scientific notes](SCIENTIFIC_NOTES.md).

`matched_readout.py` is an unregistered diagnostic, not a new model-scored task.
It makes four independent reset experiments with identical preparation prefixes
and reads used coupon, fresh coupon, blank and standard at the same event index.
Under this simulator's shared affine instrument response, the standard-normalized
used-minus-fresh contrast cancels gain and offset. This relies on instrument state
being independent of terminal event type. Noisy ratio uncertainty, more general
instrument drift and competing activity models require separate validation;
passing the clean diagnostic is not high-difficulty or unique-mechanism evidence.
