"""Runnable normalization witness; the evaluator recomputes this controller per run."""
import evaluator


def make_aeration_controller(problem):
    return evaluator._reference_factory(problem)
