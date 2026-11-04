from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def shipped_cells_path() -> Path:
    return ROOT / "data" / "scored_grid.csv"
