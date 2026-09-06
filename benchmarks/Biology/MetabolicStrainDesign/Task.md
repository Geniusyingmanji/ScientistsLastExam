# MetabolicStrainDesign — robust growth-coupled strain design

## Question and nearest tasks

Choose a small set of reaction knockouts that forces product formation while preserving growth.
Unlike SystemsBiology/GeneNetworkIntervention, the network is supplied and no causal structure is
inferred. Unlike Chemistry/LennardJonesCluster, feasibility is a flux-balance polytope and the
scientific trap is alternate growth-optimal fluxes with zero product.

## Interface

Implement design_strain(problem) and return exactly:

    {"reaction_knockouts": ["R01", "R04", "R08"]}

Problem keys are reaction_ids, stoichiometric_matrix, lower_bounds, upper_bounds,
biomass_reaction, product_reaction, allowed_reaction_knockouts, maximum_knockouts,
minimum_growth, and growth_optimality_tolerance.

Every returned ID must be allowed and distinct. The evaluator first maximizes biomass, then
minimizes product over the entire near-optimal-growth face. This prevents an arbitrary favorable
FBA solution from earning credit. Reaction identifiers and pathway-column order vary by instance,
so a fixed knockout list does not transfer. Score is robust product times growth, normalized from
the unchanged strain (0) to a truth-blind small-cardinality search witness (1), clipped to [0,1].
Held-out metabolic coefficients are reported separately.

This is a reduced constraint-based metabolic model, not a wet-lab strain or experimental claim.


## Network and objective contract

Matrix rows describe carbon, reducing equivalents, energy, and two intracellular intermediates.
All fluxes are nonnegative. The model includes an energy-supply route, two multi-step competing
routes, and alternative intermediate-to-energy conversions. Growth consumes carbon, reducing
equivalents and energy; product competes for carbon and reducing equivalents. Eliminating every
redox-consuming allowed reaction can sacrifice useful energy production, while eliminating only
terminal drains can leave alternative routes. All coefficients and bounds needed to evaluate a
design are in the public problem; hidden reference implementation details are not required.

Solve `S @ v = 0` with the public bounds and set knocked-out bounds to zero. Let `mu_star` be the
maximum biomass flux. If infeasible or `mu_star < minimum_growth`, utility is zero. Otherwise
minimize product flux over the same constraints plus
`biomass_flux >= mu_star - growth_optimality_tolerance`. Utility is
`max(0, worst_product_flux) * mu_star / (1 + 0.08 * number_of_knockouts)`.
The reference maximizes this utility over all subsets of allowed reactions within budget.
This small procedural network still permits exhaustive search; no frontier-difficulty claim is
made. The revision adds a real energy/product tradeoff, not evidence of expert-level difficulty.

## PR scope coordination

The historical `MetabolicEngineering/MetabolicStrainDesign` in PR #9 instead
combines enzyme knockouts and overexpression under sealed capacity draws. This
task accepts reaction knockouts only and minimizes product over the entire
near-optimal-growth face, so favorable alternate flux optima cannot earn credit.
The #9 author has deferred that package from split PRs #20–#24, leaving this
directory/ID available to #13. The discussion is recorded in
[PR #9](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/9) and the
[current Chemistry/Biology split](https://github.com/Geniusyingmanji/ScientistsLastExam/pull/22).
This resolves the registration collision; it is not a scientific-novelty certification.
