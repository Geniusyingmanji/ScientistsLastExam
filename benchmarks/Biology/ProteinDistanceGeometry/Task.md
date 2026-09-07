# Protein Distance Geometry

Implement `build_conformation(problem) -> {"coordinates": [[x,y,z], ...]}`.
Return exactly this key and one length-three list of finite real numbers per
`atom_ids` entry. Booleans, ragged/nested/non-list arrays, extra keys and any
coordinate outside `coordinate_bounds=[-250,250]` angstroms are invalid.

This first implementation is **synthetic C-alpha backbone geometry**, not
all-atom protein folding. `representation=synthetic_C_alpha_backbone` and
`atom_ids` order 24/28 development or 32/36 held-out beads. `bonds` lists objects
`{atoms:[i,j],bounds:[low,high]}` in angstroms, normally [3.76,3.84].
`distance_restraints` has the same schema for sparse nonlocal intervals.
`angle_bounds` lists `{atoms:[i,j,k],cosine_bounds:[low,high]}`, for vectors
r_i-r_j and r_k-r_j. The denominator is max(norm(a)*norm(b),1e-12).
`stereocenters` lists `{atoms:[i,j,k,l],sign:+1 or -1,minimum_volume:v}`.
These are **coarse local handedness constraints**, not chemical stereocenters.
Their dimensionless signed volume is
`dot(r_j-r_i,cross(r_k-r_i,r_l-r_i))/3.8^3`.
`excluded_volume_radii` is one radius per bead in angstroms (1.2 here).
Exclude volume for every pair with index separation >=3; neighbors and
next-neighbors use bond/angle constraints instead.

For an interval [a,b], violation is max(a-value,0,value-b). Steric violation
is max(0,radius_i+radius_j-distance); handedness violation is
max(0,minimum_volume-sign*volume). Loss sums mean squared violations for the
five groups, weighted by public `loss_weights`:
bonds=4, angles=2, distances=1, sterics=4, chirality=2. Empty groups contribute
zero. Length residuals use angstrom numerical values, cosine and normalized
volume residuals are dimensionless; these empirical weights define the objective.
There is no hidden coordinate/RMSD term. Rigid rotation and translation preserve
loss within coordinate bounds. Reflections preserve distances but reverse handedness.
Collapsing or rescaling structures incurs independent bonded and steric losses.

The straight-line baseline places bead i at [3.8*(i-(N-1)/2),0,0]. It is a legal
artifact, not a physically valid conformation. Score is
`clip((q-q_baseline)/(1-q_baseline),0,1)`, where `q=1/(1+L/0.2)`. Zero public loss
defines perfect quality 1; the loss scale 0.2 resolves residual constraint errors.
The input-only reference
uses shortest-path distance completion, classical MDS, chooses the better
reflection, then at most 45 nonlinear least-squares evaluations. It is a
comparison solver, not the normalization endpoint or a global optimum. Development mean is the search
score; larger held-out worlds and raw constraint losses are sealed diagnostics.
`valid` requires all four worlds valid. All worlds are repository-visible
procedural panels. NumPy/SciPy are available. `EVAL_TIMEOUT_S=300` in the task
entrypoint sets the candidate wall-clock deadline for all four worlds, including
held-out worlds, matching the default `sle eval --timeout 300`. The worker also
has the repository CPU resource limit; it is not a separate 300 seconds per world.
The maintainer measured 96 seconds for a full reference evaluation, so the default
leaves over 3x that observation. The outer wrapper allows an additional 120 seconds
for trusted evaluation and subprocess cleanup. See the task card and measured evidence.

[DGSOL's author page](https://www.mcs.anl.gov/~more/dgsol/) and Moré & Wu,
*Distance geometry optimization for protein structures* (1999), motivate the
problem. No DGSOL code or protein data is redistributed. Nearest tasks:
ProteinStabilityDesign produces sequences, GraphFromDistances produces graphs,
ForceFieldCalibration produces interaction parameters. Frontier-Engineering's
`diverse_conformer_portfolio` selects existing conformers whereas this task
constructs coordinates. The residual overlap risk is high; external review,
all-atom validation and frontier difficulty calibration remain pending.
