"""Independent derivative and noiseless inverse checks, away from scored worlds."""
import copy
import importlib.util
from pathlib import Path
import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1] / 'benchmarks/Biology/NeuralReportAttribution'


def load(name):
    spec = importlib.util.spec_from_file_location(name, TASK / 'verification' / (name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORACLE, REFERENCE = load('evaluator'), load('reference_fit')


@pytest.mark.parametrize('report', [0, 1])
@pytest.mark.parametrize('omega', [.08, .5, 2.])
def test_analytic_derivatives_match_central_differences(report, omega):
    world = ORACLE.make_world(184, 'recurrent')
    x = np.r_[world['parameters']['tau'], world['parameters']['edges'],
              np.concatenate([np.concatenate([a.ravel() for a in c]) for c in world['instruments']])]
    h, jac = REFERENCE.response_and_jacobian(x, report, omega)
    np.testing.assert_allclose(h, ORACLE.transfer(world, report, omega), atol=1e-13)
    finite = np.empty_like(jac)
    for j in range(len(x)):
        delta = np.zeros_like(x)
        delta[j] = 1e-6
        plus = REFERENCE.response_and_jacobian(x+delta, report, omega)[0]
        minus = REFERENCE.response_and_jacobian(x-delta, report, omega)[0]
        finite[:, j] = ((plus-minus)/(2e-6)).ravel()
    np.testing.assert_allclose(jac, finite, rtol=2e-6, atol=2e-9)


@pytest.mark.parametrize('kind', ['recurrent', 'report_only', 'none', 'unsupported'])
def test_reference_recovers_noiseless_independent_world(kind):
    world = ORACLE.make_world(184, kind)
    spent = []
    def exact_experiment(request):
        spent.append(request['units'])
        report = request['report']
        if request['kind'] == 'calibration':
            return dict(zip(('sensor_mixing', 'actuator_mixing', 'feedthrough', 'sensor_time_constants'),
                            [v.tolist() for v in world['instruments'][report]]))
        h = ORACLE.transfer(world, report, world['problem']['angular_frequencies'][request['frequency']])
        return {'real': h.real.tolist(), 'imag': h.imag.tolist()}
    answer = REFERENCE.infer_circuit(copy.deepcopy(world['problem']), exact_experiment)
    assert sum(spent) == 14
    ORACLE.validate(answer)
    if kind == 'unsupported':
        assert answer.get('abstain') is True
    else:
        assert answer['model'] == kind
        if kind != 'none':
            np.testing.assert_allclose([answer['feedback'], answer['report_feedback']],
                                       world['parameters']['edges'][-2:], atol=1e-5)
