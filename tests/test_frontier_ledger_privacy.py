"""Raw frontier receipts remain private even under a permissive operator umask."""
import os
import stat
from pathlib import Path

import pytest

from sle.evaluation_ledger import EvaluationLedger
from sle.frontier import FrontierLedger
from test_frontier_families import _record, _wave


def test_new_raw_ledger_permissions_ignore_permissive_umask(tmp_path):
    previous = os.umask(0o022)
    try:
        ledger = FrontierLedger(tmp_path / "canonical")
        evidence = EvaluationLedger(tmp_path / "run")
        _record(ledger, evidence, _wave(), artifact="d" * 64,
                records=[{"cell_id": "solver", "canonical_id": "artifact", "value": 15.0}])
    finally:
        os.umask(previous)
    assert stat.S_IMODE(ledger.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(ledger.event_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(ledger.lock_path.stat().st_mode) == 0o600
    paths = list(ledger.event_root.glob("*.json"))
    assert len(paths) == 1
    assert stat.S_IMODE(paths[0].stat().st_mode) == 0o600
    assert '"evaluation_receipt"' in paths[0].read_text()


def test_raw_ledger_cannot_be_created_inside_repository(tmp_path):
    (tmp_path / ".git").write_text("gitdir: elsewhere\n")
    with pytest.raises(ValueError, match="outside a git repository"):
        FrontierLedger(tmp_path / "raw")
    assert not (tmp_path / "raw").exists()


def test_existing_public_ledger_directory_is_rejected(tmp_path):
    ledger = FrontierLedger(tmp_path)
    ledger.root.mkdir(mode=0o755)
    ledger.root.chmod(0o755)
    evidence = EvaluationLedger(tmp_path / "run")
    with pytest.raises(ValueError, match="owner-only"):
        _record(ledger, evidence, _wave(), artifact="d" * 64,
                records=[{"cell_id": "solver", "canonical_id": "artifact", "value": 15.0}])
    assert not ledger.event_root.exists()
