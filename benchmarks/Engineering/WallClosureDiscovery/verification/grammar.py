"""The closure grammar: a small expression language the oracle can evaluate and a person can read.

The product of this task is a *formula*, so it crosses the sandbox boundary as data rather than as
a callable - which is also the only thing that can cross it. An expression is a nested list:

    ["mul", ["const", 41, 100], ["var", "y"]]        ->  0.41 * y+

Variables are `y` (the wall distance in wall units) and `re` (the friction Reynolds number).
Constants are exact rationals, so a submitted formula means one thing and reads the same to the
oracle and to a reviewer. The node budget is small on purpose: the task is about finding the law,
not about fitting an arbitrarily flexible function, and a grammar with room for a lookup table
would measure the wrong thing.
"""
from __future__ import annotations

from fractions import Fraction

import numpy as np

MAX_NODES = 40
MAX_DEPTH = 10
UNARY = {"neg", "exp", "tanh", "sqrt", "square"}
BINARY = {"add", "sub", "mul", "div"}


def count_nodes(expression, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError("expression deeper than the cap")
    if not isinstance(expression, (list, tuple)) or not expression:
        raise ValueError("an expression is a non-empty list")
    head = expression[0]
    if head == "const":
        if len(expression) != 3:
            raise ValueError("const takes a numerator and a denominator")
        numerator, denominator = expression[1], expression[2]
        for part in (numerator, denominator):
            if isinstance(part, bool) or not isinstance(part, int):
                raise ValueError("constants are exact rationals")
        if denominator == 0:
            raise ValueError("zero denominator")
        if abs(numerator) > 10 ** 9 or abs(denominator) > 10 ** 9:
            raise ValueError("constant outside the magnitude cap")
        return 1
    if head == "var":
        if len(expression) != 2 or expression[1] not in ("y", "re"):
            raise ValueError("the variables are 'y' and 're'")
        return 1
    if head in UNARY:
        if len(expression) != 2:
            raise ValueError("%s takes one argument" % head)
        return 1 + count_nodes(expression[1], depth + 1)
    if head in BINARY:
        if len(expression) != 3:
            raise ValueError("%s takes two arguments" % head)
        return 1 + count_nodes(expression[1], depth + 1) + count_nodes(expression[2], depth + 1)
    raise ValueError("unknown operator %r" % (head,))


def evaluate_expression(expression, y, re_tau):
    """Evaluate on a grid. Guards keep a malformed formula from producing nonsense silently."""
    head = expression[0]
    if head == "const":
        return np.full_like(y, float(Fraction(expression[1], expression[2])), dtype=float)
    if head == "var":
        return y if expression[1] == "y" else np.full_like(y, float(re_tau), dtype=float)
    if head in UNARY:
        inner = evaluate_expression(expression[1], y, re_tau)
        if head == "neg":
            return -inner
        if head == "exp":
            # Clipped so that a runaway exponent is a bad formula rather than an overflow warning
            # that turns into a silent inf downstream.
            return np.exp(np.clip(inner, -700.0, 700.0))
        if head == "tanh":
            return np.tanh(inner)
        if head == "sqrt":
            return np.sqrt(np.clip(inner, 0.0, None))
        return inner * inner
    left = evaluate_expression(expression[1], y, re_tau)
    right = evaluate_expression(expression[2], y, re_tau)
    if head == "add":
        return left + right
    if head == "sub":
        return left - right
    if head == "mul":
        return left * right
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(np.abs(right) < 1e-12, np.nan, left / np.where(right == 0, 1.0, right))
    return out


def compile_closure(expression):
    """Validate once, then hand back something the solver can call."""
    nodes = count_nodes(expression)
    if nodes > MAX_NODES:
        raise ValueError("expression uses %d nodes, cap is %d" % (nodes, MAX_NODES))

    def closure(y, re_tau):
        values = evaluate_expression(expression, np.asarray(y, dtype=float), float(re_tau))
        if not np.all(np.isfinite(values)):
            raise ValueError("closure is not finite on the grid")
        return values
    return closure
