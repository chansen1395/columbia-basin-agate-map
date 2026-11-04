"""Download the geologic map and the land-status layers for the study area.

Everything comes from public ArcGIS REST services. The raw downloads are
cached under data/raw/ (not committed) so a rebuild can be repeated without
asking the services again. Pass refresh=True to download them afresh.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .grid import EAST, NORTH, SOUTH, WEST

GEOLOGY_URL = (
    "https://gis.dnr.wa.gov/site1/rest/services/Public_Geology/"
    "100K_Surface_Geology_WA_GeMS/FeatureServer/11"
)
PADUS_URL = (
    "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/"
    "Manager_Name_PADUS/FeatureServer/0"
)
BLM_SMA_URL = (
    "https://gis.blm.gov/arcgis/rest/services/lands/"
    "BLM_Natl_SMA_LimitedScale/MapServer/1"
)

BBOX = f"{WEST},{SOUTH},{EAST},{NORTH}"
# Polygons are simplified by the server to about 55 m. That is well inside a 2 km cell.
SIMPLIFY_DEGREES = 0.0005
USER_AGENT = "columbia-basin-agate-map (build-time data download)"


def _get(url: str, params: dict, attempts: int = 4) -> dict:
    import requests

    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                url, params=params, timeout=300, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(f"{url}: {payload['error']}")
            return payload
        except (requests.RequestException, RuntimeError, ValueError) as error:
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"download failed after {attempts} tries: {last_error}")


def query_features(layer_url: str, where: str, out_fields: str, batch: int = 200) -> list[dict]:
    """Every feature in the study area that matches `where`, as GeoJSON features.

    The object IDs are listed first and the features are then fetched in
    batches by ID, so no feature is skipped or repeated by paging. The count is
    checked against the ID list at the end.
    """
    area = {
        "geometry": BBOX,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "where": where,
    }
    listing = _get(layer_url + "/query", {"f": "json", "returnIdsOnly": "true", **area})
    ids = sorted(listing.get("objectIds") or [])
    features: list[dict] = []
    for start in range(0, len(ids), batch):
        chunk = ids[start : start + batch]
        payload = _get(
            layer_url + "/query",
            {
                "f": "geojson",
                "objectIds": ",".join(str(i) for i in chunk),
                "outFields": out_fields,
                "outSR": 4326,
                "returnGeometry": "true",
                "maxAllowableOffset": SIMPLIFY_DEGREES,
            },
        )
        features.extend(payload.get("features", []))
    if len(features) != len(ids):
        raise RuntimeError(f"{layer_url}: expected {len(ids)} features, got {len(features)}")
    return features


def _cached(path: Path, refresh: bool, loader):
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = loader()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def fetch_geology(raw_dir: Path, refresh: bool = False) -> list[dict]:
    return _cached(
        raw_dir / "geology.json",
        refresh,
        lambda: query_features(GEOLOGY_URL, "1=1", "MAP_UNIT_100K"),
    )


def fetch_padus(raw_dir: Path, refresh: bool = False) -> list[dict]:
    return _cached(
        raw_dir / "padus.json",
        refresh,
        lambda: query_features(
            PADUS_URL,
            "1=1",
            "Category,Mang_Type,Mang_Name,Unit_Nm,Des_Tp,Pub_Access,GAP_Sts",
            batch=100,
        ),
    )


def fetch_sma(raw_dir: Path, refresh: bool = False) -> list[dict]:
    return _cached(
        raw_dir / "sma.json",
        refresh,
        lambda: query_features(
            BLM_SMA_URL,
            "ADMIN_AGENCY_CODE IN ('BLM','USFS')",
            "ADMIN_AGENCY_CODE",
            batch=20,
        ),
    )


def geology_version() -> str:
    """The data set's own citation line, which names its edition."""
    info = _get(GEOLOGY_URL.rsplit("/", 1)[0], {"f": "json"})
    return info.get("copyrightText", "")
