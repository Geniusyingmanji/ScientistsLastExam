"""Public-only readout identities for the first prospective frontier cohort.

Inputs must already be canonicalized by the environment's public validator.
These keys collapse listed apparatus aliases, not every mathematical equivalence
of a hidden simulator. They neither inspect kernels nor certify scientific novelty.
Distinct keys mean different audited controls for a measured quantity; they do
not prove independent mechanisms, material transfer, or informative test design.

Molecular rows are independent preparations, so unrelated batch rows do not
belong in an identity. Climate responses depend only on forcing through the
selected annual endpoint. Catalyst reactions retain their complete causal event
prefix; calibration responses depend only on calibration kind and event clock.
Field quantities depend on one habitat row and the relevant visit methods, not
other habitat rows. The first-visit statistic ignores later visits; any/all are
order invariant. One-visit statistics are the same observable by definition.
Phase scans depend on one angle, not the other sampled angles. Empty-holder
responses ignore material preparation and are excluded as prospective targets.

The catalyst reaction prefix deliberately does not collapse preceding events on
other coupons, and no geometric rotation/translation equivalence is assumed for
molecular responses. Those stronger equivalences require separate domain review.
"""
from copy import deepcopy
import math


_ENVIRONMENTS = {'molecular_forces', 'climate_response', 'catalyst_aging',
                 'field_ecology', 'phase_equilibria'}
_MOLECULAR_CHANNELS = ('energy_ev',) + tuple('f%d%s_ev_per_a' % (i, a)
                                          for i in (1, 2, 3) for a in 'xyz')
_CLIMATE_CHANNELS = ('surface_temperature_anomaly_k', 'toa_imbalance_w_m2')
_FIELD_CHANNELS = ('first_visit_detection', 'any_visit_detection', 'all_visits_detection')


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('readout controls must be canonical finite numbers')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('readout controls must be canonical finite numbers')
    return 0.0 if result == 0 else result


def _row(sequence, row):
    if not isinstance(sequence, list) or type(row) is not int or not 0 <= row < len(sequence):
        raise ValueError('invalid readout row')
    return sequence[row]


def _channel(channel, allowed):
    if not isinstance(channel, str) or channel not in allowed:
        raise ValueError('unknown readout channel')
    return channel


def _catalyst_event(spec, row):
    index = _number(_row(spec['event_indices'], row))
    events = spec['events']
    if not isinstance(events, list) or index != int(index) or not 1 <= index <= len(events):
        raise ValueError('invalid catalyst event index')
    index = int(index)
    event = events[index-1]
    if not isinstance(event, dict) or event.get('kind') not in ('blank', 'standard', 'reaction'):
        raise ValueError('invalid catalyst event kind')
    return index, event


def readout_key(environment, spec, row, channel):
    """Return a detached JSON-serializable physical-readout control identity.

    This helper is applied to every observed row/channel before a new test, so
    observing one molecular geometry in any batch marks that geometry measured.
    It is versioned by the frozen source manifest; old protocols must retain
    their original eligibility behavior.
    """
    if not isinstance(environment, str) or environment not in _ENVIRONMENTS:
        raise ValueError('frontier readout semantics not available for environment')
    if not isinstance(spec, dict):
        raise ValueError('canonical experiment must be a mapping')
    try:
        if environment == 'molecular_forces':
            channel = _channel(channel, _MOLECULAR_CHANNELS)
            geometry = _row(spec['configurations'], row)
            _row(spec['configuration_ids'], row)
            if not isinstance(geometry, list) or len(geometry) != 3 or any(not isinstance(p, list) or len(p) != 3 for p in geometry):
                raise ValueError('invalid canonical geometry')
            controls = {'geometry': [[_number(v) for v in point] for point in geometry],
                        'temperature_k': _number(spec['temperature_k'])}
        elif environment == 'climate_response':
            channel = _channel(channel, _CLIMATE_CHANNELS)
            year = _number(_row(spec['times_years'], row))
            forcing = spec['forcing_w_m2']
            if not isinstance(forcing, list) or year != int(year) or not 1 <= year <= len(forcing):
                raise ValueError('invalid canonical annual endpoint')
            controls = {'year': int(year), 'forcing_prefix': [_number(v) for v in forcing[:int(year)]]}
        elif environment == 'catalyst_aging':
            channel = _channel(channel, ('measured_signal',))
            index, event = _catalyst_event(spec, row)
            if event['kind'] in ('blank', 'standard'):
                controls = {'event_index': index, 'calibration_kind': event['kind']}
            else:
                controls = {'event_prefix': deepcopy(spec['events'][:index])}
        elif environment == 'field_ecology':
            channel = _channel(channel, _FIELD_CHANNELS)
            habitat = _number(_row(spec['habitat_values'], row))
            visits = spec['visits']
            if not isinstance(visits, list) or not visits or any(v not in ('rapid', 'intensive') for v in visits):
                raise ValueError('invalid canonical visit list')
            if channel == 'first_visit_detection' or len(visits) == 1:
                channel = 'first_visit_detection'
                selected_visits = [visits[0]]
            else:
                selected_visits = sorted(visits)
            controls = {'habitat': habitat, 'visits': selected_visits}
        else:
            channel = _channel(channel, ('intensity',))
            angle = _number(_row(spec['angles_deg'], row))
            loading = _number(spec['loading'])
            if loading == 0:
                controls = {'angles_deg': angle, 'loading': 0.0}
            else:
                controls = {'angles_deg': angle, 'loading': loading,
                            'composition': _number(spec['composition']),
                            'hold_time': _number(spec['hold_time']),
                            'preparation': spec['preparation']}
    except (KeyError, TypeError, IndexError):
        raise ValueError('missing or malformed canonical readout controls') from None
    return {'environment': environment, 'channel': channel, 'controls': controls}


def eligible_target(environment, spec, row, channel):
    """Exclude empty apparatus controls as target evidence; references stay legal.

    Standard calibration remains eligible as instrument-response prediction;
    whether it supports a scientific claim is a separate scope review. Neither
    a static index of zero nor habitat zero means an assigned initial value.
    """
    readout_key(environment, spec, row, channel)
    if environment == 'phase_equilibria':
        return _number(spec['loading']) != 0
    if environment == 'catalyst_aging':
        return _catalyst_event(spec, row)[1]['kind'] != 'blank'
    return True
