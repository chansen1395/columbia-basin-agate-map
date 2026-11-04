import json

import pytest

from agate_map.grid import (
    FIELDS,
    LAT_STEP,
    LON_STEP,
    Cell,
    cell_center,
    cell_index,
    cell_size_km,
    lattice,
    lattice_extent,
    lattice_origin,
    read_cells,
    write_cells,
)


def test_cells_are_at_least_2_km_across_the_study_area():
    for lat in (45.7, 46.0, 46.5, 47.0):
        height, width = cell_size_km(lat)
        assert min(height, width) >= 2.0


def test_lattice_covers_the_study_area_without_gaps():
    cells = lattice()
    assert len(cells) == 65 * 80
    assert len(set(cells)) == len(cells)
    _, _, rows, cols = lattice_origin()
    assert rows * cols == len(cells)


def test_lattice_extent_is_the_study_area():
    assert lattice_extent() == (45.7, -120.6, 47.0, -118.2)


def test_center_and_index_agree():
    row, col = cell_index(46.4, -119.5)
    lat, lon = cell_center(row, col)
    assert cell_index(lat, lon) == (row, col)
    # A point exactly on a latitude edge belongs to the cell above it.
    assert (lat, lon) == (46.41, -119.505)


def test_cell_bounds_span_one_step():
    south, west, north, east = Cell(46.41, -119.505, 0.5, 1.0).bounds
    assert round(north - south, 6) == LAT_STEP
    assert round(east - west, 6) == LON_STEP


def test_round_trip(tmp_path):
    path = tmp_path / "grid.csv"
    cells = [Cell(46.41, -119.505, 0.5, 0.75), Cell(46.43, -119.505, 0.0, 1.0)]
    write_cells(path, cells)
    assert read_cells(path) == cells


def test_read_rejects_coordinates_off_the_lattice(tmp_path):
    path = tmp_path / "grid.csv"
    path.write_text("cell_lat,cell_lon,score,eligible_share\n46.4123,-119.4871,0.50,0.00\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a cell center"):
        read_cells(path)


def test_read_rejects_extra_or_reordered_columns(tmp_path):
    path = tmp_path / "grid.csv"
    path.write_text(
        "name,cell_lat,cell_lon,score,eligible_share\nsomewhere,46.41,-119.505,0.50,0.00\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="columns must be exactly"):
        read_cells(path)


@pytest.mark.parametrize("row", ["46.41,-119.505,1.50,0.0", "46.41,-119.505,0.5,-0.1"])
def test_read_rejects_values_outside_zero_to_one(tmp_path, row):
    path = tmp_path / "grid.csv"
    path.write_text("cell_lat,cell_lon,score,eligible_share\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="between 0 and 1"):
        read_cells(path)


def test_read_rejects_a_repeated_cell(tmp_path):
    path = tmp_path / "grid.csv"
    path.write_text(
        "cell_lat,cell_lon,score,eligible_share\n46.41,-119.505,0.5,0.0\n46.41,-119.505,0.6,0.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        read_cells(path)


def test_shipped_grid_is_valid(shipped_cells_path):
    assert shipped_cells_path.read_text(encoding="utf-8").splitlines()[0] == ",".join(FIELDS)
    cells = read_cells(shipped_cells_path)
    assert 0.5 * len(lattice()) < len(cells) <= len(lattice())
    assert any(cell.score > 0 for cell in cells)


def test_build_info_matches_the_shipped_grid(shipped_cells_path):
    info = json.loads((shipped_cells_path.parent / "build_info.json").read_text(encoding="utf-8"))
    cells = read_cells(shipped_cells_path)
    assert info["cells_in_study_area"] == len(lattice())
    assert info["cells_scored"] == len(cells)
    assert info["cells_scored"] + info["cells_blank_outside_geologic_map"] == info["cells_in_study_area"]
    assert info["cells_score_above_0"] == sum(1 for c in cells if c.score > 0)
    assert info["cells_score_at_least_0.5"] == sum(1 for c in cells if c.score >= 0.5)
    assert info["cells_with_any_eligible_land"] == sum(1 for c in cells if c.eligible_share > 0)
    assert info["cells_outlined_as_eligible"] == sum(1 for c in cells if c.eligible_share >= 0.5)
    assert info["cell_degrees"] == {"lat": LAT_STEP, "lon": LON_STEP}
    shares = info["favorable_geology_by_land_class_percent"]
    assert sum(shares.values()) == pytest.approx(100, abs=0.5)
