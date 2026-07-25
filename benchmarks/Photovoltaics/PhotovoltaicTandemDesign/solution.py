"""Weak valid baseline: one finite-absorption junction per public budget."""


def design_tandem(problem):
    designs = []
    for index, cap in enumerate(problem["fabrication_budget_caps"]):
        depth = min(
            float(problem["optical_depth_bounds"][1]),
            (
                float(cap) - float(problem["junction_overhead_cost"])
            ) / float(problem["optical_depth_cost"]),
        )
        designs.append({
            "bandgaps_ev": [1.55 + 0.03 * index],
            "optical_depths": [depth],
        })
    return {"designs": designs}
