from agate_map.units import TIERS, WEIGHTS, weight_of


def test_weights_are_between_zero_and_one():
    assert WEIGHTS
    assert all(0.0 < weight <= 1.0 for weight in WEIGHTS.values())


def test_tiers_descend_and_do_not_share_units():
    weights = [weight for weight, _, _ in TIERS]
    assert weights == sorted(weights, reverse=True)
    all_units = [unit for _, _, units in TIERS for unit in units]
    assert len(all_units) == len(set(all_units))


def test_ringold_conglomerate_outranks_ringold_fine_facies():
    assert weight_of("PLMcg(r)") > weight_of("PLMc(r)") > 0


def test_unfavorable_and_unknown_units_weigh_nothing():
    for unit in ("Mv(wfs)", "Mv(sp)", "Ql", "Qds", "Qfs(t)", "wtr", "not-a-unit", "", None):
        assert weight_of(unit) == 0.0


def test_missoula_flood_gravel_is_weighted_but_slack_water_silt_is_not():
    assert weight_of("Qfg(3)") == 0.5
    assert weight_of("Qfs(3)") == 0.0
