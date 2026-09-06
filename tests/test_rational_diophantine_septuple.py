"""Binary research-object verification, including exact smaller controls."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "challenges/Mathematics/RationalDiophantineSeptuple"
CLASSIC = ["11/192", "35/192", "155/27", "512/27", "1235/48", "180873/16"]
ALMOST = ["243/560", "1147/5040", "1100/63", "7820/567", "95/112", "38269/6480", "196/45"]


def checker():
    path = TASK / "verify.py"
    assert path.is_file(), "Missing data-only exact challenge verifier"
    spec = importlib.util.spec_from_file_location("septuple_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fermat_quadruple_checks_only_six_off_diagonal_pairs():
    result = checker().verify(["1", "3", "8", "120"], expected_count=4)
    assert result["schema_valid"] and result["success"]
    assert result["pairs_satisfied"] == result["total_pairs"] == 6


def test_primary_positive_sextuple_satisfies_all_fifteen_pairs_but_not_target():
    verifier = checker()
    result = verifier.verify(CLASSIC, expected_count=6)
    assert result["schema_valid"] and result["success"]
    assert result["pairs_satisfied"] == result["total_pairs"] == 15
    assert not verifier.verify(CLASSIC)["success"]
    example = TASK / "examples/sextuple.json"
    assert example.is_file(), "Missing sourced positive sextuple example"
    assert json.loads(example.read_text()) == CLASSIC


def test_twenty_of_twenty_one_is_failure_without_continuous_score():
    result = checker().verify(ALMOST)
    assert result["schema_valid"] and not result["success"]
    assert result["pairs_satisfied"] == 20 and result["total_pairs"] == 21
    assert "score" not in result and "combined_score" not in result


@pytest.mark.parametrize("value", [
    "0", "-1", "-1/2", "1/-2", "1/0", "0/3", "1.0", "1e2", "1+2", "2**4",
    "nan", "NaN", "Infinity", "1/2/3", "", " 1", "+1", "１", 1, 1.0, True, None,
    "9" * 10000, str(1 << 2048), "1/" + str(1 << 2048),
])
def test_invalid_values_rejected_before_pair_arithmetic(value):
    result = checker().verify(CLASSIC + [value])
    assert not result["schema_valid"] and not result["success"]
    assert result["pairs_satisfied"] == 0
    json.dumps(result, allow_nan=False)


def test_equivalent_fractions_cannot_make_distinct_entries():
    result = checker().verify(["1/2", "2/4", "1", "3", "8", "120", "2"])
    assert not result["schema_valid"] and not result["success"]


@pytest.mark.parametrize("data", [{"rationals": CLASSIC}, [], tuple(CLASSIC), None, "1,3,8,120"])
def test_non_list_schema_and_wrong_count_are_rejected(data):
    result = checker().verify(data)
    assert not result["schema_valid"] and not result["success"]


def test_denominator_square_is_checked_and_rationals_are_reduced():
    verifier = checker()
    assert verifier.verify(["2/4", "5/2"], expected_count=2)["success"]  # 9/4
    assert not verifier.verify(["1/2", "2/3"], expected_count=2)["success"]  # 4/3
    assert not verifier.verify(["1", "1/4"], expected_count=2)["success"]  # 5/4


def test_bit_limit_applies_to_raw_components_before_reduction():
    oversized = str(1 << 2048)
    result = checker().verify([oversized + "/" + oversized], expected_count=1)
    assert not result["schema_valid"]
    permitted = str((1 << 2048) - 1)
    assert checker().verify([permitted], expected_count=1)["schema_valid"]


@pytest.mark.parametrize("payload, status", [
    (json.dumps(CLASSIC), "invalid"), (json.dumps(ALMOST), "not_found"),
    (json.dumps(CLASSIC + ["0"]), "invalid"), ("[NaN]", "invalid"),
    ("__import__('os').system('false')", "invalid"), ("[", "invalid"),
])
def test_cli_accepts_json_data_only_and_exit_matches_failure(payload, status):
    checker()
    completed = subprocess.run([sys.executable, str(TASK / "verify.py")], input=payload,
                               capture_output=True, text=True)
    result = json.loads(completed.stdout)
    assert completed.returncode != 0 and not result["success"]
    assert result["status"] == status


def test_cli_file_input_and_repeatability(tmp_path):
    checker()
    submission = tmp_path / "seven.json"
    submission.write_text(json.dumps(ALMOST))
    command = [sys.executable, str(TASK / "verify.py"), str(submission)]
    first = subprocess.run(command, capture_output=True, text=True)
    second = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == second.returncode == 1
    assert first.stdout == second.stdout and json.loads(first.stdout)["pairs_satisfied"] == 20


def test_cli_oversized_document_is_rejected():
    checker()
    completed = subprocess.run([sys.executable, str(TASK / "verify.py")], input=" " * 100000,
                               capture_output=True, text=True)
    result = json.loads(completed.stdout)
    assert completed.returncode == 2 and not result["schema_valid"]
