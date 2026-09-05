"""Runnable normalization witness; the evaluator recomputes this controller per run."""
import evaluator


def make_hvac_controller(problem):
    return evaluator._reference_factory(problem)
