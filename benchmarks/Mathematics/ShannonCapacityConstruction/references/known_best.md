# Verified historical construction and scope

## 1. Reference and provenance

Retrieved on 2026-09-06 from the primary source:
[Sven Polak and Alexander Schrijver, *New lower bound on the Shannon capacity of
C7 from circular graphs*, arXiv:1808.07438v2, 26 November 2018](https://arxiv.org/html/1808.07438v2).
The section headed **Appendix: explicit code** lists all 367 five-digit words.
The fixture preserves that order and converts each character to an integer,
including leading zeros. It is construction data, not a sampled estimate.

The filename `known_best.md` follows repository convention. Here **367 is a
verified historical finite reference**, not a blanket claim of current best
Shannon capacity or an assertion that no larger fifth-power set exists.

## 2. Baseline and reference replay

[Task.md](../Task.md) specifies the product-code baseline and its normalization.
The reference replay must reproduce the literal fixture, including when its
Python file is copied into a directory without task assets.

## 3. Ablations and capability ladder

No formal capability-ablation ladder has been measured for this resource.
Independent graph checks validate the artifact; they do not measure which
search capabilities are necessary to improve it.

## 4. Shortcut probes

The public Appendix makes reference retrieval and literal replay available.
The 2018 source discusses the construction method and unsuccessful local searches;
those searches do not prove its optimality. This resource does not report a
systematic shortcut ceiling or infer frontier difficulty from those searches.

## 5. Frontier draws and calibration

Exploratory testing has occurred and fresh model-produced objects are being
checked in a separate report. No formal SLE calibration run is recorded;
full-program calibration and trusted candidate execution are blocked on H200
sandbox mount permissions. Long-horizon headroom remains untested.

## 6. Construction audit

The complete 367-word list returned from the source was parsed and compared to
the fixture: all rows agreed. SHA-256 of the UTF-8 compact JSON row list
(`json.dumps(codewords, separators=(",", ":"))`) is:

```text
3f24988518568a090a7023079439281738c245dfe73171d7981cf589b02d77f3
```

## 7. Robustness and scope

The production verifier checks all 67,161 distinct pairs with circular-distance
arithmetic. The independent test instead enumerates all 242 nonzero offsets in
`{-1,0,1}^5` around each word and checks membership in the set: 88,814 neighbor
probes, no conflicts.

Subsequent primary context, checked on 2026-09-06:

- [Itty, Rosin, Carstensen and Reichman, arXiv:2607.21517v2,
  Section 3.1](https://arxiv.org/html/2607.21517v2): reuses the 367-word set as a
  base for a 134,753-word construction in the tenth power.
- [Gao, arXiv:2607.27869v1, abstract and Sections 4–5](https://arxiv.org/html/2607.27869v1):
  uses a 367-word base in a recursive construction reaching the 200th power.
- [The Itty et al. data repository](https://github.com/nathanielitty/lower-bounds-for-shannon-capacity)
  is linked context, not the source of this package's fixture.

Those higher-dimensional artifacts and capacity improvements are not evaluated
here. No current-world-record, task-difficulty, or discovery certification is
inferred from the finite score. Improving this fixture would first establish a
larger exactly verified fifth-power independent set; literature comparison is a
separate requirement before claiming novelty.
