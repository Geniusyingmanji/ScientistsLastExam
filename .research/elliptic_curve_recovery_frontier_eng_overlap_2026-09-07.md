# EllipticCurveRecovery — Frontier-Eng overlap review

Reviewed 2026-09-07 against the pinned Frontier-Eng paper task list and the
available repository catalog.

- Classification: no direct overlap.
- Nearest entries: AES-128 CTR, SHA-256, and SHA3-256.
- Distinction: this task buys exact finite-field point counts, enumerates the
  compatible coefficient residues, combines them by CRT inside a bounded integer
  window, and must refuse singular or genus-two worlds. The nearby entries measure
  cryptographic implementation throughput; they do not expose an
  arithmetic-geometry inverse problem or a query budget.
- Residual risk: the construction is mathematically recognizable once the curve
  family is named. Independent mathematics review and a frozen frontier-model draw
  remain required before certification.
