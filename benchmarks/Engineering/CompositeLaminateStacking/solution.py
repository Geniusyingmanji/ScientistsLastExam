"""Weak valid quasi-isotropic stacking baseline."""


def design_laminate(problem):
    counts = {int(k): int(v) // 2 for k, v in problem["required_angle_counts"].items()}
    half = []
    while sum(counts.values()):
        for angle in (0, 45, -45, 90):
            if counts.get(angle, 0):
                half.append(angle)
                counts[angle] -= 1
    return {"ply_angles_deg": half + half[::-1]}
