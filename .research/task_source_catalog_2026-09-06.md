# Task source catalog — where every combinatorial-record task's numbers came from

This tracks, for the batch of "construct an explicit object, verify fast and exactly, score
against a real published record" tasks built in September 2026: which task came from which
source, what each source actually is, and which further sources were surveyed but not yet
mined into tasks. Written so the next round of task construction does not have to re-derive
this from scratch, and so a reviewer can see at a glance whether an anchor's source is a
primary paper, a maintained record table, or a secondary aggregator.

## Tasks built, by source

| Task | PR | Primary source(s) |
|---|---|---|
| `Superconductivity/SuperconductorTcRecord` | #7 (open) | 9 individual experimental physics papers (Drozdov et al., *Nature* 2019, LaH10; Somayazulu et al. 2019, H3S; Kong et al. 2021, YH6/YH9; etc.) |
| `Mathematics/NarrowAdmissibleTuple` | #7 (open) | D.H.J. Polymath, arXiv:1409.8361 (retrospective); Michael Nielsen's Polymath wiki |
| `Mathematics/ZarankiewiczMatrix` | #8 | arXiv:2605.01120 (AlphaEvolve LLM-search paper); arXiv:2608.26603 (Saurabh follow-up) |
| `Mathematics/DegreeDiameterGraph` | #8 | arXiv:2606.15860 (Mizuno, LLM-interaction paper); Wikipedia mirror of the combinatoricswiki.org degree/diameter table |
| `Mathematics/VanDerWaerdenColoring` | #8 | Wikipedia, "Van der Waerden number" (sourced further to Chvátal 1970, Stevens & Shantaram 1978, Rabung & Lotts) |
| `Mathematics/SchurPartition` | #8 | Golomb & Baumert 1965 (DOI 10.1145/321296.321300); Heule 2017 (arXiv:1711.08076); Fredricksen & Sweet 2000; Rowley 2021 (arXiv:2107.03560) |
| `Mathematics/ErdosMinimumOverlap` | #12 | Wikipedia, "Minimum overlap problem"; Haugland (arXiv:1609.08000); White (arXiv:2201.05704); AlphaEvolve (arXiv:2506.13131) |
| `Mathematics/HeilbronnTrianglePacking` | #12 | Erich's Packing Center; Comellas & Yebra 2002 (DOI 10.37236/1623); Dehbi & Zeng 2022 |
| `Mathematics/KissingNumber` (dims 5, 6 added) | #15 | Cohn's kissing-numbers page; Korkine & Zolotareff 1873 (D5/E6 root systems) |
| `Mathematics/TammesSphericalCode` | #15 | Cohn's Spherical Codes database; Musin & Tarasov 2015 (DOI 10.1080/10586458.2015.1022842); surfaced via HorizonMath |
| `Mathematics/DifferenceBasisRatio` | #15 | arXiv:2511.02864 (Georgiev, Gómez-Serrano, Tao, Wagner); surfaced via HorizonMath |
| `Mathematics/AutocorrelationSequence` | #15 | EinsteinArena benchmark certificates; Together AI (2026); Cloninger & Steinerberger (arXiv:1403.7988); Matolcsi & Vinuesa (arXiv:0907.1379); surfaced via HorizonMath |
| `Mathematics/MeritFactorSequence` | #15 | Borwein, Choi, Jedwab 2004 (DOI 10.1109/TIT.2004.838341); surfaced via HorizonMath |
| `Mathematics/BinaryCodeRecords` | #15 | codetables.de (Grassl); Kaikkonen 1989; surfaced via HorizonMath |
| `Mathematics/ConstantWeightCode` | #15 | Bluskov 2018 (*Electron. Notes Discrete Math.* 65); Brouwer's Andw table; surfaced via HorizonMath |
| `Mathematics/CoveringDesignBlocks` | #15 | La Jolla Covering Repository (direct re-fetch failed — DNS error — sourced via HorizonMath as a cross-referencing secondary aggregator; disclosed in the task's own `known_best.md`) |

## Source descriptions

### Aggregator benchmarks (themselves collections of already-researched problems)

- **HorizonMath** (`github.com/ewang26/HorizonMath`, Wang et al., Oxford/Harvard/Princeton, arXiv:2603.15617) — a 2026 AI-research benchmark of 136 problems across 8 math/physics domains, each with a `data/baselines.json` entry giving the current best-known value, its primary citation, and a `search_notes` field documenting how the benchmark's own authors verified it. Used here as a *pointer* to primary literature, not as the anchor's source of truth by itself — every number pulled from it was independently re-confirmed against the cited primary source (or disclosed when that re-confirmation failed, as with `CoveringDesignBlocks`).
- **AlphaEvolve papers** (arXiv:2506.13131, arXiv:2511.02864; Google DeepMind, with academic co-authors including Terence Tao on the second) — report genuine new records across ~67 hand-picked construction problems in analysis, combinatorics, geometry, and number theory, found by an LLM-driven evolutionary coding agent. The single most productive citation trail in this batch: five of the sixteen tasks above trace to these two papers.

### Maintained record-table websites (single-maintainer, updated on an ongoing basis)

- **Erich's Packing Center** (`erich-friedman.github.io/packing`) — Erich Friedman's long-running table of best-known configurations for dozens of packing-type problems (Heilbronn triangles, circle packing, etc.), each entry marked proven-optimal or best-known-only.
- **Cohn's kissing numbers / Spherical Codes** (`cohn.mit.edu/kissing-numbers`, `cohn.mit.edu/spherical-codes`) — Henry Cohn's maintained tables of best-known sphere-packing-adjacent configurations (kissing numbers, Tammes-problem point sets).
- **La Jolla Covering Repository** (`ljcr.dmgordon.org`) — Dan Gordon's maintained repository of covering-design records, plus (per this round's survey) sibling repositories for difference sets and circulant weighing matrices not yet mined.
- **codetables.de** (Markus Grassl) — maintained best-known bounds on linear-code minimum distances, the modern successor to Brouwer's older linear-code tables.
- **Brouwer's tables** (`aeb.win.tue.nl`) — Andries Brouwer's maintained tables for constant-weight codes, general binary codes, and (per this round's survey, not yet mined) strongly regular graph parameters and distance-regular graph data.

### Community-maintained reference pages (sourced further to primary literature each time)

- **Wikipedia record pages** — "Minimum overlap problem," "Van der Waerden number," "Table of the largest known graphs of a given diameter and maximal degree." Used only after independently re-fetching and cross-checking the specific cited numbers against primary sources or a second independent search.

### Individual primary papers (one-off numeric anchors, not living tables)

Polymath8b (arXiv:1409.8361); Golomb & Baumert 1965; Heule 2017 (arXiv:1711.08076);
Fredricksen & Sweet 2000; Rowley 2021 (arXiv:2107.03560); Haugland (arXiv:1609.08000);
White (arXiv:2201.05704); Comellas & Yebra 2002; Dehbi & Zeng 2022; Korkine & Zolotareff
1873; Musin & Tarasov 2015; Kaikkonen 1989; Bluskov 2018; Borwein, Choi & Jedwab 2004;
Cloninger & Steinerberger (arXiv:1403.7988); Matolcsi & Vinuesa (arXiv:0907.1379).

### Newer competition/certificate sites (2026-era, narrower scope than the above)

- **EinsteinArena** (`einsteinarena.com`) — hosts specific "beat this certificate" problems (e.g. the autocorrelation inequalities) with a frozen numeric record and, in some cases, a published solution file.
- **Together AI's EinsteinArena-new-SOTA GitHub repo** — a specific 2026 submission superseding a 2010 published bound on the signed autocorrelation constant.

## Surveyed this round but not yet mined into tasks

Found while answering "what other professionally-curated open-problem sources exist"
(2026-09-06 survey). Recorded here so a future session doesn't have to re-search for them.

| Source | What it is | Status | Fit for this task style |
|---|---|---|---|
| **erdosproblems.com** (Thomas Bloom) | ~1,220 cataloged Erdős problems, 48% marked solved, per-problem pages with live status and often a running best-known-bound narrative | Actively maintained, current to 2025-2026; already documents AI-found constructions improving records on some problems | High — but heterogeneous; most problems are asymptotic/existence-only, a minority reduce to an explicit finite object. Mine problem-by-problem, not as one task. See the 5 specific candidates below. |
| **Radziszowski's "Small Ramsey Numbers" (DS1)**, *Electron. J. Combin.* | Dynamic survey of Ramsey-type numbers: diagonal, off-diagonal, multicolor, cycles, books, wheels, hypergraphs | Actively maintained — most recent revision April 2026 | High — off-diagonal and multicolor entries don't overlap the existing `Mathematics/RamseyLowerBound` task's diagonal cases. See the 4 specific candidates below. |
| **Brouwer's strongly-regular-graph table** (`aeb.win.tue.nl/graphs/srg/srgtab.html`) | Feasible SRG(v,k,λ,μ) parameter sets up to v≤1300, each annotated existence/non-existence/open | Author has 2024-2025 publications on related graphs; site appears tended | High — an open parameter cell is settled by exhibiting an explicit adjacency matrix; the 2015 resolution of SRG(460,153,32,60) is a real precedent for this being a genuine research event, not busywork. |
| **La Jolla Difference Set / Circulant Weighing Matrix repositories** | Sibling repositories to the Covering Repository, same maintainer | Active, 2025-2026 updates seen on Zenodo mirrors | Medium-high — same verification shape as `CoveringDesignBlocks`, different object types. |
| **Costas array trackers** (Rickard group site; OEIS A008404 / A001441) | Exhaustive counts through order ~30, heuristic extensions further | OEIS entries updated July 2026 | Medium — an explicit Costas permutation matrix is instantly verifiable, but the open question (existence at orders 32-33) is closer to existence-only than a "bigger is better" record. |
| **Neil Sloane's sphere-packing pages** (`neilsloane.com/packings`) | Putatively-optimal point configurations on spheres, dimensions 3-5 | Appears maintained | Medium — adjacent to but distinct from kissing numbers/Tammes; would need care to avoid overlap. |
| **MOLS table N(n)** (Colbourn-Dinitz *Handbook of Combinatorial Designs*) | Best-known count of mutually orthogonal Latin squares of order n | Book-based, revised per edition, no single live webpage found | Medium — a set of n MOLS is trivially fast to verify; sourcing an anchor means citing the current handbook edition, not a re-fetchable URL. |
| **AIM Problem Lists** (`aimpl.org`) | Editorial-board-curated wiki lists tied to AIM workshops (additive combinatorics, Ramsey theory, hereditary discrepancy, etc.) | Uncertain — site's TLS cert had issues on fetch; no visible per-list update timestamps | Low-medium — real curation, but reachability and freshness need to be re-checked before relying on it. |
| **Moorhouse's "Projective Planes of Small Order"** | Explicit incidence data for known small projective planes | Stale — last revised Nov. 2017 | Low-medium — the underlying open problems (order-12 existence, order-49 enumeration) are real, but the page itself isn't actively tended. |
| **TOPP** (The Open Problems Project, Demaine/Mitchell/O'Rourke) | Long-running computational-geometry open-problem list | Alive as infrastructure (GitHub Pages), unclear how actively curated | Low — mostly existence/complexity questions (folding, visibility, TSP variants), not numeric-record tables. |
| **Open Problem Garden** | Wiki covering algebra/combinatorics/graph theory/geometry/number theory open problems | **Flagged inactive** — recent activity feed dominated by spam edits | Do not use as a live source; historical index at best. |

### Specific candidate problems already extracted from the two strongest new sources

From **erdosproblems.com**:

1. **#2, covering systems** — maximize the minimum modulus of a finite covering system; best known 42 (Owens 2014). Verification is more involved (checking coverage requires reasoning about the LCM of moduli, not a flat brute-force range) — flagged as harder to verify fast; needs a smarter check before building.
2. **#30, Sidon set density** — classic Sidon set in `{1,...,N}`; Singer's 1938 construction gives `(1-o(1))N^{1/2}`, tightest matching upper bound is 2025 (Carter, Hunter & O'Bryant). Fast `O(n^2 log n)` verification.
3. **#156, minimal maximal Sidon sets** — smallest *non-extendable* Sidon set; Ruzsa's construction gives `(N log N)^{1/3}`, open whether the log factor is removable.
4. **#241, Bose-Chowla B_3 sets** — triple-sum-distinct analogue of Sidon sets; Bose-Chowla 1962 construction vs. Green's 2001 upper bound. Fast `O(n^3)` verification.
5. **#500, Turán's (3,4)-hypergraph problem** — one of the most famous open problems in extremal set theory; Turán's tripartite construction (density 5/9) vs. Razborov's 2010 flag-algebra upper bound (~0.5612). Verification `O(n^4)`.

From **Radziszowski's DS1**:

1. **R(4,6)**: 36 ≤ R ≤ 40, lower-bound witness an explicit 35-vertex 2-coloring (Exoo 2019).
2. **R(5,6)**: 59 ≤ R ≤ 87, witness a 58-vertex coloring (Exoo, Oct. 2023, arXiv:2310.17099) — large gap, very recent.
3. **R(3,10)**: 40 ≤ R ≤ 42, witness a 39-vertex triangle-free graph with independence number ≤ 9.
4. **R(3,3,3,3)** (4-color diagonal triangle Ramsey number): 51 ≤ R ≤ 62, witness Chung's 1973 50-vertex 4-coloring (proven optimal only within the restricted "group-partition" construction class, not overall).

None of these nine has been built into a task yet. Next step, if pursued: verify each
citation independently (matching the rigor applied to every task above), design the exact
candidate function signature and baseline, and measure real baseline/reference numbers by
running code — the same process used for every task in the table above.
