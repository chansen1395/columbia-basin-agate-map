import pytest
from shapely.geometry import box, mapping

from agate_map.landmask import build_eligible, is_eligible_class


def pad(props, geometry):
    return {"type": "Feature", "properties": props, "geometry": mapping(geometry)}


BLM_FEE = {"Category": "Fee", "Mang_Name": "BLM", "Pub_Access": "OA", "GAP_Sts": "3"}
SMA_BLM = {"ADMIN_AGENCY_CODE": "BLM"}


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({}, True),
        ({"Mang_Name": "USFS"}, True),
        ({"Mang_Name": "SDNR"}, False),  # Washington DNR trust land is excluded
        ({"Mang_Name": "FWS"}, False),
        ({"Mang_Name": "DOE"}, False),
        ({"Mang_Name": "NPS"}, False),
        ({"Category": "Designation"}, False),
        ({"Category": "Easement"}, False),
        ({"Pub_Access": "RA"}, False),
        ({"Pub_Access": "XA"}, False),
        ({"Pub_Access": "UK"}, False),
        ({"GAP_Sts": "2"}, False),
        ({"GAP_Sts": 3}, True),
    ],
)
def test_eligible_class(changes, expected):
    assert is_eligible_class({**BLM_FEE, **changes}) is expected


def test_land_needs_both_pad_us_and_the_agency_layer():
    parcel = box(0, 0, 4, 4)
    land = build_eligible([pad(BLM_FEE, parcel)], [pad(SMA_BLM, box(0, 0, 2, 4))])
    assert land.area == pytest.approx(8)


def test_any_overlapping_pad_us_polygon_removes_the_land():
    parcel = box(0, 0, 4, 4)
    wilderness = {"Category": "Designation", "Mang_Name": "BLM", "Des_Tp": "WA", "Pub_Access": "RA", "GAP_Sts": "1"}
    acec = {"Category": "Designation", "Mang_Name": "BLM", "Des_Tp": "ACEC", "Pub_Access": "OA", "GAP_Sts": "3"}
    land = build_eligible(
        [pad(BLM_FEE, parcel), pad(wilderness, box(0, 0, 1, 4)), pad(acec, box(3, 0, 4, 4))],
        [pad(SMA_BLM, parcel)],
    )
    assert land.area == pytest.approx(8)


def test_stray_lines_left_by_overlays_are_dropped():
    parcel = box(0, 0, 4, 4)
    neighbor = {"Category": "Fee", "Mang_Name": "FWS", "Pub_Access": "RA", "GAP_Sts": "2"}
    land = build_eligible([pad(BLM_FEE, parcel), pad(neighbor, box(4, 0, 6, 4))], [pad(SMA_BLM, parcel)])
    assert land.geom_type in ("Polygon", "MultiPolygon")
    assert land.area == pytest.approx(16)


def test_no_candidate_land_is_an_error():
    with pytest.raises(RuntimeError, match="no BLM or Forest Service land"):
        build_eligible([pad({**BLM_FEE, "Mang_Name": "FWS"}, box(0, 0, 1, 1))], [pad(SMA_BLM, box(0, 0, 1, 1))])
