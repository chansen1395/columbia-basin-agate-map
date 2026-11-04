"""Geology weights, by map unit of the Washington DNR 1:100,000 surface geology.

The weights are assigned by judgment from the published unit descriptions and
the sources named in the README. They are not fitted to find reports and are
not probabilities. Any unit not listed here has weight 0.

The premise: agate and petrified wood reach the surface as pebbles and cobbles
carried by rivers and floods, so coarse river or flood gravel is more likely to
hold them than basalt, loess, dune sand or slack-water silt.

Tier 1.0  Coarse river gravel of the ancestral Columbia River system. The DNR
          descriptions call these well-rounded pebble to cobble gravels with
          quartzite, granitic, metamorphic and volcanic clasts: the Ringold
          Formation conglomerate and the gravel facies of the Ellensburg
          Formation. Pebbles of petrified wood are reported in the Ellensburg
          gravels (Beck, 1937).
Tier 0.5  Gravel that may be reworked from those units, or finer deposits with
          some gravel. Named as DNR names them: "Missoula, glacial Lake,
          deposits of" (gravel units Qfg) and "Missoula flood deposits,
          backwater gravel of" (Qf(bg)); Pliocene to Pleistocene gravels
          (QPLcg fan and terrace gravel, QMcg pebble to cobble gravel, PLcg(t)
          Thorp Gravel); the Ringold Formation fluvial and lake facies
          (PLMc(r)); Pliocene-Miocene interbedded fluvial and lake deposits
          with pebble lenses (PLMc); and Pleistocene-Miocene fluvial gravel,
          sand, silt and clay (QMc).
Tier 0.25 Sand, silt and fan or river deposits that carry a little of the same
          material: the Ellensburg Formation sandstones and siltstones
          (Mc(e), Mc(ev); they include conglomerate and pebble beds), Miocene
          fluvial sand, silt and gravel beds (Mc), fanglomerate, and alluvium
          and terrace deposits along the rivers.

The Frenchman Springs Member of the Wanapum Basalt is left at 0. Petrified wood
is reported in the Ginkgo flow (Campbell and Reidel, 1991), a flow within that
member, and the 1:100,000 map does not separate that flow from the rest of it.
"""

from __future__ import annotations

TIERS = (
    (
        1.0,
        "Coarse river gravel of the ancestral Columbia River system",
        ("PLMcg(r)", "Mcg", "Mcg(e)", "Mcg(es)"),
    ),
    (
        0.5,
        "Reworked gravel, and finer facies with pebble lenses",
        (
            "Qfg", "Qfg(1)", "Qfg(2)", "Qfg(3)", "Qfg(3-4u)", "Qfg(4)", "Qf(bg)",
            "QPLcg", "QMcg", "PLcg(t)",
            "PLMc(r)", "PLMc", "QMc",
        ),
    ),
    (
        0.25,
        "Sand, silt, fan and river deposits that carry some of the same material",
        ("Mc", "Mc(e)", "Mc(ev)", "PLMaf", "Qa", "Qaf", "Qafo", "Qt"),
    ),
)

WEIGHTS: dict[str, float] = {unit: weight for weight, _, units in TIERS for unit in units}


def weight_of(unit: str | None) -> float:
    """Weight for a DNR map unit code. Unknown or missing units weigh 0."""
    return WEIGHTS.get(unit or "", 0.0)
