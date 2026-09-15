"""Research-control regressions; synthetic rows are not scientific measurements."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cache_grid_integrity", ROOT / ".research/cache_policy/grid.py")
grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)


def records():
    return [dict(name=name, shift=0, dev=0.5, held=float(index), world_count=18, valid_worlds=18)
            for index, (name, _cfg) in enumerate(grid.CELLS)]


def test_heldout_changes_cannot_change_selection_or_break_development_ties():
    rows = records()
    expected = grid.CELLS[:3]
    assert grid._best_cells(list(reversed(rows)), 3) == expected
    for row in rows:
        row["held"] = 100000 - row["held"]
    assert grid._best_cells(rows, 3) == expected
    for row in rows:
        del row["held"]
    assert grid._best_cells(rows, 3) == expected


def test_invalid_grid_cell_is_never_selected_as_scientific_candidate():
    rows = records()
    rows[0].update(dev=1.0, valid_worlds=17)
    assert grid._best_cells(rows, 1) == grid.CELLS[1:2]
    with pytest.raises(ValueError, match="fully valid"):
        grid._best_cells(rows, len(rows))


def test_duplicate_missing_and_unmeasured_rows_fail_closed():
    rows = records()
    with pytest.raises(ValueError, match="exactly one"):
        grid._best_cells(rows[:-1], 1)
    with pytest.raises(ValueError, match="exactly one"):
        grid._best_cells(rows[:-1] + rows[:1], 1)
    rows[0].update(world_count=17, valid_worlds=17)
    with pytest.raises(ValueError, match="measured world validity"):
        grid._best_cells(rows, 1)
    rows[0]["world_count"] = 18
    del rows[0]["valid_worlds"]
    with pytest.raises(ValueError, match="measured world validity"):
        grid._best_cells(rows, 1)


def test_failed_grid_evaluation_restores_seeds_and_discards_shifted_cache():
    worlds = grid.ev.DEVELOPMENT_WORLDS + grid.ev.HELDOUT_WORLDS
    original = [world["seed"] for world in worlds]
    with patch.object(grid.ev, "evaluate", side_effect=RuntimeError("fixture failure")):
        with pytest.raises(RuntimeError, match="fixture failure"):
            grid._run("unused", {}, 3)
    assert [world["seed"] for world in worlds] == original
    assert grid.ev._WORLDS == {}
