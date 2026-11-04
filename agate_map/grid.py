"""The scoring lattice and the scored-grid CSV.

A cell is 0.02 degrees of latitude by 0.03 degrees of longitude, which is
about 2.2 km by 2.3 km at 46.5 N. Nothing finer than a cell is ever computed
or published.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

LAT_STEP = 0.02
LON_STEP = 0.03

# Study area, west to east and south to north (degrees).
WEST, EAST, SOUTH, NORTH = -120.6, -118.2, 45.7, 47.0

# A cell is outlined on the map as collecting-eligible land if at least this
# share of it is eligible land.
OVERLAY_MIN_SHARE = 0.5

FIELDS = ("cell_lat", "cell_lon", "score", "eligible_share")

_KM_PER_DEG = 111.32


@dataclass(frozen=True)
class Cell:
    lat: float  # cell center
    lon: float  # cell center
    score: float  # relative geology score of the cell, 0 to 1
    eligible_share: float  # share of the cell on land where casual collecting is generally allowed

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(south, west, north, east) edges of the cell."""
        return (
            round(self.lat - LAT_STEP / 2, 6),
            round(self.lon - LON_STEP / 2, 6),
            round(self.lat + LAT_STEP / 2, 6),
            round(self.lon + LON_STEP / 2, 6),
        )


def cell_size_km(lat: float) -> tuple[float, float]:
    """Cell height and width in kilometers at the given latitude."""
    return (
        LAT_STEP * _KM_PER_DEG,
        LON_STEP * _KM_PER_DEG * math.cos(math.radians(lat)),
    )


def cell_index(lat: float, lon: float) -> tuple[int, int]:
    """Lattice row and column of the cell that holds a point."""
    # round() first so a point exactly on an edge does not fall into the
    # neighboring cell because of floating-point error.
    return (
        math.floor(round(lat / LAT_STEP, 9)),
        math.floor(round(lon / LON_STEP, 9)),
    )


def cell_center(row: int, col: int) -> tuple[float, float]:
    return (
        round((row + 0.5) * LAT_STEP, 6),
        round((col + 0.5) * LON_STEP, 6),
    )


def lattice() -> list[tuple[int, int]]:
    """Every (row, col) whose cell lies inside the study area."""
    south_row, west_col = cell_index(SOUTH, WEST)
    north_row, east_col = cell_index(NORTH, EAST)
    return [
        (row, col)
        for row in range(south_row, north_row)
        for col in range(west_col, east_col)
    ]


def lattice_origin() -> tuple[int, int, int, int]:
    """(south_row, west_col, rows, cols) of the study-area lattice."""
    south_row, west_col = cell_index(SOUTH, WEST)
    north_row, east_col = cell_index(NORTH, EAST)
    return south_row, west_col, north_row - south_row, east_col - west_col


def lattice_extent() -> tuple[float, float, float, float]:
    """(south, west, north, east) edges of the whole lattice, in degrees."""
    south_row, west_col, rows, cols = lattice_origin()
    return (
        round(south_row * LAT_STEP, 6),
        round(west_col * LON_STEP, 6),
        round((south_row + rows) * LAT_STEP, 6),
        round((west_col + cols) * LON_STEP, 6),
    )


def write_cells(path: str | Path, cells) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FIELDS)
        for cell in cells:
            writer.writerow(
                [f"{cell.lat:.6f}", f"{cell.lon:.6f}", f"{cell.score:.2f}", f"{cell.eligible_share:.2f}"]
            )


def read_cells(path: str | Path) -> list[Cell]:
    """Read cells and check that each one sits on the lattice."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path}: columns must be exactly {', '.join(FIELDS)}")
        cells = []
        seen = set()
        for number, row in enumerate(reader, start=2):
            lat, lon = float(row["cell_lat"]), float(row["cell_lon"])
            score, share = float(row["score"]), float(row["eligible_share"])
            for name, value in (("score", score), ("eligible_share", share)):
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"{path}:{number}: {name} must be between 0 and 1")
            index = cell_index(lat, lon)
            expected = cell_center(*index)
            if abs(expected[0] - lat) > 1e-6 or abs(expected[1] - lon) > 1e-6:
                raise ValueError(
                    f"{path}:{number}: ({lat}, {lon}) is not a cell center on the "
                    f"{LAT_STEP} x {LON_STEP} degree lattice"
                )
            if index in seen:
                raise ValueError(f"{path}:{number}: duplicate cell ({lat}, {lon})")
            seen.add(index)
            cells.append(Cell(lat, lon, score, share))
    return cells
