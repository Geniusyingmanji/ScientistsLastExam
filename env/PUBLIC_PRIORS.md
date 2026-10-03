# What the completed GPT cohorts were told

Discovery claims are conditional on the information supplied in the task. Five
of the seven evaluated worlds explicitly supplied their governing model family.
In those worlds, experiment design, parameter or topology identification and
transfer remain meaningful scientific work. Repeating the supplied equation is
not evidence of discovering that equation.

This inventory uses the actual archived public problem descriptions from all
26 archived core/expansion episode packets. It does not infer exposure from
private simulator source or from a model's final answer. The packets have export
gaps; the checked descriptions themselves are present. Removing only the task
profile wrapper leaves one identical scientific description per world across
the recorded contexts. Scores and historical depth annotations are unchanged.

| Evaluated world | Explicit scientific prior in the public problem | Empirical work still needed |
|---|---|---|
| Coupled oscillators | Full linear force balance; reciprocal nonnegative springs; known masses; coefficient ranges; no nonlinear force, delay or hidden mass | Identify active links and coefficients; test cuts, loads, damping and forcing with the same model |
| Reaction kinetics | Sparse reversible first-order transfers; conservation and detailed balance; Arrhenius temperature law and rate/energy ranges | Identify pathways and rates; discriminate topology and predict new mixtures or temperature schedules |
| Heat transport | Diffusion–advection–loss PDE, heater shape, boundary conditions, one/two-region material menu and parameter ranges | Identify transport/loss/heterogeneity; establish where a fitted account predicts new configurations |
| Gene regulation | Sigmoid regulatory ODE, signed edge orientation, no self edges and parameter ranges | Infer the signed network and response scales; test pulses and changed preparations |
| Ising spin | Pairwise energy and Boltzmann equilibrium law; finite known spin set; parameter ranges and exact control semantics | Infer fields and interactions; distinguish direct bonds from correlation and transfer to interventions |
| Microecology | Preparation, channels, noise, material accounting and ideal intervention semantics; no governing growth/interaction equation supplied | Develop and test quantitative relationships or causal accounts with explicit alternatives and scope |
| Hysteresis material | Reset, preparation, field history, continuity, noise and readout semantics; no response equation or mechanism menu supplied | Distinguish competing accounts of history dependence, relaxation and memory using informative protocols |

Source anchors in the frozen public packets are
`/public_contexts/*/problem/physical_family` (oscillators and Ising),
`/public_contexts/*/problem/candidate_family` (reaction and gene regulation),
`/public_contexts/*/problem/physics` (heat), and the complete public problem
objects for microecology and material history. The corresponding public-contract
implementations are [oscillators](coupled_oscillators/world.py),
[reaction](reaction_kinetics/world.py), [heat](heat_transport/world.py),
[gene regulation](gene_regulation/world.py), [Ising](ising_spin/world.py),
[microecology](microecology/world.py), and [material](hysteresis_material/protocol.py).
Private packet paths, instance seeds and held-out targets are not published here.

## Consequences for the next evaluation

Report supplied-family identification and instrument-contract mechanism
exploration as explicit task conditions. Their shared predictive score can
remain a descriptive pilot aggregate, but it does not isolate one common
discovery demand. Open choice of research question is separate from how much
physical theory the task supplies.

A future comparison can hold the world, legal controls, observations and budgets
fixed while varying a versioned public theory supplement. The lower-information
condition must still state truthful units, preparation, control effects, noise
and instrument limits. Simply deleting an equation does not demonstrate novelty
or resistance to memorization: a familiar apparatus may reveal its family, and
the model may already know the relevant scientific principles.

Such a comparison is a new prompt/prior experiment, with new frozen cohorts and
failure records. It must precede or be separated from budget scaling. No prompt
was retrospectively changed, no episode was rerun, and no gain from reduced
prior information has been measured. Mechanism-level claims still require
traceable evidence, meaningful alternatives and prospective tests of the
specific model version actually submitted.

An optional `apparatus_only` presentation already exists for oscillators and
Ising, as documented in the [runner instructions](README.md). The completed
cohorts above used the full descriptions. Availability of that option does not
constitute a tested lower-information cohort or extend its support to every world.
