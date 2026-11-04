"""Score every lattice cell from the geologic map.

A cell's score is the area-weighted mean of the unit weights over the part of
the cell that the geologic map covers:

    score = sum(weight(unit) * area of unit in the cell) / area of the cell the map covers

A cell is scored only if the map covers at least MIN_COVERED_SHARE of it. The
Washington map stops at the state line, so cells in Oregon get no score, and
they are left blank rather than scored 0.

Each scored cell also records how much of it is collecting-eligible land (see
landmask.py). That share does not change the score. Areas are computed in
degrees. Over one 2 km cell the ratio is the same as in square kilometers.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grid import Cell, cell_center, lattice
from .units import weight_of

MIN_COVERED_SHARE = 0.5


@dataclass
class GridResult:
    cells: list[Cell]  # cells covered by the geologic map
    total_cells: int  # cells in the study area
    no_geology: int  # cells the geologic map does not cover (blank on the map)


def score_grid(geology_features, eligible, min_covered: float = MIN_COVERED_SHARE) -> GridResult:
    import shapely
    from shapely.geometry import box, shape
    from shapely.strtree import STRtree

    geoms, weights = [], []
    for feature in geology_features:
        geom = shape(feature["geometry"])
        geoms.append(geom if geom.is_valid else geom.buffer(0))
        weights.append(weight_of(feature["properties"].get("MAP_UNIT_100K")))
    tree = STRtree(geoms)

    cells: list[Cell] = []
    no_geology = 0
    cell_list = lattice()
    for row, col in cell_list:
        lat, lon = cell_center(row, col)
        south, west, north, east = Cell(lat, lon, 0.0, 0.0).bounds
        cell_area = (east - west) * (north - south)

        covered = weighted = 0.0
        for index in tree.query(box(west, south, east, north)):
            area = shapely.clip_by_rect(geoms[index], west, south, east, north).area
            covered += area
            weighted += weights[index] * area
        if covered / cell_area < min_covered:
            no_geology += 1
            continue

        eligible_area = shapely.clip_by_rect(eligible, west, south, east, north).area
        cells.append(
            Cell(
                lat,
                lon,
                round(min(1.0, weighted / covered), 2),
                round(min(1.0, eligible_area / cell_area), 2),
            )
        )
    return GridResult(cells, len(cell_list), no_geology)
