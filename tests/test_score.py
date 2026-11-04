import pytest
from shapely.geometry import box, mapping

from agate_map.grid import Cell, cell_center, cell_index
from agate_map.score import score_grid

# One real lattice cell, so the cell edges are exact.
ROW, COL = cell_index(46.41, -119.485)
LAT, LON = cell_center(ROW, COL)
SOUTH, WEST, NORTH, EAST = Cell(LAT, LON, 0.0, 0.0).bounds
MIDDLE = (WEST + EAST) / 2
WHOLE = box(WEST, SOUTH, EAST, NORTH)
NOWHERE = box(10, 10, 11, 11)  # no eligible land in the study area


def unit(code, geometry):
    return {"type": "Feature", "properties": {"MAP_UNIT_100K": code}, "geometry": mapping(geometry)}


def scored(geology, eligible=NOWHERE):
    result = score_grid(geology, eligible)
    return {(c.lat, c.lon): c for c in result.cells}, result


def test_score_is_the_area_weighted_mean_of_the_unit_weights():
    geology = [
        unit("PLMcg(r)", box(WEST, SOUTH, MIDDLE, NORTH)),  # weight 1.0, half the cell
        unit("Qa", box(MIDDLE, SOUTH, EAST, NORTH)),  # weight 0.25, other half
    ]
    cells, result = scored(geology)
    assert list(cells) == [(LAT, LON)] and result.total_cells == 5200
    assert cells[(LAT, LON)].score == pytest.approx(0.625, abs=0.01)


def test_the_whole_cell_is_scored_whether_or_not_it_is_eligible_land():
    geology = [unit("PLMcg(r)", WHOLE)]
    cells, _ = scored(geology, eligible=WHOLE)
    assert cells[(LAT, LON)].score == 1.0
    assert cells[(LAT, LON)].eligible_share == 1.0
    cells, _ = scored(geology, eligible=NOWHERE)
    assert cells[(LAT, LON)].score == 1.0
    assert cells[(LAT, LON)].eligible_share == 0.0


def test_eligible_share_is_the_share_of_the_cell():
    geology = [unit("Ql", WHOLE)]
    eligible = box(MIDDLE, SOUTH, EAST, NORTH)
    cells, _ = scored(geology, eligible)
    assert cells[(LAT, LON)].eligible_share == 0.5
    assert cells[(LAT, LON)].score == 0.0


def test_unknown_units_score_zero():
    cells, _ = scored([unit("not-a-unit", WHOLE)])
    assert cells[(LAT, LON)].score == 0.0


def test_a_cell_outside_the_geologic_map_is_left_out_not_scored_zero():
    cells, result = scored([])
    assert cells == {}
    assert result.no_geology == result.total_cells == 5200


def test_a_cell_the_map_covers_less_than_half_of_is_left_out():
    geology = [unit("PLMcg(r)", box(WEST, SOUTH, WEST + (EAST - WEST) * 0.4, NORTH))]
    cells, _ = scored(geology)
    assert cells == {}


def test_the_score_divides_by_the_covered_area_only():
    # The map covers the western 60 percent of the cell, all of it weight 1.0.
    geology = [unit("PLMcg(r)", box(WEST, SOUTH, WEST + (EAST - WEST) * 0.6, NORTH))]
    cells, _ = scored(geology)
    assert cells[(LAT, LON)].score == 1.0


def test_every_covered_cell_gets_a_score():
    big = box(-120.6, 45.7, -118.2, 47.0)
    result = score_grid([unit("Qfg", big)], NOWHERE)
    assert len(result.cells) == result.total_cells == 5200
    assert {c.score for c in result.cells} == {0.5}
