"""Data-free two-variable LP and thread-creation compatibility fixtures."""
import os
import threading
import warnings
import numpy as np
import scipy
from scipy.optimize import linprog
from scipy.optimize._highs._highs_wrapper import _highs_wrapper
from scipy.sparse import csc_matrix


def micro(case, checkpoint):
    checkpoint('candidate_entered')
    if case == 'import_only':
        return {'numpy': np.__version__, 'scipy': scipy.__version__,
                'environment': {key: os.environ.get(key) for key in (
                    'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}}
    if case == 'python_thread':
        try:
            worker = threading.Thread(target=lambda: None)
            worker.start()
            worker.join()
            return {'thread_started': True}
        except RuntimeError:
            return {'thread_started': False, 'failure_category': 'RuntimeError'}
    # min -x - 2y, x+y=1, x,y>=0 has unique optimum x=0,y=1,f=-2.
    c = np.array([-1.0, -2.0])
    a = np.array([[1.0, 1.0]])
    b = np.array([1.0])
    checkpoint('solver_entered')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if case in ('linprog_default', 'linprog_threads_one'):
            options = {} if case == 'linprog_default' else {'threads': 1}
            result = linprog(c, A_eq=a, b_eq=b, bounds=[(0, None)] * 2,
                             method='highs', options=options)
            answer = {'success': bool(result.success), 'status': int(result.status),
                      'x': result.x.tolist() if result.x is not None else None,
                      'fun': float(result.fun) if result.fun is not None else None}
        elif case in ('direct_threads_one', 'direct_serial_minmax'):
            matrix = csc_matrix(a)
            options = {'threads': 1} if case == 'direct_threads_one' else {
                'parallel': False, 'min_threads': 1, 'max_threads': 1}
            options.update({'log_to_console': False, 'output_flag': False})
            result = _highs_wrapper(c, matrix.indptr, matrix.indices, matrix.data,
                                    b, b, np.zeros(2), np.full(2, np.inf),
                                    np.empty(0, dtype=np.uint8), options)
            answer = {'status': int(result['status']),
                      'x': list(result['x']) if result.get('x') is not None else None,
                      'fun': float(result['fun']) if result.get('fun') is not None else None}
        else:
            raise ValueError('unknown fixed micro fixture')
        answer['warning_categories'] = [type(w.message).__name__ for w in caught]
    checkpoint('solver_returned')
    return answer
