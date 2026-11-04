import struct

import numpy as np
import pytest

from agate_map.__main__ import main
from agate_map.grid import Cell, cell_index, lattice_origin, read_cells
from agate_map.render import (
    MAP_MAX_ZOOM,
    OVERLAY_LABEL,
    PNG_WIDTH_PX,
    RAMP,
    build_html,
    build_png,
    overlay_cells,
    score_array,
    score_rgba,
    web_mercator_image,
)


def test_score_array_puts_each_cell_on_its_lattice_position():
    south_row, west_col, rows, cols = lattice_origin()
    row, col = cell_index(46.41, -119.505)
    values = score_array([Cell(46.41, -119.505, 0.7, 0.0)])
    assert values.shape == (rows, cols)
    assert values[row - south_row, col - west_col] == 0.7
    assert np.isnan(values).sum() == rows * cols - 1


def test_blank_cells_are_transparent_and_a_zero_score_is_not():
    values = np.array([[np.nan, 0.0, 1.0]])
    rgba = score_rgba(values)
    assert rgba[0, 0, 3] == 0
    assert rgba[0, 1, 3] == 255 and rgba[0, 2, 3] == 255
    assert tuple(rgba[0, 1, :3]) == tuple(int(RAMP[0][i : i + 2], 16) for i in (1, 3, 5))
    assert tuple(rgba[0, 2, :3]) == tuple(int(RAMP[-1][i : i + 2], 16) for i in (1, 3, 5))


def test_web_mercator_image_keeps_north_at_the_top_and_cell_edges_sharp():
    south_row, west_col, rows, cols = lattice_origin()
    values = np.full((rows, cols), np.nan)
    values[-1, 0] = 1.0  # the north-west corner cell
    image = web_mercator_image(values)
    assert image.shape[0] == rows * 4 and image.shape[1] == cols
    assert image[0, 0, 3] == 255  # top-left pixel is that cell
    assert image[-1, 0, 3] == 0  # bottom-left is blank
    assert set(np.unique(image[..., 3])) <= {0, 255}


def test_overlay_threshold_is_half_the_cell():
    low = Cell(46.41, -119.505, 0.2, 0.4)  # score 0.2, 40 percent eligible
    high = Cell(46.43, -119.505, 0.0, 0.5)  # score 0, 50 percent eligible
    assert overlay_cells([low, high]) == [high]


def test_html_has_both_layers_no_markers_and_a_capped_zoom(shipped_cells_path, tmp_path):
    cells = read_cells(shipped_cells_path)
    html = build_html(cells, tmp_path / "map.html").read_text(encoding="utf-8")
    assert "L.imageOverlay(" in html
    assert OVERLAY_LABEL in html  # the toggleable overlay layer and its legend entry
    assert html.count("L.polygon(") + html.count("L.geoJson(") + html.count("L.geoJSON(") >= 1
    assert "L.marker(" not in html
    assert f'"maxZoom": {MAP_MAX_ZOOM}' in html or f"maxZoom: {MAP_MAX_ZOOM}" in html
    assert "not a probability" in html and "Blank: outside the Washington geologic map" in html
    assert "bindTooltip" not in html and "bindPopup" not in html  # no per-cell hover or ranking


def test_png_is_1600_wide_and_carries_no_metadata(shipped_cells_path, tmp_path):
    path = build_png(read_cells(shipped_cells_path), tmp_path / "map.png")
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width == PNG_WIDTH_PX and 1000 <= height <= 1400
    assert len(data) > 10_000
    assert b"Exif" not in data and b"GPS" not in data


def test_render_command_builds_both_files(shipped_cells_path, tmp_path):
    assert main(["--cells", str(shipped_cells_path), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "columbia_basin_agate_map.html").stat().st_size > 1_000
    assert (tmp_path / "columbia_basin_agate_map.png").stat().st_size > 10_000


def test_an_empty_grid_still_renders(tmp_path):
    assert build_png([], tmp_path / "empty.png").exists()
    assert build_html([], tmp_path / "empty.html").exists()


def test_render_command_rejects_an_off_lattice_grid(tmp_path):
    bad = tmp_path / "grid.csv"
    bad.write_text("cell_lat,cell_lon,score,eligible_share\n46.4123,-119.4871,0.50,0.00\n", encoding="utf-8")
    with pytest.raises(ValueError):
        main(["--cells", str(bad), "--out", str(tmp_path)])
