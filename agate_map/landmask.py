"""Land where casual rock collecting is generally allowed.

The overlay is deliberately narrow. Land counts only if all of these hold:

1. PAD-US 4.1 lists it as a fee-owned unit of the Bureau of Land Management or
   the Forest Service, with Open public access and GAP status 3 (multiple use).
2. The BLM Surface Management Agency layer agrees that it is BLM or Forest
   Service land.
3. No other PAD-US polygon overlaps it. Special designations (wilderness,
   areas of critical environmental concern, wild and scenic river corridors,
   monuments, roadless areas), easements, military and tribal land, wildlife
   refuges and state or local units all sit in other polygons, so any overlap
   removes the land.

Washington DNR trust land is left out on purpose. The Washington Geological
Survey rockhounding page both says personal collecting is generally allowed on
state lands and lists State Trust lands among the places where rockhounding is
not permitted. When the rule is uncertain, the land is excluded.

This is a screening rule, not a legal finding. Mining claims, local closures,
seasonal limits and permit requirements are not in these layers.
"""

from __future__ import annotations

ELIGIBLE_MANAGERS = {"BLM", "USFS"}
ELIGIBLE_SMA_CODES = {"BLM", "USFS"}


def is_eligible_class(props: dict) -> bool:
    """True for a PAD-US polygon that can count toward the mask."""
    return (
        props.get("Category") == "Fee"
        and props.get("Mang_Name") in ELIGIBLE_MANAGERS
        and props.get("Pub_Access") == "OA"
        and str(props.get("GAP_Sts")) == "3"
    )


def _geom(feature):
    from shapely.geometry import shape

    shp = shape(feature["geometry"])
    return shp if shp.is_valid else shp.buffer(0)


def candidate_land(padus_features, sma_features):
    """BLM and Forest Service land that PAD-US and the SMA layer both report, before overlays."""
    from shapely.ops import unary_union

    candidates = [_geom(f) for f in padus_features if is_eligible_class(f["properties"])]
    confirmed = [
        _geom(f) for f in sma_features if f["properties"].get("ADMIN_AGENCY_CODE") in ELIGIBLE_SMA_CODES
    ]
    if not candidates or not confirmed:
        raise RuntimeError("no BLM or Forest Service land came back from the services")
    return unary_union(candidates).intersection(unary_union(confirmed))


def build_eligible(padus_features, sma_features):
    """Shapely geometry of the eligible land, from GeoJSON features."""
    from shapely.ops import unary_union

    land = candidate_land(padus_features, sma_features)
    others = [_geom(f) for f in padus_features if not is_eligible_class(f["properties"])]
    if others:
        land = land.difference(unary_union(others))
    # Keep only the polygon parts; overlays can leave stray lines and points.
    parts = [g for g in getattr(land, "geoms", [land]) if g.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(parts)
