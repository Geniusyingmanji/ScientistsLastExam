# Robust Reserve Network Design

Implement `design_reserve(problem) -> {"protected_patches": ["p0", ...]}`.
Return exactly this key, with distinct allowed string IDs. Empty is legal;
unknown IDs, duplicates, non-list outputs and exceeding the hard cost budget
are invalid. NumPy/SciPy are available; candidate evaluation budget is 120 CPU seconds.

Public fields: `patch_ids` orders N sites; `costs` is an N-vector of integer cost
units; `budget` is in the same units. `species_weights` has S positive weights;
`initial_occupancy` has shape S,N. `habitat_quality`, `extinction_rates` have
shape C,S,N; `dispersal_matrices` has shape C,S,N,N, ordered scenario, species,
source j, destination i. All coefficients are dimensionless per discrete step.
`time_grid` is [0,...,12], indicating twelve equal transitions. Sites outside
the chosen set cannot hold populations; initially p[c,s,i] = x[i]*initial[s,i].
For each step simultaneously update

`pressure[c,s,i] = sum_j d[c,s,j,i]*x[j]*p[c,s,j]`

`p_new[c,s,i] = x[i]*(p[c,s,i]*(1-e[c,s,i]) + (1-p[c,s,i])*(1-exp(-pressure[c,s,i])))`.

Utility is the minimum over public scenarios of the final sum
`sum_s,i species_weights[s]*habitat_quality[c,s,i]*p[c,s,i]`.
This reduced mean-field occupancy model uses unoccupied fraction for colonization;
extinction and colonization are mutually exclusive starting-state terms.
Quality weights final occupancy and also affects the supplied extinction arrays;
use those arrays directly, do not infer constants. Zero sources cannot colonize.
The model preserves [0,1] occupancy and is not an individual-based simulator.

The empty set has utility and score zero. Score is `clip(utility/reference,0,1)`;
the frozen reference greedily adds maximal marginal utility per cost, followed
by one best feasible one-for-one swap. Ties use lexical IDs. It is not optimal.
Development has 40/44 sites, held-out 48/52; all have four species and three
scenarios, with shifted landscapes and source locations. Mean development score
is `combined_score`; held-out score and raw utility are sealed diagnostics.
`valid` requires every world valid. Worlds are repository-visible procedural
panels, not secret ecological data. Candidate output never supplies utility.

The spatial-extinction motivation is [Hanski and Ovaskainen (2000)](https://doi.org/10.1038/35008063).
The specific discrete recurrence is a benchmark assumption, not that paper's
exact model or a validated real conservation-policy recommendation. No external
data/code is redistributed. Ecological review and strong-solver calibration remain pending.
Nearest tasks: FedBatchBioprocessDesign controls reactor dynamics;
GeneNetworkIntervention discovers regulatory effects; SparseRecovery designs
measurements. Here discrete choices alter spatial propagation under shared budgets.
