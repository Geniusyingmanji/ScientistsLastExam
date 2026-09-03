# Related-work claims checked against primary sources (2026-09-03)

Every budget and control-arm claim in the positioning document was re-read from the arXiv
abstract or full text (curl), or the project README where the paper lacks the number. A previous
WebFetch summary had invented three properties of MADE that appear nowhere in its paper; this
pass quotes only text actually present in the source.

## Verdicts

| benchmark | source | budget (verbatim) | open-loop / placebo arm | verdict |
|---|---|---|---|---|
| Frontier-Eng | arXiv 2604.12290 | "a fixed openevolve budget of 100 iterations" | none; depth-vs-width split n×d≤256, all arms with feedback | PARTIAL: 100 is the openevolve budget of the main experiment, not a protocol constant; abstract says eight models, body nine |
| EdgeBench | arXiv 2607.05155 | "at least 12 hours of continuous agent operation" | **yes**: "n=6 independent attempts of τ=2 hours, with all state discarded between attempts and only the best result kept" | VERIFIED (134 tasks, only 51 public; log-sigmoid R²=0.998) |
| MLS-Bench | arXiv 2605.08678 | action / test / capacity budgets, no step count | none | PARTIAL: transfer is across "benchmarks, environments, or base-model scales" plus a multi-seed policy |
| AlgoTune | arXiv 2507.15887 | "a fixed budget of $1 for each task" | none | CONTRADICTED on count: **154** tasks, not 155 (abstract, §5, README) |
| RE-Bench | arXiv 2411.15114 | humans 8 h; agents at 2 / 8 / 32 h | best-of-k of shorter attempts (with feedback) | VERIFIED; note 1.0 = the *task author's* reference, sub-start scores floored to 0 |
| ALE-Bench | arXiv 2506.09050 | "limited to 4 hours using C++20" | none | PARTIAL: paper says "score-based", not "continuous" |
| MLE-bench | arXiv 2410.07095 | "a maximum of 24 hours to produce a submission" | pass@k scaling only | VERIFIED (75 competitions, medal rate) |
| ScienceAgentBench | arXiv 2410.05080 | self-debug stops on two identical consecutive programs; "three independent runs … select the best run" | none | CONTRADICTED: the 3 is best-of-3 runs, not 3 self-debug rounds |
| MLR-Bench | arXiv 2505.19955 | n/a | none | CONTRADICTED on the judge clause: MLR-Judge "detected even more hallucination cases" and scored them 3.73/10; the 80% is 8 of 10 tasks on a Claude Code subset |
| CausaLab | arXiv 2605.26029 | "the observation budget is 2 and the intervention budget is 4(k−1)" | **partly**: matched functional-form / hidden-perturbation / target-edge controls, and offline "Golden" intervention chains | CONTRADICTED on "10 deployments"; 92% accuracy vs 0.471 all-edge F₁ VERIFIED (purely observational 6-node setting) |
| CausalGame | arXiv 2607.04293 (ICML 2026 oral) | "a budget of 200 drones and up to 10 deployment calls" | prompting vs agentic modes | VERIFIED: this is where "10 deployments" comes from |
| MADE | arXiv 2601.20996; github.com/diffractivelabs/MADE | "5 independent discovery episodes with an oracle query budget of 50" | none (random / Chemeleon / non-agentic baselines) | VERIFIED; "best-of-N", "memory-less", "40-60% faster" appear nowhere - the earlier summary was hallucinated |
| PMO | arXiv 2206.12411 | "We limit the number of oracle calls to 10000" | none | CONTRADICTED: 1,000 is the later "PMO-1K" convention (LICO, arXiv 2406.18851), not PMO |
| AlphaEvolve | arXiv 2506.13131 | no per-problem count; "thousands of LLM samples suffice"; "~100 compute-hours to evaluate any new solution" | none | PARTIAL: 10²–10³ evaluations per problem NOT VERIFIED; 49→48 and MAP-elites + islands VERIFIED |
| lab-in-loop | arXiv 2603.26177 | 800 replicated experiments | **yes, explicitly**: "a random feedback control in which hit/miss labels are permuted. Under this control, the performance gain disappears" | VERIFIED (+53.4%, p=0.003) |
| Gurkan et al. | arXiv 2606.05408 (GECCO '26 workshop) | n/a | classical GP subtree mutation as control | VERIFIED: "in 87% of chains, over 93% of mutations revisit a previously seen structural form" |
| LEAPBench | arXiv 2605.15341 | "capping each run at 30 iterations"; 55 tasks | GP-UCB reference + semantics-stripped prompt arm | PARTIAL: 53% is "24 of 45 biology tasks", not all 55; the benchmark is named LEAPBench |
| DiscoveryWorld | arXiv 2406.06769 (NeurIPS 2024 D&B spotlight) | 100 steps (Easy) / 1000 steps (Normal, Challenge) | none | PARTIAL: three metrics (completion, task-relevant actions, discovered knowledge), not completion alone |
| SFE | arXiv 2506.10521 | single pass ("each experiment is conducted once") | none | PARTIAL: 830 items and GPT-4o judge VERIFIED; NeurIPS 2025 *poster* confirmed, D&B track not |
| SGI-Bench | arXiv 2512.16969 | zero-shot, temperature 0; dry experiments use PassAll@k | none | PARTIAL: paper says "over 1,000"; 1,263 only by summing per-task counts |
| ResearchClawBench | arXiv 2606.07591 | context compaction at 128k tokens; no per-task budget | none | PARTIAL: 40 tasks, GPT-5.1 judge, 50-point parity and the limitation sentence VERIFIED; "strictly one attempt" never stated (inferable from 280 runs = 7 × 40) |

## What this changes in the positioning

- "No benchmark uses an open-loop control" is too strong. EdgeBench runs a memoryless best-of-N
  arm (6 × 2 h) as an ablation, lab-in-loop runs a permuted-feedback control, and CausaLab injects
  offline "Golden" intervention chains. What no benchmark does is use **open-loop saturation as an
  admission criterion** for whether a task can measure iteration at all. The claim is now worded
  that way.
- MLR-Bench does not support "LLM judges reward fabricated results". It supports the narrower
  point that coding agents fabricate at high rates on open-ended research tasks (8 of 10 in a
  Claude Code subset) - and its own judge caught them. Use it for the fabrication rate, not the
  judge failure.
- 100 iterations is Frontier-Eng's setting for one experiment, not a field convention; budgets
  across the field run from 3 independent runs to 10,000 oracle calls to 24 hours.

## Corrections applied to the documents

AlgoTune 155 → 154; ScienceAgentBench "3 self-debug attempts" → "best of 3 independent runs";
MLR-Bench judge clause removed; CausaLab budget → 2 observations + 4(k−1) interventions, with
"10 deployments" attributed to CausalGame; PMO 1,000 → 10,000 (PMO-1K is LICO's convention);
AlphaEvolve evaluation count dropped as unverified; LEAP → LEAPBench with the 45-task denominator;
SGI-Bench 1,263 → "over 1,000"; SFE venue → NeurIPS 2025 poster; DiscoveryWorld → three metrics;
open-loop differentiation → admission criterion, not the mere presence of a control arm.
