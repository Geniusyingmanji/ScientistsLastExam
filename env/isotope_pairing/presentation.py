"""Candidate-facing research instructions for the operator prototype workflow."""
from copy import deepcopy


def research_task():
    return deepcopy({
        'id': 'isotope_history_validation',
        'version': 'isotope_history_validation-0.1.0',
        'status': 'operator_prototype_not_model_driver_registered',
        'question': 'Investigate how source recipes and their timing affect the measured product. Develop an account from observations, then test a prediction on a condition you have not measured.',
        'workflow': [
            'Use the apparatus description to choose legal experiments. Cite returned observation IDs.',
            'Before fresh measurements, freeze a self-contained predict(spec) program and state its scope and tolerance.',
            'Choose a fresh target and a readout. A test may validate one predictor or compare two explanations compatible with earlier observations.',
            'Report disagreements, failed predictions and inconclusive tests. A successful prediction does not uniquely identify the hidden mechanism.'
        ],
        'operator_actions': ['observe_source', 'preview_experiments', 'preview_preregistration', 'preregister', 'finish'],
        'execution_note': 'These are trusted operator methods, not permission to import environment code. An agent-facing driver is not yet registered.',
        'submission_note': 'Use the prospective request schema supplied by the operator: profile, scope, rivals, experiments, readout, replicates, revision_of and change_note. Evidence IDs must reference prior observations. The operator freezes executable predictors before collecting test observations.',
        'evaluation': 'Fresh prediction tests and declared uncertainty are recorded separately from explanatory evidence. Initial assigned values are not discovery targets. No automatic discovery-depth score or required mechanism label.'
    })
