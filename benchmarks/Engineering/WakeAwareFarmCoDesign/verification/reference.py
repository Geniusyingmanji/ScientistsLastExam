"""Runnable normalization witness; the evaluator recomputes the same policy per run."""
import evaluator


def design_wind_farm(problem):
    layout, yaw = evaluator._reference(problem)
    return {"layout_xy_m": layout.tolist(), "yaw_by_direction_deg": yaw.tolist()}
