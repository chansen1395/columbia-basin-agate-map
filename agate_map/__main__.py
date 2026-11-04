"""Build the map, or rebuild the scored grid from the public services.

    python -m agate_map            draw the map from data/scored_grid.csv
    python -m agate_map rebuild    download the data, rescore the grid, then draw the map
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .grid import (
    EAST,
    LAT_STEP,
    LON_STEP,
    NORTH,
    OVERLAY_MIN_SHARE,
    SOUTH,
    WEST,
    cell_size_km,
    read_cells,
    write_cells,
)
from .render import build_html, build_png, overlay_cells

STEM = "columbia_basin_agate_map"


def _km2(geometry) -> float:
    """Area in square kilometers of the part of a geometry inside the study area."""
    import shapely

    inside = shapely.clip_by_rect(geometry, WEST, SOUTH, EAST, NORTH)
    return inside.area * 111.32**2 * math.cos(math.radians((SOUTH + NORTH) / 2))


def _render(cells, out: Path) -> None:
    height, width = cell_size_km(46.5)
    print(f"{len(cells)} cells (each about {height:.1f} x {width:.1f} km)")
    print(f"wrote {build_html(cells, out / (STEM + '.html'))}")
    print(f"wrote {build_png(cells, out / (STEM + '.png'))}")


def _rebuild(args) -> None:
    from . import fetch
    from .landclass import land_class_shares
    from .landmask import build_eligible, candidate_land
    from .score import MIN_COVERED_SHARE, score_grid

    print("downloading geology, PAD-US and BLM Surface Management Agency polygons ...")
    geology = fetch.fetch_geology(args.raw, args.refresh)
    padus = fetch.fetch_padus(args.raw, args.refresh)
    sma = fetch.fetch_sma(args.raw, args.refresh)
    print(f"  {len(geology)} geologic polygons, {len(padus)} PAD-US polygons, {len(sma)} SMA polygons")

    eligible = build_eligible(padus, sma)
    result = score_grid(geology, eligible)
    cells = result.cells
    write_cells(args.cells, cells)

    info = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "cell_degrees": {"lat": LAT_STEP, "lon": LON_STEP},
        "min_geology_coverage": MIN_COVERED_SHARE,
        "overlay_min_eligible_share": OVERLAY_MIN_SHARE,
        "cells_in_study_area": result.total_cells,
        "cells_scored": len(cells),
        "cells_blank_outside_geologic_map": result.no_geology,
        "cells_score_above_0": sum(1 for c in cells if c.score > 0),
        "cells_score_at_least_0.5": sum(1 for c in cells if c.score >= 0.5),
        "cells_with_any_eligible_land": sum(1 for c in cells if c.eligible_share > 0),
        "cells_outlined_as_eligible": len(overlay_cells(cells)),
        "cells_score_at_least_0.5_and_outlined": sum(
            1 for c in overlay_cells(cells) if c.score >= 0.5
        ),
        "blm_and_forest_land_km2": round(_km2(candidate_land(padus, sma))),
        "eligible_land_km2": round(_km2(eligible)),
        "favorable_geology_by_land_class_percent": land_class_shares(geology, padus, eligible),
        "polygons_downloaded": {"geology": len(geology), "pad_us": len(padus), "blm_sma": len(sma)},
        "geology_edition": fetch.geology_version(),
    }
    args.cells.with_name("build_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(
        f"{result.total_cells} cells in the study area; {len(cells)} scored; "
        f"{result.no_geology} blank (outside the geologic map); "
        f"{info['cells_score_at_least_0.5']} score 0.5 or more; "
        f"{info['cells_outlined_as_eligible']} outlined as eligible land"
    )
    print(f"wrote {args.cells}")
    _render(cells, args.out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", nargs="?", choices=("render", "rebuild"), default="render")
    parser.add_argument("--cells", type=Path, default=Path("data/scored_grid.csv"))
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--raw", type=Path, default=Path("data/raw"), help="download cache (rebuild only)")
    parser.add_argument("--refresh", action="store_true", help="ignore the download cache (rebuild only)")
    args = parser.parse_args(argv)

    if args.command == "rebuild":
        _rebuild(args)
    else:
        _render(read_cells(args.cells), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
