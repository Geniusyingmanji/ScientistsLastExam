"""The allowed serial NMR/JIT path works without exposing optional TBB threads."""
import importlib.metadata
from pathlib import Path
import tempfile
import unittest

from _sandbox_tools import skip_unless_sandbox
from sle.secure_eval import CandidateProxy, read_candidate_packages


@skip_unless_sandbox("bwrap")
class NmrsimRuntimeProfileTests(unittest.TestCase):
    def test_serial_nmrsim_and_jit_work_while_tbb_backend_is_masked(self):
        try:
            importlib.metadata.version("nmrsim")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("trusted interpreter does not install the nmrsim profile")
        source = '''def probe():
    import os
    import nmrsim.qm
    import numba
    from numba import njit
    try:
        from numba.np.ufunc import tbbpool
    except ImportError:
        tbb_visible = False
    else:
        tbb_visible = True
    value = njit(lambda x: x + 1)(2)
    return {"value": int(value), "tbb_visible": tbb_visible,
            "thread_layer": os.environ["NUMBA_THREADING_LAYER"],
            "num_threads": numba.config.NUMBA_NUM_THREADS}
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "frontier_eval").mkdir()
            (root / "frontier_eval/candidate_packages.txt").write_text("nmrsim\n")
            candidate = root / "candidate.py"
            candidate.write_text(source)
            packages = read_candidate_packages(root)
            with CandidateProxy(candidate, "probe", timeout_s=60, packages=packages) as worker:
                result = worker()
        self.assertEqual(result, {"value": 3, "tbb_visible": False,
                                  "thread_layer": "workqueue", "num_threads": 1})
