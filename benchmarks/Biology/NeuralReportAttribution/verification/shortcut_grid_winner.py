"""Public-input-only algebraic probe: calibrated inverse response, no likelihood fit.

Builder audit selects thresholds/scales on development. Heldout is used once after
selection. This file contains no frozen-world labels, seeds, or lookup table.
"""
import numpy as np


def acquire_features(problem, experiment, *, null_only=False):
    estimates = []
    for report in ((1,) if null_only else (0, 1)):
        cal = experiment({'kind': 'calibration', 'report': report, 'frequency': 0,
                          'units': 1 if null_only else 2})
        c, b, d, tau = [np.asarray(cal[k]) for k in
                        ('sensor_mixing', 'actuator_mixing', 'feedthrough', 'sensor_time_constants')]
        for freq in (0, 3):
            omega = problem['angular_frequencies'][freq]
            data = experiment({'kind': 'response', 'report': report, 'frequency': freq, 'units': 1})
            h = np.asarray(data['real']) + 1j*np.asarray(data['imag'])
            neural = np.linalg.solve(c, (h-d)*(1+1j*omega*tau[:, None])) @ np.linalg.inv(b)
            a = 1j*omega*np.eye(4) - np.linalg.inv(neural)
            estimates.append((report, a))
    matrices = np.array([a for _, a in estimates])
    mean = matrices.real.mean(axis=0)
    off_diagonal = mean - np.diag(np.diag(mean))
    report_feedback = np.mean([a[1, 3].real for report, a in estimates if report == 1])
    # An omitted slow mediator makes apparent P -> V2 feedback complex and frequency dependent.
    mismatch = max(float(np.max(np.abs(matrices[:, 1, 2].imag))),
                   float(np.ptp(matrices[:, 1, 2].real)))
    return (float(np.max(np.abs(off_diagonal))), mismatch,
            float(mean[1, 2]), float(report_feedback))


def answer_from_features(features, config):
    null_threshold, mismatch_threshold, feedback_threshold, feedback_scale, report_scale = config
    magnitude, mismatch, feedback, report_feedback = features
    if magnitude < null_threshold:
        return {'model': 'none'}
    if mismatch > mismatch_threshold:
        return {'abstain': True}
    recurrent = feedback > feedback_threshold
    return {'model': 'recurrent' if recurrent else 'report_only',
            'feedback': float(np.clip(feedback*feedback_scale, 0, 1.2)) if recurrent else 0.,
            'report_feedback': float(np.clip(report_feedback*report_scale, 0, 1.2))}


def infer_circuit(problem, experiment, *, config=(.13, .35, .08, .9, 1.)):
    return answer_from_features(acquire_features(problem, experiment), config)


def null_or_refuse(problem, experiment):
    magnitude, _, _, _ = acquire_features(problem, experiment, null_only=True)
    return {'model': 'none'} if magnitude < .35 else {'abstain': True}
