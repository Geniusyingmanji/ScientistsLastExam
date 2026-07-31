# MultiEchelonStock — optimize multi-stage supply chain inventory

## Scientific background
A multi-echelon inventory system has multiple stages (factory→warehouse→retailer) each
holding buffer stock. Setting base-stock levels to minimize total holding+backorder cost
while meeting a service-level constraint is the core problem in supply chain management.
The bullwhip effect (demand amplification upstream) and lead-time interactions create
non-trivial coupling between stages.

Reference: Clark & Scarf, Mgmt. Sci. 6, 475 (1960); Graves & Willems, Supply Chain Mgmt (2003).

## Your task
```python
def optimize_inventory(n_stages, lead_times, holding_costs, backorder_costs, service_target):
    \"\"\"Return base-stock levels (3,) for a 3-stage supply chain.
    Balance cost vs. service level (target 95%).\"\"\"
```

## Rules
- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
