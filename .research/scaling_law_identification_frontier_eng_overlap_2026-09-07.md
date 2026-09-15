# ScalingLawIdentification — Frontier-Eng overlap review

Reviewed 2026-09-07 against the pinned Frontier-Eng paper task list and the
available repository catalog.

- Classification: no direct overlap.
- Nearest entries: MallocLab, MLA, FlashAttention, and TriMul.
- Distinction: this task spends a profiling budget on a black-box size ladder,
  identifies an asymptotic class and scale, and refuses branch-dependent or
  high-jitter worlds. The nearby entries optimize concrete kernels or allocators;
  they do not infer a law from noisy timings or score calibrated refusal.
- Residual risk: the six target classes are textbook. The discriminating content
  lies in ladder selection, sealed extrapolation, and the two refusal axes. A
  frozen frontier-model draw and independent algorithms review remain required.
