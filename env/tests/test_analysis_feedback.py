"""Repairable, bounded feedback for common public-analysis mistakes."""
import json

from env import analysis_worker
from env.runner import SYSTEM


def execute(code):
    analysis_worker._namespace = {"__name__": "__scientific_analysis__"}
    return analysis_worker.analyze({"code": code, "problem": {}, "history": [],
                                    "records": [{"observation": {"axis": [0, 1],
                                    "channels": ["x"], "values": [[0.0], [1.0]]}}]})


def test_record_shape_error_points_to_candidate_and_can_be_repaired():
    failed = execute("import numpy as np\ny = np.asarray(records[0]['observation'], dtype=float)")
    assert failed["ok"] is False
    assert failed["error"] == "TypeError"
    assert "dict" in failed["message"]
    assert failed["phase"] == "execution"
    assert failed["candidate_line"] == 2
    assert "traceback" not in failed
    corrected = execute("import numpy as np\ny = np.asarray(records[0]['observation']['values'], dtype=float)\nresult = y.tolist()")
    assert corrected["ok"] is True
    assert corrected["result"] == [[0.0], [1.0]]
    assert 'observation["values"]' in SYSTEM


def test_numpy_serialization_error_is_distinct_from_execution():
    failed = execute("import numpy as np\nresult = np.array([1., 2.])")
    assert failed["error"] == "TypeError"
    assert failed["phase"] == "result_serialization"
    assert failed["candidate_line"] is None
    assert "ndarray" in failed["message"]


def test_syntax_error_line_and_message_are_bounded_and_json_safe():
    failed = execute("result = 1\nif True\n    result = 2")
    assert failed["error"] == "SyntaxError"
    assert failed["candidate_line"] == 2
    large = execute("raise ValueError('x' * 10000)")
    assert len(large["message"]) == 600
    json.dumps(large, allow_nan=False)


def test_public_stdout_survives_a_later_analysis_error():
    failed = execute("print('intermediate fit: 0.25')\nraise ValueError('invalid public fit bounds')")
    assert failed["stdout"] == "intermediate fit: 0.25\n"
    assert failed["message"] == "invalid public fit bounds"
