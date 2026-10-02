"""Small analytic fixtures only; the six-instance calibration is not run here."""
import ast
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from env.orbital_dynamics import strong_reference as strong
from env.orbital_dynamics.protocol import CHANNELS


@pytest.fixture(autouse=True)
def no_private_instance_kernel_or_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("strong reference must not access private instances, kernel or network")
    monkeypatch.setattr("env.orbital_dynamics.world.World.__init__", fail)
    monkeypatch.setattr("env.orbital_dynamics.kernel.Kernel.trajectory", fail)
    monkeypatch.setattr("env.orbital_dynamics.kernel.Kernel.derivative", fail)
    monkeypatch.setattr("env.orbital_dynamics.kernel.Parameters.generate", fail)
    monkeypatch.setattr("socket.socket", fail)
    monkeypatch.setattr("socket.create_connection", fail)


def circular_record(radius=1.2, horizon=2., count=9, power=2.):
    # Analytic fixture derives directly from centripetal acceleration; no private
    # simulator or the reference predictor is used to create observations.
    frequency = math.sqrt(1. / (radius ** 2 + .25 ** 2) ** ((power + 1) / 2))
    times = np.linspace(0, horizon, count)
    theta = frequency * times
    values = np.column_stack((radius * np.cos(theta), radius * np.sin(theta),
                              -radius * frequency * np.sin(theta), radius * frequency * np.cos(theta)))
    spec = {"position": [radius, 0.], "velocity": [0., radius * frequency],
            "times": times.tolist(), "impulses": []}
    return {"spec": spec, "observation": {"axis": times.tolist(), "channels": list(CHANNELS),
                                            "values": values.tolist()}}


@pytest.mark.parametrize("power", [1., 2., 3.])
def test_reference_matches_independent_circle_and_post_impulse_boundary(power):
    record = circular_record(power=power)
    model = {"mu": 1., "p": power, "drag": 0.}
    predicted = strong.predict_with_diagnostics(model, record["spec"])
    assert predicted["values"] == pytest.approx(np.array(record["observation"]["values"]), abs=2e-8)
    assert predicted["usage"]["rhs_evaluations"] > 0
    final = deepcopy(record["spec"])
    final["impulses"] = [{"time": 2., "delta_v": [.2, -.1]}]
    changed = np.array(strong.predict(model, final))
    expected = np.array(record["observation"]["values"])
    expected[-1, 2:] += [.2, -.1]
    assert changed == pytest.approx(expected, abs=2e-8)
    # Include an interior event and one adjacent floating-point event. Compare
    # boundary states to an independently applied velocity assignment.
    short = deepcopy(record["spec"])
    short["times"] = [0., 1., math.nextafter(1., 2.), 2.]
    short["impulses"] = [{"time": 1., "delta_v": [.1, 0.]},
                         {"time": math.nextafter(1., 2.), "delta_v": [0., -.1]}]
    observed = np.array(strong.predict(model, short))
    assert observed[2] - observed[1] == pytest.approx([0., 0., 0., -.1], abs=1e-12)


def test_one_small_circle_fit_is_finite_without_claiming_radial_law_identification():
    record = circular_record()
    original = deepcopy(record)
    result = strong.fit([record])
    assert result["model"] is not None and result["training_noise_weighted_mse"] < .001
    assert result["usage"]["residual_calls"] <= 160
    assert result["usage"]["completed_residuals"] == result["usage"]["residual_calls"]
    assert result["optimizer_starts"] == 1 and result["author_informed"]
    assert not result["autonomous_discovery"]
    assert result["retained_point_rule"] == "single_optimizer_endpoint"
    assert record == original
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    # A circle constrains acceleration only at this radius; fitted mu and p are
    # not asserted to recover their analytic generating values individually.
    fitted = result["model"]
    effective = fitted["mu"] / (1.2 ** 2 + .25 ** 2) ** ((fitted["p"] + 1) / 2)
    assert effective == pytest.approx(1. / (1.2 ** 2 + .25 ** 2) ** 1.5, rel=1e-3)


def test_positive_drag_obeys_independent_angular_momentum_decay():
    record = circular_record()
    model = {"mu": 1.1, "p": 2.6, "drag": .12}
    values = np.asarray(strong.predict(model, record["spec"]))
    momentum = values[:, 0] * values[:, 3] - values[:, 1] * values[:, 2]
    expected = momentum[0] * np.exp(-model["drag"] * np.asarray(record["spec"]["times"]))
    assert momentum == pytest.approx(expected, abs=2e-8)
    assert momentum[-1] < momentum[0]


def test_t0_and_exact_event_rows_do_not_enter_fit_loss(monkeypatch):
    record = circular_record(horizon=1., count=5)
    record["spec"]["impulses"] = [{"time": 1., "delta_v": [.2, 0.]}]
    altered = deepcopy(record)
    altered["observation"]["values"][0] = [1e5] * 4
    altered["observation"]["values"][-1] = [-1e5] * 4

    def one_evaluation(fun, x0, **kwargs):
        value = fun(np.asarray(x0))
        return SimpleNamespace(x=x0, fun=value, success=False, status=0, nfev=1)
    monkeypatch.setattr(strong, "least_squares", one_evaluation)
    before, after = strong.fit([record]), strong.fit([altered])
    assert before["training_rows"] == 3 and before["excluded_t0_and_exact_impulse_rows"] == 2
    assert before["training_noise_weighted_mse"] == after["training_noise_weighted_mse"]
    assert before["model"] == after["model"]
    assert not after["converged"] and after["stop_reason"] == "optimizer_nfev_limit"


def test_residual_limit_counts_finite_difference_calls_and_preserves_first_finite_point():
    result = strong.fit([circular_record(horizon=.5, count=3)], limits={"residual_calls": 1})
    assert result["stop_reason"] == "residual_call_limit" and not result["converged"]
    assert result["usage"]["residual_calls"] == result["usage"]["completed_residuals"] == 1
    assert result["model"] == dict(zip(strong.PARAMETER_NAMES, strong.INITIAL))
    assert result["retained_point_rule"] == "last_completed_residual_chronological_not_best"


def test_interruption_retains_last_point_even_when_its_loss_is_worse(monkeypatch):
    last = np.asarray([.6, 3., .15])
    losses = []
    def interrupted(fun, initial, **kwargs):
        losses.append(float(np.mean(fun(np.asarray(initial)) ** 2)))
        losses.append(float(np.mean(fun(last) ** 2)))
        raise strong._BudgetStop("fixture_interruption")
    monkeypatch.setattr(strong, "least_squares", interrupted)
    result = strong.fit([circular_record()])
    assert losses[1] > losses[0]
    assert result["model"] == dict(zip(strong.PARAMETER_NAMES, last))
    assert result["training_noise_weighted_mse"] == losses[1]
    assert result["usage"]["residual_calls"] == 2 and not result["converged"]


@pytest.mark.parametrize("limit,reason", [("rhs_evaluations", "fit_rhs_limit"),
                                         ("rhs_per_trajectory", "trajectory_rhs_limit")])
def test_rhs_caps_stop_before_extra_work_and_preserve_no_partial_model(limit, reason):
    result = strong.fit([circular_record()], limits={limit: 1})
    assert result["model"] is None and result["stop_reason"] == reason
    assert result["usage"]["rhs_evaluations"] == 1
    assert result["usage"]["completed_residuals"] == 0
    with pytest.raises(RuntimeError, match=reason) as caught:
        strong.predict({"mu": 1., "p": 2., "drag": 0.}, circular_record()["spec"], limits={limit: 1})
    assert caught.value.usage["rhs_evaluations"] == 1


@pytest.mark.parametrize("clock,reason", [("process_time", "cpu_limit"), ("monotonic", "wall_limit")])
def test_time_budget_can_stop_before_first_solve(monkeypatch, clock, reason):
    calls = iter([0., 100., 100.])
    monkeypatch.setattr(strong.time, clock, lambda: next(calls, 100.))
    monkeypatch.setattr(strong, "_simulate", lambda *a: pytest.fail("no solve may start after the time limit"))
    result = strong.fit([circular_record()])
    assert result["model"] is None and result["stop_reason"] == reason
    assert result["usage"]["residual_calls"] == 0


def test_numerical_failure_is_recorded_without_retry(monkeypatch):
    calls = []
    def broken(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("deliberate solver failure")
    monkeypatch.setattr(strong, "solve_ivp", broken)
    result = strong.fit([circular_record()])
    assert result["model"] is None and result["stop_reason"] == "numerical_failure:RuntimeError"
    assert len(calls) == 1 and result["usage"]["completed_residuals"] == 0


@pytest.mark.parametrize("change", [{"max_nfev": 31}, {"residual_calls": 161}, {"cpu_seconds": 31},
                                     {"wall_seconds": 61}, {"seed": 7}, {"cpu_seconds": True},
                                     {"max_nfev": 1.5}, {"rhs_evaluations": 10**1000},
                                     {"wall_seconds": float("nan")}])
def test_limits_only_reduce_predeclared_budgets(change):
    with pytest.raises(ValueError):
        strong.fit([circular_record()], limits=change)


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(seed=7), lambda r: r.update(operator_stratum="secret"),
    lambda r: r["observation"].update(private_parameters={}),
    lambda r: r["observation"].update(axis=[True]),
    lambda r: r["observation"]["values"][0].__setitem__(0, True),
    lambda r: r["observation"]["values"][0].__setitem__(0, float("inf")),
    lambda r: r["observation"]["values"][0].__setitem__(0, 10**1000),
    lambda r: r["observation"]["values"].pop(),
    lambda r: r["observation"]["channels"].reverse(),
])
def test_fit_rejects_private_payloads_and_malformed_public_records(mutation):
    record = circular_record()
    mutation(record)
    with pytest.raises(ValueError):
        strong.fit([record])


def test_no_dynamic_rows_and_unknown_model_fields_are_rejected():
    record = circular_record(horizon=0., count=1)
    with pytest.raises(ValueError, match="nonzero"):
        strong.fit([record])
    with pytest.raises(ValueError, match="only mu"):
        strong.predict({"mu": 1., "p": 2., "drag": 0., "seed": 7}, circular_record()["spec"])
    with pytest.raises(ValueError, match="bounds"):
        strong.predict({"mu": 0., "p": 2., "drag": 0.}, circular_record()["spec"])


def test_python38_and_direct_import_boundary():
    tree = ast.parse(Path(strong.__file__).read_text(), feature_version=(3, 8))
    relative = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level]
    assert relative == ["protocol"]
    imports = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert set(imports) <= {"math", "numbers", "time", "numpy"}
    assert not any(isinstance(node, ast.Name) and node.id in ("World", "Kernel", "Parameters")
                   for node in ast.walk(tree))
