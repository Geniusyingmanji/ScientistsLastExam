# KissingNumber — known-best lower bounds

`sota_ref` is the best published construction size (a lower bound on the kissing number),
not an upper bound. Dimension 11 is omitted because recent AI-search claims there are contested.

| dim d | baseline 2d | lower bound | source |
|---|---|---|---|
| 5 | 10 | 40 | Cohn table; D5 root system (Korkine & Zolotareff, 1873): permutations of (+/-1,+/-1,0,0,0) |
| 6 | 12 | 72 | Cohn table; E6 root system (Korkine & Zolotareff, 1873) |
| 9 | 18 | 306 | Cohn table (https://cohn.mit.edu/kissing-numbers/) |
| 10 | 20 | 510 | Cohn table |
| 12 | 24 | 841 | Cohn table; Takhanov, Yun, Assylbekov arXiv:2606.18984 (was 840 from 1971) |

Dimensions 5 and 6 added 2026-09-06, independently re-confirmed via web search against Cohn's
survey and the D5/E6 root-system constructions; both lower bounds are long-standing (1873),
not AI-search claims, unlike the dimension-11 situation below.

A configuration larger than the listed lower bound scores above 1.0. Primitive integer witnesses
are checked exactly. A non-integral floating witness is accepted at the evaluator's fixed angular
tolerance and remains a benchmark candidate until an exact or interval certificate establishes
the 60° inequalities. Update this table and `verification/evaluator.py:SIZES` if Cohn's table moves.

The geometric certificate is pairwise angle ≥ 60° on the unit sphere. Integer vectors are
reduced by gcd (so x and 2x count once; antipodes stay distinct) and checked exactly. The
AlphaEvolve sufficient lemma (max ‖x‖ < min_{x≠y} ‖x−y‖) is stricter than 60° and is not
required.

Sources:

- https://cohn.mit.edu/kissing-numbers/
- arxiv:2506.13131
- arxiv:2606.18984
