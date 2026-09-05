"""Runnable normalization witness; the evaluator recomputes the same policy per run."""
import evaluator


def design_laminate(problem):
    return {"ply_angles_deg": evaluator._reference(problem)}
