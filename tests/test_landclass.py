import pytest
from shapely.geometry import box, mapping

from agate_map import landclass
from agate_map.landclass import land_class_shares

# All test geometry sits inside the study area (120.6-118.2 W, 45.7-47.0 N).
WEST, SOUTH = -120.0, 46.0


def feature(props, geometry):
    return {"type": "Feature", "properties": props, "geometry": mapping(geometry)}


def unit(code, geometry):
    return feature({"MAP_UNIT_100K": code}, geometry)


def tile(i):
    """The i-th 1 x 1 degree-tenth block in a row, for building adjacent regions."""
    return box(WEST + i * 0.1, SOUTH, WEST + (i + 1) * 0.1, SOUTH + 0.1)


def test_shares_sum_to_100_and_split_by_class():
    geology = [unit("PLMcg(r)", box(WEST, SOUTH, WEST + 0.4, SOUTH + 0.1))]  # four tiles, weight 1.0
    padus = [
        feature({"Mang_Name": "DOE", "Mang_Type": "FED"}, tile(0)),
        feature({"Mang_Name": "FWS", "Mang_Type": "FED"}, tile(1)),
    ]
    shares = land_class_shares(geology, padus, eligible=box(10, 10, 11, 11))
    assert shares[landclass.DOE] == 25.0
    assert shares[landclass.REFUGE] == 25.0
    assert shares[landclass.UNMAPPED] == 50.0
    assert sum(shares.values()) == pytest.approx(100, abs=0.2)


def test_only_favorable_units_count():
    geology = [
        unit("PLMcg(r)", tile(0)),  # weight 1.0: counts
        unit("Qfg", tile(1)),  # weight 0.5: counts
        unit("Qa", tile(2)),  # weight 0.25: does not
        unit("Mv(sp)", tile(3)),  # basalt, weight 0: does not
    ]
    shares = land_class_shares(geology, [], eligible=box(10, 10, 11, 11))
    assert shares[landclass.UNMAPPED] == 100.0
    padus = [feature({"Mang_Name": "DOE"}, tile(3))]  # on an unfavorable tile
    assert land_class_shares(geology, padus, eligible=box(10, 10, 11, 11))[landclass.UNMAPPED] == 100.0


def test_land_in_two_classes_counts_once_in_the_first():
    geology = [unit("PLMcg(r)", tile(0))]
    padus = [
        feature({"Mang_Name": "DOE"}, tile(0)),
        feature({"Mang_Name": "DOD"}, tile(0)),
    ]
    shares = land_class_shares(geology, padus, eligible=tile(0))
    assert shares[landclass.ELIGIBLE] == 100.0
    assert shares.get(landclass.DOE, 0) == 0
    assert shares[landclass.UNMAPPED] == 0


@pytest.mark.parametrize(
    "props, expected",
    [
        ({"Mang_Name": "DOE"}, landclass.DOE),
        ({"Mang_Name": "FWS"}, landclass.REFUGE),
        ({"Mang_Name": "NPS"}, landclass.REFUGE),
        ({"Mang_Name": "DOD"}, landclass.MILITARY),
        ({"Mang_Type": "TRIB", "Mang_Name": "TRIB"}, landclass.TRIBAL),
        ({"Des_Tp": "TRIBL", "Mang_Name": "BIA"}, landclass.TRIBAL),
        ({"Mang_Name": "SDNR"}, landclass.OTHER),
        ({"Mang_Name": "CITY"}, landclass.OTHER),
        ({}, landclass.OTHER),
    ],
)
def test_pad_us_polygons_fall_into_one_group(props, expected):
    assert landclass._group(props) == expected


def test_no_favorable_geology_is_an_error():
    with pytest.raises(RuntimeError, match="no favorable geology"):
        land_class_shares([unit("Ql", tile(0))], [], eligible=box(10, 10, 11, 11))
