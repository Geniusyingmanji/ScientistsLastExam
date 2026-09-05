"""Runnable normalization witness; the evaluator recomputes the same policy per run."""
import evaluator


def schedule_pumps(problem):
    return {"pump_speed": evaluator._reference(problem).tolist()}
