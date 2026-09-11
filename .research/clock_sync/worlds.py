"""Prototype world set v1."""
H, B = 14400.0, 20000
DEV = [
    {"name": "d01", "seed": 101, "nodes": 5, "extra": 2, "calibrated": [0, 1]},
    {"name": "d02", "seed": 102, "nodes": 6, "extra": 3, "calibrated": [0, 2, 4]},
    {"name": "d03", "seed": 103, "nodes": 6, "extra": 2, "calibrated": [1]},
    {"name": "d04", "seed": 104, "nodes": 7, "extra": 3, "calibrated": [0, 3, 5]},
    {"name": "d05", "seed": 105, "nodes": 7, "extra": 4, "calibrated": [2, 4]},
    {"name": "d06", "seed": 106, "nodes": 8, "extra": 4, "calibrated": [0, 1, 5, 7]},
    {"name": "d07", "seed": 111, "nodes": 6, "extra": 3, "calibrated": []},
    {"name": "d08", "seed": 107, "nodes": 6, "extra": 3, "calibrated": [0, 2], "fault": "step", "fault_size": 3e-9, "fault_node": 1, "soft_nodes": [4]},
    {"name": "d09", "seed": 108, "nodes": 7, "extra": 3, "calibrated": [1, 3], "fault": "step", "fault_size": -3e-9},
    {"name": "d10", "seed": 109, "nodes": 6, "extra": 3, "calibrated": [0, 1, 2, 3], "fault": "miscalibrated", "fault_link": 0, "fault_size": 40e-6, "soft_nodes": [3, 5]},
    {"name": "d11", "seed": 110, "nodes": 7, "extra": 4, "calibrated": [0, 2, 3, 5], "fault": "miscalibrated", "fault_link": 0, "fault_size": 60e-6, "soft_nodes": [3, 5]},
    {"name": "d12", "seed": 112, "nodes": 7, "extra": 3, "calibrated": [0, 2], "fault": "jump", "fault_size": 10e-6, "fault_at": 0.4},
]
HELD = [
    {"name": "h01", "seed": 201, "nodes": 6, "extra": 3, "calibrated": [0, 1, 3]},
    {"name": "h02", "seed": 202, "nodes": 7, "extra": 3, "calibrated": [0, 2, 4]},
    {"name": "h03", "seed": 203, "nodes": 8, "extra": 5, "calibrated": [0, 2, 4, 6]},
    {"name": "h04", "seed": 204, "nodes": 5, "extra": 2, "calibrated": [0, 1]},
    {"name": "h05", "seed": 205, "nodes": 7, "extra": 3, "calibrated": [0, 3], "fault": "step", "fault_size": 2.5e-9},
    {"name": "h06", "seed": 206, "nodes": 6, "extra": 3, "calibrated": [0, 1, 2], "fault": "miscalibrated", "fault_link": 2, "fault_size": 60e-6, "soft_nodes": [4]},
]
for s in DEV + HELD:
    s.setdefault("budget", B); s.setdefault("horizon", H)
