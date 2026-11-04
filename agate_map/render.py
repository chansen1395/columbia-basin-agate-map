"""Render the scored grid as an interactive HTML map and a static PNG.

The main layer is a heat map of the relative geology score, one block per
lattice cell (about 2.2 km). The second layer outlines the cells that are mostly
collecting-eligible land. Cells outside the Washington geologic map are blank.
No cell is picked out, ranked or labeled, and the interactive map has no
markers. The zoom is capped so the base map cannot be pushed far past the
resolution of the data.
"""

from __future__ import annotations

import math
from pathlib import Path

from .grid import (
    EAST,
    LAT_STEP,
    NORTH,
    OVERLAY_MIN_SHARE,
    SOUTH,
    WEST,
    Cell,
    cell_index,
    lattice_extent,
    lattice_origin,
)

# Orientation labels only. These are towns, not collecting sites.
# name: (lat, lon, label offset x, label offset y, horizontal alignment)
CITIES = {
    "Yakima": (46.602, -120.506, 5, 4, "left"),
    "Richland": (46.286, -119.285, -5, 4, "right"),
    "Kennewick": (46.211, -119.137, 5, -10, "left"),
    "Pasco": (46.240, -119.101, 5, 4, "left"),
    "Walla Walla": (46.065, -118.343, -5, 4, "right"),
    "Hermiston": (45.840, -119.290, 5, 4, "left"),
}

# One-hue sequential ramp (blue), light to dark.
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#184f95", "#0d366b"]
OVERLAY_COLOR = "#eb6834"  # outline for collecting-eligible land

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"

# USGS The National Map tiles: public domain, no key needed.
BASEMAP_URL = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}"
MAP_MIN_ZOOM = 6
MAP_MAX_ZOOM = 10

TITLE = "Southern Columbia Basin agate geology score"
SCORE_LABEL = "Relative geology score (assigned, 0 to 1)"
OVERLAY_LABEL = "Land where casual collecting is generally allowed (check before you collect)"
BLANK_LABEL = "Blank: outside the Washington geologic map"
STUDY_AREA = "Study area: 45.7 to 47.0 N, 120.6 to 118.2 W"
NOTE = (
    f"{STUDY_AREA}. A relative geology score, not a probability. Each block is a cell of about 2.2 km. "
    "Most favorable geology is on private, tribal, refuge and Hanford land, where collecting is not "
    "generally allowed. Collecting rules vary and change, so check with the land manager before you collect."
)

PNG_WIDTH_PX = 1600


def _colormap():
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list("score", RAMP)


def score_array(cells: list[Cell]):
    """Scores on the study-area lattice, rows running south to north, NaN where blank."""
    import numpy as np

    south_row, west_col, rows, cols = lattice_origin()
    values = np.full((rows, cols), np.nan)
    for cell in cells:
        row, col = cell_index(cell.lat, cell.lon)
        values[row - south_row, col - west_col] = cell.score
    return values


def overlay_cells(cells: list[Cell]) -> list[Cell]:
    """Cells that are mostly collecting-eligible land."""
    return [cell for cell in cells if cell.eligible_share >= OVERLAY_MIN_SHARE]


def score_rgba(values):
    """RGBA bytes for a score array. Blank cells are fully transparent."""
    import numpy as np

    rgba = _colormap()(np.nan_to_num(values, nan=0.0))
    rgba[np.isnan(values)] = 0.0
    return (rgba * 255).round().astype("uint8")


def _mercator_y(lat: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def web_mercator_image(values, oversample: int = 4):
    """RGBA image of the lattice for a Leaflet overlay, north at the top.

    Leaflet draws image overlays in Web Mercator, so rows are resampled by
    nearest neighbor to even Mercator steps. That keeps cell edges sharp.
    """
    import numpy as np

    south, _, north, _ = lattice_extent()
    rgba = score_rgba(values)
    rows = rgba.shape[0]
    out_rows = rows * oversample
    y_top, y_bottom = _mercator_y(north), _mercator_y(south)
    ys = y_top + (np.arange(out_rows) + 0.5) / out_rows * (y_bottom - y_top)
    lats = np.degrees(2 * np.arctan(np.exp(ys)) - math.pi / 2)
    source = np.clip(np.floor((lats - south) / LAT_STEP).astype(int), 0, rows - 1)
    return rgba[source]


def build_html(cells: list[Cell], path: str | Path) -> Path:
    import folium
    from folium.raster_layers import ImageOverlay

    fmap = folium.Map(
        location=[(SOUTH + NORTH) / 2, (WEST + EAST) / 2],
        zoom_start=8,
        min_zoom=MAP_MIN_ZOOM,
        max_zoom=MAP_MAX_ZOOM,
        tiles=None,
        control_scale=True,
    )
    folium.TileLayer(
        tiles=BASEMAP_URL,
        attr="USGS The National Map",
        name="USGS Topo base map",
        min_zoom=MAP_MIN_ZOOM,
        max_zoom=MAP_MAX_ZOOM,
    ).add_to(fmap)

    south, west, north, east = lattice_extent()
    ImageOverlay(
        image=web_mercator_image(score_array(cells)),
        bounds=[[south, west], [north, east]],
        opacity=0.75,
        pixelated=True,
        name="Relative geology score (not a probability)",
    ).add_to(fmap)

    outlined = overlay_cells(cells)
    features = []
    for cell in outlined:
        s, w, n, e = cell.bounds
        features.append(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]},
            }
        )
    folium.GeoJson(
        {"type": "FeatureCollection", "features": features},
        name=OVERLAY_LABEL,
        style_function=lambda _feature: {"color": OVERLAY_COLOR, "weight": 2, "fill": False},
    ).add_to(fmap)

    fmap.get_root().html.add_child(
        folium.Element(
            f"""
<div style="position:fixed; top:10px; left:50%; transform:translateX(-50%); z-index:9999;
  background:rgba(255,255,255,0.94); padding:8px 16px; border:1px solid #ccc; border-radius:6px;
  font-family:sans-serif; font-size:14px; font-weight:bold; color:{INK}; max-width:92vw;">
  {TITLE}
</div>
<div style="position:fixed; bottom:24px; left:12px; z-index:9999; background:rgba(255,255,255,0.94);
  padding:10px 14px; border:1px solid #ccc; border-radius:6px; font-family:sans-serif;
  font-size:12px; color:{INK_SECONDARY}; max-width:340px; line-height:1.4;">
  <b style="color:{INK}">{SCORE_LABEL}</b><br/>
  <span style="display:inline-block;width:100%;height:10px;border-radius:2px;
    background:linear-gradient(to right,{RAMP[0]},{RAMP[3]},{RAMP[7]});"></span><br/>
  <span style="float:left">0</span><span style="float:right">1</span><br style="clear:both"/>
  <span style="display:inline-block;width:12px;height:12px;border:2px solid {OVERLAY_COLOR};
    box-sizing:border-box;"></span> {OVERLAY_LABEL}<br/>
  <span style="font-size:11px">{BLANK_LABEL}.<br/>{NOTE}</span>
</div>
"""
        )
    )
    folium.LayerControl(collapsed=False).add_to(fmap)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(path))
    return path


def build_png(cells: list[Cell], path: str | Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    cmap = _colormap().with_extremes(bad=(0.0, 0.0, 0.0, 0.0))

    dpi = 150
    fig, ax = plt.subplots(figsize=(PNG_WIDTH_PX / dpi, 8.0), dpi=dpi)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    south, west, north, east = lattice_extent()
    image = ax.imshow(
        np.ma.masked_invalid(score_array(cells)),
        cmap=cmap,
        vmin=0.0,
        vmax=1.0,
        extent=[west, east, south, north],
        origin="lower",
        interpolation="nearest",
        aspect="auto",
        zorder=2,
    )

    for cell in overlay_cells(cells):
        s, w, n, e = cell.bounds
        ax.add_patch(
            Rectangle((w, s), e - w, n - s, facecolor="none", edgecolor=OVERLAY_COLOR, linewidth=1.3, zorder=4)
        )

    for name, (lat, lon, dx, dy, align) in CITIES.items():
        ax.plot(lon, lat, marker="o", markersize=4, color=INK, markeredgecolor=SURFACE, zorder=5)
        ax.annotate(
            name,
            (lon, lat),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=align,
            fontsize=9,
            color=INK,
            zorder=5,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": SURFACE, "edgecolor": "none", "alpha": 0.75},
        )

    ax.set_xlim(WEST, EAST)
    ax.set_ylim(SOUTH, NORTH)
    ax.set_aspect(1.0 / np.cos(np.radians((SOUTH + NORTH) / 2)))
    ax.set_xticks(np.arange(-120.5, -118.0, 0.5))
    ax.set_yticks(np.arange(45.75, 47.0, 0.25))
    ax.grid(color=GRID, linewidth=0.6, zorder=1)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9, length=0)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.set_xlabel("Longitude (degrees west)", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("Latitude (degrees north)", color=INK_SECONDARY, fontsize=10)
    ax.xaxis.set_major_formatter(lambda x, _: f"{abs(x):.1f}")

    ax.set_title(TITLE, loc="left", color=INK, fontsize=15, fontweight="bold", pad=10)

    colorbar = fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    colorbar.set_label(SCORE_LABEL, color=INK_SECONDARY, fontsize=10)
    colorbar.ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    colorbar.outline.set_edgecolor(GRID)

    ax.legend(
        handles=[
            Line2D([0], [0], color=OVERLAY_COLOR, linewidth=0, marker="s", markersize=9,
                   markerfacecolor="none", markeredgecolor=OVERLAY_COLOR, markeredgewidth=1.5,
                   label=OVERLAY_LABEL),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.11),
        fontsize=9,
        frameon=False,
        labelcolor=INK,
    )

    fig.text(
        0.012,
        0.012,
        f"{BLANK_LABEL}. {STUDY_AREA}.\n"
        "A relative geology score, not a probability. Each block is a cell of about 2.2 km.\n"
        "Most favorable geology is on private, tribal, refuge and Hanford land, where collecting is not\n"
        "generally allowed. Collecting rules vary and change: check with the land manager.",
        color=INK_SECONDARY,
        fontsize=9,
        va="bottom",
    )
    fig.tight_layout(rect=(0, 0.11, 1, 1))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor(), metadata={"Software": None})
    plt.close(fig)
    return path
