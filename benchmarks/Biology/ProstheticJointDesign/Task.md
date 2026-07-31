# ProstheticJointDesign — optimize knee prosthesis geometry

## Scientific background
Total knee replacement design requires optimizing the femoral condyle and tibial insert
geometry to maximize range-of-motion (rollback during flexion) while keeping contact stress
below the polyethylene yield limit (~25 MPa). The geometry varies across flexion zones
(extension, mid-flexion, deep flexion) with conflicting requirements: larger femoral radii
improve rollback but increase stress; higher conformity improves stability but limits motion.

Reference: Walker, Biomechanics of the Knee (Springer, 2005).

## Your task
```python
def design_joint(n_params):
    \"\"\"Return 8 parameters: 4 femoral radii [15-50 mm] + 4 tibial radii [20-100 mm]
    for 4 flexion zones (0-30, 30-60, 60-90, 90-120 degrees).\"\"\"
```
## Rules
- Only edit `solution.py`. numpy/scipy only. CPU. Do not read `verification/`.
