import copy
import math
import numpy as np
import pytest
from env.retention_capacity.world import World
from env.retention_capacity.order_task import pair, observe, score, validate_pair


def test_matched_integral_clock_but_stateful_response_differs():
    w = World(71200)
    for final in (6., 9.):
        d = pair(1., [0., 1., 2.], 2., final)
        def clock(s, f):
            flow = s['flow']
            return sum(((flow[i+1]['at'] if i+1 < len(flow) else final)-x['at'])*f(x['rate']) for i,x in enumerate(flow))
        for f in (lambda q:q, lambda q:q*q, lambda q:math.exp(q)):
            assert clock(d['left'], f) == pytest.approx(clock(d['right'], f))
        y = observe(w, d, noise_key=None)
        assert abs(y[0]-y[1]) > .01


def test_absolute_and_signed_contrast_have_distinct_penalties():
    y = np.array([[.2, .4], [.6, .3]])
    assert score(y, y)['score'] == 100
    shifted = score(y+.1, y)
    assert shifted['contrast_score'] == pytest.approx(100)
    assert shifted['absolute_score'] == pytest.approx(100/math.e)
    swapped = score(y[:, ::-1], y)
    assert swapped['contrast_score'] < swapped['absolute_score']
    # Accurate common mean cannot earn full marks for a nonzero order effect.
    zero_order = score(np.repeat(y.mean(axis=1)[:, None], 2, axis=1), y)
    assert zero_order['score'] < 50


def test_invalid_pair_and_invalid_predictions_rejected():
    w = World(71200)
    d = pair(1., [0., 1., 2.], 2., 6.)
    for change in ('load', 'time', 'rate'):
        bad = copy.deepcopy(d)
        if change == 'load': bad['right']['load'] = 2.
        elif change == 'time': bad['right']['times'] = [7.]
        else: bad['right']['flow'][0]['rate'] = 1.
        with pytest.raises(ValueError): validate_pair(w, bad)
    for p in ([[True, False]], [[float('nan'), 0]], [1, 2], [[1]]):
        with pytest.raises(ValueError): score(p, [[.2, .4]])
