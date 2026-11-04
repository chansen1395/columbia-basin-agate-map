"""Who holds the favorable geology?

Splits the area of favorable geology (unit weight of 0.5 or more) among broad
land classes, so the README can say how much of it lies where casual collecting
is generally allowed and how much does not. Classes are taken in this order, and
land that is in more than one class counts only in the first:

1. collecting-eligible land (the overlay on the map)
2. Department of Energy land (the Hanford Site)
3. wildlife refuges and national monuments (FWS, NPS)
4. military land
5. tribal reservations
6. any other PAD-US polygon (state and local land, designations, easements)
7. no PAD-US record, which is mostly private land

Shares are of the favorable geology inside the study area and the Washington
geologic map. They are rough: PAD-US has gaps, and a tribal reservation
boundary encloses private parcels too.
"""

from __future__ import annotations

from .grid import EAST, NORTH, SOUTH, WEST
from .units import weight_of

FAVORABLE_MIN_WEIGHT = 0.5

ELIGIBLE = "Collecting-eligible land (BLM, national forest)"
DOE = "Hanford Site (Department of Energy)"
REFUGE = "National wildlife refuge or monument (FWS, NPS)"
MILITARY = "Military land"
TRIBAL = "Tribal reservation"
OTHER = "Other land in PAD-US (state, local, designations, easements)"
UNMAPPED = "No PAD-US record (mostly private)"


def _group(props: dict) -> str:
    if props.get("Mang_Name") == "DOE":
        return DOE
    if props.get("Mang_Name") in ("FWS", "NPS"):
        return REFUGE
    if props.get("Mang_Name") == "DOD":
        return MILITARY
    if props.get("Mang_Type") == "TRIB" or props.get("Des_Tp") == "TRIBL":
        return TRIBAL
    return OTHER


def land_class_shares(geology_features, padus_features, eligible) -> dict[str, float]:
    """Percent of the favorable geology in each land class, summing to 100."""
    import shapely
    from shapely.geometry import shape
    from shapely.ops import unary_union

    def clipped(feature):
        geom = shape(feature["geometry"])
        geom = geom if geom.is_valid else geom.buffer(0)
        return shapely.clip_by_rect(geom, WEST, SOUTH, EAST, NORTH)

    favorable = unary_union(
        [
            clipped(f)
            for f in geology_features
            if weight_of(f["properties"].get("MAP_UNIT_100K")) >= FAVORABLE_MIN_WEIGHT
        ]
    )
    total = favorable.area
    if total == 0:
        raise RuntimeError("no favorable geology in the study area")

    grouped: dict[str, list] = {DOE: [], REFUGE: [], MILITARY: [], TRIBAL: [], OTHER: []}
    for feature in padus_features:
        grouped[_group(feature["properties"])].append(clipped(feature))

    classes = [(ELIGIBLE, shapely.clip_by_rect(eligible, WEST, SOUTH, EAST, NORTH))]
    classes += [(name, unary_union(parts)) for name, parts in grouped.items() if parts]

    shares: dict[str, float] = {}
    remaining = favorable
    for name, geom in classes:
        shares[name] = remaining.intersection(geom).area / total * 100
        remaining = remaining.difference(geom)
    shares[UNMAPPED] = remaining.area / total * 100
    return {name: round(share, 1) for name, share in shares.items()}
